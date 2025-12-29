"""uHttp - Micro HTTP Server
python or micropython
(c) 2022-2024 Pavel Revak <pavelrevak@gmail.com>
"""

import os as _os
import socket as _socket
import select as _select
import json as _json
import time as _time

KB = 2 ** 10
MB = 2 ** 20
GB = 2 ** 30

LISTEN_SOCKETS = 2
MAX_WAITING_CLIENTS = 5
MAX_HEADERS_LENGTH = 4 * KB
MAX_CONTENT_LENGTH = 512 * KB
FILE_CHUNK_SIZE = 4 * KB  # bytes - chunk size for streaming file responses
KEEP_ALIVE_TIMEOUT = 15  # seconds
KEEP_ALIVE_MAX_REQUESTS = 100  # max requests per connection

HEADERS_DELIMITERS = (b'\n\r\n', b'\n\n')
BOUNDARY = 'frame'
CONTENT_LENGTH = 'content-length'
CONTENT_TYPE = 'content-type'
CONTENT_TYPE_XFORMDATA = 'application/x-www-form-urlencoded'
CONTENT_TYPE_HTML_UTF8 = 'text/html; charset=UTF-8'
CONTENT_TYPE_JSON = 'application/json'
CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'
CONTENT_TYPE_MULTIPART_REPLACE = (
    'multipart/x-mixed-replace; boundary=' + BOUNDARY)
CACHE_CONTROL = 'cache-control'
CACHE_CONTROL_NO_CACHE = 'no-cache'
LOCATION = 'Location'
CONNECTION = 'connection'
CONNECTION_CLOSE = 'close'
CONNECTION_KEEP_ALIVE = 'keep-alive'
COOKIE = 'cookie'
SET_COOKIE = 'set-cookie'
HOST = 'host'
CONTENT_TYPE_MAP = {
    'html': CONTENT_TYPE_HTML_UTF8,
    'htm': CONTENT_TYPE_HTML_UTF8,
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'svg': 'image/svg+xml',
    'webp': 'image/webp',
    'ico': 'image/x-icon',
    'bmp': 'image/bmp',
}
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
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    500: "Internal Server Error",
    501: "Not Implemented",
    503: "Service Unavailable",
    505: "HTTP Version Not Supported",
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
        msg = str(status)
        if status in STATUS_CODES:
            msg += " " + STATUS_CODES[status]
        if message:
            msg += ": " + message
        super().__init__(msg)
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
            if pos > len(data) - 3:
                break
            res.extend(data[:pos].replace(b'+', b' '))
            code = bytes(data[pos + 1:pos + 3])
            res.append(int(code, 16))
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
            except (UnicodeError, ValueError) as err:
                raise HttpErrorWithResponse(
                    400, "Bad query coding") from err
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
    try:
        path = decode_percent_encoding(path).decode('utf-8')
    except (UnicodeError, ValueError) as err:
        raise HttpErrorWithResponse(
            400, "Wrong header path coding") from err
    return path, query


def parse_header_line(line):
    """Parse header line to key and value"""
    try:
        line = line.decode('ascii')
    except ValueError as err:
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
    elif isinstance(data, (bytes, bytearray, memoryview)):
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_OCTET_STREAM
    else:
        raise HttpErrorWithResponse(415, str(type(data)))
    headers[CONTENT_LENGTH] = len(data)
    return data


