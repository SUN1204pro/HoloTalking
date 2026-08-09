import socket
import os
import time
import struct
import zlib

# RDT Configuration over UDP
TARGET_HOST = "127.0.0.1"  # Replace with 2nd computer IP or "192.168.1.98" for local Wi-Fi
UDP_PORT = 9998
PAYLOAD_SIZE = 4096  # 4KB chunk per RDT packet
TIMEOUT = 0.5        # 500ms timeout for ACK

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_VIDEO = os.path.join(BASE_DIR, "..", "result", "latest_result.mp4")

def calculate_checksum(data: bytes) -> int:
    """Calculates 16-bit CRC checksum for error detection."""
    return zlib.crc32(data) & 0xFFFF

def create_rdt_packet(seq_num: int, packet_type: int, payload: bytes) -> bytes:
    """
    RDT Packet Format:
    - seq_num (4 bytes unsigned int)
    - packet_type (1 byte: 0=START, 1=DATA, 2=END)
    - checksum (2 bytes unsigned short)
    - payload (bytes)
    """
    checksum = calculate_checksum(payload)
    header = struct.pack("!IBH", seq_num, packet_type, checksum)
    return header + payload

def send_rdt_video(receiver_host=TARGET_HOST, file_path=TARGET_VIDEO):
    if not os.path.exists(file_path):
        print(f"❌ RDT Error: Video file {file_path} does not exist.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    
    file_size = os.path.getsize(file_path)
    print(f"🚀 RDT Sender: Starting Reliable Data Transfer over UDP to {receiver_host}:{UDP_PORT}")
    print(f"📦 File: {os.path.basename(file_path)} ({file_size} bytes, {round(file_size/(1024*1024), 2)} MB)")
    print("----------------------------------------------------------------------")

    # 1. Send START packet (File size metadata)
    seq_num = 0
    start_payload = str(file_size).encode("utf-8")
    start_packet = create_rdt_packet(seq_num, 0, start_payload)

    while True:
        try:
            sock.sendto(start_packet, (receiver_host, UDP_PORT))
            ack_data, _ = sock.recvfrom(1024)
            ack_seq, ack_type = struct.unpack("!IB", ack_data[:5])
            if ack_seq == seq_num and ack_type == 0:
                print("✅ RDT Handshake ACK received. Starting data packet stream...")
                break
        except socket.timeout:
            print("⚠️ ACK Timeout on START packet, retransmitting...")

    # 2. Send DATA packets in chunks
    bytes_sent = 0
    start_time = time.time()
    retransmissions = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(PAYLOAD_SIZE)
            if not chunk:
                break
            
            seq_num += 1
            data_packet = create_rdt_packet(seq_num, 1, chunk)
            
            # Stop-and-Wait RDT retransmission loop
            while True:
                try:
                    sock.sendto(data_packet, (receiver_host, UDP_PORT))
                    ack_data, _ = sock.recvfrom(1024)
                    ack_seq, _ = struct.unpack("!IB", ack_data[:5])
                    if ack_seq == seq_num:
                        bytes_sent += len(chunk)
                        break
                except socket.timeout:
                    retransmissions += 1
                    print(f"⚠️ RDT Timeout on Packet #{seq_num}, retransmitting...")

    # 3. Send END packet
    seq_num += 1
    end_packet = create_rdt_packet(seq_num, 2, b"END")
    while True:
        try:
            sock.sendto(end_packet, (receiver_host, UDP_PORT))
            ack_data, _ = sock.recvfrom(1024)
            ack_seq, _ = struct.unpack("!IB", ack_data[:5])
            if ack_seq == seq_num:
                break
        except socket.timeout:
            print("⚠️ ACK Timeout on END packet, retransmitting...")

    elapsed = time.time() - start_time
    print(f"\n🎉 RDT Transfer Complete!")
    print(f"  ➜ Total Bytes Transferred: {bytes_sent} bytes")
    print(f"  ➜ Total Time: {round(elapsed, 2)}s")
    print(f"  ➜ RDT Speed: {round((bytes_sent/1024/1024)/max(elapsed, 0.001), 2)} MB/s")
    print(f"  ➜ Retransmissions (Packet Loss Recovered): {retransmissions}")

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else TARGET_HOST
    send_rdt_video(target)
