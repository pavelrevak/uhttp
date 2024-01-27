"""uHttp - Micro HTTP Server
python or micropython
"""

import socket as _socket
import select as _select
import json as _json


MAX_WAITING_CLIENTS = 5
MAX_HEADERS_LENGTH = 4 * 1024
MAX_CONTENT_LENGTH = 64 * 1024
HEADERS_DELIMITERS = (b'\n\r\n', b'\n\n')
CONTENT_LENGTH = 'content-length'
CONTENT_TYPE = 'content-type'
CONTENT_TYPE_XFORMDATA = 'application/x-www-form-urlencoded'
CONTENT_TYPE_HTML_UTF8 = 'text/html;charset=UTF-8'
CONTENT_TYPE_JSON = 'application/json'
CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'
CACHE_CONTROL = 'cache-control'
CACHE_CONTROL_NO_CACHE = 'no-cache'
LOCATION = 'Location'
CONNECTION = 'connection'
CONNECTION_CLOSE = 'close'
COOKIE = 'cookie'
SET_COOKIE = 'set-cookie'
HOST = 'host'
METHODS = (
    'CONNECT', 'DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST',
    'PUT', 'TRACE')
PROTOCOLS = ('HTTP/1.0', 'HTTP/1.1')
STATUS_CODES = {
    100: "Continue",
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    408: "Request Timeout",
    410: "Gone",
    411: "Length Required",
    413: "Payload Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    416: "Range Not Satisfiable",
    500: "Internal Server Error",
    501: "Not Implemented",
    503: "Service Unavailable",
    507: "Insufficient Storage",
}


class ClientError(Exception):
    """Server error"""


class HttpError(ClientError):
    """uHttp error"""


class HttpDisconnected(HttpError):
    """uHttp error"""


class HttpErrorWithResponse(HttpError):
    """uHttp errpr with result"""

    def __init__(self, status=500, message=None):
        super().__init__(f"{status} {STATUS_CODES[status]}: {message}")
        self._status = status

    @property
    def status(self):
        """Result status code"""
        return self._status


def decode_percent_encoding(data):
    """Decode percent encoded data (bytes)"""
    res = bytearray()
    while data:
        if b'%' in data:
            pos = data.index(b'%')
            res.extend(data[:pos].replace(b'+', b' '))
            res.append(int(bytes(data[pos + 1:pos + 3]), 16))
            data = data[pos + 3:]
        else:
            break
    res.extend(data.replace(b'+', b' '))
    return bytes(res)


def parse_header_parameters(value):
    """Parse parameters/directives from header value, returns dict"""
    directives = {}
    for part in value.split(';'):
        if '=' in part:
            key, val = part.split('=', 1)
            directives[key.strip()] = val.strip().strip('"')
        elif part:
            directives[part.strip()] = None
    return directives


def parse_query(raw_query, query=None):
    """Parse raw_query from URL, append it to existing query, returns dict"""
    if query is None:
        query = {}
    for query_part in raw_query.split(b'&'):
        if query_part:
            try:
                if b'=' in query_part:
                    key, val = query_part.split(b'=', 1)
                    key = decode_percent_encoding(key).decode('utf-8')
                    val = decode_percent_encoding(val).decode('utf-8')
                else:
                    key = decode_percent_encoding(query_part).decode('utf-8')
                    val = None
            except UnicodeError as err:
                raise HttpErrorWithResponse(
                    400, f"Bad query encoding: {query_part} ({err})") from err
            if key not in query:
                query[key] = val
            elif isinstance(query[key], list):
                query[key].append(val)
            else:
                query[key] = [query[key], val]
    return query

def parse_url(url):
    """Parse URL to path and query"""
    query = None
    if b'?' in url:
        path, raw_query = url.split(b'?', 1)
        query = parse_query(raw_query, query)
    else:
        path = url
    path = decode_percent_encoding(path).decode('utf-8')
    return path, query


def parse_header_line(line):
    """Parse header line to key and value"""
    try:
        line = line.decode('ascii')
    except UnicodeError as err:
        raise HttpErrorWithResponse(
            400, f"Wrong header line encoding: {line}") from err
    if ':' not in line:
        raise HttpErrorWithResponse(400, f"Wrong header format {line}")
    key, val = line.split(':', 1)
    return key.strip().lower(), val.strip()


