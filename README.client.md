# uHTTP Client: micro HTTP client


## Features

- MicroPython and CPython compatible
- Select-based async (no async/await, no threading)
- Keep-alive connections with automatic reuse
- Fluent API: `response = client.get('/path').wait()`
- JSON support (auto-encode request, lazy decode response)
- Binary data support
- Cookies persistence
- SSL/TLS support for HTTPS


## Usage

### Basic blocking request

```python
from uhttp_client import HttpClient

client = HttpClient('httpbin.org', port=80)

response = client.get('/get').wait()
print(response.status)      # 200
print(response.json())      # parsed JSON

client.close()
```

### Context manager

```python
with HttpClient('httpbin.org', port=80) as client:
    response = client.get('/get').wait()
    print(response.status)
```

### JSON API

```python
client = HttpClient('api.example.com', port=80)

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

client = HttpClient('httpbin.org', port=80)

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
    HttpClient('httpbin.org', port=80),
    HttpClient('httpbin.org', port=80),
    HttpClient('httpbin.org', port=80),
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
backend = HttpClient('api.example.com', port=80)

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

### Class `HttpClient`

**`HttpClient(host, port=80, ssl_context=None, connect_timeout=10, idle_timeout=30, max_response_length=1MB)`**

Parameters:
- `host` - Server hostname
- `port` - Server port (default: 80)
- `ssl_context` - Optional `ssl.SSLContext` for HTTPS
- `connect_timeout` - Connection timeout in seconds (default: 10)
- `idle_timeout` - Idle/response timeout in seconds (default: 30)
- `max_response_length` - Maximum response size (default: 1MB)

#### Properties

- `host` - Server hostname
- `port` - Server port
- `is_connected` - True if socket is connected
- `state` - Current state (STATE_IDLE, STATE_SENDING, etc.)
- `cookies` - Cookies dict (persistent across requests)
- `read_sockets` - Sockets to monitor for reading (for select)
- `write_sockets` - Sockets to monitor for writing (for select)

#### Methods

**`request(method, path, headers=None, data=None, query=None, json=None)`**

Start HTTP request (async). Returns `self` for chaining.

- `method` - HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` - Request path
- `headers` - Optional headers dict
- `data` - Request body (bytes, str, or dict/list for JSON)
- `query` - Optional query parameters dict
- `json` - Shortcut for data with JSON encoding

**`get(path, **kwargs)`** - Send GET request

**`post(path, **kwargs)`** - Send POST request

**`put(path, **kwargs)`** - Send PUT request

**`delete(path, **kwargs)`** - Send DELETE request

**`head(path, **kwargs)`** - Send HEAD request

**`patch(path, **kwargs)`** - Send PATCH request

**`wait(timeout=None)`**

Wait for response (blocking). Returns `HttpResponse` or `None` on timeout.

**`process_events(read_sockets, write_sockets)`**

Process select events. Returns `HttpResponse` when complete, `None` otherwise.

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


## Cookies

Cookies are automatically:
- Stored from `Set-Cookie` response headers
- Sent with subsequent requests

```python
client = HttpClient('example.com', port=80)

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
client = HttpClient('httpbin.org', port=80)

# All requests use the same connection
for i in range(10):
    response = client.get('/get', query={'n': i}).wait()
    print(f"Request {i}: {response.status}")

client.close()
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

client = HttpClient('example.com', port=80)

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
IDLE_TIMEOUT = 30                 # seconds
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
