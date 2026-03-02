"""
Test dual-stack TCP socket (IPv4 + IPv6 on single socket).

This tests if a single IPv6 socket can accept both IPv4 and IPv6 connections
by setting IPV6_V6ONLY=0.

IPv4 clients appear as IPv4-mapped IPv6 addresses: ::ffff:127.0.0.1
"""

import socket
import time
import sys

PORT = 8766

# Detect platform
IS_MICROPYTHON = sys.implementation.name == 'micropython'

# IPV6_V6ONLY constant - may not exist on all platforms
# Linux: 26, macOS: 27, Windows: 27
IPV6_V6ONLY = getattr(socket, 'IPV6_V6ONLY', 26 if sys.platform == 'linux' else 27)

# IPPROTO_IPV6 constant
IPPROTO_IPV6 = getattr(socket, 'IPPROTO_IPV6', 41)


def get_ipv6_addr(host, port):
    """Get proper address tuple for IPv6 bind/connect.

    MicroPython uses 2-tuple: (host, port)
    CPython uses 4-tuple: (host, port, flowinfo, scopeid)

    Note: We don't use getaddrinfo() because old Python 3.3 has a bug
    where it returns raw bytes instead of parsed sockaddr tuple.
    """
    if IS_MICROPYTHON:
        return (host, port)
    else:
        return (host, port, 0, 0)


def get_ipv4_addr(host, port):
    """Get proper address tuple for IPv4 bind/connect."""
    return (host, port)


def test_constants():
    """Test if required constants exist."""
    print("=" * 50)
    print("Testing constants")
    print("Platform:", sys.implementation.name)
    print("=" * 50)

    print("AF_INET6:", getattr(socket, 'AF_INET6', 'NOT FOUND'))
    print("AF_INET:", getattr(socket, 'AF_INET', 'NOT FOUND'))
    print("IPPROTO_IPV6:", IPPROTO_IPV6)
    print("IPV6_V6ONLY:", IPV6_V6ONLY)

    if not hasattr(socket, 'AF_INET6'):
        print("ERROR: AF_INET6 not available!")
        return False

    return True


def test_v6only_option():
    """Test if IPV6_V6ONLY socket option can be set."""
    print()
    print("=" * 50)
    print("Testing IPV6_V6ONLY socket option")
    print("=" * 50)

    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    # Try to get current value
    try:
        current = s.getsockopt(IPPROTO_IPV6, IPV6_V6ONLY)
        print("Current IPV6_V6ONLY value:", current)
    except Exception as e:
        print("Cannot get IPV6_V6ONLY:", e)
        current = None

    # Try to set to 0 (dual-stack)
    try:
        s.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0)
        print("Set IPV6_V6ONLY to 0: OK")
    except Exception as e:
        print("ERROR: Cannot set IPV6_V6ONLY to 0:", e)
        s.close()
        return False

    # Verify it was set
    try:
        new_value = s.getsockopt(IPPROTO_IPV6, IPV6_V6ONLY)
        print("New IPV6_V6ONLY value:", new_value)
        if new_value != 0:
            print("WARNING: Value not changed to 0!")
    except Exception as e:
        print("Cannot verify IPV6_V6ONLY:", e)

    s.close()
    return True


def test_ipv6_bind():
    """Test if IPv6 bind works at all."""
    print()
    print("=" * 50)
    print("Testing basic IPv6 bind")
    print("=" * 50)

    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Try different address formats
    test_addrs = [
        ('::1', 8770),                    # 2-tuple
        ('::1', 8770, 0, 0),              # 4-tuple
        ('', 8770, 0, 0),                 # empty string
    ]

    for addr in test_addrs:
        try:
            s2 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s2.bind(addr)
            print("bind({}) = OK".format(addr))
            s2.close()
            return True
        except Exception as e:
            print("bind({}) = FAILED: {}".format(addr, e))

    s.close()
    return False


