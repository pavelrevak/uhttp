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
| [uhttp-server](https://github.com/pavelrevak/uhttp-server) | HTTP server with keep-alive, streaming, event mode | `pip install uhttp-server` |
| [uhttp-client](https://github.com/pavelrevak/uhttp-client) | HTTP client with keep-alive, auth, cookies | `pip install uhttp-client` |
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

## Repository Structure

This is a meta-repository that includes both packages as git submodules:

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/pavelrevak/uhttp.git

# Update submodules to latest main
git submodule update --remote
```

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

- [Server documentation](server/README.md) - HttpServer, HttpConnection, SSL, event mode
- [Client documentation](client/README.md) - HttpClient, HttpResponse, auth, cookies

## Testing

```bash
# Create test environment
python3.14 -m venv .venv-test
.venv-test/bin/pip install -e ./server -e ./client

# Run tests
.venv-test/bin/python -m unittest discover server/tests/
.venv-test/bin/python -m unittest discover client/tests/
```

## Examples

See examples in each package:
- [server/examples/](server/examples/) - HTTPS server, HTTP→HTTPS redirect, multi-input select
- [client/examples/](client/examples/) - Basic usage, HTTPS, async with select

## License

MIT
