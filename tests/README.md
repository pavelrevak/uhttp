# uHTTP Test Suite

Comprehensive test suite for the uHTTP library covering all major functionality.

## Running Tests

From the project root directory:

```bash
# Run all tests
python -m unittest discover -s tests

# Run all tests with verbose output
python -m unittest discover -s tests -v

# Run specific test file
python -m unittest tests.test_data_parsing

# Run specific test class
python -m unittest tests.test_data_parsing.TestDataParsing

# Run specific test method
python -m unittest tests.test_data_parsing.TestDataParsing.test_json_simple_object
```

## Test Files

### Core Functionality Tests

- **test_utils.py** (15 tests)
  - Low-level parsing functions
  - Percent encoding/decoding
  - Header parameter parsing
  - Query string parsing

- **test_data_parsing.py** (25 tests)
  - JSON data parsing
  - Form data (application/x-www-form-urlencoded)
  - Cookie parsing
  - Query strings
  - URL path handling
  - Binary data

### Security Tests

- **test_content_length_security.py** (6 tests)
  - Content-Length header validation
  - HTTP request smuggling prevention
  - Pipelined request handling

- **test_error_handling.py** (13 tests)
  - Malformed requests
  - Invalid headers
  - Unsupported methods/protocols
  - Size limit enforcement
  - Invalid JSON handling
  - RFC 2616 compliance (Host header required for HTTP/1.1)

### HTTP Protocol Tests

- **test_pipelining.py** (2 tests)
  - Multiple requests in one TCP packet
  - GET and POST pipelining

### Keep-Alive Tests

- **test_keepalive.py** (5 tests)
  - Persistent connections
  - Connection reuse
  - HTTP/1.1 default keep-alive

- **test_keepalive_simple.py** (4 tests)
  - Simple keep-alive scenarios
  - Connection header validation
  - Request counter increment

- **test_keepalive_http10.py** (5 tests)
  - HTTP/1.0 keep-alive behavior
  - Explicit Connection: keep-alive header
  - Protocol detection

- **test_keepalive_limits.py** (4 tests in 2 classes)
  - Max requests per connection limit
  - Idle connection timeout
  - Connection close behavior

- **test_server_keepalive.py** (6 tests)
  - Server-side keep-alive handling
  - Multiple protocols (HTTP/1.0 and HTTP/1.1)

### Concurrency Tests

- **test_concurrent_connections.py** (4 tests)
  - Multiple simultaneous clients
  - Rapid connection/disconnection
  - Max waiting clients limit
  - Slow clients

### Advanced Features

- **test_multipart.py** (4 tests)
  - Multipart responses
  - Streaming data
  - Frame-by-frame delivery

## Test Coverage

Total: **93 tests** covering:
- HTTP request/response parsing
- Keep-alive connection management
- Security (request smuggling, size limits)
- Concurrent connections
- Error handling
- Multipart responses
- URL encoding/decoding
- Cookie handling
- Query parameter parsing

## Requirements

- Python 3.7+
- No external dependencies required (uses built-in `unittest` framework)

## Test Structure

All tests use the `unittest` framework with:
- `setUpClass`/`tearDownClass` for server lifecycle
- `setUp` for per-test state reset
- Proper socket cleanup with try-finally blocks
- Descriptive test names and docstrings
