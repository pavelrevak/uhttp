#!/usr/bin/env python3
"""
Slow client simulator for testing server behavior with slow clients.

Modes:
- download: Read data very slowly (tests server send buffer / EAGAIN)
- upload: Send data very slowly (tests server receive buffer / EAGAIN)
"""
import socket
import time
import argparse


def slow_download(host, port, path, chunk_size=100, delay=0.1, use_ssl=False):
    """
    Download a file very slowly.

    Args:
        host: Server hostname/IP
        port: Server port
        path: URL path to request
        chunk_size: Bytes to read at a time (smaller = slower)
        delay: Seconds to wait between reads
        use_ssl: Use HTTPS
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set small receive buffer to increase backpressure
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)

    try:
        print(f"Connecting to {host}:{port}...")
        sock.connect((host, port))

        if use_ssl:
            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=host)

        # Send HTTP request
        request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        sock.send(request.encode())
        print(f"Sent request: GET {path}")

        # Read response slowly
        total_bytes = 0
        start_time = time.time()
        headers_done = False
        response_headers = b''

        print(f"Reading with chunk_size={chunk_size}, delay={delay}s...")
        print("-" * 50)

        while True:
            try:
                chunk = sock.recv(chunk_size)
                if not chunk:
                    break

                total_bytes += len(chunk)
                elapsed = time.time() - start_time
                rate = total_bytes / elapsed if elapsed > 0 else 0

                # Parse headers
                if not headers_done:
                    response_headers += chunk
                    if b'\r\n\r\n' in response_headers:
                        headers_done = True
                        header_part = response_headers.split(b'\r\n\r\n')[0]
                        print("Headers received:")
                        print(header_part.decode())
                        print("-" * 50)

                # Progress
                print(f"\rReceived: {total_bytes:,} bytes | "
                      f"Rate: {rate:,.0f} B/s | "
                      f"Time: {elapsed:.1f}s", end='', flush=True)

                # Slow down!
                time.sleep(delay)

            except socket.timeout:
                print("\nTimeout waiting for data")
                break

        elapsed = time.time() - start_time
        rate = total_bytes / elapsed if elapsed > 0 else 0

        print(f"\n{'=' * 50}")
        print(f"Download complete!")
        print(f"Total: {total_bytes:,} bytes")
        print(f"Time: {elapsed:.1f} seconds")
        print(f"Average rate: {rate:,.0f} bytes/second")

    finally:
        sock.close()


def slow_upload(host, port, path, data_size=10240, chunk_size=100, delay=0.1,
                use_ssl=False, content_type='application/octet-stream'):
    """
    Upload data very slowly.

    Args:
        host: Server hostname/IP
        port: Server port
        path: URL path to POST to
        data_size: Total bytes to send
        chunk_size: Bytes to send at a time (smaller = slower)
        delay: Seconds to wait between sends
        use_ssl: Use HTTPS
        content_type: Content-Type header
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set small send buffer to increase backpressure on our side too
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

    try:
        print(f"Connecting to {host}:{port}...")
        sock.connect((host, port))

        if use_ssl:
            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=host)

        # Prepare data to send
        data = b'X' * data_size

        # Send HTTP headers first (fast)
        headers = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {data_size}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        sock.send(headers.encode())
        print(f"Sent headers: POST {path} ({data_size:,} bytes)")

        # Send body slowly
        total_sent = 0
        start_time = time.time()

        print(f"Sending with chunk_size={chunk_size}, delay={delay}s...")
        print("-" * 50)

        while total_sent < data_size:
            # Calculate how much to send
            remaining = data_size - total_sent
            to_send = min(chunk_size, remaining)

            # Send chunk
            chunk = data[total_sent:total_sent + to_send]
            sent = sock.send(chunk)
            total_sent += sent

            elapsed = time.time() - start_time
            rate = total_sent / elapsed if elapsed > 0 else 0
            progress = (total_sent / data_size) * 100

            print(f"\rSent: {total_sent:,}/{data_size:,} bytes ({progress:.1f}%) | "
                  f"Rate: {rate:,.0f} B/s | "
                  f"Time: {elapsed:.1f}s", end='', flush=True)

            # Slow down!
            time.sleep(delay)

        print(f"\n{'=' * 50}")
        print("Upload complete! Waiting for response...")

        # Read response
        sock.settimeout(10)
        response = b''
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass

        elapsed = time.time() - start_time
        rate = total_sent / elapsed if elapsed > 0 else 0

        print(f"\nResponse ({len(response)} bytes):")
        print("-" * 50)
        try:
            print(response.decode()[:500])
            if len(response) > 500:
                print(f"... ({len(response) - 500} more bytes)")
        except UnicodeDecodeError:
            print(f"(binary data, {len(response)} bytes)")

        print(f"\n{'=' * 50}")
        print(f"Total sent: {total_sent:,} bytes")
        print(f"Time: {elapsed:.1f} seconds")
        print(f"Average rate: {rate:,.0f} bytes/second")

    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description='Slow client simulator for testing server with slow clients')

    parser.add_argument('host', help='Server hostname or IP')
    parser.add_argument('-p', '--port', type=int, default=80,
                        help='Server port (default: 80)')
    parser.add_argument('--path', default='/',
                        help='URL path (default: /)')
    parser.add_argument('-c', '--chunk', type=int, default=100,
                        help='Bytes per chunk (default: 100)')
    parser.add_argument('-d', '--delay', type=float, default=0.1,
                        help='Delay between chunks in seconds (default: 0.1)')
    parser.add_argument('-s', '--ssl', action='store_true',
                        help='Use HTTPS')

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--download', action='store_true', default=True,
                            help='Download mode - slow read (default)')
    mode_group.add_argument('--upload', action='store_true',
                            help='Upload mode - slow send')

    # Upload specific
    parser.add_argument('--size', type=int, default=10240,
                        help='Data size to upload in bytes (default: 10240)')
    parser.add_argument('--content-type', default='application/octet-stream',
                        help='Content-Type for upload (default: application/octet-stream)')

    args = parser.parse_args()

    port = args.port
    if port == 80 and args.ssl:
        port = 443

    if args.upload:
        slow_upload(
            host=args.host,
            port=port,
            path=args.path,
            data_size=args.size,
            chunk_size=args.chunk,
            delay=args.delay,
            use_ssl=args.ssl,
            content_type=args.content_type
        )
    else:
        slow_download(
            host=args.host,
            port=port,
            path=args.path,
            chunk_size=args.chunk,
            delay=args.delay,
            use_ssl=args.ssl
        )


if __name__ == '__main__':
    main()
