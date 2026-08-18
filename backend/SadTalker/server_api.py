import os
import sys
import shutil
import asyncio
import glob
import time
import socket
import struct
import threading
import subprocess
import hashlib
import uuid
import re
import json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import requests
import io
from src.utils.wav2lip_processor import process_wav2lip
from PIL import Image
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)
except Exception:
    pass

def apply_speed_to_audio(audio_path: str, speed: float):
    """Speeds up/slows down an existing WAV file in-place using ffmpeg's atempo filter
    (preserves pitch). No-op when speed is ~1.0."""
    speed = max(0.5, min(2.0, speed or 1.0))
    if abs(speed - 1.0) < 1e-3:
        return
    tmp_path = audio_path + ".speed_tmp.wav"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", audio_path, "-filter:a", f"atempo={speed}", tmp_path
    ]
    try:
        subprocess.run(cmd, check=True)
        os.replace(tmp_path, audio_path)
    except Exception as e:
        print(f"[TTS speed] Failed to apply speed {speed}x, keeping original tempo:", e)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def transcode_to_wav_bytes(raw_bytes: bytes) -> bytes:
    """Re-encodes arbitrary audio bytes (e.g. a browser MediaRecorder blob, which is
    actually WebM/Opus even when the frontend names the file '*.wav') into real WAV
    PCM bytes via ffmpeg, which sniffs the real container from content rather than
    trusting any filename/extension. Gemini's audio understanding rejects/mis-parses
    audio whose declared mime type doesn't match its actual encoding, so anything
    forwarded to it as "audio/wav" must actually be WAV."""
    run_id = uuid.uuid4().hex
    tmp_in = os.path.join("temp_files", f"{run_id}_in.bin")
    tmp_out = os.path.join("temp_files", f"{run_id}_out.wav")
    os.makedirs("temp_files", exist_ok=True)
    try:
        with open(tmp_in, "wb") as f:
            f.write(raw_bytes)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", tmp_in, "-ar", "16000", "-ac", "1", tmp_out],
            check=True
        )
        with open(tmp_out, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_in):
            os.remove(tmp_in)
        if os.path.exists(tmp_out):
            os.remove(tmp_out)


def generate_silent_wav(output_path: str, duration_sec: float = 1.5, sample_rate: int = 16000):
    import wave
    import struct
    num_samples = int(duration_sec * sample_rate)
    with wave.open(output_path, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack('<' + ('h' * num_samples), *([0] * num_samples)))

def process_and_save_bg_removed(raw_bytes: bytes, output_path: str):
    """Processes remove.bg raw response bytes and saves as standard RGB PNG for SadTalker."""
    img = Image.open(io.BytesIO(raw_bytes))
    if img.mode == "RGBA":
        rgb_img = Image.new("RGB", img.size, (0, 0, 0))
        rgb_img.paste(img, mask=img.split()[3])
        rgb_img.save(output_path, "PNG")
    else:
        img.convert("RGB").save(output_path, "PNG")

def remove_image_background(input_path: str, output_path: str) -> str:
    """Removes background using local rembg library or remove.bg API fallback."""
    print(f"[BG Removal] Processing image: {input_path}")
    try:
        import rembg
        input_img = Image.open(input_path)
        nobg_img = rembg.remove(input_img)
        if nobg_img.mode == "RGBA":
            rgb_img = Image.new("RGB", nobg_img.size, (0, 0, 0))
            rgb_img.paste(nobg_img, mask=nobg_img.split()[3])
            rgb_img.save(output_path, "PNG")
        else:
            nobg_img.convert("RGB").save(output_path, "PNG")
        print(f"[rembg] Local background removal succeeded -> {output_path}")
        return output_path
    except Exception as e:
        print(f"[rembg] Local background removal failed ({e}), trying remove.bg API...")

    remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "").strip()
    if remove_bg_key:
        try:
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': open(input_path, 'rb')},
                data={'size': 'auto'},
                headers={'X-Api-Key': remove_bg_key},
                timeout=20
            )
            if response.status_code == 200:
                process_and_save_bg_removed(response.content, output_path)
                print(f"[remove.bg] Background removal successful -> {output_path}")
                return output_path
            else:
                print(f"[remove.bg] HTTP {response.status_code}: {response.text[:200]}")
        except Exception as err:
            print(f"[remove.bg] Error: {err}")

    img = Image.open(input_path)
    img.convert("RGB").save(output_path, "PNG")
    return output_path


def crop_to_1x1_square(input_path: str, output_path: str, target_size: int = 512) -> str:
    """Crops image to a 1:1 square centered around detected face or image center."""
    try:
        import cv2
        img = Image.open(input_path)
        img_cv = cv2.imread(input_path)
        if img_cv is not None:
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            if len(faces) > 0:
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                center_x, center_y = x + w // 2, y + h // 2
                crop_size = int(max(w, h) * 2.2)
                img_h, img_w = img_cv.shape[:2]
                crop_size = min(crop_size, img_h, img_w)
                
                left = max(0, center_x - crop_size // 2)
                top = max(0, center_y - crop_size // 2)
                right = min(img_w, left + crop_size)
                bottom = min(img_h, top + crop_size)
                
                box_side = min(right - left, bottom - top)
                right = left + box_side
                bottom = top + box_side
                
                img_cropped = img.crop((left, top, right, bottom))
                img_resized = img_cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)
                img_resized.save(output_path)
                print(f"[1x1 Crop] Face-centered 1:1 crop successful -> {output_path}")
                return output_path
    except Exception as e:
        print(f"[1x1 Crop] Face detection failed ({e}), falling back to center 1:1 crop")

    try:
        img = Image.open(input_path)
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img_cropped = img.crop((left, top, left + min_dim, top + min_dim))
        img_resized = img_cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)
        img_resized.save(output_path)
        print(f"[1x1 Crop] Center 1:1 crop saved -> {output_path}")
        return output_path
    except Exception as err:
        print(f"[1x1 Crop] Fallback error: {err}")
        return input_path


# SadTalker's preprocessing (face crop + 3DMM coefficient extraction) is itself
# cache-aware -- it skips recomputation if the same source_image path already has a
# ".mat"/landmarks file sitting next to it. But server_api.py used to hand it a
# freshly timestamped copy of the avatar on every request, so that cache never hit.
# Keying the copy by content hash means repeat generations against the same avatar
# reuse the same path and actually get the free 3DMM/landmark cache hit.
AVATAR_CACHE_DIR = "avatar_cache"
os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)


