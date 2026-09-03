"""In-process SadTalker engine.

inference.py spawns a fresh `python inference.py` per request, which reloads every
checkpoint onto the GPU each time (~10-20s). This module loads the models once and
reuses them, so after warm-up a generation only pays for the actual inference.

server_api.py uses this when SADTALKER_WARM != "0". A single lock serialises
generations because the models are not safe to run concurrently.
"""
import os
import sys
import shutil
import threading

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch

from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff
from src.facerender.animate import AnimateFromCoeff
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data
from src.utils.init_path import init_path

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CHECKPOINT_DIR = os.path.join(_BASE_DIR, "checkpoints")
_CONFIG_DIR = os.path.join(_BASE_DIR, "src", "config")
_SIZE = 256

_lock = threading.Lock()
_models = {}          # preprocess -> (preprocess_model, audio_to_coeff, animate_from_coeff)
_device = None


def pick_device() -> str:
    if os.environ.get("SADTALKER_FORCE_CPU") == "1":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _get_models(preprocess: str):
    """Load (or reuse) the three SadTalker model groups for a given preprocess mode."""
    global _device
    if _device is None:
        _device = pick_device()
    key = preprocess if preprocess in ("crop", "extcrop", "full", "extfull", "resize") else "crop"
    if key not in _models:
        paths = init_path(_CHECKPOINT_DIR, _CONFIG_DIR, _SIZE, False, key)
        print(f"[sadtalker_engine] loading models on {_device} (preprocess={key})...")
        _models[key] = (
            CropAndExtract(paths, _device),
            Audio2Coeff(paths, _device),
            AnimateFromCoeff(paths, _device),
        )
        print(f"[sadtalker_engine] models ready (preprocess={key})")
    return _models[key]


def warmup(preprocess: str = "crop"):
    """Load the models now so the first real request doesn't pay for it."""
    with _lock:
        _get_models(preprocess)


def generate(
    source_image: str,
    audio_path: str,
    result_dir: str,
    clip_name: str,
    preprocess: str = "crop",
    still: bool = True,
    expression_scale: float = 1.0,
    pose_style: int = 0,
    enhancer: str = "none",
    batch_size: int = None,
) -> str:
    """Run the full SadTalker pipeline in-process. Returns the path to the mp4
    written inside result_dir (named clip_name)."""
    if batch_size is None:
        try:
            batch_size = int(os.environ.get("SADTALKER_BATCH_SIZE", "4"))
        except ValueError:
            batch_size = 4
    preprocess = preprocess if preprocess in ("crop", "extcrop", "full", "extfull", "resize") else "crop"
    enh = enhancer if enhancer and enhancer != "none" else None

    with _lock:
        preprocess_model, audio_to_coeff, animate_from_coeff = _get_models(preprocess)

        save_dir = source_image + "hcmus"          # sibling dir kept for 3DMM cache reuse
        os.makedirs(save_dir, exist_ok=True)
        first_frame_dir = os.path.join(save_dir, "first_frame_dir")
        os.makedirs(first_frame_dir, exist_ok=True)

        first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
            source_image, first_frame_dir, preprocess, source_image_flag=True, pic_size=_SIZE
        )
        if first_coeff_path is None:
            raise RuntimeError("SadTalker: could not extract 3DMM coeffs from the avatar image.")

        batch = get_data(first_coeff_path, audio_path, _device, None, still=still)
        coeff_path = audio_to_coeff.generate(batch, save_dir, pose_style, None)

        data = get_facerender_data(
            coeff_path, crop_pic_path, first_coeff_path, audio_path,
            batch_size, None, None, None,
            expression_scale=expression_scale, still_mode=still,
            preprocess=preprocess, size=_SIZE,
        )
        result = animate_from_coeff.generate(
            data, save_dir, source_image, crop_info,
            enhancer=enh, background_enhancer=None, preprocess=preprocess, img_size=_SIZE,
        )

        os.makedirs(result_dir, exist_ok=True)
        final_path = os.path.join(result_dir, clip_name)
        shutil.move(result, final_path)
        return final_path
