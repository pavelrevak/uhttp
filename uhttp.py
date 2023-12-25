"""uHttp - Micro Http Server
"""

import time
import socket
import select
import gc
import json


MAX_HEADERS_LENGTH = 4096
MAX_CONTENT_LENGTH = 65536
HEADERS_DELIMITERS = (b'\n\r\n', b'\n\n')
CONTENT_LENGTH = 'content-length'
CONTENT_TYPE = 'content-type'
CONTENT_DISPOSITION = 'content-disposition'
CONTENT_TYPE_XFORMDATA = 'application/x-www-form-urlencoded'
CONTENT_TYPE_HTML_UTF8 = 'text/html;charset=UTF-8'
CONTENT_TYPE_JSON = 'application/json'
CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'
CACHE_CONTROL = 'cache-control'
CACHE_CONTROL_NO_CACHE = 'no-cache'
LOCATION = 'Location'
CONNECTION = 'connection'
CONNECTION_CLOSE = 'close'
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
    411: "Length Required",
    413: "Payload Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    416: "Range Not Satisfiable",
    500: "Internal Server Error",
    501: "Not Implemented",
    507: "Insufficient Storage",
}


class UHttpError(Exception):
    """uHttp error"""


class UHttpDisconnected(UHttpError):
    """uHttp error"""


class UHttpErrorResponse(UHttpError):
    """uHttp errpr with result"""

    def __init__(self, status=500, message=None):
        super().__init__(f"{status} {STATUS_CODES[status]}: {message}")
        self._status = status

    @property
    def status(self):
        return self._status


def decode_percent_encoding(data):
    """Decode percent encoded string

    Arguments:
        data: percent encoded data (bytearray)

    Returns:
        decoded data (bytearray)
    """
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
    """Parse parameters from header value

    Arguments:
        value: directive value

    Returns:
        dictionary with directives
    """
    directives = {}
    for part in value.split(';'):
        if '=' in part:
            key, val = part.split('=', 1)
            directives[key.strip()] = val.strip().strip('"')
        elif part:
            directives[part.strip()] = None
    return directives


def parse_query(raw_query, query=None):
    """Parse raw_query from URL
    append it to existing query,

    Arguments:
        raw_query: input query from URL or from post data (bytes)
        query: existing query, will be extended (dict)

    Returns:
        query (dict)
    """
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
                raise UHttpErrorResponse(
                    400, f"Bad query encoding: {query_part} ({err})") from err
            if key not in query:
                query[key] = val
            elif isinstance(query[key], list):
                query[key].append(val)
            else:
                query[key] = [query[key], val]
    return query

def parse_url(url):
    """Parse URL to path and query

    Arguments:
        url: raw URL address

    Returns:
        path: path part from URL
        query: parsed query
    """
    query = None
    if b'?' in url:
        path, raw_query = url.split(b'?', 1)
        query = parse_query(raw_query, query)
    else:
        path = url
    path = decode_percent_encoding(path).decode('utf-8')
    return path, query


def parse_header_line(line):
    try:
        line = line.decode('ascii')
    except UnicodeError as err:
        raise UHttpErrorResponse(400, f"Bad request: {line}") from err
    if ':' not in line:
        raise UHttpErrorResponse(400, "Wrong header format")
    key, val = line.split(':', 1)
    return key.strip().lower(), val.strip()


def encode_data(headers, data):
    """encode data by its type
    """
    if isinstance(data, (dict, list, tuple, int, float)):
        data = json.dumps(data).encode('ascii')
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
        raise UHttpErrorResponse(500, f"Unsupported data type: {type(data)}")
    headers[CONTENT_LENGTH] = len(data)
    if CACHE_CONTROL not in headers:
        headers[CACHE_CONTROL] = CACHE_CONTROL_NO_CACHE
    return data