def get_cached_avatar_path(image_path: str) -> str:
    with open(image_path, "rb") as f:
        digest = hashlib.md5(f.read()).hexdigest()
    cached_path = os.path.join(AVATAR_CACHE_DIR, f"{digest}.png")
    if not os.path.exists(cached_path):
        shutil.copy(image_path, cached_path)
    return cached_path


def clear_results_and_temp_files():
    """Wipes every prior generation's output before starting a new avatar, so
    temp_files/ and result/ don't accumulate old runs indefinitely. Only clears
    contents -- the directories themselves (and avatar_cache/custom_voices, which
    are intentionally persistent caches) are left in place."""
    for dir_path in ("temp_files", "result"):
        if not os.path.isdir(dir_path):
            continue
        for entry in os.listdir(dir_path):
            entry_path = os.path.join(dir_path, entry)
            try:
                if os.path.isdir(entry_path) and not os.path.islink(entry_path):
                    shutil.rmtree(entry_path)
                else:
                    os.remove(entry_path)
            except Exception as e:
                print(f"[cleanup] Failed to remove {entry_path}: {e}")
    os.makedirs("temp_files", exist_ok=True)
    os.makedirs("result", exist_ok=True)


try:
    from vieneu import Vieneu
    VIENEU_AVAILABLE = True
except ImportError:
    VIENEU_AVAILABLE = False

try:
    from voxcpm import VoxCPM
    VOXCPM_AVAILABLE = True
except ImportError:
    VOXCPM_AVAILABLE = False

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

# --- Custom voice (ElevenLabs voice -> VoxCPM cloning reference) -----------
# VoxCPM is a heavy local model: load it once, lazily, and reuse across requests.
CUSTOM_VOICE_CACHE_DIR = "custom_voices"
os.makedirs(CUSTOM_VOICE_CACHE_DIR, exist_ok=True)
_voxcpm_instance = None


def get_voxcpm():
    global _voxcpm_instance
    if _voxcpm_instance is None:
        print("[VoxCPM] Loading model for the first time (this can take a while)...")
        _voxcpm_instance = VoxCPM.from_pretrained("openbmb/VoxCPM2")
    return _voxcpm_instance


def get_elevenlabs_client(api_key: str = None):
    key = (api_key and api_key.strip()) or os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not ELEVENLABS_AVAILABLE or not key:
        return None
    return ElevenLabs(api_key=key)


REFERENCE_TEXT_VI = "Xin chào, đây là giọng nói mẫu tiếng Việt để làm giọng tham chiếu cho việc nhân bản giọng nói."


def get_or_create_reference_audio(voice_id: str, api_key: str = None) -> str:
    """Builds the VoxCPM voice-cloning reference for an ElevenLabs voice_id and
    caches it as a local WAV file. The reference audio's *content* (Vietnamese prosody,
    pronunciation) comes from VieNeu -- a native Vietnamese TTS -- which is then re-voiced
    into the target ElevenLabs voice's timbre via ElevenLabs' speech-to-speech ("Voice
    Changer") conversion. This sounds far more natural than ElevenLabs' own multilingual
    TTS speaking Vietnamese directly. Cached on disk so each voice is only built once --
    delete the cached file under custom_voices/ to force a refresh."""
    ref_path = os.path.join(CUSTOM_VOICE_CACHE_DIR, f"{voice_id}.wav")
    if os.path.exists(ref_path):
        return ref_path

    if not VIENEU_AVAILABLE:
        raise RuntimeError("ViEneu TTS library is not installed or available.")
    client = get_elevenlabs_client(api_key)
    if client is None:
        raise RuntimeError("ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env.")

    vieneu_wav = ref_path + ".vieneu_src.wav"
    tts = Vieneu()
    voice = tts.get_preset_voice("Thái Sơn")
    audio_data = tts.infer(text=REFERENCE_TEXT_VI, voice=voice)
    tts.save(audio_data, vieneu_wav)

    tmp_mp3 = ref_path + ".src.mp3"
    try:
        with open(vieneu_wav, "rb") as f:
            result = client.speech_to_speech.convert(
                voice_id=voice_id,
                audio=(os.path.basename(vieneu_wav), f.read(), "audio/wav"),
                model_id="eleven_multilingual_sts_v2",
                output_format="mp3_44100_128",
            )
        with open(tmp_mp3, "wb") as f:
            for chunk in result:
                f.write(chunk)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_mp3, ref_path],
            check=True
        )
    finally:
        if os.path.exists(vieneu_wav):
            os.remove(vieneu_wav)
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)
    return ref_path


def synthesize_tts(
    text: str,
    audio_path: str,
    speed: float = 1.0,
    tts_engine: str = "vietneu",
    voice_name: str = None,
    elevenlabs_voice_id: str = None,
    elevenlabs_api_key: str = None,
    voice_style: str = None,
):
    """Synthesizes `text` to `audio_path`, dispatching to VieNeu presets or VoxCPM,
    the latter cloning a custom ElevenLabs voice reference."""
    if tts_engine == "voxcpm":
        if not VOXCPM_AVAILABLE:
            raise RuntimeError("voxcpm package is not installed.")
        if not elevenlabs_voice_id:
            raise RuntimeError("Select an ElevenLabs voice to use as the VoxCPM reference.")
        ref_path = get_or_create_reference_audio(elevenlabs_voice_id, elevenlabs_api_key)
        model = get_voxcpm()
        # VoxCPM follows a natural-language style/delivery instruction prepended in
        # parentheses ahead of the actual line, e.g. "(deep, solemn, regal tone) <text>".
        prompted_text = f"({voice_style.strip()}) {text}" if voice_style and voice_style.strip() else text
        wav = model.generate(text=prompted_text, reference_wav_path=ref_path, normalize=True)
        import soundfile as sf
        sf.write(audio_path, wav, model.tts_model.sample_rate)
    else:
        if not VIENEU_AVAILABLE:
            raise RuntimeError("ViEneu TTS library is not installed or available.")
        tts = Vieneu()
        voice = tts.get_preset_voice(voice_name or "Thái Sơn")
        audio_data = tts.infer(text=text, voice=voice)
        tts.save(audio_data, audio_path)
    apply_speed_to_audio(audio_path, speed)


