# uHTTP simple HTTP server

- support micropython and also cpython
- low level
- synchronous (not uses async)
- support delayed response, user can hold client instance and reply later
- support for raw data (html, binary, ...) and also for json (send and receive)
- need at least 48KB RAM to work

### example:
```python
import uhttp

server = uhttp.HttpServer(port=9980)

while True:
    client = server.wait()
    if client:
        if client.path == '/':
            client.response("<h1>hello</h1><p>uHTTP</p>")
        elif client.path == '/rpc':
            client.response({'message': 'hello', 'success': True})
        else:
            client.response(status=404)

```
