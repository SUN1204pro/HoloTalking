import os
import sys
import subprocess
import torch

def process_wav2lip(video_path: str, audio_path: str, output_path: str, checkpoint_path: str = "checkpoints/wav2lip_gan.pth") -> str:
    """
    Applies Wav2Lip lip-synchronization over a generated SadTalker head-motion video.
    Falls back gracefully to the original video if checkpoint is missing or error occurs.
    """
    if not os.path.exists(checkpoint_path):
        print(f"[Wav2Lip Warning] Checkpoint {checkpoint_path} not found. Returning SadTalker motion video.")
        return video_path

    try:
        python_exe = sys.executable
        cmd = [
            python_exe, "-m", "src.utils.wav2lip_inference",
            "--checkpoint_path", checkpoint_path,
            "--face", video_path,
            "--audio", audio_path,
            "--outfile", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"[Wav2Lip Success] Refined lip sync saved to {output_path}")
            return output_path
        else:
            print(f"[Wav2Lip Error] Process returned non-zero code. Output: {result.stderr}")
            return video_path
    except Exception as e:
        print(f"[Wav2Lip Exception] {str(e)}")
        return video_path