app = FastAPI(title="OpenTalking + SadTalker + ViEneu API")

# Ensure static and result directories exist
os.makedirs("temp_files", exist_ok=True)
os.makedirs("examples/source_image", exist_ok=True)
os.makedirs("result", exist_ok=True)
os.makedirs("../../result", exist_ok=True)

app.mount("/static", StaticFiles(directory="temp_files"), name="static")
app.mount("/examples", StaticFiles(directory="examples"), name="examples")
app.mount("/result", StaticFiles(directory="result"), name="result")
app.mount("/custom_voices", StaticFiles(directory=CUSTOM_VOICE_CACHE_DIR), name="custom_voices")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Holofan TCP streamer: start the listener once, in-process, so a new client
# connecting to it sees the same active_clients list that /generate pushes to.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.append(_backend_dir)
import socket_video_server
socket_video_server.start_server_background()

# --- Continuous holofan push-stream state -----------------------------------
# While a stream is "active", a background thread keeps pushing content to the
# target device forever (until stopped): the freeze-frame clip while SadTalker
# is busy generating (or before any talking clip exists), otherwise the latest
# generated talking clip.
FREEZE_VIDEO_PATH = os.path.join("..", "..", "result", "freeze_frame.mp4")
LATEST_RESULT_PATH = "../../result/latest_result.mp4"
_last_avatar_image_path = None
_is_generating = False
_stream_lock = threading.Lock()
_stream_state = {"active": False, "target_ip": None, "port": None}


def _build_freeze_video(image_path: str, duration: float = 3.0):
    """Encode the current avatar image into a short MP4 so the holofan link can
    push a frozen frame while SadTalker is generating a new talking clip."""
    if not image_path or not os.path.exists(image_path):
        return
    try:
        os.makedirs(os.path.dirname(FREEZE_VIDEO_PATH), exist_ok=True)
        cmd = (
            f'ffmpeg -y -hide_banner -loglevel error -loop 1 -i "{image_path}" '
            f'-t {duration} -vf "format=yuv420p" -c:v libx264 -movflags +faststart "{FREEZE_VIDEO_PATH}"'
        )
        subprocess.run(cmd, shell=True, check=True)
    except Exception as e:
        print(f"[freeze video] Failed to build freeze clip: {e}")


def _direct_send_file(file_path: str, ip: str, port: int, timeout: float = 6.0) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    file_size = os.path.getsize(file_path)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.sendall(struct.pack("!Q", file_size))
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(64144)
                if not chunk:
                    break
                s.sendall(chunk)
        return True
    finally:
        s.close()


def _push_stream_loop(interval_seconds: float):
    """Runs while _stream_state['active'] is True: forever pushes either the
    freeze frame (while SadTalker is generating, or no talking clip exists yet)
    or the latest talking clip to the configured target, until stopped."""
    while True:
        with _stream_lock:
            if not _stream_state["active"]:
                return
            ip = _stream_state["target_ip"]
            port = _stream_state["port"]
        video_to_send = FREEZE_VIDEO_PATH if (_is_generating or not os.path.exists(LATEST_RESULT_PATH)) else LATEST_RESULT_PATH
        try:
            _direct_send_file(video_to_send, ip, port)
        except Exception as e:
            print(f"[stream loop] Push to {ip}:{port} failed: {e}")
        time.sleep(interval_seconds)


