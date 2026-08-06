import os
import sys
import shutil
import asyncio
import glob
import requests
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

try:
    from vieneu import Vieneu
    VIENEU_AVAILABLE = True
except ImportError:
    VIENEU_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

# Directories
RESULT_DIR_APP = os.path.join(APP_ROOT, "result")
RESULT_DIR_SADTALKER = os.path.join(BASE_DIR, "result")
TEMP_DIR = os.path.join(BASE_DIR, "temp_files", "backend_avatars_processing")

os.makedirs(RESULT_DIR_APP, exist_ok=True)
os.makedirs(RESULT_DIR_SADTALKER, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

AVATAR_CONFIGS = [
    {
        "id": "thd",
        "name": "Trần Hưng Đạo",
        "source_file": "thd.png",
        "voice": "Thái Sơn",
        "script": "Ta là Hưng Đạo Đại Vương Trần Quốc Tuấn. Ta khuyên các ngươi đồng lòng diệt giặc, bảo vệ giang sơn Tổ quốc!",
        "output_video_name": "thd_result.mp4"
    },
    {
        "id": "vuahung",
        "name": "Vua Hùng",
        "source_file": "vuahung.png",
        "voice": "Gia Bảo",
        "script": "Các Vua Hùng đã có công dựng nước, Bác cháu ta phải cùng nhau giữ lấy nước.",
        "output_video_name": "vuahung_result.mp4"
    }
]


def ensure_rgb_png(image_path: str, output_path: str):
    """Ensures image is converted to standard RGB PNG format."""
    img = Image.open(image_path)
    if img.mode != "RGB":
        rgb_img = Image.new("RGB", img.size, (0, 0, 0))
        if img.mode == "RGBA":
            rgb_img.paste(img, mask=img.split()[3])
        else:
            rgb_img.paste(img)
        rgb_img.save(output_path, "PNG")
    else:
        img.save(output_path, "PNG")


def remove_background(image_path: str, output_path: str) -> str:
    """Removes background via remove.bg API key, with graceful fallback to original image."""
    remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "").strip()
    if remove_bg_key:
        print(f"[{os.path.basename(image_path)}] Attempting remove.bg background removal...")
        try:
            response = requests.post(
                'https://api.remove.bg/v1.0/removebg',
                files={'image_file': open(image_path, 'rb')},
                data={'size': 'auto', 'bg_color': '000000'},
                headers={'X-Api-Key': remove_bg_key},
                timeout=15
            )
            if response.status_code == 200:
                temp_raw = output_path + ".raw.png"
                with open(temp_raw, "wb") as f:
                    f.write(response.content)
                ensure_rgb_png(temp_raw, output_path)
                if os.path.exists(temp_raw):
                    os.remove(temp_raw)
                print(f"[{os.path.basename(image_path)}] remove.bg success -> {output_path}")
                return output_path
            else:
                print(f"[{os.path.basename(image_path)}] remove.bg HTTP {response.status_code}, falling back to original image.")
        except Exception as e:
            print(f"[{os.path.basename(image_path)}] remove.bg failed ({e}), falling back to original image.")

    ensure_rgb_png(image_path, output_path)
    return output_path


def generate_tts_audio(text: str, voice_name: str, audio_path: str):
    """Generates Vietnamese TTS speech using ViEneu."""
    if not VIENEU_AVAILABLE:
        raise RuntimeError("ViEneu TTS library is not installed in current environment.")
    
    print(f"Generating ViEneu TTS ('{voice_name}'): '{text}'...")
    tts = Vieneu()
    try:
        voice = tts.get_preset_voice(voice_name)
    except Exception:
        voice = tts.get_preset_voice("Thái Sơn")
        
    audio_data = tts.infer(text=text, voice=voice)
    tts.save(audio_data, audio_path)
    print(f"Saved TTS audio to {audio_path}")


async def run_sadtalker_inference(image_path: str, audio_path: str, run_dir: str):
    """Runs SadTalker video generation python script with resize preprocess."""
    python_exe = sys.executable
    cmd_parts = [
        f'"{python_exe}"', "inference.py",
        "--driven_audio", f'"{audio_path}"',
        "--source_image", f'"{image_path}"',
        "--result_dir", f'"{run_dir}"',
        "--preprocess", "resize",
        "--still"
    ]
    
    command_str = " ".join(cmd_parts)
    print(f"Running SadTalker command: {command_str}")
    
    process = await asyncio.create_subprocess_shell(command_str, cwd=BASE_DIR)
    await process.communicate()
    
    if process.returncode != 0:
        raise RuntimeError("SadTalker inference script failed execution.")


async def process_avatar_config(cfg: dict):
    print(f"\n==================================================")
    print(f"Processing Avatar: {cfg['name']} ({cfg['source_file']})")
    print(f"==================================================")

    # 1. Source Image Path
    src_image = os.path.join(BASE_DIR, "examples", "source_image", cfg["source_file"])
    if not os.path.exists(src_image):
        src_image = os.path.join(APP_ROOT, "backend", cfg["source_file"])
    if not os.path.exists(src_image):
        raise FileNotFoundError(f"Source image {cfg['source_file']} not found.")

    avatar_run_dir = os.path.join(TEMP_DIR, cfg["id"])
    os.makedirs(avatar_run_dir, exist_ok=True)

    # 2. remove.bg processing
    bg_removed_image = os.path.join(avatar_run_dir, f"{cfg['id']}_nobg.png")
    processed_image = remove_background(src_image, bg_removed_image)

    # 3. Vietneu TTS Audio
    audio_path = os.path.join(avatar_run_dir, f"{cfg['id']}_voice.wav")
    generate_tts_audio(cfg["script"], cfg["voice"], audio_path)

    # 4. SadTalker Video Generation
    await run_sadtalker_inference(processed_image, audio_path, avatar_run_dir)

    # Find generated video recursively in subdirectories
    videos = glob.glob(os.path.join(avatar_run_dir, "**", "*.mp4"), recursive=True)
    if not videos:
        raise RuntimeError(f"No video file produced for avatar {cfg['name']}")

    newest_video = max(videos, key=os.path.getctime)
    
    # 5. Save final video into folder 'result'
    target_result_app = os.path.join(RESULT_DIR_APP, cfg["output_video_name"])
    target_result_sadtalker = os.path.join(RESULT_DIR_SADTALKER, cfg["output_video_name"])

    shutil.copy(newest_video, target_result_app)
    shutil.copy(newest_video, target_result_sadtalker)

    print(f"✅ SUCCESSFULLY SAVED FINAL VIDEO TO:")
    print(f"   -> {target_result_app}")
    print(f"   -> {target_result_sadtalker}")


async def main():
    print("Starting batch processing for backend avatar PNG files...")
    for cfg in AVATAR_CONFIGS:
        try:
            await process_avatar_config(cfg)
        except Exception as e:
            print(f"❌ Error processing {cfg['name']}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