def run_dual_stack_test():
    """Test dual-stack server accepting both IPv4 and IPv6 clients."""
    print()
    print("=" * 50)
    print("Running dual-stack server test")
    print("=" * 50)
    print()

    # Create IPv6 socket
    print("Creating IPv6 server socket...")
    server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Disable IPV6_V6ONLY to accept IPv4 connections too
    try:
        server.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0)
        print("IPV6_V6ONLY set to 0 (dual-stack enabled)")
    except Exception as e:
        print("WARNING: Cannot set IPV6_V6ONLY:", e)
        print("Dual-stack may not work")

    # Bind to all interfaces (:: for IPv6, also accepts IPv4)
    # Debug: show what getaddrinfo returns
    try:
        gai_result = socket.getaddrinfo('::', PORT, socket.AF_INET6, socket.SOCK_STREAM)
        print("getaddrinfo('::') =", gai_result)
    except Exception as e:
        print("getaddrinfo('::') failed:", e)

    bind_addr = get_ipv6_addr('::', PORT)
    print("Using bind_addr:", bind_addr, "type:", type(bind_addr))
    try:
        server.bind(bind_addr)
        server.listen(2)
        server.setblocking(False)
        print("Server bound to [::]:{}".format(PORT))
    except Exception as e:
        print("ERROR: Cannot bind server:", e)
        server.close()
        return

    results = {'ipv4': False, 'ipv6': False}

    # Test 1: IPv4 client connection
    print()
    print("-" * 30)
    print("Test 1: IPv4 client (127.0.0.1)")
    print("-" * 30)

    client4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client4.connect(get_ipv4_addr('127.0.0.1', PORT))
        print("IPv4 client connected!")

        time.sleep(0.1)
        conn4, addr4 = server.accept()
        print("Server accepted from:", addr4)

        # Check if it's IPv4-mapped address
        addr_str = str(addr4)
        if '::ffff:' in addr_str or '127.0.0.1' in addr_str:
            print("  -> IPv4-mapped IPv6 address (expected)")

        # Send/receive test
        client4.send(b"Hello from IPv4!")
        time.sleep(0.1)
        data = conn4.recv(1024)
        print("Server received:", data)

        conn4.send(b"Response to IPv4")
        time.sleep(0.1)
        response = client4.recv(1024)
        print("Client received:", response)

        conn4.close()
        client4.close()
        results['ipv4'] = True
        print("IPv4 test: PASSED")

    except Exception as e:
        print("IPv4 test FAILED:", e)
        try:
            client4.close()
        except:
            pass

    # Test 2: IPv6 client connection
    print()
    print("-" * 30)
    print("Test 2: IPv6 client (::1)")
    print("-" * 30)

    client6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        client6.connect(get_ipv6_addr('::1', PORT))
        print("IPv6 client connected!")

        time.sleep(0.1)
        conn6, addr6 = server.accept()
        print("Server accepted from:", addr6)

        # Send/receive test
        client6.send(b"Hello from IPv6!")
        time.sleep(0.1)
        data = conn6.recv(1024)
        print("Server received:", data)

        conn6.send(b"Response to IPv6")
        time.sleep(0.1)
        response = client6.recv(1024)
        print("Client received:", response)

        conn6.close()
        client6.close()
        results['ipv6'] = True
        print("IPv6 test: PASSED")

    except Exception as e:
        print("IPv6 test FAILED:", e)
        try:
            client6.close()
        except:
            pass

    server.close()

    # Summary
    print()
    print("=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)
    print("IPv4 on dual-stack socket:", "PASS" if results['ipv4'] else "FAIL")
    print("IPv6 on dual-stack socket:", "PASS" if results['ipv6'] else "FAIL")

    if results['ipv4'] and results['ipv6']:
        print()
        print("SUCCESS! Dual-stack socket works!")
        print("Single IPv6 socket can accept both IPv4 and IPv6.")
    elif results['ipv6'] and not results['ipv4']:
        print()
        print("PARTIAL: Only IPv6 works.")
        print("IPV6_V6ONLY may be forced on, or system doesn't support dual-stack.")
        print("You'll need two separate sockets for IPv4 and IPv6.")
    else:
        print()
        print("FAILED: Neither protocol works properly.")


def run_test():
    """Run all tests."""
    print()
    print("=" * 50)
    print("DUAL-STACK SOCKET TEST")
    print("(IPv4 + IPv6 on single socket)")
    print("=" * 50)
    print()

    if not test_constants():
        return

    # Test if basic IPv6 bind works
    if not test_ipv6_bind():
        print()
        print("IPv6 bind not working on this system.")
        print("IPv6 may be disabled in kernel or Python has a bug.")
        return

    if not test_v6only_option():
        print()
        print("Cannot configure dual-stack. Testing separate sockets...")
        return

    run_dual_stack_test()


if __name__ == "__main__":
    run_test()