@app.get("/")
def root():
    return {
        "message": "OpenTalking + SadTalker + ViEneu API Server is running!",
        "docs": "http://127.0.0.1:8000/docs",
        "health": "http://127.0.0.1:8000/api/health"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "engine": "OpenTalking + SadTalker + ViEneu",
        "vieneu_available": VIENEU_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/voices")
def get_voices():
    """Returns available Vietneu preset voices with metadata."""
    return [
        {"id": "Thái Sơn", "name": "Thái Sơn", "gender": "Nam", "region": "Miền Bắc", "desc": "Giọng nam Bắc trầm ấm, dõng dạc"},
        {"id": "Gia Bảo", "name": "Gia Bảo", "gender": "Nam", "region": "Miền Nam", "desc": "Giọng nam Nam Bộ truyền cảm, dõng dạc"},
        {"id": "Đức Trí", "name": "Đức Trí", "gender": "Nam", "region": "Miền Bắc", "desc": "Giọng nam Bắc uy nghi, truyền cảm"},
        {"id": "Ngọc Lan", "name": "Ngọc Lan", "gender": "Nữ", "region": "Miền Bắc", "desc": "Giọng nữ Bắc dịu dàng, trong trẻo"},
        {"id": "Mỹ Duyên", "name": "Mỹ Duyên", "gender": "Nữ", "region": "Miền Nam", "desc": "Giọng nữ Nam Bộ ngọt ngào"},
        {"id": "Trúc Ly", "name": "Trúc Ly", "gender": "Nữ", "region": "Miền Trung", "desc": "Giọng nữ Miền Trung điềm tĩnh"},
        {"id": "Xuân Vĩnh", "name": "Xuân Vĩnh", "gender": "Nam", "region": "Miền Bắc", "desc": "Giọng nam Bắc rõ ràng, hùng hồn"},
        {"id": "Trọng Hữu", "name": "Trọng Hữu", "gender": "Nam", "region": "Miền Nam", "desc": "Giọng nam Nam Bộ nồng ấm"},
        {"id": "Bình An", "name": "Bình An", "gender": "Nam", "region": "Miền Trung", "desc": "Giọng nam Miền Trung mộc mạc"},
        {"id": "Ngọc Linh", "name": "Ngọc Linh", "gender": "Nữ", "region": "Miền Bắc", "desc": "Giọng nữ Bắc truyền cảm"},
    ]


@app.get("/api/elevenlabs/voices")
def get_elevenlabs_voices(api_key: str = None):
    """Returns the caller's ElevenLabs voice library, for use as a VoxCPM cloning reference."""
    if not ELEVENLABS_AVAILABLE:
        raise HTTPException(status_code=500, detail="elevenlabs package is not installed.")
    client = get_elevenlabs_client(api_key)
    if client is None:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env.")
    try:
        result = client.voices.get_all()
        return [
            {
                "id": v.voice_id,
                "name": v.name,
                "category": getattr(v, "category", None),
                "preview_url": getattr(v, "preview_url", None),
            }
            for v in result.voices
        ]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch ElevenLabs voices: {str(e)}")


@app.post("/api/elevenlabs/design")
def design_elevenlabs_voice(voice_description: str = Form(...), api_key: str = Form(None)):
    """Generates a few voice previews from a text description (ElevenLabs Voice Design).
    Returns base64 mp3 previews the user can audition before saving one as a real voice."""
    if not ELEVENLABS_AVAILABLE:
        raise HTTPException(status_code=500, detail="elevenlabs package is not installed.")
    client = get_elevenlabs_client(api_key)
    if client is None:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env.")
    try:
        result = client.text_to_voice.design(voice_description=voice_description, auto_generate_text=True)
        return {
            "text": result.text,
            "previews": [
                {
                    "generated_voice_id": p.generated_voice_id,
                    "audio_base_64": p.audio_base_64,
                    "media_type": p.media_type,
                    "duration_secs": p.duration_secs,
                }
                for p in result.previews
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to design voice: {str(e)}")


@app.post("/api/elevenlabs/save-designed-voice")
def save_designed_voice(
    voice_name: str = Form(...),
    voice_description: str = Form(...),
    generated_voice_id: str = Form(...),
    api_key: str = Form(None),
):
    """Saves a chosen Voice Design preview as a real voice in the caller's ElevenLabs library,
    so it shows up in /api/elevenlabs/voices and can be used as a VoxCPM cloning reference."""
    if not ELEVENLABS_AVAILABLE:
        raise HTTPException(status_code=500, detail="elevenlabs package is not installed.")
    client = get_elevenlabs_client(api_key)
    if client is None:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env.")
    try:
        voice = client.text_to_voice.create(
            voice_name=voice_name,
            voice_description=voice_description,
            generated_voice_id=generated_voice_id,
        )
        return {
            "id": voice.voice_id,
            "name": voice.name,
            "preview_url": getattr(voice, "preview_url", None),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to save designed voice: {str(e)}")


@app.post("/api/elevenlabs/voice-changer")
def voice_changer(
    voice_id: str = Form(...),
    api_key: str = Form(None),
    audio: UploadFile = File(...),
):
    """Speech-to-Speech (ElevenLabs 'Voice Changer'): converts an uploaded recording into the
    target voice_id, keeping the same delivery/timing. Free-tier compatible, unlike Voice Design.
    The result is cached as that voice's VoxCPM cloning reference, replacing the short preview clip
    with a longer, better-conditioned sample."""
    if not ELEVENLABS_AVAILABLE:
        raise HTTPException(status_code=500, detail="elevenlabs package is not installed.")
    client = get_elevenlabs_client(api_key)
    if client is None:
        raise HTTPException(status_code=400, detail="ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env.")

    tmp_mp3 = os.path.join(CUSTOM_VOICE_CACHE_DIR, f"{voice_id}.sts.mp3")
    ref_path = os.path.join(CUSTOM_VOICE_CACHE_DIR, f"{voice_id}.wav")
    try:
        audio_bytes = audio.file.read()
        result = client.speech_to_speech.convert(
            voice_id=voice_id,
            audio=(audio.filename, audio_bytes, audio.content_type),
            model_id="eleven_multilingual_sts_v2",
            output_format="mp3_44100_128",
        )
        with open(tmp_mp3, "wb") as f:
            for chunk in result:
                f.write(chunk)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_mp3, ref_path],
            check=True
        )
        return {"voice_id": voice_id, "reference_audio_url": f"http://127.0.0.1:8000/custom_voices/{voice_id}.wav"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Voice changer conversion failed: {str(e)}")
    finally:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)


@app.get("/api/avatars")
def get_avatars():
    """Returns preset digital human avatars available on server."""
    avatar_files = glob.glob("examples/source_image/*.png") + glob.glob("examples/source_image/*.jpg") + glob.glob("examples/source_image/*.jpeg")
    avatars = []
    for filepath in sorted(avatar_files):
        filename = os.path.basename(filepath)
        avatars.append({
            "id": filename,
            "filename": filename,
            "url": f"http://127.0.0.1:8000/examples/source_image/{filename}"
        })
    return avatars


@app.post("/preprocess_avatar")
async def preprocess_avatar(
    image: UploadFile = File(None),
    preset_avatar: str = Form(None)
):
    clear_results_and_temp_files()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("temp_files", f"preprocess_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    image_path = os.path.join(run_dir, "input_avatar.png")
    if image and image.filename:
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    elif preset_avatar:
        preset_file_path = os.path.join("examples/source_image", preset_avatar)
        if os.path.exists(preset_file_path):
            shutil.copy(preset_file_path, image_path)
        else:
            raise HTTPException(status_code=400, detail=f"Preset avatar '{preset_avatar}' not found.")
    else:
        raise HTTPException(status_code=400, detail="Please upload an avatar image or pick a preset avatar.")
        
    output_filename = "avatar_bg_removed.png"
    output_path = os.path.join(run_dir, output_filename)
    
    output_path = remove_image_background(image_path, output_path)

    global _last_avatar_image_path
    _last_avatar_image_path = output_path
    _build_freeze_video(output_path)

    return {
        "status": "success",
        "processed_image_url": f"http://127.0.0.1:8000/static/preprocess_{timestamp}/{os.path.basename(output_path)}",
        "processed_image_path": output_path
    }


def split_into_sentences(text: str) -> list:
    """Splits text on sentence-ending punctuation (. ! ? and the ellipsis), keeping the
    punctuation attached. Used to pipeline generation: render+stream sentence 1 while
    later sentences are still being generated, instead of waiting on the whole script."""
    if not text or not text.strip():
        return []
    parts = re.split(r'(?<=[.!?…])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


async def render_talking_clip(
    cached_avatar_path: str, audio_path: str, run_dir: str, clip_name: str,
    preprocess: str = "crop", enhancer: str = "none", still: bool = True,
    expression_scale: float = 1.0, pose_style: int = 0, lipsync_engine: str = "wav2lip",
) -> str:
    """Runs SadTalker (+ optional Wav2Lip refinement) on an already-synthesized audio
    clip and returns the path to the final video. Shared by /generate and
    /generate_stream so a multi-sentence script can render clip-by-clip."""
    global _is_generating
    python_exe = sys.executable
    cmd_parts = [
        f'"{python_exe}"', "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{cached_avatar_path}"',
        "--result_dir", f'"{run_dir}"',
        "--preprocess", preprocess if preprocess in ["crop", "extcrop", "full", "extfull", "resize"] else "crop",
        "--expression_scale", str(expression_scale),
        "--pose_style", str(pose_style)
    ]
    if still:
        cmd_parts.append("--still")
    if enhancer and enhancer != "none":
        cmd_parts.extend(["--enhancer", enhancer])

    ans = " ".join(cmd_parts)
    _is_generating = True
    try:
        process = await asyncio.create_subprocess_shell(ans)
        await process.communicate()
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail="SadTalker video generation script failed.")
    finally:
        _is_generating = False

    list_of_videos = glob.glob(f'{run_dir}/**/*.mp4', recursive=True)
    if not list_of_videos:
        raise HTTPException(status_code=500, detail="No video generated by SadTalker!")

    newest_video_path = max(list_of_videos, key=os.path.getctime)
    final_video_path = os.path.join(run_dir, clip_name)
    shutil.move(newest_video_path, final_video_path)

    if lipsync_engine == "wav2lip":
        process_wav2lip(final_video_path, audio_path, final_video_path)

    return final_video_path


@app.post("/generate")
async def generate_video(
    inputType: str = Form("text"),
    image: UploadFile = File(None),
    preset_avatar: str = Form(None),
    audio: UploadFile = File(None),
    text: str = Form(None),
    use_gemini: bool = Form(False),
    persona: str = Form(None),
    api_key: str = Form(None),
    voice_name: str = Form("Thái Sơn"),
    speed: float = Form(1.0),
    tts_engine: str = Form("vietneu"),
    elevenlabs_voice_id: str = Form(None),
    elevenlabs_api_key: str = Form(None),
    voice_style: str = Form(None),
    preprocess: str = Form("crop"),
    enhancer: str = Form("none"),
    still: bool = Form(True),
    expression_scale: float = Form(1.0),
    pose_style: int = Form(0),
    lipsync_engine: str = Form("wav2lip"),
    skip_bg_remove: bool = Form(False)
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("temp_files", f"test_run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # 1. Resolve Audio Path & Gemini text FIRST before image processing
    audio_path = os.path.join(run_dir, "input_audio.wav")
    final_speak_text = text or "Xin chào."

    # ONLY live / audio mode can use Gemini
    if inputType != "audio":
        use_gemini = False

    if inputType == "text":
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text input is empty.")
        final_speak_text = text.strip()
    else:
        if not audio:
            raise HTTPException(status_code=400, detail="Audio file missing.")
        
        if use_gemini:
            audio.file.seek(0)
            raw_bytes = audio.file.read()
            try:
                wav_bytes = transcode_to_wav_bytes(raw_bytes)
                final_speak_text = generate_gemini_response(
                    audio_bytes=wav_bytes,
                    mime_type="audio/wav",
                    persona=persona,
                    api_key=api_key
                )
            except Exception as e:
                print("Gemini Audio AI response failed:", e)
                final_speak_text = ""

            # If Gemini text is empty or space ' ', instantly freeze screen on avatar image
            if not final_speak_text or not final_speak_text.strip():
                print("[Gemini] Empty / space text received. Freezing screen instantly on live avatar image.")
                return {
                    "status": "success",
                    "video_url": None,
                    "spoken_text": " ",
                    "generation_time_seconds": 0,
                    "lipsync_engine": lipsync_engine
                }

            if final_speak_text and final_speak_text.strip():
                try:
                    synthesize_tts(
                        text=final_speak_text, audio_path=audio_path, speed=speed,
                        tts_engine=tts_engine, voice_name=voice_name,
                        elevenlabs_voice_id=elevenlabs_voice_id, elevenlabs_api_key=elevenlabs_api_key,
                        voice_style=voice_style
                    )
                except Exception as e:
                    print(f"TTS ({tts_engine}) failed, falling back to original recorded audio:", e)
                    with open(audio_path, "wb") as buffer:
                        buffer.write(wav_bytes)
            else:
                with open(audio_path, "wb") as buffer:
                    buffer.write(wav_bytes)
        else:
            # Browser MediaRecorder blobs are commonly WebM/Opus even though the
            # frontend names the file "*.wav" -- transcode by content, not by name,
            # so SadTalker's audio loader always receives a real WAV file.
            audio.file.seek(0)
            raw_bytes = audio.file.read()
            with open(audio_path, "wb") as buffer:
                buffer.write(transcode_to_wav_bytes(raw_bytes))

    if inputType == "text":
        try:
            synthesize_tts(
                text=final_speak_text, audio_path=audio_path, speed=speed,
                tts_engine=tts_engine, voice_name=voice_name,
                elevenlabs_voice_id=elevenlabs_voice_id, elevenlabs_api_key=elevenlabs_api_key,
                voice_style=voice_style
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS ({tts_engine}) failed: {str(e)}")

    # 2. Resolve avatar image path
    image_path = os.path.join(run_dir, "input_avatar.png")
    if image and image.filename:
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    elif preset_avatar:
        preset_file_path = os.path.join("examples/source_image", preset_avatar)
        if os.path.exists(preset_file_path):
            shutil.copy(preset_file_path, image_path)
        else:
            raise HTTPException(status_code=400, detail=f"Preset avatar '{preset_avatar}' not found.")
    else:
        # Default fallback image if none provided
        default_preset = glob.glob("examples/source_image/*.*")
        if default_preset:
            shutil.copy(default_preset[0], image_path)
        else:
            raise HTTPException(status_code=400, detail="Please upload an avatar image or pick a preset avatar.")

    output_filename = "avatar_bg_removed.png"
    output_path = os.path.join(run_dir, output_filename)

    if skip_bg_remove:
        print(f"[remove.bg] skip_bg_remove is true, using image as is: {image_path}")
        output_path = image_path
    else:
        output_path = remove_image_background(image_path, output_path)

    global _last_avatar_image_path
    _last_avatar_image_path = output_path
    _build_freeze_video(output_path)
    cached_avatar_path = get_cached_avatar_path(output_path)

    # 3. Render the talking clip (SadTalker + optional Wav2Lip refinement)
    start_time = time.time()
    final_video_name = "final_output.mp4"
    try:
        final_video_path = await render_talking_clip(
            cached_avatar_path, audio_path, run_dir, final_video_name,
            preprocess=preprocess, enhancer=enhancer, still=still,
            expression_scale=expression_scale, pose_style=pose_style, lipsync_engine=lipsync_engine
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    elapsed_seconds = round(time.time() - start_time, 2)

    # 4. Save copy to result folder
    result_copy_path = os.path.join("result", f"result_{timestamp}.mp4")
    shutil.copy(final_video_path, result_copy_path)
    shutil.copy(final_video_path, "../../result/latest_result.mp4")

    # Auto-push the freshly generated clip to any connected holofan client(s),
    # without blocking the HTTP response on the broadcast itself.
    threading.Thread(
        target=socket_video_server.broadcast_video_update,
        args=("../../result/latest_result.mp4",),
        daemon=True
    ).start()

    return {
        "status": "success",
        "video_url": f"http://127.0.0.1:8000/static/test_run_{timestamp}/{final_video_name}",
        "result_url": f"http://127.0.0.1:8000/result/result_{timestamp}.mp4",
        "spoken_text": final_speak_text,
        "generation_time_seconds": elapsed_seconds,
        "lipsync_engine": lipsync_engine
    }


@app.post("/generate_stream")
async def generate_video_stream(
    inputType: str = Form("text"),
    image: UploadFile = File(None),
    preset_avatar: str = Form(None),
    audio: UploadFile = File(None),
    text: str = Form(None),
    use_gemini: bool = Form(False),
    persona: str = Form(None),
    api_key: str = Form(None),
    voice_name: str = Form("Thái Sơn"),
    speed: float = Form(1.0),
    tts_engine: str = Form("vietneu"),
    elevenlabs_voice_id: str = Form(None),
    elevenlabs_api_key: str = Form(None),
    voice_style: str = Form(None),
    preprocess: str = Form("crop"),
    enhancer: str = Form("none"),
    still: bool = Form(True),
    expression_scale: float = Form(1.0),
    pose_style: int = Form(0),
    lipsync_engine: str = Form("wav2lip"),
    skip_bg_remove: bool = Form(False)
):
    """Same pipeline as /generate, but splits the text into sentences and streams back
    one clip per sentence (Server-Sent Events) as each finishes rendering, instead of
    waiting for the whole script. The frontend starts playing clip 1 immediately while
    later sentences are still being synthesized/rendered -- cuts perceived wait even
    though total generation time is unchanged."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("temp_files", f"stream_run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    if inputType != "audio":
        use_gemini = False

    # 1. Resolve what text (if any) will be spoken, and the avatar image, up front --
    # both are needed before any per-sentence work can start.
    final_speak_text = None
    raw_audio_bytes = None
    if inputType == "text":
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text input is empty.")
        final_speak_text = text.strip()
    else:
        if not audio:
            raise HTTPException(status_code=400, detail="Audio file missing.")
        audio.file.seek(0)
        raw_bytes = audio.file.read()
        if use_gemini:
            try:
                wav_bytes = transcode_to_wav_bytes(raw_bytes)
                final_speak_text = generate_gemini_response(
                    audio_bytes=wav_bytes, mime_type="audio/wav", persona=persona, api_key=api_key
                )
            except Exception as e:
                print("Gemini Audio AI response failed:", e)
                final_speak_text = ""
        else:
            raw_audio_bytes = transcode_to_wav_bytes(raw_bytes)

    image_path = os.path.join(run_dir, "input_avatar.png")
    if image and image.filename:
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    elif preset_avatar:
        preset_file_path = os.path.join("examples/source_image", preset_avatar)
        if os.path.exists(preset_file_path):
            shutil.copy(preset_file_path, image_path)
        else:
            raise HTTPException(status_code=400, detail=f"Preset avatar '{preset_avatar}' not found.")
    else:
        default_preset = glob.glob("examples/source_image/*.*")
        if default_preset:
            shutil.copy(default_preset[0], image_path)
        else:
            raise HTTPException(status_code=400, detail="Please upload an avatar image or pick a preset avatar.")

    output_path = os.path.join(run_dir, "avatar_bg_removed.png")
    if skip_bg_remove:
        output_path = image_path
    else:
        output_path = remove_image_background(image_path, output_path)

    global _last_avatar_image_path
    _last_avatar_image_path = output_path
    _build_freeze_video(output_path)
    cached_avatar_path = get_cached_avatar_path(output_path)

    async def event_stream():
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        # No text at all (empty/silent Gemini reply, or a plain audio upload with no
        # sentence structure to split) -- render once, exactly like /generate.
        if not final_speak_text or not final_speak_text.strip():
            if raw_audio_bytes is None:
                yield sse({"type": "done", "spoken_text": " ", "video_url": None})
                return
            sentences = None
        else:
            sentences = split_into_sentences(final_speak_text) or [final_speak_text.strip()]

        total = len(sentences) if sentences else 1
        yield sse({"type": "meta", "total": total, "full_text": final_speak_text or ""})

        last_video_path = None
        try:
            for i in range(total):
                clip_audio_path = os.path.join(run_dir, f"audio_{i}.wav")
                if sentences is not None:
                    sentence = sentences[i]
                    synthesize_tts(
                        text=sentence, audio_path=clip_audio_path, speed=speed,
                        tts_engine=tts_engine, voice_name=voice_name,
                        elevenlabs_voice_id=elevenlabs_voice_id, elevenlabs_api_key=elevenlabs_api_key,
                        voice_style=voice_style
                    )
                else:
                    sentence = final_speak_text or ""
                    with open(clip_audio_path, "wb") as f:
                        f.write(raw_audio_bytes)

                clip_start = time.time()
                clip_video_path = await render_talking_clip(
                    cached_avatar_path, clip_audio_path, run_dir, f"clip_{i}.mp4",
                    preprocess=preprocess, enhancer=enhancer, still=still,
                    expression_scale=expression_scale, pose_style=pose_style, lipsync_engine=lipsync_engine
                )
                last_video_path = clip_video_path
                elapsed = round(time.time() - clip_start, 2)

                result_copy_path = os.path.join("result", f"result_{timestamp}_{i}.mp4")
                shutil.copy(clip_video_path, result_copy_path)

                yield sse({
                    "type": "clip",
                    "index": i,
                    "total": total,
                    "sentence": sentence,
                    "video_url": f"http://127.0.0.1:8000/static/stream_run_{timestamp}/{os.path.basename(clip_video_path)}",
                    "result_url": f"http://127.0.0.1:8000/result/result_{timestamp}_{i}.mp4",
                    "generation_time_seconds": elapsed,
                })
        except HTTPException as e:
            yield sse({"type": "error", "detail": e.detail})
            return
        except Exception as e:
            yield sse({"type": "error", "detail": str(e)})
            return

        if last_video_path:
            shutil.copy(last_video_path, "../../result/latest_result.mp4")
            threading.Thread(
                target=socket_video_server.broadcast_video_update,
                args=("../../result/latest_result.mp4",),
                daemon=True
            ).start()

        yield sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def generate_gemini_response(user_message: str = None, audio_bytes: bytes = None, mime_type: str = "audio/wav", persona: str = None, history_json: str = None, api_key: str = None) -> str:
    import json
    import base64
    key = (api_key and api_key.strip()) or os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Missing Gemini API Key, returning fallback text ' '")
        return " "

    system_instruction = (
        "Bạn là một nhân vật AI đại diện ảo (Avatar) thông minh, sinh động, nói tiếng Việt. "
        "Hãy trả lời tự nhiên, thân thiện và cô đọng (tốt nhất từ 2-4 câu) để phù hợp cho nhân vật nói chuyện trong clip video ngắn."
    )
    if persona and persona.strip():
        system_instruction += f"\n\nVai trò / Tính cách nhân vật của bạn: {persona.strip()}"

    parts = []
    if audio_bytes:
        encoded = base64.b64encode(audio_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded
            }
        })
        parts.append({"text": "Hãy lắng nghe câu hỏi/lời nói giọng nói này của người dùng và trả lời bằng văn bản tiếng Việt tự nhiên, cô đọng."})
    elif user_message:
        parts.append({"text": user_message})
    else:
        parts.append({"text": "Xin chào nhân vật AI."})

    contents = []
    if history_json:
        try:
            parsed_history = json.loads(history_json)
            if isinstance(parsed_history, list):
                contents.extend(parsed_history)
        except Exception as e:
            print("Error parsing conversation history:", e)

    contents.append({
        "role": "user",
        "parts": parts
    })

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.6-flash", "gemini-flash-latest"]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.7
            }
        }
        try:
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
            if res.status_code == 200:
                res_data = res.json()
                if "candidates" in res_data and res_data["candidates"]:
                    candidate = res_data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text_list = [p.get("text", "") for p in candidate["content"]["parts"] if isinstance(p, dict) and "text" in p]
                        combined_text = " ".join([t.strip() for t in text_list if t.strip()]).strip()
                        if combined_text:
                            print(f"[Gemini Success via {model}]: {combined_text}")
                            return combined_text
            else:
                print(f"[Gemini {model} HTTP {res.status_code}]: {res.text[:200]}")
        except Exception as e:
            print(f"[Gemini call model {model} failed]:", e)

    # When no text received from Gemini, run text " "
    print("[Gemini] No text returned from any Gemini model. Falling back to text ' '")
    return " "


@app.post("/agent/chat")
async def agent_chat(
    image: UploadFile = File(None),
    preset_avatar: str = Form(None),
    user_message: str = Form(...),
    persona: str = Form(None),
    history: str = Form(None),
    api_key: str = Form(None),
    voice_name: str = Form("Thái Sơn"),
    speed: float = Form(1.0),
    tts_engine: str = Form("vietneu"),
    elevenlabs_voice_id: str = Form(None),
    elevenlabs_api_key: str = Form(None),
    voice_style: str = Form(None),
    preprocess: str = Form("crop"),
    enhancer: str = Form("none"),
    still: bool = Form(True),
    expression_scale: float = Form(1.0),
    pose_style: int = Form(0),
    skip_bg_remove: bool = Form(False)
):
    if not user_message or not user_message.strip():
        raise HTTPException(status_code=400, detail="User message is empty.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("temp_files", f"agent_run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # 1. Resolve avatar image
    image_path = os.path.join(run_dir, "agent_avatar.png")
    if image and image.filename:
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    elif preset_avatar:
        preset_file_path = os.path.join("examples/source_image", preset_avatar)
        if os.path.exists(preset_file_path):
            shutil.copy(preset_file_path, image_path)
        else:
            # Check if relative path or filename
            shutil.copy(preset_avatar if os.path.exists(preset_avatar) else "examples/source_image/art_0.png", image_path)
    else:
        # Default fallback
        default_preset = glob.glob("examples/source_image/*.*")
        if default_preset:
            shutil.copy(default_preset[0], image_path)
        else:
            raise HTTPException(status_code=400, detail="Avatar image missing.")

    output_filename = "agent_avatar_bg.png"
    output_path = os.path.join(run_dir, output_filename)
    
    if skip_bg_remove:
        print(f"[remove.bg] skip_bg_remove is true, using agent avatar as is: {image_path}")
        output_path = image_path
    else:
        remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "").strip()
        if remove_bg_key:
            print(f"[remove.bg] Attempting agent avatar background removal for: {image_path}")
            try:
                response = requests.post(
                    'https://api.remove.bg/v1.0/removebg',
                    files={'image_file': open(image_path, 'rb')},
                    data={'size': 'auto'},
                    headers={'X-Api-Key': remove_bg_key},
                    timeout=20
                )
                if response.status_code == 200:
                    process_and_save_bg_removed(response.content, output_path)
                    print(f"[remove.bg] Agent avatar background removal successful -> {output_path}")
                else:
                    print(f"[remove.bg] Failed with HTTP {response.status_code}: {response.text[:200]}")
                    output_path = image_path
            except Exception as e:
                print(f"[remove.bg] Error during background removal: {e}")
                output_path = image_path
        else:
            print("[remove.bg] REMOVE_BG_API_KEY not configured or empty, skipping background removal.")
            output_path = image_path

    # 2. Gemini Response
    agent_text = generate_gemini_response(
        user_message=user_message,
        persona=persona,
        history_json=history,
        api_key=api_key
    )

    # 3. TTS Audio Generation (ViEneu preset voice or VoxCPM cloning an ElevenLabs voice)
    audio_path = os.path.join(run_dir, "agent_voice.wav")
    try:
        synthesize_tts(
            text=agent_text, audio_path=audio_path, speed=speed,
            tts_engine=tts_engine, voice_name=voice_name,
            elevenlabs_voice_id=elevenlabs_voice_id, elevenlabs_api_key=elevenlabs_api_key,
            voice_style=voice_style
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS ({tts_engine}) synthesis failed: {str(e)}")

    # 4. SadTalker Video Synthesis
    cached_avatar_path = get_cached_avatar_path(output_path)
    cmd_parts = [
        "python", "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{cached_avatar_path}"',
        "--result_dir", f'"{run_dir}"',
        "--preprocess", preprocess if preprocess in ["crop", "extcrop", "full", "extfull", "resize"] else "crop",
        "--expression_scale", str(expression_scale),
        "--pose_style", str(pose_style)
    ]

    if still:
        cmd_parts.append("--still")

    if enhancer and enhancer != "none":
        cmd_parts.extend(["--enhancer", enhancer])

    ans = " ".join(cmd_parts)

    try:
        process = await asyncio.create_subprocess_shell(ans)
        await process.communicate()
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail="SadTalker video generation failed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    list_of_videos = glob.glob(f'{run_dir}/**/*.mp4', recursive=True)
    if not list_of_videos:
        raise HTTPException(status_code=500, detail="No video generated by SadTalker!")

    newest_video_path = max(list_of_videos, key=os.path.getctime)
    final_video_name = "final_agent_output.mp4"
    final_video_path = os.path.join(run_dir, final_video_name)
    shutil.move(newest_video_path, final_video_path)

    return {
        "status": "success",
        "user_message": user_message,
        "agent_response": agent_text,
        "video_url": f"http://127.0.0.1:8000/static/agent_run_{timestamp}/{final_video_name}",
        "audio_url": f"http://127.0.0.1:8000/static/agent_run_{timestamp}/agent_voice.wav"
    }


@app.post("/api/push_video")
async def push_video_to_client(
    target_ip: str = Form("192.168.1.98"),
    port: int = Form(9999)
):
    """
    Sends the latest generated MP4 video directly to the specified target socket IP:port 
    (or broadcasts to socket_video_server connected clients if target_ip is empty).
    """
    target_video = "../../result/latest_result.mp4"
    if not os.path.exists(target_video):
        target_video = os.path.join("result", "latest_result.mp4")
    
    if not os.path.exists(target_video):
        videos = glob.glob("result/*.mp4") + glob.glob("../../result/*.mp4")
        if videos:
            target_video = max(videos, key=os.path.getctime)
        else:
            raise HTTPException(status_code=404, detail="No video file found to send.")

    file_size = os.path.getsize(target_video)
    
    # 1. Send directly via TCP socket to target_ip:port if specified
    if target_ip and target_ip.strip():
        clean_ip = target_ip.strip()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(6.0)
            s.connect((clean_ip, port))
            
            # Send 8-byte header
            header = struct.pack("!Q", file_size)
            s.sendall(header)
            
            bytes_sent = 0
            with open(target_video, "rb") as f:
                while True:
                    chunk = f.read(64144)
                    if not chunk:
                        break
                    s.sendall(chunk)
                    bytes_sent += len(chunk)
            s.close()
            
            return {
                "status": "success",
                "message": f"Successfully sent video ({round(file_size/(1024*1024), 2)} MB) to {clean_ip}:{port}",
                "target_ip": clean_ip,
                "port": port,
                "bytes_sent": bytes_sent
            }
        except Exception as e:
            print(f"Direct socket send to {clean_ip}:{port} failed: {e}. Trying fallback broadcast...")

    # 2. Fallback: Broadcast to the already-running holofan listener's connected clients.
    if not socket_video_server.active_clients:
        raise HTTPException(
            status_code=404,
            detail="No holofan clients connected to the socket streamer (port 9999) and direct send failed/unset."
        )
    try:
        socket_video_server.broadcast_video_update(target_video)
        return {
            "status": "success",
            "message": f"Broadcasted video ({round(file_size/(1024*1024), 2)} MB) to {len(socket_video_server.active_clients)} active socket client(s).",
            "file_size": file_size
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to send video over socket: {str(err)}")


@app.post("/api/push_video/start")
async def start_push_stream(
    target_ip: str = Form(...),
    port: int = Form(9999),
    interval_seconds: float = Form(2.0)
):
    """
    Starts a continuous push loop to target_ip:port: keeps sending the freeze-frame
    clip while SadTalker is generating (or before any talking clip exists), and the
    latest talking clip otherwise, forever, until /api/push_video/stop is called.
    """
    clean_ip = target_ip.strip()
    if not clean_ip:
        raise HTTPException(status_code=400, detail="target_ip is required.")

    with _stream_lock:
        if _stream_state["active"]:
            return {
                "status": "already_running",
                "message": f"Already streaming to {_stream_state['target_ip']}:{_stream_state['port']}."
            }
        _stream_state["active"] = True
        _stream_state["target_ip"] = clean_ip
        _stream_state["port"] = port
        threading.Thread(target=_push_stream_loop, args=(interval_seconds,), daemon=True).start()

    return {"status": "success", "message": f"Started continuous push to {clean_ip}:{port}"}


@app.post("/api/push_video/stop")
async def stop_push_stream():
    with _stream_lock:
        if not _stream_state["active"]:
            return {"status": "not_running", "message": "No active stream to stop."}
        ip, port = _stream_state["target_ip"], _stream_state["port"]
        _stream_state["active"] = False

    return {"status": "success", "message": f"Stopped continuous push to {ip}:{port}"}


@app.get("/api/push_video/status")
async def push_stream_status():
    with _stream_lock:
        return {
            "active": _stream_state["active"],
            "target_ip": _stream_state["target_ip"],
            "port": _stream_state["port"],
            "is_generating": _is_generating
        }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_api:app", host="0.0.0.0", port=8000, reload=True)