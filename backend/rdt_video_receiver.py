import socket
import os
import time
import struct
import zlib

LISTEN_HOST = "0.0.0.0"
UDP_PORT = 9998
OUTPUT_FILE = "received_rdt_holofan_video.mp4"

def calculate_checksum(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFF

def send_ack(sock, addr, seq_num: int, packet_type: int):
    """Sends 5-byte ACK packet back to sender."""
    ack_packet = struct.pack("!IB", seq_num, packet_type)
    sock.sendto(ack_packet, addr)

def start_rdt_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_HOST, UDP_PORT))
    
    print(f"📡 RDT Receiver Listening over UDP on {LISTEN_HOST}:{UDP_PORT}...")
    print("---------------------------------------------------------------")

    while True:
        expected_seq = 0
        file_size = 0
        bytes_received = 0
        start_time = 0
        file_obj = None

        print("\n⏳ Ready for incoming RDT video transmission...")

        while True:
            packet, addr = sock.recvfrom(65535)
            if len(packet) < 7:
                continue

            # Unpack RDT header
            seq_num, packet_type, checksum = struct.unpack("!IBH", packet[:7])
            payload = packet[7:]

            # Verify checksum
            if calculate_checksum(payload) != checksum:
                print(f"❌ Corrupted RDT Packet #{seq_num} (Checksum mismatch)! Dropping...")
                continue

            # 1. START Packet
            if packet_type == 0:
                file_size = int(payload.decode("utf-8"))
                expected_seq = 0
                send_ack(sock, addr, seq_num, 0)
                file_obj = open(OUTPUT_FILE, "wb")
                bytes_received = 0
                start_time = time.time()
                print(f"📦 RDT Stream Initiated by {addr[0]}:{addr[1]}. Expected size: {file_size} bytes ({round(file_size/(1024*1024), 2)} MB)")
                expected_seq = 1

            # 2. DATA Packet
            elif packet_type == 1:
                if seq_num == expected_seq:
                    if file_obj:
                        file_obj.write(payload)
                        bytes_received += len(payload)
                    send_ack(sock, addr, seq_num, 1)
                    expected_seq += 1
                elif seq_num < expected_seq:
                    # Duplicate packet received, re-ack
                    send_ack(sock, addr, seq_num, 1)

            # 3. END Packet
            elif packet_type == 2:
                send_ack(sock, addr, seq_num, 2)
                if file_obj:
                    file_obj.close()
                elapsed = time.time() - start_time
                print(f"🎉 RDT Transfer Complete! Saved to '{OUTPUT_FILE}' ({round(elapsed, 2)}s)")
                print(f"📊 Transfer speed: {round((bytes_received/1024/1024)/max(elapsed, 0.001), 2)} MB/s")
                break

if __name__ == "__main__":
    start_rdt_receiver()
