"""Basic HTTP client examples"""

from uhttp_client import HttpClient


def example_simple_get():
    """Simple GET request"""
    print("=== Simple GET ===")

    client = HttpClient('httpbin.org', port=80)

    response = client.get('/get').wait()
    print(f"Status: {response.status}")
    print(f"Headers: {list(response.headers.keys())}")
    print(f"Body preview: {response.data[:100]}...")

    client.close()


def example_json_api():
    """Working with JSON API"""
    print("\n=== JSON API ===")

    client = HttpClient('httpbin.org', port=80)

    # GET with query parameters
    response = client.get('/get', query={'page': 1, 'limit': 10}).wait()
    data = response.json()
    print(f"Query args received by server: {data['args']}")

    # POST with JSON body
    response = client.post('/post', json={
        'username': 'john',
        'email': 'john@example.com'
    }).wait()
    data = response.json()
    print(f"JSON sent to server: {data['json']}")

    # PUT request
    response = client.put('/put', json={'id': 1, 'name': 'updated'}).wait()
    print(f"PUT status: {response.status}")

    # DELETE request
    response = client.delete('/delete').wait()
    print(f"DELETE status: {response.status}")

    client.close()


def example_keep_alive():
    """Keep-alive connection reuse"""
    print("\n=== Keep-Alive ===")

    client = HttpClient('httpbin.org', port=80)

    # Multiple requests on same connection
    for i in range(5):
        response = client.get('/get', query={'request': i}).wait()
        print(f"Request {i}: status={response.status}, connected={client.is_connected}")

    client.close()


def example_context_manager():
    """Using context manager for automatic cleanup"""
    print("\n=== Context Manager ===")

    with HttpClient('httpbin.org', port=80) as client:
        response = client.get('/get').wait()
        print(f"Status: {response.status}")

    print("Connection automatically closed")


def example_custom_headers():
    """Custom headers"""
    print("\n=== Custom Headers ===")

    client = HttpClient('httpbin.org', port=80)

    response = client.get('/headers', headers={
        'X-Custom-Header': 'my-value',
        'Authorization': 'Bearer token123'
    }).wait()

    data = response.json()
    print(f"Server saw headers: {data['headers']}")

    client.close()


def example_binary_data():
    """Sending and receiving binary data"""
    print("\n=== Binary Data ===")

    client = HttpClient('httpbin.org', port=80)

    # Send binary data
    binary_payload = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD])
    response = client.post('/post', data=binary_payload).wait()
    print(f"Sent {len(binary_payload)} bytes")

    # Receive binary (image)
    response = client.get('/image/png').wait()
    print(f"Received image: {len(response.data)} bytes")
    print(f"Content-Type: {response.content_type}")

    client.close()


if __name__ == '__main__':
    example_simple_get()
    example_json_api()
    example_keep_alive()
    example_context_manager()
    example_custom_headers()
    example_binary_data()
