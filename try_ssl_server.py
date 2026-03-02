import socket
import ssl
import select
import time
import errno

PORT = 19995


def server():
    print(f"[{time.time_ns() // 10000000}] creating ssl context")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain('cert.pem', 'key.pem')

    print(f"[{time.time_ns() // 10000000}] creating socket")
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', PORT))
    sock.listen(1)

    print(f"[{time.time_ns() // 10000000}] waiting for connection")
    cl, addr = sock.accept()
    print(f"[{time.time_ns() // 10000000}] TCP accepted {addr}")

    cl.setblocking(False)
    ssl_sock = ctx.wrap_socket(cl, server_side=True, do_handshake_on_connect=False)
    # ssl_sock = ctx.wrap_socket(cl, server_side=True)
    print(f"[{time.time_ns() // 10000000}] wrap_socket done (non-blocking, no handshake)")

    # 1. Select na read - čo vráti?
    while True:
        print(f"\n[{time.time_ns() // 10000000}] waiting for read on socket")
        r, w, _ = select.select([ssl_sock], [], [], 10)
        print(f"[{time.time_ns() // 10000000}] select returned: readable={bool(r)}")

        if r:
            # 2. Skúsim recv - čo sa stane?
            print(f"\n[{time.time_ns() // 10000000}] trying recv(1024)...")
            try:
                data = ssl_sock.recv(1024)
                print(f"[{time.time_ns() // 10000000}] recv returned: {data!r}")
                if data is None:
                    print("probably errno.ENOENT")
                    continue
                if not data:
                    print("closing: data==None")
                    break
            except OSError as err:
                errcode = errno.errorcode[err.errno]
                print(f"[{time.time_ns() // 10000000}] recv raised OSError: {err} {err.errno} {errcode}")
                if err.errno == errno.ENOENT:
                    continue
                print("closing")
                break

    ssl_sock.close()
    sock.close()


server()