class HttpClient():
    """Simple socket client"""

    # pylint: disable=too-many-instance-attributes

    STATE_DATA = 2
    STATE_LOADED = 3
    def __init__(self, sock, addr):
        """Create http client

        Arguments:
            sock: client socket
            addr: tuple with address and port from client
        """
        self._addr = addr
        self._socket = sock
        self._buffer = bytearray()
        self._rx_bytes_counter = 0
        self._method = None
        self._url = None
        self._protocol = None
        self._headers = None
        self._data = None
        self._path = None
        self._query = None
        self._content_length = None
        self._time = time.time()
        self._state = None

    def __del__(self):
        self._socket.close()

    def __str__(self):
        result = "HttpClient: "
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
        return self.headers_get(HOST, '')

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
    def socket(self):
        """This socket"""
        return self._socket

    @property
    def rx_bytes_counter(self):
        """Read bytes counter"""
        return self._rx_bytes_counter

    @property
    def is_loaded_headers(self):
        """State"""
        return bool(self._headers)

    @property
    def is_loaded_all(self):
        """State"""
        return self._state == self.STATE_LOADED

    @property
    def content_length(self):
        """Content length"""
        if self._headers is None:
            return None
        if self._content_length is None:
            content_length = self.headers_get(CONTENT_LENGTH, None)
            if not content_length:
                self._content_length = False
            elif content_length.isnumeric():
                self._content_length = int(content_length)
            else:
                raise UHttpErrorResponse(400, f"Wrong content length {content_length}")
        return self._content_length

    def _recv_to_buffer(self, size):
        buffer = self._socket.recv(size - len(self._buffer))
        # print(f"RX: {buffer}")
        if not buffer:
            raise UHttpDisconnected(f"Lost connection from client {self.addr}")
        self._rx_bytes_counter += len(buffer)
        self._buffer.extend(buffer)

    def _parse_http_request(self, line):
        if line.count(b' ') != 2:
            raise UHttpError(f"Bad request: {line}")
        method, url, protocol = line.strip().split(b' ')
        try:
            self._method = method.decode('ascii')
            self._url = url.decode('ascii')
            self._protocol = protocol.decode('ascii')
        except UnicodeError as err:
            raise UHttpErrorResponse(400, f"Bad request: {line} ({err})") from err
        if self._method not in METHODS:
            raise UHttpErrorResponse(405, f"Unexpected method in request {self._method}")
        if self._protocol not in PROTOCOLS:
            raise UHttpErrorResponse(400, f"Unexpected protocol in request {self._protocol}")
        self._path, self._query = parse_url(url)

    def _process_data(self):
        if len(self._buffer) != self.content_length:
            return
        value = self.headers_get(CONTENT_TYPE, '')
        content_type_parts = parse_header_parameters(value)
        if CONTENT_TYPE_XFORMDATA in content_type_parts:
            self._data = parse_query(self._buffer)
        elif CONTENT_TYPE_JSON in content_type_parts:
            try:
                self._data = json.loads(self._buffer)
            except json.JSONDecodeError as err:
                raise UHttpErrorResponse(400, f"ERROR: Json decode: {err}") from err
        else:
            self._data = self._buffer
            self._buffer = bytearray()
        self._state = self.STATE_LOADED

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
                raise UHttpErrorResponse(413, f"content-length: {self.content_length}")
            self._state = self.STATE_DATA
            self._process_data()
        else:
            self._state = self.STATE_LOADED

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
            raise UHttpErrorResponse(414, "Request header is too big")

    def read_request(self):
        """Read HTTP request. Call this when data ready on a socket"""
        if self._state is None:
            self._read_headers()
        elif self._state == self.STATE_DATA:
            self._recv_to_buffer(self.content_length)
            self._process_data()

    def headers_get(self, key, default=None):
        """Get value from headers"""
        return self._headers.get(key.lower(), default)

    def response(self, data=None, status=200, headers=None):
        """Create general response

        Arguments:
            status: HTTP status code
            headers: dictionary with custom headers
            data: content
        """
        header = f'{PROTOCOLS[-1]} {status} {STATUS_CODES[status]}\r\n'
        if headers is None:
            headers = {}
        if data:
            data = encode_data(headers, data)
        if CONNECTION not in headers:
            headers[CONNECTION] = CONNECTION_CLOSE
        for key, val in headers.items():
            header += f'{key}: {val}\r\n'
        header += '\r\n'
        self.socket.sendall(header.encode('ascii'))
        if data:
            self.socket.sendall(data)
        self._socket.close()

    def response_redirect(self, url, status=302):
        """Redirect response

        Arguments:
            url: URL address to send redirect
        """
        self.response(status=status, headers={LOCATION: url})


class HttpServer():
    """Http server
    """
    def __init__(
            self,
            address='0.0.0.0',
            port=80):
        """Create http server

        Arguments:
            address: internet address or IP for listening port
            port: TCP port for HTTP
        """
        self._socket = socket.socket()
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((address, port))
        self._socket.listen(1)
        self._waiting_clients = []

    @property
    def socket(self):
        """Server socket"""
        return self._socket

    def _accept(self):
        cl_socket, addr = self._socket.accept()
        print(f'_____________________________________\nNEW connection: {addr}')
        client = HttpClient(cl_socket, addr)
        self._waiting_clients.append(client)

    def _process_client(self, client):
        try:
            client.read_request()
        except UHttpErrorResponse as err:
            print(f'uHttp error: {err}')
            client.response(data=str(err), status=err.status)
            self._waiting_clients.remove(client)
        except UHttpError as err:
            print(f'uHttp error: {err}')
            self._waiting_clients.remove(client)
            del client
            gc.collect()
        if client.is_loaded_all:
            self._waiting_clients.remove(client)
            return client
        return None

    def wait(self, timeout=1):
        """Wait for client connect

        Arguments:
            timeout: waiting time, default is 1 second

        Returns:
            None or talk_client result
        """
        read_sockets = [client.socket for client in self._waiting_clients]
        read_sockets.append(self._socket)
        read_events = select.select(read_sockets, [], [], timeout)[0]
        if self._socket in read_events:
            self._accept()
        for client in self._waiting_clients:
            if client.socket in read_events:
                return self._process_client(client)
        return None
