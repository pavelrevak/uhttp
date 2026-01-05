"""Non-blocking (async) HTTP client examples using select"""

import select
from uhttp_client import HttpClient


def example_single_async():
    """Single async request with manual select loop"""
    print("=== Single Async Request ===")

    client = HttpClient('httpbin.org', port=80)

    # Start request without blocking (async is default)
    client.get('/get', query={'mode': 'async'})
    print("Request started, waiting for response...")

    # Manual select loop
    while True:
        r, w, _ = select.select(
            client.read_sockets,
            client.write_sockets,
            [], 10.0  # timeout
        )

        response = client.process_events(r, w)
        if response:
            print(f"Response: status={response.status}")
            print(f"Data: {response.json()['args']}")
            break

    client.close()


def example_parallel_requests():
    """Multiple clients working in parallel"""
    print("\n=== Parallel Requests ===")

    # Create multiple clients
    clients = [
        HttpClient('httpbin.org', port=80),
        HttpClient('httpbin.org', port=80),
        HttpClient('httpbin.org', port=80),
    ]

    # Start all requests (async is default)
    for i, client in enumerate(clients):
        client.get('/delay/1', query={'client': i})
        print(f"Client {i} request started")

    # Wait for all responses
    responses = {}
    while len(responses) < len(clients):
        # Collect all sockets
        read_socks = []
        write_socks = []
        for client in clients:
            read_socks.extend(client.read_sockets)
            write_socks.extend(client.write_sockets)

        r, w, _ = select.select(read_socks, write_socks, [], 10.0)

        # Process events for each client
        for i, client in enumerate(clients):
            if i not in responses:
                resp = client.process_events(r, w)
                if resp:
                    responses[i] = resp
                    print(f"Client {i} done: status={resp.status}")

    # Cleanup
    for client in clients:
        client.close()

    print(f"All {len(responses)} requests completed in parallel")


def example_mixed_operations():
    """Async requests with different methods"""
    print("\n=== Mixed Async Operations ===")

    client = HttpClient('httpbin.org', port=80)

    operations = [
        ('GET', '/get', None),
        ('POST', '/post', {'action': 'create'}),
        ('PUT', '/put', {'action': 'update'}),
        ('DELETE', '/delete', None),
    ]

    for method, path, json_data in operations:
        client.request(method, path, json=json_data)  # async is default

        while True:
            r, w, _ = select.select(
                client.read_sockets,
                client.write_sockets,
                [], 5.0
            )
            response = client.process_events(r, w)
            if response:
                print(f"{method} {path}: status={response.status}")
                break

    client.close()


def example_with_timeout_handling():
    """Handling timeouts in async mode"""
    print("\n=== Timeout Handling ===")

    client = HttpClient('httpbin.org', port=80)
    client.get('/delay/2')  # 2 second delay, async is default

    timeout_seconds = 5
    elapsed = 0

    while elapsed < timeout_seconds:
        r, w, _ = select.select(
            client.read_sockets,
            client.write_sockets,
            [], 1.0  # 1 second intervals
        )

        if not r and not w:
            elapsed += 1
            print(f"Waiting... {elapsed}s")
            continue

        response = client.process_events(r, w)
        if response:
            print(f"Response received: status={response.status}")
            break
    else:
        print("Request timed out!")

    client.close()


if __name__ == '__main__':
    example_single_async()
    example_parallel_requests()
    example_mixed_operations()
    example_with_timeout_handling()
