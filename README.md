# uHTTP: micro HTTP server


## Features:

- support MicroPython and also cPython
- minimalist and low level implementation using posix sockets
- is fully synchronous (not uses ASYNC or multiple threads) but can work with multiple connections
- support delayed response, user can hold client instance and reply later
- support for raw data (HTML, binary, ...) and also for JSON (send and receive)
- need at least 32KB RAM to work (depends on configured limits)
- do many check for bad requests and or headers, and many errors will not break this


## Testing

Comprehensive test suite with 93 tests covering all major functionality.

Run all tests from the project root:

```bash
# Run all tests
python -m unittest discover -s tests

# Run with verbose output
python -m unittest discover -s tests -v
```

See [tests/README.md](tests/README.md) for detailed test documentation.


## usage

```python
import uhttp

server = uhttp.HttpServer(port=9980)

while True:
    client = server.wait()
    if client:
        if client.path == '/':
            # result is html
            client.respond("<h1>hello</h1><p>uHTTP</p>")
        elif client.path == '/rpc':
            # result is json
            client.respond({'message': 'hello', 'success': True, 'headers': client.headers, 'query': client.query})
        else:
            client.respond("Not found", status=404)

```


## API

### General methods:

**`import uhttp`**

**`uhttp.decode_percent_encoding(data)`**

- Decode percent encoded data (bytes)

**`uhttp.parse_header_parameters(value)`**

- Parse parameters/directives from header value, returns dict

**`uhttp.parse_query(raw_query, query=None)`**

- Parse raw_query from URL, append it to existing query, returns dict

**`uhttp.parse_url(url)`**

- Parse URL to path and query

**`uhttp.parse_header_line(line)`**

- Parse header line to key and value

**`uhttp.encode_response_data(headers, data)`**

- Encode response data by its type


### Class `HttpServer`:

**`HttpServer(address='0.0.0.0', port=80)`**

#### Properties:

**`socket(self)`**

- Server socket

**`read_sockets(self)`**

- All sockets waiting for communication, used for select

#### Methods:

**`process_events(self, read_events)`**

- Process sockets with read_events, returns None or instance of HttpClient with established connection

**`wait(self, timeout=1)`**

- Wait for new clients with specified timeout, returns None or instance of HttpClient with established connection


### Class `HttpClient`:

**`HttpClient(sock, addr)`**

#### Properties:

**`addr(self)`**

- Client address

**`method(self)`**

- HTTP method

**`url(self)`**

- URL address

**`host(self)`**

- URL address

**`full_url(self)`**

- URL address

**`protocol(self)`**

- Protocol

**`headers(self)`**

- headers dict

**`data(self)`**

- Content data

**`path(self)`**

- Path

**`query(self)`**

- Query dict

**`cookies(self)`**

- Query dict

**`socket(self)`**

- This socket

**`is_loaded_all(self)`**

- State if request is fully loaded

**`content_length(self)`**

- Content length

#### Methods:

**`headers_get(self, key, default=None)`**

- Return value from headers by key, or default if key not found

**`process_request(self)`**

- Process HTTP request when read event on client socket

**`respond(self, data=None, status=200, headers=None, cookies=None)`**

- Create general response with data, status and headers as dict

**`respond_redirect(self, url, status=302, cookies=None)`**

- Create redirect response to URL
