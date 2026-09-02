"""Measures the "freeze frame first, then real video" latency of the holofan
automatic broadcast (socket_video_server.py, port 9999):

  1. request -> freeze frame arrival   (should be fast: freeze is (re)built
     early in /generate, before SadTalker even starts running)
  2. freeze arrival -> real video arrival   (dominated by SadTalker + TTS +
     optional Wav2Lip refinement)
  3. total end-to-end, both by the /generate HTTP response and by the real
     video's actual arrival over the socket

Connects a plain TCP client to the server's existing broadcast port (the same
mechanism backend/socket_video_client.py uses) and records every push's
arrival time + a hash of its bytes, then calls /generate and correlates.

Usage:
    python benchmark_latency.py --label MPS --server http://127.0.0.1:8000 \
        --socket-port 9999 --out results_mps.json
"""
import argparse
import hashlib
import json
import socket
import struct
import threading
import time

import requests

CHUNK_SIZE = 64144


def listen_for_pushes(host: str, port: int, received: list, stop_event: threading.Event, connected_event: threading.Event):
    """Background thread: connects once, then records (arrival_time, size, sha1) for
    every file pushed by the server's broadcast loop until stop_event is set."""
    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((host, port))
            s.settimeout(None)
            connected_event.set()
            while not stop_event.is_set():
                header = s.recv(8)
                if not header or len(header) < 8:
                    break
                file_size = struct.unpack("!Q", header)[0]
                if file_size == 0:
                    continue
                digest = hashlib.sha1()
                remaining = file_size
                while remaining > 0:
                    chunk = s.recv(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    digest.update(chunk)
                    remaining -= len(chunk)
                received.append({
                    "t": time.time(),
                    "size": file_size,
                    "sha1": digest.hexdigest(),
                })
            s.close()
        except Exception:
            if stop_event.is_set():
                return
            time.sleep(0.3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="e.g. MPS or CPU, just for the report")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--socket-port", type=int, default=9999)
    parser.add_argument("--preset-avatar", default="art_0.png")
    parser.add_argument("--text", default="Xin chào, đây là bài kiểm tra đo độ trễ hệ thống.")
    parser.add_argument("--voice-name", default="Thái Sơn")
    parser.add_argument("--settle-seconds", type=float, default=3.0,
                         help="How long to keep listening after the HTTP response returns, "
                              "to catch the background auto-push of the real video.")
    parser.add_argument("--out", default=None, help="Optional path to write JSON results to")
    args = parser.parse_args()

    received = []
    stop_event = threading.Event()
    connected_event = threading.Event()
    listener = threading.Thread(
        target=listen_for_pushes,
        args=("127.0.0.1", args.socket_port, received, stop_event, connected_event),
        daemon=True,
    )
    listener.start()
    if not connected_event.wait(timeout=10):
        print(f"[{args.label}] Could not connect to socket broadcast on port {args.socket_port} within 10s.")
        stop_event.set()
        return

    print(f"[{args.label}] Connected to broadcast socket. Firing /generate ...")
    t0 = time.time()
    resp = requests.post(
        f"{args.server}/generate",
        data={
            "inputType": "text",
            "text": args.text,
            "preset_avatar": args.preset_avatar,
            "voice_name": args.voice_name,
            "lipsync_engine": "wav2lip",
        },
        timeout=300,
    )
    t_response = time.time()
    resp.raise_for_status()
    body = resp.json()
    print(f"[{args.label}] /generate responded in {round(t_response - t0, 3)}s "
          f"(server-reported generation_time_seconds={body.get('generation_time_seconds')})")

    # Give the background auto-push thread (fired after the response is already
    # built) a little time to actually land the real video over the socket.
    time.sleep(args.settle_seconds)
    stop_event.set()
    listener.join(timeout=2)

    pushes_after_t0 = [p for p in received if p["t"] >= t0]
    print(f"[{args.label}] Captured {len(pushes_after_t0)} push(es) after request start.")

    result = {
        "label": args.label,
        "t0": t0,
        "t_http_response": t_response,
        "total_http_seconds": round(t_response - t0, 3),
        "server_reported_generation_seconds": body.get("generation_time_seconds"),
        "pushes": [{"seconds_after_t0": round(p["t"] - t0, 3), "size": p["size"], "sha1": p["sha1"]} for p in pushes_after_t0],
    }

    if len(pushes_after_t0) >= 1:
        freeze = pushes_after_t0[0]
        result["request_to_freeze_seconds"] = round(freeze["t"] - t0, 3)
    if len(pushes_after_t0) >= 2:
        # Real video = first push whose content differs from the freeze push's.
        freeze_hash = pushes_after_t0[0]["sha1"]
        real = next((p for p in pushes_after_t0[1:] if p["sha1"] != freeze_hash), None)
        if real:
            result["freeze_to_real_seconds"] = round(real["t"] - pushes_after_t0[0]["t"], 3)
            result["total_to_real_video_seconds"] = round(real["t"] - t0, 3)

    print(f"[{args.label}] Result: {json.dumps(result, indent=2)}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[{args.label}] Wrote {args.out}")


if __name__ == "__main__":
    main()
