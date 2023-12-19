"""uHttp - Micro Http Server
"""

import socket
import select
import gc
import json


class UHttpError(Exception):
    """uHttp error"""


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
                raise UHttpError(f"Bad query encoding: {query_part} ({err})") from err
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


class HttpClient():
    """Simple socket client"""

    # pylint: disable=too-many-instance-attributes

    _CHUNK_SIZE = 4096
    _MAX_CONTENT_LENGTH = 65536
    CONTENT_LENGTH = 'Content-Length'
    CONTENT_TYPE = 'Content-Type'
    CONTENT_DISPOSITION = 'Content-Disposition'
    CONTENT_TYPE_XFORMDATA = 'application/x-www-form-urlencoded'
    CONTENT_TYPE_HTML_UTF8 = 'text/html;charset=UTF-8'
    CONTENT_TYPE_JSON = 'application/json'
    CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'
    CACHE_CONTROL = 'Cache-Control'
    CACHE_CONTROL_NO_CACHE = 'no-cache'
    CONNECTION = 'Connection'
    CONNECTION_CLOSE = 'close'
    HOST = 'Host'
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

    def __init__(
            self, sock, addr,
            chunk_size=_CHUNK_SIZE,
            max_content_lenght=_MAX_CONTENT_LENGTH):
        self._addr = addr
        self._socket = sock
        self._buffer = bytearray()
        self._bytes_counter = 0
        self._chunk_size = chunk_size
        self._max_content_lenght = max_content_lenght
        self._method = None
        self._url = None
        self._protocol = None
        self._headers = None
        self._data = None
        self._path = None
        self._query = None

    def __del__(self):
        self._socket.close()

    def __str__(self):
        result = f"HttpClient: "
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
        return self.headers_get(self.HOST, '')

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
    def bytes_counter(self):
        """Read bytes counter"""
        return self._bytes_counter

    def headers_get(self, key, default=None):
        """Get value from headers

        Arguments:
            key: key from headers (case insensitive)
            default: default value if the key does not exists

        Returns:
            value from headers
        """
        return self._headers.get(key.lower(), default)

    def _recv(self, size):
        if len(self._buffer) < size:
            buffer = self._socket.recv(size - len(self._buffer))
            self._buffer.extend(buffer)

    def read(self, size=None):
        """Read chunk"""
        if size is None:
            size = self._chunk_size
        self._recv(size)
        res = self._buffer[:size]
        self._buffer = self._buffer[size:]
        self._bytes_counter += len(res)
        # print("RECV:", res)
        return res

    def read_block(self, size=None, delimiter=b'\n'):
        """Read chunk block with delimiter

        Arguments:
            size: chunk size (default is self._chunk_size)
            delimiter: data block delimiter

        Returns:
            data block
        """
        if size is None:
            size = self._chunk_size
        if delimiter not in self._buffer:
            self._recv(size)
            if delimiter not in self._buffer:
                res = bytes(self._buffer)
                self._buffer = bytearray()
                return res
        endline_index = bytes(self._buffer).index(delimiter) + len(delimiter)
        res = bytes(self._buffer[:endline_index])
        self._buffer = self._buffer[endline_index:]
        self._bytes_counter += len(res)
        # print("RECV:", res)
        return res

    def read_request(self):
        """Read request
        """
        line = self.read_block()
        if not line:
            raise UHttpError("No data received")
        if line[-1] != 0x0a:
            raise UHttpError(f"Request line is too long > {len(line)}")
        try:
            method, url, protocol = line.strip().split(b' ')
        except ValueError as err:
            raise UHttpError(f"Bad request: {line} ({err})") from err
        try:
            self._method = method.decode('ascii')
            self._protocol = protocol.decode('ascii')
            self._url = url.decode('ascii')
        except UnicodeError as err:
            raise UHttpError(f"Bad request: {line} ({err})") from err
        if self._method not in self.METHODS:
            raise UHttpError(f"Unexpected method in request {self._method}")
        if self._protocol not in self.PROTOCOLS:
            raise UHttpError(f"Unexpected protocol in request {self._protocol}")
        self.read_headers()
        self.read_data()
        self._path, self._query = parse_url(url)

    def read_headers(self):
        """Read headers
        """
        self._headers = {}
        while True:
            line = self.read_block()
            if line[-1] != 0x0a:
                raise UHttpError("Header line is too long")
            try:
                line = line.decode('ascii').strip()
            except UnicodeError as err:
                raise UHttpError(f"Bad header: {line} ({err})") from err
            if not line:
                break
            if ':' in line:
                key, val = line.split(':', 1)
                val = val.strip()
                if key.lower() == self.CONTENT_DISPOSITION.lower():
                    val = parse_header_parameters(val)
                self._headers[key.lower()] = val
            else:
                raise UHttpError("Wrong header format")

    def read_data(self):
        """Read data part
        """
        content_length = int(self.headers_get(self.CONTENT_LENGTH, 0))
        if not content_length:
            # ignore data if there is no content length
            return
        if content_length > self._max_content_lenght:
            raise UHttpError(f'Data too large: {content_length}')
        value = self.headers_get(self.CONTENT_TYPE, '')
        content_type_parts = parse_header_parameters(value)
        res_data = self.read(content_length)
        if self.CONTENT_TYPE_XFORMDATA in content_type_parts:
            self._data = parse_query(res_data)
        elif self.CONTENT_TYPE_JSON in content_type_parts:
            try:
                self._data = json.loads(res_data)
            except json.JSONDecodeError as err:
                raise UHttpError(f"ERROR: Json decode: {err}") from err
        else:
            self._data = res_data

    def encode_data(self, headers, data):
        """Create general response

        Arguments:
            headers: dictionary headers data,
                will update Content-Type, Content-Length
                and cache control will set to 'no-cache'
            data: content data:
                dict, list, tuple, int, float:
                    create JSON response and json content type
                str: will be encoded as UTF-8 and text/html content type
                bytes, bytearray: will be sent as is
        Returns:
            encoded content data
        """
        if isinstance(data, (dict, list, tuple, int, float)):
            data = json.dumps(data).encode('ascii')
            if self.CONTENT_TYPE not in headers:
                headers[self.CONTENT_TYPE] = self.CONTENT_TYPE_JSON
        elif isinstance(data, str):
            data = data.encode('utf-8')
            if self.CONTENT_TYPE not in headers:
                headers[self.CONTENT_TYPE] = self.CONTENT_TYPE_HTML_UTF8
        elif isinstance(data, (bytes, bytearray)):
            if self.CONTENT_TYPE not in headers:
                headers[self.CONTENT_TYPE] = self.CONTENT_TYPE_OCTET_STREAM
        else:
            raise UHttpError(f"Unsupported data type: {type(data)}")
        headers[self.CONTENT_LENGTH] = len(data)
        if self.CACHE_CONTROL not in headers:
            headers[self.CACHE_CONTROL] = self.CACHE_CONTROL_NO_CACHE
        return data

    def response(self, status=200, headers=None, data=None):
        """Create general response

        Arguments:
            status: HTTP status code
            headers: dictionary with custom headers
            data: content
        """
        header = f'HTTP/1.1 {status} {self.STATUS_CODES[status]}\r\n'
        if headers is None:
            headers = {}
        if data:
            data = self.encode_data(headers, data)
        if self.CONNECTION not in headers:
            headers[self.CONNECTION] = self.CONNECTION_CLOSE
        for key, val in headers.items():
            header += f'{key}: {val}\r\n'
        header += '\r\n'
        self.socket.sendall(header.encode('utf-8'))
        if data:
            self.socket.sendall(data)
        self._socket.close()

    def response_redirect(self, url, status=302):
        """Redirect response

        Arguments:
            url: URL address to send redirect
        """
        self.response(status=status, headers={'Location': url})


class HttpServer():
    """Http server
    """
    def __init__(self, address='0.0.0.0', port=80):
        """Create http server

        Arguments:
            address: internet address or IP for listening port
            port: TCP port for HTTP
        """
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((address, port))
        self._server.listen(1)

    @property
    def socket(self):
        """Client socket

        Returns:
            client socket
        """
        return self._server

    def accept(self):
        """Accept new connection from client

        Returns:
            instance of client or None on error
        """
        cl_socket, addr = self._server.accept()
        client = HttpClient(cl_socket, addr)
        try:
            client.read_request()
        except UHttpError as err:
            print(f'uHttp error: {err}')
            del client
            client = None
            gc.collect()
        return client

    def wait(self, timeout=1):
        """Wait for client connect

        Arguments:
            timeout: waiting time, default is 1 second

        Returns:
            None or talk_client result
        """
        read_event = select.select([self._server], [], [], timeout)[0]
        if read_event:
            return self.accept()
        return None
