# uHTTP Client: micro HTTP client


## Features

- MicroPython and CPython compatible
- Select-based async (no async/await, no threading)
- Keep-alive connections with automatic reuse
- Fluent API: `response = client.get('/path').wait()`
- URL parsing with automatic SSL detection
- Base path support for API versioning
- JSON support (auto-encode request, lazy decode response)
- Binary data support
- Cookies persistence
- HTTP Basic and Digest authentication
- SSL/TLS support for HTTPS


## Usage

### URL-based initialization (recommended)

```python
from uhttp_client import HttpClient

# HTTPS with automatic SSL context
client = HttpClient('https://api.example.com')
response = client.get('/users').wait()
client.close()

# With base path for API versioning
client = HttpClient('https://api.example.com/v1')
response = client.get('/users').wait()  # requests /v1/users
client.close()

# HTTP
client = HttpClient('http://localhost:8080')
```

### Traditional initialization

```python
from uhttp_client import HttpClient

client = HttpClient('httpbin.org', port=80)
response = client.get('/get').wait()
client.close()

# With explicit SSL context
import ssl
ctx = ssl.create_default_context()
client = HttpClient('api.example.com', port=443, ssl_context=ctx)
```

### Context manager

```python
with HttpClient('https://httpbin.org') as client:
    response = client.get('/get').wait()
    print(response.status)
```

### JSON API

```python
client = HttpClient('https://api.example.com/v1')

# GET with query parameters
response = client.get('/users', query={'page': 1, 'limit': 10}).wait()

# POST with JSON body
response = client.post('/users', json={'name': 'John'}).wait()

# PUT
response = client.put('/users/1', json={'name': 'Jane'}).wait()

# DELETE
response = client.delete('/users/1').wait()

client.close()
```

### Custom headers

```python
response = client.get('/protected', headers={
    'Authorization': 'Bearer token123',
    'X-Custom-Header': 'value'
}).wait()
```

### Binary data

```python
# Send binary
response = client.post('/upload', data=b'\x00\x01\x02\xff').wait()

# Receive binary
response = client.get('/image.png').wait()
image_bytes = response.data
```


## HTTPS

### Automatic (with URL)

```python
from uhttp_client import HttpClient

# SSL context created automatically for https:// URLs
client = HttpClient('https://api.example.com')
response = client.get('/secure').wait()
client.close()
```

### Manual SSL context

```python
import ssl
from uhttp_client import HttpClient

ctx = ssl.create_default_context()
client = HttpClient('api.example.com', port=443, ssl_context=ctx)
response = client.get('/secure').wait()
client.close()
```

### MicroPython HTTPS

```python
import ssl
from uhttp_client import HttpClient

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
client = HttpClient('api.example.com', port=443, ssl_context=ctx)
response = client.get('/secure').wait()
client.close()
```


## Async (non-blocking) mode

Default mode is async. Use with external select loop:

```python
import select
from uhttp_client import HttpClient

client = HttpClient('http://httpbin.org')

# Start request (non-blocking)
client.get('/delay/2')

# Manual select loop
while True:
    r, w, _ = select.select(
        client.read_sockets,
        client.write_sockets,
        [], 10.0
    )

    response = client.process_events(r, w)
    if response:
        print(response.status)
        break

client.close()
```

### Parallel requests

```python
import select
from uhttp_client import HttpClient

clients = [
    HttpClient('http://httpbin.org'),
    HttpClient('http://httpbin.org'),
    HttpClient('http://httpbin.org'),
]

# Start all requests
for i, client in enumerate(clients):
    client.get('/delay/1', query={'n': i})

# Wait for all
results = {}
while len(results) < len(clients):
    read_socks = []
    write_socks = []
    for c in clients:
        read_socks.extend(c.read_sockets)
        write_socks.extend(c.write_sockets)

    r, w, _ = select.select(read_socks, write_socks, [], 10.0)

    for i, client in enumerate(clients):
        if i not in results:
            resp = client.process_events(r, w)
            if resp:
                results[i] = resp

for client in clients:
    client.close()
```

### Combined with HttpServer

```python
import select
from uhttp_server import HttpServer
from uhttp_client import HttpClient

server = HttpServer(port=8080)
backend = HttpClient('http://api.example.com')

while True:
    r, w, _ = select.select(
        server.read_sockets + backend.read_sockets,
        server.write_sockets + backend.write_sockets,
        [], 1.0
    )

    # Handle incoming requests
    incoming = server.process_events(r, w)
    if incoming:
        backend.get('/data', query=incoming.query)

    # Handle backend response
    response = backend.process_events(r, w)
    if response:
        incoming.respond(data=response.data)
```


