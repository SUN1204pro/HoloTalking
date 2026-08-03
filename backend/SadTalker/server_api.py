import os
import sys
import shutil
import asyncio
import glob
import time
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from vieneu import Vieneu
    VIENEU_AVAILABLE = True
except ImportError:
    VIENEU_AVAILABLE = False

app = FastAPI(title="OpenTalking + SadTalker + ViEneu API")

# Ensure static directories exist
os.makedirs("temp_files", exist_ok=True)
os.makedirs("examples/source_image", exist_ok=True)

app.mount("/static", StaticFiles(directory="temp_files"), name="static")
app.mount("/examples", StaticFiles(directory="examples"), name="examples")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        {"id": "Thái Sơn", "name": "Thái Sơn", "gender": "Nam", "region": "Miền Bắc", "desc": "Giọng nam Bắc trầm ấm, dõng dạc, truyền cảm"},
        {"id": "Ngọc Huyền", "name": "Ngọc Huyền", "gender": "Nữ", "region": "Miền Bắc", "desc": "Giọng nữ Bắc dịu dàng, trong trẻo, tự nhiên"},
        {"id": "Nam Phương", "name": "Nam Phương", "gender": "Nam", "region": "Miền Nam", "desc": "Giọng nam Nam Bộ hào sảng, thân thiện"},
        {"id": "Minh Hoàng", "name": "Minh Hoàng", "gender": "Nam", "region": "Miền Trung", "desc": "Giọng nam Miền Trung điềm tĩnh, mộc mạc"},
        {"id": "Bảo Quốc", "name": "Bảo Quốc", "gender": "Nam", "region": "Miền Bắc", "desc": "Giọng nam Bắc uy nghi, hùng hồn (phù hợp Lịch sử)"},
        {"id": "Kim Ngân", "name": "Kim Ngân", "gender": "Nữ", "region": "Miền Nam", "desc": "Giọng nữ Nam Bộ truyền cảm, ngọt ngào"},
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
    pose_style: int = Form(0)
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("temp_files", f"test_run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # 1. Resolve avatar image path
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

    # Background removal attempt
    remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "").strip()
    if remove_bg_key:
        try:
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': open(image_path, 'rb')},
                data={'size': 'auto', 'bg_color': '000000'},
                headers={'X-Api-Key': remove_bg_key},
                timeout=4
            )
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
            else:
                output_path = image_path
        except Exception:
            output_path = image_path
    else:
        output_path = image_path

    # 2. Resolve Audio Path
    audio_path = os.path.join(run_dir, "input_audio.wav")
    final_speak_text = text

    if inputType == "text":
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text input is empty.")
        
        if use_gemini:
            try:
                final_speak_text = generate_gemini_response(
                    user_message=text,
                    persona=persona,
                    api_key=api_key
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Gemini API failed: {str(e)}")

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
                if VIENEU_AVAILABLE:
                    tts = Vieneu()
                    voice = tts.get_preset_voice(voice_name or "Thái Sơn")
                    audio_data = tts.infer(text=final_speak_text, voice=voice)
                    tts.save(audio_data, audio_path)
            except Exception as e:
                print("Gemini Audio AI response failed, falling back to direct audio:", e)
                with open(audio_path, "wb") as buffer:
                    buffer.write(raw_bytes)
        else:
            audio.file.seek(0)
            with open(audio_path, "wb") as buffer:
                shutil.copyfileobj(audio.file, buffer)

    # 3. Construct SadTalker inference command using active Python executable
    python_exe = sys.executable
    cmd_parts = [
        f'"{python_exe}"', "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{output_path}"',
        "--result_dir", f'"{run_dir}"',
        "--preprocess", preprocess if preprocess in ["crop", "extcrop", "resize", "full", "extfull"] else "crop",
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

    return {
        "status": "success",
        "video_url": f"http://127.0.0.1:8000/static/test_run_{timestamp}/{final_video_name}",
        "spoken_text": final_speak_text if inputType == "text" else None,
        "generation_time_seconds": elapsed_seconds
    }


def generate_gemini_response(user_message: str = None, audio_bytes: bytes = None, mime_type: str = "audio/wav", persona: str = None, history_json: str = None, api_key: str = None) -> str:
    import json
    import base64
    key = (api_key and api_key.strip()) or os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key. Please configure GEMINI_API_KEY in .env or provide key in frontend.")

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

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]
    last_error = None

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
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if res.status_code == 200:
                res_data = res.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                last_error = f"Model {model} HTTP {res.status_code}: {res.text}"
        except Exception as e:
            last_error = str(e)

    raise HTTPException(status_code=500, detail=f"Failed to generate AI response from Gemini. {last_error}")


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
    pose_style: int = Form(0)
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
    remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "").strip()
    if remove_bg_key:
        try:
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': open(image_path, 'rb')},
                data={'size': 'auto', 'bg_color': '000000'},
                headers={'X-Api-Key': remove_bg_key},
                timeout=4
            )
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
            else:
                output_path = image_path
        except Exception:
            output_path = image_path
    else:
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
        "--preprocess", preprocess if preprocess in ["crop", "extcrop", "resize", "full", "extfull"] else "crop",
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