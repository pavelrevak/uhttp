"""uHttp Client - Micro HTTP Client
python or micropython
(c) 2026 Pavel Revak <pavelrevak@gmail.com>
"""

import errno
import socket as _socket
import select as _select
import json as _json

KB = 2 ** 10
MB = 2 ** 20

CONNECT_TIMEOUT = 10
IDLE_TIMEOUT = 30

MAX_RESPONSE_HEADERS_LENGTH = 4 * KB
MAX_RESPONSE_LENGTH = 1 * MB

HEADERS_DELIMITERS = (b'\r\n\r\n', b'\n\n')
CONTENT_LENGTH = 'content-length'
CONTENT_TYPE = 'content-type'
CONTENT_TYPE_JSON = 'application/json'
CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'
CONNECTION = 'connection'
CONNECTION_CLOSE = 'close'
CONNECTION_KEEP_ALIVE = 'keep-alive'
COOKIE = 'cookie'
SET_COOKIE = 'set-cookie'
HOST = 'host'
USER_AGENT = 'user-agent'
USER_AGENT_VALUE = 'uhttp-client/1.0'
TRANSFER_ENCODING = 'transfer-encoding'

STATE_IDLE = 0
STATE_CONNECTING = 1
STATE_SENDING = 2
STATE_RECEIVING_HEADERS = 3
STATE_RECEIVING_BODY = 4
STATE_COMPLETE = 5


class HttpClientError(Exception):
    """HTTP client error"""


class HttpConnectionError(HttpClientError):
    """Connection error"""


class HttpTimeoutError(HttpClientError):
    """Timeout error"""


class HttpResponseError(HttpClientError):
    """Response parsing error"""


def _parse_header_line(line):
    try:
        line = line.decode('ascii')
    except ValueError as err:
        raise HttpResponseError(f"Wrong header line encoding: {line}") from err
    if ':' not in line:
        raise HttpResponseError(f"Wrong header format: {line}")
    key, val = line.split(':', 1)
    return key.strip().lower(), val.strip()


def _encode_query(query):
    if not query:
        return ''
    parts = []
    for key, val in query.items():
        if isinstance(val, list):
            for v in val:
                parts.append(f"{key}={v}")
        elif val is None:
            parts.append(key)
        else:
            parts.append(f"{key}={val}")
    return '?' + '&'.join(parts)


def _encode_request_data(data, headers):
    if data is None:
        return None
    if isinstance(data, (dict, list, tuple)):
        data = _json.dumps(data).encode('ascii')
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_JSON
    elif isinstance(data, str):
        data = data.encode('utf-8')
    elif isinstance(data, (bytes, bytearray, memoryview)):
        if CONTENT_TYPE not in headers:
            headers[CONTENT_TYPE] = CONTENT_TYPE_OCTET_STREAM
    else:
        raise HttpClientError(f"Unsupported data type: {type(data)}")
    return bytes(data)


class HttpResponse:
    """HTTP response"""

    def __init__(self, status, status_message, headers, data):
        self._status = status
        self._status_message = status_message
        self._headers = headers
        self._data = data
        self._json = None

    @property
    def content_length(self):
        val = self._headers.get(CONTENT_LENGTH)
        return int(val) if val else None

    @property
    def content_type(self):
        return self._headers.get(CONTENT_TYPE, '')

    @property
    def data(self):
        return self._data

    @property
    def headers(self):
        return self._headers

    @property
    def status(self):
        return self._status

    @property
    def status_message(self):
        return self._status_message

    def json(self):
        """Parse response body as JSON (lazy, cached)"""
        if self._json is None:
            try:
                self._json = _json.loads(self._data)
            except ValueError as err:
                raise HttpResponseError(f"JSON decode error: {err}") from err
        return self._json

    def __repr__(self):
        return f"HttpResponse({self._status} {self._status_message})"


