# uHTTP: micro HTTP server and client

Minimalist HTTP libraries for MicroPython and CPython.

## Features

- MicroPython and CPython compatible
- Low-level POSIX socket implementation
- Fully synchronous (no async/await, no threading) but handles multiple simultaneous connections
- Memory-efficient: works with low memory on MCUs
- SSL/TLS support for HTTPS
- IPv6 and dual-stack support

## Packages

The library is split into two independent packages:

### [uhttp-server](https://github.com/cortexm/uhttp-server)

- HTTP server with keep-alive, streaming, event mode

### [uhttp-client](https://github.com/cortexm/uhttp-client)

- HTTP client with keep-alive, auth, cookies

## Installation

```bash
# Install only what you need
pip install uhttp-server
pip install uhttp-client
```

For MicroPython, copy `uhttp/server.py` and/or `uhttp/client.py` from the respective repository to your device.

## Quick Start

### Server

```python
from uhttp.server import HttpServer

server = HttpServer(port=8080)

while True:
    client = server.wait()
    if client:
        client.respond({'message': 'Hello from uHTTP!'})
```

### Client

```python
from uhttp.client import HttpClient

with HttpClient('https://httpbin.org') as client:
    response = client.get('/get').wait()
    print(response.json())
```

## Documentation

- [Server documentation](https://github.com/cortexm/uhttp-server#readme)
- [Client documentation](https://github.com/cortexm/uhttp-client#readme)

## License

MIT
