#!/usr/bin/env python3
"""
Simple test for pipelining order preservation
"""
import unittest
import socket
import time
import threading
import uhttp


class TestPipeliningSimple(unittest.TestCase):
    """Simple pipelining test"""

    def test_server_blocks_second_request_until_first_responds(self):
        """Test that server doesn't return second pipelined request before first is answered"""

        server = uhttp.HttpServer(port=9976)
        events = []

        def run_server():
            try:
                events.append('server_started')
                # First wait should return first request
                client1 = None
                for _ in range(20):  # Try for 2 seconds
                    client1 = server.wait(timeout=0.1)
                    if client1:
                        break
                events.append(f'wait1_returned:{client1}')
                if client1:
                    events.append(f'got_request:{client1.path}')

                    # Second wait should NOT return second request yet (still in buffer, but waiting)
                    # Because we haven't responded to first request yet
                    time.sleep(0.1)  # Give it time to fail if it would
                    client2 = server.wait(timeout=0.01)  # Very short timeout
                    if client2:
                        events.append(f'ERROR:got_second_before_responding:{client2.path}')
                    else:
                        events.append('correctly_blocked_second')

                    # Now respond to first
                    client1.respond({'msg': 'first'})
                    events.append('responded_to_first')

                    # Now third wait should return second request
                    client3 = server.wait(timeout=1.0)
                    if client3:
                        events.append(f'got_request:{client3.path}')
                        client3.respond({'msg': 'second'})
                        events.append('responded_to_second')

            except Exception as e:
                import traceback
                events.append(f'ERROR:{e}')
                events.append(f'TRACEBACK:{traceback.format_exc()}')

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)  # Give server more time to start
        events.append('client_starting')

        # Send pipelined requests
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(('localhost', 9976))
            events.append('client_connected')
            sock.settimeout(3.0)

            # Send both requests in one packet
            pipelined = (
                b"GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n"
                b"GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n"
            )
            sock.sendall(pipelined)

            # Read both responses
            all_data = b""
            start_time = time.time()
            while time.time() - start_time < 2.0:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    all_data += chunk
                    # Stop when we have both responses
                    if all_data.count(b'"msg":') >= 2:
                        break
                except socket.timeout:
                    break
                time.sleep(0.01)

        finally:
            sock.close()

        server_thread.join(timeout=2.0)
        server.close()

        # Verify event order
        self.assertIn('got_request:/first', events)
        self.assertIn('correctly_blocked_second', events)
        self.assertIn('responded_to_first', events)
        self.assertIn('got_request:/second', events)

        # Make sure server didn't get second request before responding to first
        self.assertNotIn('ERROR:got_second_before_responding:/second', events)

        # Verify order
        first_idx = events.index('got_request:/first')
        block_idx = events.index('correctly_blocked_second')
        respond_idx = events.index('responded_to_first')
        second_idx = events.index('got_request:/second')

        self.assertLess(first_idx, block_idx)
        self.assertLess(block_idx, respond_idx)
        self.assertLess(respond_idx, second_idx)


if __name__ == '__main__':
    unittest.main()
