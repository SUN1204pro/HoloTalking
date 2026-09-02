"""Test receiver that simulates the holofan device for latency measurement.

Run this in its own process/venv (env 2) while server_api.py runs normally (env 1).
Point the backend at this receiver with:

    curl -X POST http://127.0.0.1:8000/api/push_video/start \\
      -F "target_ip=127.0.0.1" -F "port=9998" -F "interval_seconds=1.0"

Then trigger a generation (e.g. POST /generate) and watch this process's output:
each incoming push is timestamped and labeled by size, so you can see exactly
when the freeze-frame clip arrives vs. when the real generated clip replaces it,
and how long each transfer itself took.
"""
import socket
import struct
import sys
import time

HOST = "0.0.0.0"
PORT = 9998
CHUNK_SIZE = 64144

_last_size = None


def format_ts(t):
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"


def handle_connection(conn, addr):
    global _last_size
    while True:
        header = b""
        while len(header) < 8:
            chunk = conn.recv(8 - len(header))
            if not chunk:
                return
            header += chunk

        file_size = struct.unpack("!Q", header)[0]
        t_receive_start = time.time()

        bytes_received = 0
        while bytes_received < file_size:
            chunk = conn.recv(min(CHUNK_SIZE, file_size - bytes_received))
            if not chunk:
                break
            bytes_received += len(chunk)

        t_receive_end = time.time()
        elapsed = t_receive_end - t_receive_start

        kind = "SAME as last" if file_size == _last_size else "NEW clip"
        _last_size = file_size

        print(
            f"[{format_ts(t_receive_end)}] Received {bytes_received} bytes "
            f"({round(bytes_received/1024/1024, 2)} MB) in {round(elapsed, 3)}s "
            f"({round((bytes_received/1024/1024)/max(elapsed, 0.001), 2)} MB/s) -- {kind}",
            flush=True,
        )


def main(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, port))
    server_socket.listen(5)
    print(f"[holofan test receiver] Listening on {HOST}:{port} ...", flush=True)

    while True:
        conn, addr = server_socket.accept()
        print(f"[{format_ts(time.time())}] Connection from {addr[0]}:{addr[1]}", flush=True)
        try:
            handle_connection(conn, addr)
        except Exception as e:
            print(f"[holofan test receiver] Connection error: {e}", flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    main(port)
