import socket
import ssl
import select
import time

PORT = 19995


def client():
    time.sleep(0.1)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    sock = socket.socket()
    sock.connect(('localhost', PORT))
    print("[client] TCP connected")

    # Klient robí SSL handshake a hneď posiela request
    ssl_sock = ctx.wrap_socket(sock, server_hostname='localhost')
    print("[client] SSL handshake done, sending HTTP request...")

    request = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
    sent = ssl_sock.send(request)
    print(f"[client] request sent {sent}")

    ssl_sock.close()

client()
