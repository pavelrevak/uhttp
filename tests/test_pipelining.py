#!/usr/bin/env python3
"""
Test HTTP pipelining - sending multiple requests in one TCP packet
"""
import unittest
import socket
import time
import threading
import uhttp


class TestPipelining(unittest.TestCase):
    """Test suite for HTTP pipelining"""

    server = None
    server_thread = None
    request_count = 0
    PORT = 9982

    @classmethod
    def setUpClass(cls):
        """Start server once for all tests"""
        cls.server = uhttp.HttpServer(port=cls.PORT)

        def run_server():
            try:
                while cls.server:
                    client = cls.server.wait(timeout=0.5)
                    if client:
                        cls.request_count += 1
                        client.respond({
                            'request_number': cls.request_count,
                            'path': client.path,
                            'method': client.method
                        })
            except Exception:
                pass

        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """Stop server after all tests"""
        if cls.server:
            cls.server.close()
            cls.server = None

    def setUp(self):
        """Reset request count before each test"""
        TestPipelining.request_count = 0

    def test_pipelining_get_requests(self):
        """Test sending multiple GET requests in one packet"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', self.PORT))

        # Send two pipelined requests in one packet
        pipelined_requests = (
            b"GET /test1 HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
            b"GET /test2 HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
        )

        sock.sendall(pipelined_requests)

        # Read all data (both responses may come together)
        sock.settimeout(1.0)
        all_data = b""
        try:
            while len(all_data) < 8192:  # Read up to 8KB
                chunk = sock.recv(4096)
                if not chunk:
                    break
                all_data += chunk
        except socket.timeout:
            pass

        sock.close()

        # Split responses by finding HTTP status lines
        parts = all_data.split(b"HTTP/1.1 200 OK")

        # Verify both responses received
        self.assertGreaterEqual(len(parts), 3)  # Empty + response1 + response2
        response1 = b"HTTP/1.1 200 OK" + parts[1]
        response2 = b"HTTP/1.1 200 OK" + parts[2]

        self.assertIn(b"200 OK", response1)
        self.assertIn(b"test1", response1)
        self.assertIn(b"200 OK", response2)
        self.assertIn(b"test2", response2)
        self.assertEqual(self.request_count, 2)

    def test_pipelining_post_and_get(self):
        """Test pipelining POST with body and GET request"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', self.PORT))

        # POST with exact Content-Length + pipelined GET
        pipelined_requests = (
            b"POST /api HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 14\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
            b'{"id": 123456}'  # Exactly 14 bytes
            b"GET /status HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        sock.sendall(pipelined_requests)

        # Read all data (both responses may come together)
        sock.settimeout(1.0)
        all_data = b""
        try:
            while len(all_data) < 8192:  # Read up to 8KB
                chunk = sock.recv(4096)
                if not chunk:
                    break
                all_data += chunk
        except socket.timeout:
            pass

        sock.close()

        # Split responses by finding HTTP status lines
        parts = all_data.split(b"HTTP/1.1 200 OK")

        # Verify both responses received
        self.assertGreaterEqual(len(parts), 3)  # Empty + response1 + response2
        response1 = b"HTTP/1.1 200 OK" + parts[1]
        response2 = b"HTTP/1.1 200 OK" + parts[2]

        self.assertIn(b"200 OK", response1)
        self.assertIn(b"/api", response1)
        self.assertIn(b"200 OK", response2)
        self.assertIn(b"/status", response2)
        self.assertEqual(self.request_count, 2)


if __name__ == '__main__':
    unittest.main()