class HttpConnection():
    """Simple HTTP client connection"""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, server, sock, addr, **kwargs):
        """sock - client socket, addr - tuple (ip, port)"""
        self._server = server
        self._addr = addr
        self._socket = sock
        # Set appropriate I/O methods based on socket type
        # In MicroPython, both regular and SSL sockets have recv/send methods
        # In CPython, SSL sockets use read/write instead
        # Prefer recv/send if available (MicroPython), fall back to read/write (CPython SSL)
        if hasattr(sock, 'recv'):
            self._socket_recv = sock.recv
            self._socket_send = sock.send
        else:
            self._socket_recv = sock.read
            self._socket_send = sock.write
        self._buffer = bytearray()
        self._send_buffer = bytearray()
        self._rx_bytes_counter = 0
        self._method = None
        self._url = None
        self._protocol = None
        self._headers = None
        self._data = None
        self._path = None
        self._query = None
        self._content_length = None
        self._cookies = None
        self._is_multipart = False
        self._response_started = False
        self._response_keep_alive = False
        self._file_handle = None
        self._last_activity = _time.time()
        self._requests_count = 0
        self._max_headers_length = kwargs.get(
            'max_headers_length', MAX_HEADERS_LENGTH)
        self._max_content_length = kwargs.get(
            'max_content_length', MAX_CONTENT_LENGTH)
        self._file_chunk_size = kwargs.get(
            'file_chunk_size', FILE_CHUNK_SIZE)
        self._keep_alive_timeout = kwargs.get(
            'keep_alive_timeout', KEEP_ALIVE_TIMEOUT)
        self._keep_alive_max_requests = kwargs.get(
            'keep_alive_max_requests', KEEP_ALIVE_MAX_REQUESTS)

    def __del__(self):
        self.close()

    def __repr__(self):
        result = f"HttpConnection: [{self.remote_address}] {self.method}"
        result += f" http://{self.full_url}"
        return result

    @property
    def addr(self):
        """Client address"""
        return self._addr

    @property
    def remote_address(self):
        """Return client address"""
        forwarded = self.headers_get_attribute('x-forwarded-for')
        if forwarded:
            return forwarded.split(',')[0]
        return f"{self._addr[0]}:{self._addr[1]}"

    @property
    def remote_addresses(self):
        """Return client address"""
        forwarded = self.headers_get_attribute('x-forwarded-for')
        if forwarded:
            return forwarded
        return f"{self._addr[0]}:{self._addr[1]}"

    @property
    def is_secure(self):
        """Return True if connection is using SSL/TLS"""
        return bool(self._server._ssl_context)

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
        return self.headers_get_attribute(HOST, '')

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
            raw_cookies = self.headers_get_attribute(COOKIE)
            if raw_cookies:
                for cookie_param in self.headers_get_attribute(COOKIE).split(';'):
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
    def rx_bytes_counter(self):
        """Read bytes counter"""
        return self._rx_bytes_counter

    @property
    def is_loaded(self):
        """True when request is fully loaded"""
        return self._method and (not self.content_length or self._data)

    @property
    def is_waiting_for_response(self):
        """True when request is loaded but response not yet started"""
        return self.is_loaded and not self._response_started

    @property
    def is_timed_out(self):
        """True when connection has been idle too long"""
        return (_time.time() - self._last_activity) > self._keep_alive_timeout

    @property
    def is_max_requests_reached(self):
        """True when connection reached max requests limit"""
        return self._requests_count >= self._keep_alive_max_requests

    @property
    def has_data_to_send(self):
        """True when there is data waiting to be sent or file being streamed"""
        return len(self._send_buffer) > 0 or self._file_handle is not None

    @property
    def content_type(self):
        """Content type"""
        return self.headers_get_attribute(CONTENT_TYPE, '')

    @property
    def content_length(self):
        """Content length"""
        if self._headers is None:
            return None
        if self._content_length is None:
            content_length = self.headers_get_attribute(CONTENT_LENGTH)
            if content_length is None:
                self._content_length = False
            elif content_length.isdigit():
                self._content_length = int(content_length)
            else:
                raise HttpErrorWithResponse(
                    400, f"Wrong content length {content_length}")
        return self._content_length

    def headers_get_attribute(self, key, default=None):
        """Return headers value"""
        if self._headers:
            return self._headers.get(key, default)
        return default

    def _recv_to_buffer(self, size):
        try:
            buffer = self._socket_recv(size - len(self._buffer))
        except OSError as err:
            # EAGAIN/EWOULDBLOCK means no data available (non-blocking socket)
            errno = getattr(err, 'errno', None)
            if errno in (11, 35):  # EAGAIN, EWOULDBLOCK
                return  # Not an error, just no data yet
            raise HttpDisconnected(f"{err}: {self.addr}") from err
        if not buffer:
            raise HttpDisconnected(f"Lost connection from client {self.addr}")
        self._rx_bytes_counter += len(buffer)
        self._buffer.extend(buffer)
        self.update_activity()

    def _parse_http_request(self, line):
        if line.count(b' ') != 2:
            raise HttpError(f"Bad request: {line}")
        method, url, protocol = line.strip().split(b' ')
        try:
            self._method = method.decode('ascii')
            self._url = url.decode('ascii')
            self._protocol = protocol.decode('ascii')
        except ValueError as err:
            raise HttpErrorWithResponse(
                400, f"Bad request: {line} ({err})") from err
        if self._method not in METHODS:
            raise HttpErrorWithResponse(501)
        if self._protocol not in PROTOCOLS:
            raise HttpErrorWithResponse(505)
        self._path, self._query = parse_url(url)

    def _process_data(self):
        if len(self._buffer) < self.content_length:
            return
        # Extract only content_length bytes from buffer
        data_bytes = bytes(self._buffer[:self.content_length])
        # Keep remaining bytes in buffer for next request (keep-alive)
        self._buffer = self._buffer[self.content_length:]

        value = self.content_type
        content_type_parts = parse_header_parameters(value)
        if CONTENT_TYPE_XFORMDATA in content_type_parts:
            self._data = parse_query(data_bytes)
        elif CONTENT_TYPE_JSON in content_type_parts:
            try:
                self._data = _json.loads(data_bytes)
            except ValueError as err:
                raise HttpErrorWithResponse(
                    400, f"ERROR: Json decode: {err}") from err
        else:
            self._data = data_bytes

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

        # RFC 2616: HTTP/1.1 requires Host header
        if self._protocol == 'HTTP/1.1' and 'host' not in self._headers:
            raise HttpErrorWithResponse(400, "Host header is required for HTTP/1.1")

        if self.content_length:
            if self.content_length > self._max_content_length:
                raise HttpErrorWithResponse(413)
            self._process_data()

    def _read_headers(self):
        # Check if headers are already complete in buffer (pipelining support)
        for delimiter in HEADERS_DELIMITERS:
            if delimiter in self._buffer:
                end_index = self._buffer.index(delimiter)
                end_index += len(delimiter)
                header_lines = self._buffer[:end_index].splitlines()
                self._buffer = self._buffer[end_index:]
                self._process_headers(header_lines)
                return

        # Headers not complete, read more data from socket
        self._recv_to_buffer(self._max_headers_length)
        for delimiter in HEADERS_DELIMITERS:
            if delimiter in self._buffer:
                end_index = self._buffer.index(delimiter)
                end_index += len(delimiter)
                header_lines = self._buffer[:end_index].splitlines()
                self._buffer = self._buffer[end_index:]
                self._process_headers(header_lines)
                return
        if len(self._buffer) >= self._max_headers_length:
            raise HttpErrorWithResponse(
                431, f"({self._buffer} > {self._max_headers_length} Bytes)")

    def _send(self, data):
        """Add data to send buffer for async sending"""
        if self._socket is None:
            return
        if isinstance(data, str):
            data = data.encode('ascii')
        self._send_buffer.extend(data)
        self.try_send()

    def try_send(self):
        """Try to send data from send buffer, returns True if all sent"""
        if self._socket is None:
            return False

        # If streaming file, read next chunk when buffer is low
        if self._file_handle and len(self._send_buffer) < self._file_chunk_size:
            try:
                chunk = self._file_handle.read(self._file_chunk_size)
                if chunk:
                    self._send_buffer.extend(chunk)
                else:
                    # File fully read, close handle
                    try:
                        self._file_handle.close()
                    except OSError:
                        pass
                    self._file_handle = None
            except OSError:
                # Error reading file, close handle and connection
                if self._file_handle:
                    try:
                        self._file_handle.close()
                    except OSError:
                        pass
                    self._file_handle = None
                self.close()
                return False

        if not self._send_buffer:
            return True
        try:
            sent = self._socket_send(self._send_buffer)
            # MicroPython SSL may return None instead of bytes sent when buffer full
            if sent is None:
                return False
            if sent > 0:
                self._send_buffer = self._send_buffer[sent:]
            return len(self._send_buffer) == 0 and self._file_handle is None
        except OSError as e:
            # EAGAIN/EWOULDBLOCK means socket buffer is full (non-blocking)
            errno = getattr(e, 'errno', None)
            if errno in (11, 35):  # EAGAIN, EWOULDBLOCK
                return False
            # Other errors are real connection problems
            self.close()
            return False

    def update_activity(self):
        """Update last activity timestamp"""
        self._last_activity = _time.time()

    def _should_keep_alive(self, response_headers=None):
        """Determine if connection should be kept alive

        Args:
            response_headers: Optional dict of response headers to check for explicit Connection header

        Returns:
            bool: True if connection should be kept alive
        """
        # Check if response explicitly sets Connection header
        if response_headers and CONNECTION in response_headers:
            return response_headers[CONNECTION].lower() == CONNECTION_KEEP_ALIVE

        # Auto-detect from request Connection header
        req_connection = self.headers_get_attribute(CONNECTION, '').lower()

        # HTTP/1.1 default: keep-alive, HTTP/1.0 requires explicit header
        if self._protocol == 'HTTP/1.1':
            keep_alive = req_connection != CONNECTION_CLOSE
        else:
            keep_alive = req_connection == CONNECTION_KEEP_ALIVE

        # Disable keep-alive if max requests limit reached
        # Note: timeout is checked separately in _cleanup_idle_connections()
        if keep_alive and self.is_max_requests_reached:
            keep_alive = False

        return keep_alive

    def _finalize_sent_response(self):
        """Finalize connection after response fully sent (no buffered data)"""
        # Don't close active multipart streams
        if self._is_multipart:
            return

        if self._response_keep_alive:
            self.reset()
        else:
            self.close()

    def reset(self):
        """Reset connection for next request (keep-alive)"""
        # Close file handle if streaming
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass
            self._file_handle = None
        # Don't clear buffer - may contain start of next request
        self._method = None
        self._url = None
        self._protocol = None
        self._headers = None
        self._data = None
        self._path = None
        self._query = None
        self._content_length = None
        self._cookies = None
        self._is_multipart = False
        self._response_started = False
        self._response_keep_alive = False
        self.update_activity()

    def close(self):
        """Close connection"""
        # Close file handle if streaming
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass
            self._file_handle = None
        self._server.remove_connection(self)
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                # Socket already closed or error during close
                pass
            self._socket = None
            self._send_buffer[:] = b''

    def headers_get(self, key, default=None):
        """Return value from headers by key, or default if key not found"""
        return self._headers.get(key.lower(), default)

    def process_request(self):
        """Process HTTP request when read event on client socket"""
        if self._socket is None:
            return None
        if self._is_multipart:
            return False
        # Don't process next pipelined request until current one gets response
        if self.is_waiting_for_response:
            return False
        try:
            if self._method is None:
                self._read_headers()
            elif self.content_length:
                self._recv_to_buffer(self.content_length)
                self._process_data()
            # TODO check for stream data without content-length
            if self.is_loaded:
                self._requests_count += 1
            return self.is_loaded
        except HttpErrorWithResponse as err:
            self.respond(data=str(err), status=err.status)
            raise ClientError from err
        return None

    def _build_response_header(self, status=200, headers=None, cookies=None):
        """Build HTTP response header string

        Connection header is added automatically based on keep-alive decision if not explicitly set.
        To force connection close, set headers['connection'] = 'close'.
        """
        header = f'{PROTOCOLS[-1]} {status} {STATUS_CODES[status]}\r\n'

        if headers is None:
            headers = {}

        for key, val in headers.items():
            header += f'{key}: {val}\r\n'

        if cookies:
            for key, val in cookies.items():
                # TODO make support for attributes
                if val is None:
                    val = '; Max-Age=0'
                header += f'{SET_COOKIE}: {key}={val}\r\n'

        header += '\r\n'
        return header

    def respond(self, data=None, status=200, headers=None, cookies=None):
        """Create general respond with data, status and headers as dict

        To force connection close, set headers['connection'] = 'close'.
        By default, HTTP/1.1 uses keep-alive, HTTP/1.0 closes connection.
        """
        if self._socket is None:
            return
        if self._response_started:
            raise HttpError("Response already sent for this request")
        self._response_started = True
        self._is_multipart = False

        if headers is None:
            headers = {}
        if data:
            data = encode_response_data(headers, data)

        # Determine keep-alive behavior and add Connection header if not set
        keep_alive = self._should_keep_alive(headers)
        if CONNECTION not in headers:
            headers[CONNECTION] = (
                CONNECTION_KEEP_ALIVE if keep_alive else CONNECTION_CLOSE)

        # Store keep-alive decision for event_write
        self._response_keep_alive = keep_alive

        header = self._build_response_header(status, headers=headers, cookies=cookies)
        try:
            # Send header and body together to avoid TCP packet splitting
            # This ensures pipelined responses arrive atomically
            if data:
                # Convert header to bytes and concatenate with data
                header_bytes = header.encode('ascii') if isinstance(header, str) else header
                self._send(header_bytes + data)
            else:
                self._send(header)
            # Close only if all data was sent, otherwise wait for write events
            if not self.has_data_to_send:
                self._finalize_sent_response()
        except OSError:
            # ignore this error, client has been disconnected during sending
            self.close()

    def respond_file(self, file_name, headers=None):
        """Respond with file content, streaming asynchronously to minimize memory usage

        To force connection close, set headers['connection'] = 'close'.
        """
        if self._response_started:
            raise HttpError("Response already sent for this request")
        if headers is None:
            headers = {}

        try:
            file_size = _os.stat(file_name)[6]  # st_size
        except (OSError, ImportError, AttributeError):
            self.respond(data=f'File not found: {file_name}', status=404)
            return

        if CONTENT_TYPE not in headers:
            ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
            headers[CONTENT_TYPE] = CONTENT_TYPE_MAP.get(ext, CONTENT_TYPE_OCTET_STREAM)

        # Build headers
        headers[CONTENT_LENGTH] = file_size

        # Determine keep-alive behavior and add Connection header if not set
        keep_alive = self._should_keep_alive(headers)
        if CONNECTION not in headers:
            headers[CONNECTION] = (
                CONNECTION_KEEP_ALIVE if keep_alive else CONNECTION_CLOSE)

        # Prepare response
        self._response_keep_alive = keep_alive
        self._response_started = True
        self._is_multipart = False

        header = self._build_response_header(200, headers=headers)

        try:
            # Send headers
            self._send(header)

            # Open file for async streaming - chunks will be sent in try_send()
            self._file_handle = open(file_name, 'rb')
        except OSError:
            # Error opening file or sending headers
            if self._file_handle:
                try:
                    self._file_handle.close()
                except OSError:
                    pass
                self._file_handle = None
            self.close()

    def response_multipart(self, headers=None):
        """Create multipart respond with headers as dict"""
        if self._socket is None:
            return False
        if self._response_started:
            raise HttpError("Response already sent for this request")
        self._response_started = True
        self._is_multipart = True

        if headers is None:
            headers = {}
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_MULTIPART_REPLACE

        header = self._build_response_header(200, headers=headers)
        try:
            self._send(header)
        except OSError:
            self.close()
            return False
        return True

    def response_multipart_frame(self, data, headers=None, boundary=None):
        """Create multipart frame respond with data and headers as dict"""
        if self._socket is None:
            return False
        if not data:
            self.response_multipart_end()
            return False
        if not boundary:
            boundary = BOUNDARY
        header = f'--{boundary}\r\n'
        if headers is None:
            headers = {}
        data = encode_response_data(headers, data)
        for key, val in headers.items():
            header += f'{key}: {val}\r\n'
        header += '\r\n'
        try:
            self._send(header)
            self._send(data)
            self._send('\r\n')
        except OSError:
            self.close()
            return False
        return True

    def response_multipart_end(self, boundary=None):
        """Finish multipart stream"""
        if not boundary:
            boundary = BOUNDARY
        self._is_multipart = False

        # Determine keep-alive behavior (multipart was started without Connection header)
        # Use default protocol behavior
        keep_alive = self._should_keep_alive()
        self._response_keep_alive = keep_alive

        try:
            self._send(f'--{boundary}--\r\n')
            if not self.has_data_to_send:
                self._finalize_sent_response()
        except OSError:
            self.close()

    def respond_redirect(self, url, status=302, cookies=None):
        """Create redirect respond to URL"""
        self.respond(status=status, headers={LOCATION: url}, cookies=cookies)


