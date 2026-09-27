import socket
import ssl

host = "www.googleapis.com"
ctx = ssl.create_default_context()

try:
    with socket.create_connection((host, 443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            print(f"TLS OK, версия: {ssock.version()}")
except Exception as e:
    print(f"TLS FAIL: {type(e).__name__}: {e}")
