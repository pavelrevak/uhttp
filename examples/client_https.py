"""HTTPS client examples"""

import ssl
from uhttp_client import HttpClient


def example_https_basic():
    """Basic HTTPS request"""
    print("=== HTTPS Basic ===")

    # Create SSL context
    ctx = ssl.create_default_context()

    client = HttpClient('httpbin.org', port=443, ssl_context=ctx)

    response = client.get('/get').wait()
    print(f"Status: {response.status}")
    print(f"URL: {response.json()['url']}")

    client.close()


def example_https_api():
    """HTTPS API with JSON"""
    print("\n=== HTTPS API ===")

    ctx = ssl.create_default_context()

    with HttpClient('httpbin.org', port=443, ssl_context=ctx) as client:
        # POST JSON over HTTPS
        response = client.post('/post', json={
            'secure': True,
            'data': 'sensitive information'
        }).wait()

        data = response.json()
        print(f"Server received: {data['json']}")
        print(f"Protocol: HTTPS (verified)")


def example_https_keep_alive():
    """Multiple HTTPS requests with keep-alive"""
    print("\n=== HTTPS Keep-Alive ===")

    ctx = ssl.create_default_context()
    client = HttpClient('httpbin.org', port=443, ssl_context=ctx)

    for i in range(3):
        response = client.get('/get', query={'n': i}).wait()
        print(f"Request {i}: status={response.status}")

    client.close()


# MicroPython example (commented - different SSL API)
"""
def example_micropython_https():
    '''HTTPS on MicroPython'''
    import ssl

    # MicroPython SSL context
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    client = HttpClient('api.example.com', port=443, ssl_context=ctx)
    response = client.get('/data')
    print(response.json())
    client.close()
"""


if __name__ == '__main__':
    example_https_basic()
    example_https_api()
    example_https_keep_alive()
