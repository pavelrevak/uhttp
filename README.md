# uHTTP: micro HTTP server and client

Minimalist HTTP library for MicroPython and CPython.

## Features

- MicroPython and CPython compatible
- Low-level POSIX socket implementation
- Fully synchronous (no async/await, no threading) but handles multiple connections
- Memory-efficient: works with ~32KB RAM
- SSL/TLS support for HTTPS
- IPv6 and dual-stack support

## Packages

The library is split into independent packages:

| Package | Description | Install |
|---------|-------------|---------|
| [uhttp-server](https://github.com/cortexm/uhttp-server) | HTTP server with keep-alive, streaming, event mode | `pip install uhttp-server` |
| [uhttp-client](https://github.com/cortexm/uhttp-client) | HTTP client with keep-alive, auth, cookies | `pip install uhttp-client` |
| micro-http | Meta-package (installs both) | `pip install micro-http` |

## Installation

```bash
# Install both server and client
pip install micro-http

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

## Development

For local development, clone the repositories separately:

```bash
git clone https://github.com/cortexm/uhttp-server.git
git clone https://github.com/cortexm/uhttp-client.git

# Create shared venv
python3.14 -m venv .venv
.venv/bin/pip install -e ./uhttp-server -e ./uhttp-client

# Run tests
.venv/bin/python -m unittest discover uhttp-server/tests/
.venv/bin/python -m unittest discover uhttp-client/tests/
```

## License

MIT