## API

### Function `parse_url`

**`parse_url(url)`**

Parse URL into components. Returns `(host, port, path, ssl, auth)` tuple.

```python
from uhttp_client import parse_url

parse_url('https://api.example.com/v1/users')
# → ('api.example.com', 443, '/v1/users', True, None)

parse_url('http://localhost:8080/api')
# → ('localhost', 8080, '/api', False, None)

parse_url('https://user:pass@api.example.com')
# → ('api.example.com', 443, '', True, ('user', 'pass'))

parse_url('example.com')
# → ('example.com', 80, '', False, None)
```


### Class `HttpClient`

**`HttpClient(url_or_host, port=None, ssl_context=None, auth=None, connect_timeout=10, timeout=30, max_response_length=1MB)`**

Can be initialized with URL or host/port:

```python
# URL-based (recommended)
HttpClient('https://api.example.com/v1')

# With auth in URL
HttpClient('https://user:pass@api.example.com/v1')

# Traditional
HttpClient('api.example.com', port=443, ssl_context=ctx)
```

Parameters:
- `url_or_host` - Full URL (http://... or https://...) or hostname
- `port` - Server port (auto-detected from URL: 80 for http, 443 for https)
- `ssl_context` - Optional `ssl.SSLContext` (auto-created for https:// URLs)
- `auth` - Optional (username, password) tuple for HTTP authentication
- `connect_timeout` - Connection timeout in seconds (default: 10)
- `timeout` - Response timeout in seconds (default: 30)
- `max_response_length` - Maximum response size (default: 1MB)

#### Properties

- `host` - Server hostname
- `port` - Server port
- `base_path` - Base path from URL (prepended to all request paths)
- `is_connected` - True if socket is connected
- `state` - Current state (STATE_IDLE, STATE_SENDING, etc.)
- `auth` - Authentication credentials tuple (username, password) or None
- `cookies` - Cookies dict (persistent across requests)
- `read_sockets` - Sockets to monitor for reading (for select)
- `write_sockets` - Sockets to monitor for writing (for select)

#### Methods

**`request(method, path, headers=None, data=None, query=None, json=None, auth=None, timeout=None)`**

Start HTTP request (async). Returns `self` for chaining.

- `method` - HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` - Request path (base_path is prepended automatically)
- `headers` - Optional headers dict
- `data` - Request body (bytes, str, or dict/list for JSON)
- `query` - Optional query parameters dict
- `json` - Shortcut for data with JSON encoding
- `auth` - Optional (username, password) tuple, overrides client's default auth
- `timeout` - Optional timeout in seconds, overrides client's default timeout

**`get(path, **kwargs)`** - Send GET request

**`post(path, **kwargs)`** - Send POST request

**`put(path, **kwargs)`** - Send PUT request

**`delete(path, **kwargs)`** - Send DELETE request

**`head(path, **kwargs)`** - Send HEAD request

**`patch(path, **kwargs)`** - Send PATCH request

**`wait(timeout=None)`**

Wait for response (blocking). Returns `HttpResponse` when complete.

- `timeout` - Max time to spend in wait() call. If `None`, uses request timeout.
- Returns `None` if wait timeout expires (connection stays open, can call again).
- Raises `HttpTimeoutError` if request timeout expires (connection closed).

**`process_events(read_sockets, write_sockets)`**

Process select events. Returns `HttpResponse` when complete, `None` otherwise.

- First processes any ready data, then checks request timeout.
- Raises `HttpTimeoutError` if request timeout has expired and no complete response.

**`close()`**

Close connection.


### Class `HttpResponse`

#### Properties

- `status` - HTTP status code (int)
- `status_message` - HTTP status message (str)
- `headers` - Response headers dict (keys are lowercase)
- `data` - Response body as bytes
- `content_type` - Content-Type header value
- `content_length` - Content-Length header value

#### Methods

**`json()`**

Parse response body as JSON. Lazy evaluation, cached.


## Authentication

### Basic Auth

HTTP Basic authentication via URL or `auth` parameter:

```python
# Via URL
client = HttpClient('https://user:password@api.example.com')
response = client.get('/protected').wait()

# Via parameter
client = HttpClient('https://api.example.com', auth=('user', 'password'))
response = client.get('/protected').wait()

# Change auth at runtime
client.auth = ('new_user', 'new_password')

# Per-request auth (overrides client's default)
client = HttpClient('https://api.example.com')
response = client.get('/admin', auth=('admin', 'secret')).wait()
response = client.get('/public').wait()  # no auth
```

### Digest Auth

HTTP Digest authentication is handled automatically. On 401 response with
`WWW-Authenticate: Digest` header, the client retries with digest credentials:

```python
# Same API as Basic auth - digest is automatic
client = HttpClient('https://api.example.com', auth=('user', 'password'))

# First request gets 401, client automatically retries with digest auth
response = client.get('/protected').wait()
print(response.status)  # 200 (after automatic retry)
```

Supported digest features:
- MD5 and MD5-sess algorithms
- qop (quality of protection) with auth mode
- Nonce counting for multiple requests


## Cookies

Cookies are automatically:
- Stored from `Set-Cookie` response headers
- Sent with subsequent requests

```python
client = HttpClient('https://example.com')

# Login - server sets session cookie
client.post('/login', json={'user': 'admin', 'pass': 'secret'}).wait()

# Subsequent requests include the cookie automatically
response = client.get('/dashboard').wait()

# Access cookies
print(client.cookies)  # {'session': 'abc123'}

client.close()
```


## Keep-Alive

Connections are reused automatically (HTTP/1.1 keep-alive).

```python
client = HttpClient('https://httpbin.org')

# All requests use the same connection
for i in range(10):
    response = client.get('/get', query={'n': i}).wait()
    print(f"Request {i}: {response.status}")

client.close()
```


## Timeouts

Two types of timeouts:

### Request timeout

Total time allowed for the request. Set via `timeout` parameter on client or per-request.
When expired, raises `HttpTimeoutError` and closes connection.

```python
# Client-level timeout (default for all requests)
client = HttpClient('https://example.com', timeout=30)

# Per-request timeout (overrides client default)
response = client.get('/slow', timeout=60).wait()
```

### Wait timeout

Time to spend in `wait()` call. When expired, returns `None` but keeps connection open.
Useful for polling or interleaving with other work.

```python
client = HttpClient('https://example.com', timeout=60)  # request timeout
client.get('/slow')

# Try for 5 seconds, then do something else
response = client.wait(timeout=5)
if response is None:
    print("Still waiting, doing other work...")
    # Can call wait() again
    response = client.wait(timeout=10)
```


## Error handling

```python
from uhttp_client import (
    HttpClient,
    HttpClientError,
    HttpConnectionError,
    HttpTimeoutError,
    HttpResponseError
)

client = HttpClient('https://example.com')

try:
    response = client.get('/api').wait()
except HttpConnectionError as e:
    print(f"Connection failed: {e}")
except HttpTimeoutError as e:
    print(f"Timeout: {e}")
except HttpResponseError as e:
    print(f"Invalid response: {e}")
except HttpClientError as e:
    print(f"Client error: {e}")
finally:
    client.close()
```


## Configuration constants

```python
CONNECT_TIMEOUT = 10              # seconds
TIMEOUT = 30                      # seconds
MAX_RESPONSE_HEADERS_LENGTH = 4KB
MAX_RESPONSE_LENGTH = 1MB
```


## Examples

See [examples/](examples/) directory:
- `client_basic.py` - Basic blocking examples
- `client_https.py` - HTTPS examples
- `client_async.py` - Async select loop examples
- `client_with_server.py` - Combined server + client examples

Run examples:
```bash
PYTHONPATH=. python examples/client_basic.py
```


## CLI Tool

Simple curl-like CLI tool using uhttp_client:

```bash
# GET request
PYTHONPATH=. python tools/httpcl.py http://httpbin.org/get

# POST with JSON
PYTHONPATH=. python tools/httpcl.py http://httpbin.org/post -j '{"key": "value"}'

# Verbose mode
PYTHONPATH=. python tools/httpcl.py -v https://httpbin.org/get

# Save to file
PYTHONPATH=. python tools/httpcl.py https://httpbin.org/image/png -o image.png
```

See `tools/httpcl.py --help` for all options.


## Known Limitations

### IPv6 Not Supported

Client currently supports only IPv4:
- Uses `getaddrinfo()` which may return IPv6 addresses first on some systems (Linux)
- When server listens only on IPv4, connection to `localhost` may fail on Linux

**Workaround:** Use explicit IPv4 addresses:

```python
# May fail on Linux (localhost can resolve to ::1)
client = HttpClient('http://localhost:8080')

# Always works
client = HttpClient('http://127.0.0.1:8080')
```


## TODO

- IPv6 support (requires MicroPython testing)
