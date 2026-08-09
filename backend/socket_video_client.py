import socket
import os
import time
import struct
import sys

SERVER_IP = "192.168.1.98"
PORT = 9999
CHUNK_SIZE = 64144
OUTPUT_FILE = "received_holofan_video.mp4"

def listen_for_automatic_video_pushes(server_ip=SERVER_IP):
    print(f"📡 Connecting to Socket Video Streamer at {server_ip}:{PORT}...")
    
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_ip, PORT))
            print(f"✅ Connected to Server! Listening for real-time automatic video pushes...")
            
            while True:
                # Read 8-byte header (file size)
                header = client_socket.recv(8)
                if not header or len(header) < 8:
                    print("⚠️ Connection closed by server.")
                    break
                    
                file_size = struct.unpack("!Q", header)[0]
                if file_size == 0:
                    continue
                    
                print(f"\n📦 AUTO-RECEIVING NEW VIDEO: {file_size} bytes ({round(file_size/(1024*1024), 2)} MB)...")
                
                bytes_received = 0
                start_time = time.time()
                
                with open(OUTPUT_FILE, "wb") as f:
                    while bytes_received < file_size:
                        chunks_needed = min(CHUNK_SIZE, file_size - bytes_received)
                        chunk = client_socket.recv(chunks_needed)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        
                elapsed = time.time() - start_time
                print(f"🎉 New MP4 video received & saved to '{OUTPUT_FILE}' ({round(elapsed, 2)}s)")
                print(f"📊 Transfer speed: {round((bytes_received/1024/1024)/max(elapsed, 0.001), 2)} MB/s")
                print("---------------------------------------------------------------------")
                
        except Exception as e:
            print(f"❌ Socket error: {e}. Reconnecting in 3 seconds...")
            time.sleep(3)

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else SERVER_IP
    listen_for_automatic_video_pushes(ip)
