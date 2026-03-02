"""
Test IPv6 TCP socket communication on MicroPython.

Run this script directly on your MicroPython device to test
if IPv6 sockets work locally.
"""

import socket
import time
import sys

# IPv6 localhost address
HOST = '::1'
PORT = 8765

# Detect platform
IS_MICROPYTHON = sys.implementation.name == 'micropython'


def get_ipv6_addr(host, port):
    """Get proper address tuple for IPv6 bind/connect.

    MicroPython uses 2-tuple: (host, port)
    CPython uses 4-tuple: (host, port, flowinfo, scopeid)
    """
    if IS_MICROPYTHON:
        return (host, port)
    else:
        return (host, port, 0, 0)


def test_ipv6_support():
    """Test if IPv6 is supported at all."""
    print("=" * 40)
    print("Testing IPv6 socket support")
    print("Platform:", sys.implementation.name)
    print("=" * 40)

    # Check if AF_INET6 exists
    if not hasattr(socket, 'AF_INET6'):
        print("ERROR: socket.AF_INET6 not available!")
        print("IPv6 is not supported on this platform.")
        return False

    print("AF_INET6 constant exists: {}".format(socket.AF_INET6))

    # Try to create IPv6 socket
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        print("IPv6 socket created successfully")
        s.close()
    except Exception as e:
        print("ERROR creating IPv6 socket:", e)
        return False

    # Try getaddrinfo for IPv6
    try:
        result = socket.getaddrinfo(HOST, PORT, socket.AF_INET6, socket.SOCK_STREAM)
        print("getaddrinfo for [{}]:{} = {}".format(HOST, PORT, result))
    except Exception as e:
        print("WARNING: getaddrinfo failed:", e)

    return True


def run_test():
    """Run complete IPv6 test with server and client."""
    print()
    print("=" * 40)
    print("IPv6 Local TCP Socket Test")
    print("=" * 40)
    print()

    # First check IPv6 support
    if not test_ipv6_support():
        return

    print()
    print("=" * 40)
    print("Running server/client test")
    print("=" * 40)
    print()

    # Get proper address format for this platform
    bind_addr = get_ipv6_addr(HOST, PORT)
    connect_addr = get_ipv6_addr(HOST, PORT)
    print("Using address format:", bind_addr)

    # Create server socket first
    print("Creating server...")
    server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind(bind_addr)
        server.listen(1)
        server.setblocking(False)
        print("Server bound to [{}]:{}".format(HOST, PORT))
    except Exception as e:
        print("ERROR: Cannot bind server:", e)
        server.close()
        return

    # Create and connect client
    print("Creating client...")
    client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    try:
        client.connect(connect_addr)
        print("Client connected!")
    except Exception as e:
        print("ERROR: Client cannot connect:", e)
        server.close()
        client.close()
        return

    # Accept connection on server (may need small delay for connection to arrive)
    time.sleep(0.1)
    try:
        conn, addr = server.accept()
        print("Server accepted connection from:", addr)
    except Exception as e:
        print("ERROR: Server accept failed:", e)
        server.close()
        client.close()
        return

    # Send data from client to server
    test_data = b"IPv6 test message 12345"
    client.send(test_data)
    print("Client sent:", test_data)

    # Receive on server
    time.sleep(0.1)  # Small delay for data to arrive
    received = conn.recv(1024)
    print("Server received:", received)

    # Send response from server to client
    response = b"IPv6 response OK"
    conn.send(response)
    print("Server sent:", response)

    # Receive on client
    time.sleep(0.1)
    client_received = client.recv(1024)
    print("Client received:", client_received)

    # Cleanup
    conn.close()
    client.close()
    server.close()

    # Verify
    print()
    print("=" * 40)
    if received == test_data and client_received == response:
        print("SUCCESS! IPv6 TCP sockets work correctly!")
    else:
        print("FAILED! Data mismatch")
        print("Expected server to receive:", test_data)
        print("Actual:", received)
        print("Expected client to receive:", response)
        print("Actual:", client_received)
    print("=" * 40)


if __name__ == "__main__":
    run_test()
