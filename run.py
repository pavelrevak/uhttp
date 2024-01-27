import sys
import uhttp


def print_result(client):
    print("CLIENT: ", client)
    print("HEADERS:")
    for key, val in client.headers.items():
        print(f"  {key}: {val}")
    if client.query:
        print("QUERY:")
        for key, val in client.query.items():
            print(f"  {key}: {val}")
    if client.cookies:
        print("COOKIE:")
        for key, val in client.cookies.items():
            print(f"  {key}: {val}")
    if client.data:
        if isinstance(client.data, dict):
            print("DATA:")
            for key, val in client.data.items():
                print(f"  {key}: {val}")
        else:
            print(f"DATA: {client.data}")


def client_result_html(client):
    res = '<html><head>\n'
    res += '<meta http-equiv="Content-type" content="text/html; charset=utf-8">'
    res += '</head><body>\n'
    res += '<h1>uHttp server test</h1>\n'
    res += "<div>\n"
    res += '<a href="/">home</a>\n'
    res += '<a href="/rpc">rpc</a>\n'
    res += "</div>\n"
    res += "<p><div><b>CLIENT:</b></div>\n"
    res += f"<div><code>  {client}</code></div></p>\n"
    res += '<p><div><b>HEADERS:</b></div>\n'
    for key, val in client.headers.items():
        res += f"<div><code>{key}: {val}</code></div>\n"
    res += '</p>'
    if client.query:
        res += '<p><div><b>QUERY:</b></div>\n'
        for key, val in client.query.items():
            res += f"<div><code>  {key}: {val}</code></div>\n"
    res += '</p>'
    if client.cookies:
        res += '<p><div><b>COOKIE:</b></div>\n'
        for key, val in client.cookies.items():
            res += f"<div><code>  {key}: {val}</code></div>\n"
    res += '</p>'
    if client.data:
        if isinstance(client.data, dict):
            res += '<p><div><b>DATA:</b></div>\n'
            for key, val in client.data.items():
                res += f"<div><code>  {key}: {val}</code></div>\n"
        else:
            res += '<div><b>DATA:</b></div>\n'
            res += f'<div><b>DATA: {client.data}</b></div>\n'
    res += '</p>'
    res += '<p><form action="/get">'
    res += '<label for="get_edit1">Edit1:</label>'
    res += '<input type="text" id="get_edit1" name="get_edit1" /><br>'
    res += '<label for="get_edit2">Edit2:</label>'
    res += '<input type="text" id="get_edit2" name="get_edit2" /><br>'
    res += '<input type="submit" value="Submit (get)" />'
    res += '</form></p>'
    res += '<p><form action="/post" method="post">'
    res += '<label for="post_edit1">Edit1:</label>'
    res += '<input type="text" id="post_edit1" name="post_edit1" /><br>'
    res += '<label for="post_edit2">Edit2:</label>'
    res += '<input type="text" id="post_edit2" name="post_edit2" /><br>'
    res += '<input type="submit" value="Submit (post)" />'
    res += '</form></p>'
    res += '<body><html>\n'
    return res


def process_request(client):
    print_result(client)
    if client.path == '/rpc':
        client.respond(data=client.headers)
    elif client.path in ('/post', '/get'):
        client.respond_redirect('/')
    elif client.path == '/set-cookie':
        client.respond_redirect('/', cookies=client.query)
    else:
        res = client_result_html(client)
        client.respond(data=res)


def test(port=7780):
    print("starting web server")
    server = uhttp.HttpServer(port=port)

    while True:
        client = server.wait()
        if client:
            process_request(client)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        test(int(sys.argv[1]))
    else:
        test()