def encode_response_data(headers, data):
    """encode response data by its type"""
    if isinstance(data, (dict, list, tuple, int, float)):
        data = _json.dumps(data).encode('ascii')
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_JSON
    elif isinstance(data, str):
        data = data.encode('utf-8')
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_HTML_UTF8
    elif isinstance(data, (bytes, bytearray)):
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_OCTET_STREAM
    else:
        raise HttpErrorWithResponse(
            500, f"Unsupported data type: {type(data)}")
    headers[CONTENT_LENGTH] = len(data)
    if CACHE_CONTROL not in headers:
        headers[CACHE_CONTROL] = CACHE_CONTROL_NO_CACHE
    return data


class HttpConnection():
    """Simple HTTP client connection"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, sock, addr):
        """sock - client socket, addr - tuple (ip, port)"""
        self._addr = addr
        self._socket = sock
        self._buffer = bytearray()
        self._method = None
        self._url = None
        self._protocol = None
        self._headers = None
        self._data = None
        self._path = None
        self._query = None
        self._content_length = None
        self._cookies = None

    def __del__(self):
        if self._socket:
            self._socket.close()

    def __repr__(self):
        result = "HttpConnection: "
        result += f"[{self._addr[0]}:{self._addr[1]}] "
        result += f"{self.method} "
        result += f"http://{self.full_url} "
        result += f"{self._protocol}"
        return result

    @property
    def addr(self):
        """Client address"""
        return self._addr

    @property
    def method(self):
        """HTTP method"""
        return self._method

    @property
    def url(self):
        """URL address"""
        return self._url

    @property
    def host(self):
        """URL address"""
        return self._headers.get(HOST, '')

    @property
    def full_url(self):
        """URL address"""
        return f"{self.host}{self.url}"

    @property
    def protocol(self):
        """Protocol"""
        return self._protocol

    @property
    def headers(self):
        """headers dict"""
        return self._headers

    @property
    def data(self):
        """Content data"""
        return self._data

    @property
    def path(self):
        """Path"""
        return self._path

    @property
    def query(self):
        """Query dict"""
        return self._query

    @property
    def cookies(self):
        """Cookies dict"""
        if self._cookies is None:
            self._cookies = {}
            raw_cookies = self._headers.get(COOKIE)
            if raw_cookies:
                for cookie_param in self._headers.get(COOKIE).split(';'):
                    if '=' in cookie_param:
                        key, val = cookie_param.split('=')
                        key = key.strip()
                        if key:
                            self._cookies[key] = val.strip()
        return self._cookies

    @property
    def socket(self):
        """This socket"""
        return self._socket

    @property
    def is_loaded(self):
        """True when request is fully loaded"""
        return self._method and (not self.content_length or self._data)

    @property
    def content_type(self):
        """Content type"""
        return self._headers.get(CONTENT_TYPE, '')

    @property
    def content_length(self):
        """Content length"""
        if self._headers is None:
            return None
        if self._content_length is None:
            content_length = self._headers.get(CONTENT_LENGTH)
            if content_length is None:
                self._content_length = False
            elif content_length.isdigit():
                self._content_length = int(content_length)
            else:
                raise HttpErrorWithResponse(
                    400, f"Wrong content length {content_length}")
        return self._content_length

    def _recv_to_buffer(self, size):
        buffer = self._socket.recv(size - len(self._buffer))
        if not buffer:
            raise HttpDisconnected(f"Lost connection from client {self.addr}")
        self._buffer.extend(buffer)

    def _parse_http_request(self, line):
        if line.count(b' ') != 2:
            raise HttpError(f"Bad request: {line}")
        method, url, protocol = line.strip().split(b' ')
        try:
            self._method = method.decode('ascii')
            self._url = url.decode('ascii')
            self._protocol = protocol.decode('ascii')
        except UnicodeError as err:
            raise HttpErrorWithResponse(
                400, f"Bad request: {line} ({err})") from err
        if self._method not in METHODS:
            raise HttpErrorWithResponse(
                405, f"Unexpected method in request {self._method}")
        if self._protocol not in PROTOCOLS:
            raise HttpErrorWithResponse(
                400, f"Unexpected protocol in request {self._protocol}")
        self._path, self._query = parse_url(url)

    def _process_data(self):
        if len(self._buffer) < self.content_length:
            return
        # TODO: unexpected state when buffer has more data than content-length
        value = self.content_type
        content_type_parts = parse_header_parameters(value)
        if CONTENT_TYPE_XFORMDATA in content_type_parts:
            self._data = parse_query(self._buffer)
        elif CONTENT_TYPE_JSON in content_type_parts:
            try:
                self._data = _json.loads(self._buffer)
            except _json.JSONDecodeError as err:
                raise HttpErrorWithResponse(
                    400, f"ERROR: Json decode: {err}") from err
        else:
            self._data = self._buffer
            self._buffer = bytearray()

    def _process_headers(self, header_lines):
        self._headers = {}
        while header_lines:
            line = header_lines.pop(0)
            if not line:
                break
            if self._method is None:
                self._parse_http_request(line)
            else:
                key, val = parse_header_line(line)
                self._headers[key] = val
        if self.content_length:
            if self.content_length > MAX_CONTENT_LENGTH:
                raise HttpErrorWithResponse(
                    413, f"content-length: {self.content_length}")
            self._process_data()

    def _read_headers(self):
        self._recv_to_buffer(MAX_HEADERS_LENGTH)
        for delimiter in HEADERS_DELIMITERS:
            if delimiter in self._buffer:
                end_index = self._buffer.index(delimiter)
                end_index += len(delimiter)
                header_lines = self._buffer[:end_index].splitlines()
                self._buffer = self._buffer[end_index:]
                self._process_headers(header_lines)
                return
        if len(self._buffer) == MAX_HEADERS_LENGTH:
            raise HttpErrorWithResponse(414, "Request header is too big")

    def close(self):
        """Close connection"""
        self._socket.close()
        self._socket = None

    def headers_get(self, key, default=None):
        """Return value from headers by key, or default if key not found"""
        return self._headers.get(key.lower(), default)

    def process_request(self):
        """Process HTTP request when read event on client socket"""
        if self._socket is None:
            return None
        try:
            if self._method is None:
                self._read_headers()
            elif self.content_length:
                self._recv_to_buffer(self.content_length)
                self._process_data()
            # TODO: check for stream data without content-length
            return self.is_loaded
        except HttpErrorWithResponse as err:
            self.respond(data=str(err), status=err.status)
            raise ClientError from err
        return None

    def respond(self, data=None, status=200, headers=None, cookies=None):
        """Create general respond with data, status and headers as dict"""
        if self._socket is None:
            return
        header = f'{PROTOCOLS[-1]} {status} {STATUS_CODES[status]}\r\n'
        if headers is None:
            headers = {}
        if data:
            data = encode_response_data(headers, data)
        if CONNECTION not in headers:
            # TODO support persistent connection
            headers[CONNECTION] = CONNECTION_CLOSE
        for key, val in headers.items():
            header += f'{key}: {val}\r\n'
        if cookies:
            # Set-Cookie key can be repeated in header
            for key, val in cookies.items():
                # TODO add support for attributes
                if val is None:
                    val = '; Max-Age=0'
                header += f'{SET_COOKIE}: {key}={val}\r\n'
        header += '\r\n'
        self._socket.sendall(header.encode('ascii'))
        if data:
            self._socket.sendall(data)
        self._socket.close()

    def respond_redirect(self, url, status=302, cookies=None):
        """Create redirect respond to URL"""
        self.respond(status=status, headers={LOCATION: url}, cookies=cookies)


class HttpServer():
    """HTTP server"""

    def __init__(self, address='0.0.0.0', port=80):
        """IP address and port of listening interface for HTTP"""
        self._socket = _socket.socket()
        self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._socket.bind((address, port))
        self._socket.listen(2)
        self._waiting_connections = []

    @property
    def socket(self):
        """Server socket"""
        return self._socket

    @property
    def read_sockets(self):
        """All sockets waiting for communication, used for select"""
        read_sockets = [
            con.socket
            for con in self._waiting_connections
            if con.socket is not None]
        read_sockets.append(self._socket)
        return read_sockets

    def close(self):
        """Close HTTP server"""
        self._socket.close()

    def _remove_connection(self, connection):
        self._waiting_connections.remove(connection)

    def _accept(self):
        cl_socket, addr = self._socket.accept()
        connection = HttpConnection(cl_socket, addr)
        while len(self._waiting_connections) > MAX_WAITING_CLIENTS:
            self._remove_connection(self._waiting_connections[0])
            connection.respond('Request timeout, too many requests', status=408)
        self._waiting_connections.append(connection)

    def event_read(self, sockets):
        """Process sockets with read_event,
        returns None or instance of HttpConnection with established connection"""
        if self._socket in sockets:
            self._accept()
            return None
        for connection in self._waiting_connections:
            if connection.socket in sockets:
                try:
                    if connection.process_request():
                        self._remove_connection(connection)
                        return connection
                except ClientError:
                    connection.close()
                    self._remove_connection(connection)
        return None

    def wait(self, timeout=1):
        """Wait for new clients with specified timeout,
        returns None or instance of HttpConnection with established connection"""
        event_sockets = _select.select(self.read_sockets, [], [], timeout)[0]
        if event_sockets:
            return self.event_read(event_sockets)
        return None