class HttpClient:
    """HTTP client with keep-alive support"""

    def __init__(
            self, host, port=80, ssl_context=None,
            connect_timeout=CONNECT_TIMEOUT, idle_timeout=IDLE_TIMEOUT,
            max_response_length=MAX_RESPONSE_LENGTH):
        self._host = host
        self._port = port
        self._ssl_context = ssl_context
        self._connect_timeout = connect_timeout
        self._idle_timeout = idle_timeout
        self._max_response_length = max_response_length

        self._socket = None
        self._state = STATE_IDLE
        self._buffer = bytearray()
        self._send_buffer = bytearray()

        self._request_method = None
        self._request_path = None

        self._response_status = None
        self._response_status_message = None
        self._response_headers = None
        self._response_content_length = None

        self._cookies = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def cookies(self):
        return self._cookies

    @property
    def host(self):
        return self._host

    @property
    def is_connected(self):
        return self._socket is not None

    @property
    def port(self):
        return self._port

    @property
    def read_sockets(self):
        if self._socket and self._state in (
                STATE_RECEIVING_HEADERS, STATE_RECEIVING_BODY):
            return [self._socket]
        return []

    @property
    def state(self):
        return self._state

    @property
    def write_sockets(self):
        if self._socket and self._state == STATE_SENDING and self._send_buffer:
            return [self._socket]
        return []

    def _build_request(
            self, method, path, headers=None, data=None, query=None):
        if headers is None:
            headers = {}

        encoded_data = _encode_request_data(data, headers)
        full_path = path + _encode_query(query)

        if HOST not in headers:
            if self._port == 80 or (self._ssl_context and self._port == 443):
                headers[HOST] = self._host
            else:
                headers[HOST] = f"{self._host}:{self._port}"

        if USER_AGENT not in headers:
            headers[USER_AGENT] = USER_AGENT_VALUE

        if encoded_data:
            headers[CONTENT_LENGTH] = len(encoded_data)

        if self._cookies:
            cookie_str = '; '.join(
                f"{k}={v}" for k, v in self._cookies.items())
            headers[COOKIE] = cookie_str

        lines = [f"{method} {full_path} HTTP/1.1"]
        for key, val in headers.items():
            lines.append(f"{key}: {val}")
        lines.append('')
        lines.append('')

        request = '\r\n'.join(lines).encode('ascii')
        if encoded_data:
            request += encoded_data

        return request

    def _close(self):
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._state = STATE_IDLE
        self._buffer = bytearray()
        self._send_buffer = bytearray()

    def _connect(self):
        if self._socket is not None:
            return

        try:
            addr_info = _socket.getaddrinfo(
                self._host, self._port, 0, _socket.SOCK_STREAM)
            if not addr_info:
                raise HttpConnectionError(
                    f"Cannot resolve host: {self._host}")
            family, socktype, proto, _, addr = addr_info[0]
            sock = _socket.socket(family, socktype, proto)
            sock.settimeout(self._connect_timeout)
            sock.connect(addr)

            if self._ssl_context:
                # SSL handshake must be done in blocking mode
                sock = self._ssl_context.wrap_socket(
                    sock, server_hostname=self._host)

            sock.setblocking(False)
            self._socket = sock
        except OSError as err:
            raise HttpConnectionError(f"Connect failed: {err}") from err

    def _finalize_response(self):
        response = HttpResponse(
            self._response_status,
            self._response_status_message,
            self._response_headers,
            bytes(self._buffer[:self._response_content_length])
        )

        if not self._should_keep_alive():
            self._close()
        else:
            self._buffer = bytearray()
            self._state = STATE_IDLE

        return response

    def _parse_cookies(self):
        for key, val in self._response_headers.items():
            if key == SET_COOKIE:
                # Simple parsing - just key=value before first ;
                if '=' in val:
                    cookie_part = val.split(';')[0]
                    name, value = cookie_part.split('=', 1)
                    self._cookies[name.strip()] = value.strip()

    def _parse_headers(self, header_lines):
        self._response_headers = {}

        while header_lines:
            line = header_lines.pop(0)
            if not line:
                break
            if self._response_status is None:
                self._parse_status_line(line)
            else:
                key, val = _parse_header_line(line)
                self._response_headers[key] = val

        cl = self._response_headers.get(CONTENT_LENGTH)
        self._response_content_length = int(cl) if cl else 0

        self._parse_cookies()

    def _parse_status_line(self, line):
        try:
            line = line.decode('ascii')
        except ValueError as err:
            raise HttpResponseError(f"Invalid status line: {line}") from err

        parts = line.split(' ', 2)
        if len(parts) < 2:
            raise HttpResponseError(f"Invalid status line: {line}")

        protocol = parts[0]
        if not protocol.startswith('HTTP/'):
            raise HttpResponseError(f"Invalid protocol: {protocol}")

        try:
            self._response_status = int(parts[1])
        except ValueError as err:
            raise HttpResponseError(
                f"Invalid status code: {parts[1]}") from err

        self._response_status_message = parts[2] if len(parts) > 2 else ''

    def _process_recv_body(self):
        if self._response_content_length == 0:
            self._state = STATE_COMPLETE
            return

        self._recv_to_buffer(self._response_content_length)

        if len(self._buffer) >= self._response_content_length:
            self._state = STATE_COMPLETE

    def _process_recv_headers(self):
        self._recv_to_buffer(MAX_RESPONSE_HEADERS_LENGTH)

        for delimiter in HEADERS_DELIMITERS:
            if delimiter in self._buffer:
                end_index = self._buffer.index(delimiter) + len(delimiter)
                header_lines = self._buffer[:end_index].splitlines()
                self._buffer = self._buffer[end_index:]
                self._parse_headers(header_lines)
                if self._response_content_length > self._max_response_length:
                    raise HttpResponseError(
                        f"Response too large: {self._response_content_length}")
                self._state = STATE_RECEIVING_BODY
                if len(self._buffer) >= self._response_content_length:
                    self._state = STATE_COMPLETE
                return

        if len(self._buffer) >= MAX_RESPONSE_HEADERS_LENGTH:
            raise HttpResponseError("Response headers too large")

    def _recv_to_buffer(self, max_size):
        try:
            data = self._socket.recv(max_size - len(self._buffer))
        except OSError as err:
            if err.errno == errno.EAGAIN:
                return False
            raise HttpConnectionError(f"Recv failed: {err}") from err
        if not data:
            raise HttpConnectionError("Connection closed by server")
        self._buffer.extend(data)
        return True

    def _reset_request(self):
        self._request_method = None
        self._request_path = None
        self._response_status = None
        self._response_status_message = None
        self._response_headers = None
        self._response_content_length = None
        self._buffer = bytearray()
        self._send_buffer = bytearray()

    def _should_keep_alive(self):
        if not self._response_headers:
            return False
        conn = self._response_headers.get(CONNECTION, '').lower()
        if conn == CONNECTION_CLOSE:
            return False
        return True  # HTTP/1.1 defaults to keep-alive

    def _try_send(self):
        while self._send_buffer and self._state == STATE_SENDING:
            try:
                sent = self._socket.send(self._send_buffer)
                if sent is None:  # MicroPython SSL returns None on full buffer
                    break
                if sent > 0:
                    self._send_buffer = self._send_buffer[sent:]
            except OSError as err:
                if err.errno == errno.EAGAIN:
                    break
                raise HttpConnectionError(f"Send failed: {err}") from err

        if not self._send_buffer:
            self._state = STATE_RECEIVING_HEADERS

    def close(self):
        """Close connection"""
        self._close()

    def delete(self, path, **kwargs):
        """Send DELETE request"""
        return self.request('DELETE', path, **kwargs)

    def get(self, path, **kwargs):
        """Send GET request"""
        return self.request('GET', path, **kwargs)

    def head(self, path, **kwargs):
        """Send HEAD request"""
        return self.request('HEAD', path, **kwargs)

    def patch(self, path, **kwargs):
        """Send PATCH request"""
        return self.request('PATCH', path, **kwargs)

    def post(self, path, **kwargs):
        """Send POST request"""
        return self.request('POST', path, **kwargs)

    def process_events(self, read_sockets, write_sockets):
        """Process select events, returns HttpResponse when complete"""
        if self._state == STATE_IDLE:
            return None

        try:
            if self._socket in write_sockets and self._state == STATE_SENDING:
                self._try_send()

            if self._socket in read_sockets:
                if self._state == STATE_RECEIVING_HEADERS:
                    self._process_recv_headers()
                elif self._state == STATE_RECEIVING_BODY:
                    self._process_recv_body()

            if self._state == STATE_COMPLETE:
                return self._finalize_response()

        except (HttpConnectionError, HttpTimeoutError, HttpResponseError):
            self._close()
            raise

        return None

    def put(self, path, **kwargs):
        """Send PUT request"""
        return self.request('PUT', path, **kwargs)

    def request(
            self, method, path,
            headers=None, data=None, query=None, json=None):
        """Start HTTP request (async), returns self for chaining"""
        if json is not None:
            data = json

        if self._state != STATE_IDLE:
            raise HttpClientError("Request already in progress")

        self._reset_request()
        self._request_method = method
        self._request_path = path

        if not self.is_connected:
            self._connect()

        headers_copy = dict(headers) if headers else {}
        request_data = self._build_request(
            method, path, headers_copy, data, query)
        self._send_buffer.extend(request_data)
        self._state = STATE_SENDING

        self._try_send()

        return self

    def wait(self, timeout=None):
        """Wait for response (blocking),
        returns HttpResponse or None on timeout"""
        if self._state == STATE_IDLE:
            raise HttpClientError("No request in progress")

        if timeout is None:
            timeout = self._idle_timeout

        try:
            while self._state != STATE_COMPLETE:
                if self._state == STATE_SENDING:
                    _, w, _ = _select.select([], [self._socket], [], timeout)
                    if not w:
                        return None
                    self._try_send()
                else:
                    r, _, _ = _select.select([self._socket], [], [], timeout)
                    if not r:
                        return None
                    if self._state == STATE_RECEIVING_HEADERS:
                        self._process_recv_headers()
                    else:
                        self._process_recv_body()

            return self._finalize_response()

        except (HttpConnectionError, HttpTimeoutError):
            self._close()
            raise
