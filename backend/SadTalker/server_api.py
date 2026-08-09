import os
import sys
import shutil
import asyncio
import glob
import time
import socket
import struct
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
import io
from PIL import Image
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)
except Exception:
    pass

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


try:
    from vieneu import Vieneu
    VIENEU_AVAILABLE = True
except ImportError:
    VIENEU_AVAILABLE = False

app = FastAPI(title="OpenTalking + SadTalker + ViEneu API")

# Ensure static and result directories exist
os.makedirs("temp_files", exist_ok=True)
os.makedirs("examples/source_image", exist_ok=True)
os.makedirs("result", exist_ok=True)
os.makedirs("../../result", exist_ok=True)

app.mount("/static", StaticFiles(directory="temp_files"), name="static")
app.mount("/examples", StaticFiles(directory="examples"), name="examples")
app.mount("/result", StaticFiles(directory="result"), name="result")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        
    return {
        "status": "success",
        "processed_image_url": f"http://127.0.0.1:8000/static/preprocess_{timestamp}/{os.path.basename(output_path)}",
        "processed_image_path": output_path
    }


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
    preprocess: str = Form("crop"),
    enhancer: str = Form("gfpgan"),
    still: bool = Form(True),
    expression_scale: float = Form(1.0),
    pose_style: int = Form(0),
    lipsync_engine: str = Form("sadtalker"),
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
                final_speak_text = generate_gemini_response(
                    audio_bytes=raw_bytes,
                    mime_type=audio.content_type or "audio/wav",
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

            if final_speak_text and final_speak_text.strip() and VIENEU_AVAILABLE:
                try:
                    tts = Vieneu()
                    voice = tts.get_preset_voice(voice_name or "Thái Sơn")
                    audio_data = tts.infer(text=final_speak_text, voice=voice)
                    tts.save(audio_data, audio_path)
                except Exception as e:
                    print("ViEneu TTS failed, falling back to original recorded audio:", e)
                    with open(audio_path, "wb") as buffer:
                        buffer.write(raw_bytes)
            else:
                with open(audio_path, "wb") as buffer:
                    buffer.write(raw_bytes)
        else:
            audio.file.seek(0)
            with open(audio_path, "wb") as buffer:
                shutil.copyfileobj(audio.file, buffer)

    if inputType == "text":
        if VIENEU_AVAILABLE:
            try:
                tts = Vieneu()
                voice = tts.get_preset_voice(voice_name or "Thái Sơn")
                audio_data = tts.infer(text=final_speak_text, voice=voice)
                tts.save(audio_data, audio_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"ViEneu TTS failed: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="ViEneu TTS library is not installed or available.")

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

    # 3. Construct SadTalker inference command using active Python executable
    python_exe = sys.executable
    cmd_parts = [
        f'"{python_exe}"', "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{output_path}"',
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

    start_time = time.time()
    try:
        process = await asyncio.create_subprocess_shell(ans)
        await process.communicate()
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail="SadTalker video generation script failed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    elapsed_seconds = round(time.time() - start_time, 2)

    list_of_videos = glob.glob(f'{run_dir}/**/*.mp4', recursive=True)
    if not list_of_videos:
        raise HTTPException(status_code=500, detail="No video generated by SadTalker!")

    newest_video_path = max(list_of_videos, key=os.path.getctime)
    final_video_name = "final_output.mp4"
    final_video_path = os.path.join(run_dir, final_video_name)
    shutil.move(newest_video_path, final_video_path)

    # 4. Optional Wav2Lip refinement over SadTalker head motion
    if lipsync_engine == "wav2lip":
        process_wav2lip(final_video_path, audio_path, final_video_path)

    # 5. Save copy to result folder
    result_copy_path = os.path.join("result", f"result_{timestamp}.mp4")
    shutil.copy(final_video_path, result_copy_path)
    shutil.copy(final_video_path, "../../result/latest_result.mp4")

    return {
        "status": "success",
        "video_url": f"http://127.0.0.1:8000/static/test_run_{timestamp}/{final_video_name}",
        "result_url": f"http://127.0.0.1:8000/result/result_{timestamp}.mp4",
        "spoken_text": final_speak_text,
        "generation_time_seconds": elapsed_seconds,
        "lipsync_engine": lipsync_engine
    }


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
    preprocess: str = Form("crop"),
    enhancer: str = Form("gfpgan"),
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

    # 3. ViEneu TTS Audio Generation
    audio_path = os.path.join(run_dir, "agent_voice.wav")
    if VIENEU_AVAILABLE:
        try:
            tts = Vieneu()
            voice = tts.get_preset_voice(voice_name or "Thái Sơn")
            audio_data = tts.infer(text=agent_text, voice=voice)
            tts.save(audio_data, audio_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ViEneu TTS synthesis failed: {str(e)}")
    else:
        raise HTTPException(status_code=500, detail="ViEneu TTS library is not available.")

    # 4. SadTalker Video Synthesis
    cmd_parts = [
        "python", "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{output_path}"',
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

    # 2. Fallback: Broadcast to socket_video_server connected active clients
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.append(backend_dir)
        import socket_video_server
        socket_video_server.broadcast_video_update(target_video)
        return {
            "status": "success",
            "message": f"Broadcasted video ({round(file_size/(1024*1024), 2)} MB) to active socket clients.",
            "file_size": file_size
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to send video over socket: {str(err)}")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_api:app", host="0.0.0.0", port=8000, reload=True)