class HttpServer():
    """HTTP server"""

    def __init__(self, address='0.0.0.0', port=80, ssl_context=None, **kwargs):
        """IP address and port of listening interface for HTTP"""
        self._kwargs = kwargs
        self._ssl_context = ssl_context
        self._socket = _socket.socket()
        self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._socket.bind((address, port))
        self._socket.listen(kwargs.get('listen', LISTEN_SOCKETS))
        self._max_clients = kwargs.get(
            'max_waiting_clients', MAX_WAITING_CLIENTS)
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
        if self._socket:
            read_sockets.append(self._socket)
        return read_sockets

    @property
    def write_sockets(self):
        """All sockets with data to send, used for select"""
        return [
            con.socket
            for con in self._waiting_connections
            if con.socket is not None and con.has_data_to_send]

    def close(self):
        """Close HTTP server"""
        try:
            self._socket.close()
        except OSError:
            # Socket already closed or error during close
            pass
        self._socket = None

    def remove_connection(self, connection):
        if connection in self._waiting_connections:
            self._waiting_connections.remove(connection)

    def _cleanup_idle_connections(self):
        """Remove timed out idle connections"""
        for connection in list(self._waiting_connections):
            # Only timeout connections that are waiting for new request (not loaded)
            if not connection.is_loaded and connection.is_timed_out:
                connection.respond('Request Timeout', status=408)
                self.remove_connection(connection)

    def _accept(self):
        try:
            cl_socket, addr = self._socket.accept()
        except OSError:
            # Socket error during accept (e.g., connection reset)
            return

        # Disable Nagle's algorithm for better pipelining performance
        try:
            cl_socket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            pass  # Ignore if not supported

        # Wrap socket with SSL if ssl_context is configured
        if self._ssl_context:
            try:
                cl_socket = self._ssl_context.wrap_socket(
                    cl_socket, server_side=True)
            except OSError:
                # SSL handshake failed
                try:
                    cl_socket.close()
                except OSError:
                    pass
                return

        # Set socket to non-blocking mode for async I/O
        try:
            cl_socket.setblocking(False)
        except (OSError, AttributeError):
            pass  # Ignore if not supported

        connection = HttpConnection(self, cl_socket, addr, **self._kwargs)
        while len(self._waiting_connections) > self._max_clients:
            connection_to_remove = self._waiting_connections.pop(0)
            connection_to_remove.respond(
                'Request Timeout, too many requests', status=408)
        self._waiting_connections.append(connection)

    def event_read(self, sockets):
        """Process sockets with read_event,
        returns None or instance of HttpConnection with established connection"""
        if self._socket in sockets:
            self._accept()
            return None
        for connection in list(self._waiting_connections):
            if connection.socket is None:
                self.remove_connection(connection)
                continue
            if connection.socket in sockets:
                try:
                    if connection.process_request():
                        return connection
                except ClientError:
                    self.remove_connection(connection)
        return None

    def event_write(self, sockets):
        """Process sockets with write_event, send buffered data"""
        for connection in list(self._waiting_connections):
            if connection.socket is None:
                self.remove_connection(connection)
                continue
            if connection.socket in sockets:
                try:
                    if connection.try_send():
                        # All data sent
                        # (connection is still in waiting list after respond() if data was buffered)
                        connection._finalize_sent_response()
                except OSError:
                    self.remove_connection(connection)

    def _flush_pending_sends(self):
        """Try to flush any pending buffered data"""
        for connection in list(self._waiting_connections):
            if connection.socket is not None and connection.has_data_to_send:
                try:
                    if connection.try_send():
                        connection._finalize_sent_response()
                except OSError:
                    self.remove_connection(connection)

    def _check_pipelined_requests(self):
        """Check for pipelined requests already in buffer, returns first loaded connection"""
        for connection in list(self._waiting_connections):
            if connection.socket is None:
                self.remove_connection(connection)
                continue
            # Skip connections waiting for response (pipelining order preservation)
            if connection.is_waiting_for_response:
                continue
            # If buffer has data and not currently loaded, try to process
            if len(connection._buffer) > 0 and not connection.is_loaded:
                try:
                    if connection.process_request():
                        return connection
                except ClientError:
                    self.remove_connection(connection)
        return None

    def process_events(self, read_sockets, write_sockets):
        """Process select results, returns loaded connection or None

        This allows using external select with multiple servers/sockets:

        Example:
            server1 = HttpServer(port=80)
            server2 = HttpServer(port=443, ssl_context=ctx)

            read_all = server1.read_sockets + server2.read_sockets
            write_all = server1.write_sockets + server2.write_sockets
            r, w, _ = select.select(read_all, write_all, [], timeout)

            client = server1.process_events(r, w) or server2.process_events(r, w)
        """
        if write_sockets:
            self.event_write(write_sockets)
        if read_sockets:
            return self.event_read(read_sockets)
        return None

    def wait(self, timeout=1):
        """Wait for new clients with specified timeout,
        returns None or instance of HttpConnection with established connection"""
        self._cleanup_idle_connections()

        # First, try to flush any pending buffered data before checking pipelined requests
        # This ensures responses are sent in correct order (RFC 2616 pipelining)
        self._flush_pending_sends()

        # Check for pipelined requests already in buffer (after flushing writes)
        connection = self._check_pipelined_requests()
        if connection:
            return connection

        # Wait for socket events
        read_sockets, write_sockets, _ = _select.select(
            self.read_sockets, self.write_sockets, [], timeout)

        return self.process_events(read_sockets, write_sockets)
