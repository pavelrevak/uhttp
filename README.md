# uHTTP simple low level synchronous micropython HTTP server


example:
```python
import uhttp

server = uhttp.HttpServer(port=9980)

while True:
    client = server.wait()
    if client:
        if client.path == '/':
            client.response("<h1>hello</h1><p>uHTTP</p>")
        else:
            client.response(status=404)

```
