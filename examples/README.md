# uHTTP Examples

Example scripts demonstrating various features of the uHTTP library.

Run examples from the project root directory:
```bash
PYTHONPATH=. python examples/<example>.py
```

## HTTP Client Examples

### Basic Client Usage

**File:** `client_basic.py`

Demonstrates basic HTTP client features:
- Simple GET requests
- JSON API (GET, POST, PUT, DELETE)
- Keep-alive connections
- Context manager
- Custom headers
- Binary data

```bash
PYTHONPATH=. python examples/client_basic.py
```

### HTTPS Client

**File:** `client_https.py`

HTTPS client with SSL/TLS support.

```bash
PYTHONPATH=. python examples/client_https.py
```

### Async/Non-blocking Client

**File:** `client_async.py`

Non-blocking HTTP client using select():
- Single async request
- Parallel requests (multiple clients)
- Mixed operations (GET, POST, PUT, DELETE)
- Timeout handling

```bash
PYTHONPATH=. python examples/client_async.py
```

### Client + Server Integration

**File:** `client_with_server.py`

Combining HttpServer and HttpClient:
- API aggregator (parallel requests to multiple backends)
- Simple proxy (uncomment in code to run)

```bash
PYTHONPATH=. python examples/client_with_server.py
```

## SSL/HTTPS Server Examples

### Prerequisites

Generate a self-signed SSL certificate for testing:

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

### Simple HTTPS Server

**File:** `https_server.py`

Basic HTTPS server with SSL support.

```bash
PYTHONPATH=. python examples/https_server.py
```

Test with:
```bash
curl -k https://localhost:8443/
curl -k https://localhost:8443/api/test
```

### HTTP to HTTPS Redirect

**File:** `http_to_https_redirect.py`

Runs two servers:
- HTTP server (port 8080) - redirects all requests to HTTPS
- HTTPS server (port 8443) - serves actual content

```bash
PYTHONPATH=. python examples/http_to_https_redirect.py
```

Test with:
```bash
# This will be redirected to HTTPS
curl -L http://localhost:8080/test

# Direct HTTPS access
curl -k https://localhost:8443/test
```

## Features Demonstrated

- **SSL/TLS Support**: Creating HTTPS servers with `ssl_context`
- **Keep-Alive Connections**: Persistent connections for better performance
- **Redirects**: HTTP 302 redirects using `respond_redirect()`
- **Multiple Servers**: Running HTTP and HTTPS servers simultaneously with `select()`
- **Security Property**: Using `client.is_secure` to check if connection is encrypted

## Production Notes

For production deployment:

1. **Use standard ports**: Change `8080` → `80` and `8443` → `443` (requires root/admin privileges)

2. **Use proper certificates**: Replace self-signed certificates with certificates from a Certificate Authority (Let's Encrypt, etc.)

3. **Configure SSL context properly**:
   ```python
   context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
   context.minimum_version = ssl.TLSVersion.TLSv1_2
   context.load_cert_chain(certfile='fullchain.pem', keyfile='privkey.pem')
   ```

4. **Use HSTS headers** to enforce HTTPS:
   ```python
   client.respond(
       data={'message': 'Hello'},
       headers={'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'}
   )
   ```
