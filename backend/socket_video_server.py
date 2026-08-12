import socket
import os
import time
import struct
import threading

HOST = "0.0.0.0"
PORT = 9999
CHUNK_SIZE = 64144

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_VIDEO = os.path.join(BASE_DIR, "..", "result", "latest_result.mp4")

# Connected client sockets list
active_clients = []
clients_lock = threading.Lock()

def broadcast_video_update(file_path):
    """Broadcasting newly generated MP4 video packets to all connected sockets automatically."""
    if not os.path.exists(file_path):
        return

    file_size = os.path.getsize(file_path)
    print(f"\n⚡ AUTO PUSH: New video detected ({file_size} bytes)! Broadcasting to {len(active_clients)} connected client(s)...")

    # Header format: 8-byte unsigned long long (file size)
    header = struct.pack("!Q", file_size)

    with clients_lock:
        disconnected_clients = []
        for client_socket, addr in active_clients:
            try:
                client_socket.sendall(header)
                bytes_sent = 0
                start_time = time.time()
                
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        client_socket.sendall(chunk)
                        bytes_sent += len(chunk)
                        
                elapsed = time.time() - start_time
                print(f"  ➜ Pushed {bytes_sent} bytes to {addr[0]}:{addr[1]} in {round(elapsed, 2)}s ({round((bytes_sent/1024/1024)/max(elapsed, 0.001), 2)} MB/s)")
            except Exception as e:
                print(f"  ❌ Failed sending to {addr[0]}:{addr[1]} ({e})")
                disconnected_clients.append((client_socket, addr))

        # Cleanup disconnected sockets
        for dead in disconnected_clients:
            if dead in active_clients:
                active_clients.remove(dead)

def watch_video_file():
    """Background file watcher to auto-trigger video transfer when system generates new MP4."""
    last_mtime = 0
    print("👀 Watching 'result/latest_result.mp4' for real-time video updates...")
    while True:
        try:
            if os.path.exists(TARGET_VIDEO):
                mtime = os.path.getmtime(TARGET_VIDEO)
                if mtime != last_mtime and os.path.getsize(TARGET_VIDEO) > 0:
                    last_mtime = mtime
                    # Small pause to ensure file write completed
                    time.sleep(0.3)
                    broadcast_video_update(TARGET_VIDEO)
        except Exception as e:
            print(f"Watcher error: {e}")
        time.sleep(0.5)

_server_started = False
_server_lock = threading.Lock()

def start_server_background():
    """Start the TCP listener in a background thread once. Safe to call repeatedly
    (e.g. from the FastAPI startup hook) - only spins up the listener on the first call."""
    global _server_started
    with _server_lock:
        if _server_started:
            return
        _server_started = True
        threading.Thread(target=accept_incoming_connections, daemon=True).start()

def accept_incoming_connections():
    """Listens for incoming client socket connections."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print(f"🚀 Automatic Socket Video Streamer listening on {HOST}:{PORT}")
    print("---------------------------------------------------------------")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"🟢 New Client Connected: {addr[0]}:{addr[1]}")
        with clients_lock:
            active_clients.append((client_socket, addr))
        
        # If a video already exists, send latest video to newly connected client immediately
        if os.path.exists(TARGET_VIDEO) and os.path.getsize(TARGET_VIDEO) > 0:
            threading.Thread(target=broadcast_video_update, args=(TARGET_VIDEO,), daemon=True).start()

if __name__ == "__main__":
    # Start background file watcher thread
    watcher_thread = threading.Thread(target=watch_video_file, daemon=True)
    watcher_thread.start()

    # Start socket listener
    accept_incoming_connections()
