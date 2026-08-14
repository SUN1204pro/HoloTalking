# Adapted from https://github.com/thinhlpg/vixtts-demo (vixtts_demo.py)
#
# Standalone viXTTS inference server. Runs under the `tts_env` conda environment
# (the one with `coqui TTS` installed) and is launched as a subprocess by
# server_api.py, which runs under the `sadtalker` env. Loads the viXTTS model
# once and serves voice-cloning TTS requests over HTTP so repeated generations
# reuse the already-loaded model instead of reloading it every request.
import os
import tempfile

import soundfile as sf
import torch
import torchaudio
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response
from huggingface_hub import snapshot_download, hf_hub_download


def _torchaudio_load_via_soundfile(path, *args, **kwargs):
    """This machine's torchaudio build only loads audio through torchcodec, which
    needs FFmpeg shared libs that aren't resolvable here. XTTS just needs a
    (channels, samples) tensor + sample rate, so read it via soundfile instead."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return torch.from_numpy(data.T), sr


torchaudio.load = _torchaudio_load_via_soundfile

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

try:
    from underthesea import sent_tokenize
except Exception:
    sent_tokenize = None

try:
    from vinorm import TTSnorm
except Exception:
    TTSnorm = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(SCRIPT_DIR, "vixtts_model")

app = FastAPI(title="viXTTS Inference Server")
_model = None


def load_model():
    global _model
    if _model is not None:
        return _model

    os.makedirs(MODEL_DIR, exist_ok=True)
    required_files = ["model.pth", "config.json", "vocab.json", "speakers_xtts.pth"]
    if not all(os.path.exists(os.path.join(MODEL_DIR, f)) for f in required_files):
        print(f"[viXTTS] Downloading model to {MODEL_DIR}...", flush=True)
        snapshot_download(repo_id="capleaf/viXTTS", repo_type="model", local_dir=MODEL_DIR)
        hf_hub_download(repo_id="coqui/XTTS-v2", filename="speakers_xtts.pth", local_dir=MODEL_DIR)
        print("[viXTTS] Model download finished.", flush=True)

    config = XttsConfig()
    config.load_json(os.path.join(MODEL_DIR, "config.json"))
    model = Xtts.init_from_config(config)
    print("[viXTTS] Loading checkpoint (first request only)...", flush=True)
    model.load_checkpoint(config, checkpoint_dir=MODEL_DIR, use_deepspeed=False)
    if torch.cuda.is_available():
        model.cuda()
    elif torch.backends.mps.is_available():
        model.to("mps")

    _model = model
    print("[viXTTS] Model ready.", flush=True)
    return _model


def normalize_vietnamese_text(text):
    if TTSnorm is None:
        return text
    try:
        text = TTSnorm(text, unknown=False, lower=False, rule=True)
    except Exception:
        return text
    return (
        text.replace("..", ".").replace("!.", "!").replace("?.", "?")
        .replace(" .", ".").replace(" ,", ",").replace('"', "").replace("'", "")
    )


def calculate_keep_len(text, lang):
    """Simple hack for short sentences, ported from the viXTTS demo."""
    if lang in ["ja", "zh-cn"]:
        return -1
    word_count = len(text.split())
    num_punct = text.count(".") + text.count("!") + text.count("?") + text.count(",")
    if word_count < 5:
        return 15000 * word_count + 2000 * num_punct
    elif word_count < 10:
        return 13000 * word_count + 2000 * num_punct
    return -1


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}


@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    language: str = Form("vi"),
    normalize_text: bool = Form(True),
    reference_audio: UploadFile = File(...),
):
    model = load_model()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await reference_audio.read())
        ref_path = tmp.name

    out_path = None
    try:
        gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
            audio_path=ref_path,
            gpt_cond_len=model.config.gpt_cond_len,
            max_ref_length=model.config.max_ref_len,
            sound_norm_refs=model.config.sound_norm_refs,
        )

        tts_text = normalize_vietnamese_text(text) if (normalize_text and language == "vi") else text

        if language in ("ja", "zh-cn"):
            sentences = tts_text.split("。")
        elif sent_tokenize is not None:
            sentences = sent_tokenize(tts_text)
        else:
            sentences = [tts_text]

        wav_chunks = []
        for sentence in sentences:
            if not sentence.strip():
                continue
            chunk = model.inference(
                text=sentence,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                # Values carried over from the viXTTS demo, tuned for this checkpoint.
                temperature=0.3,
                length_penalty=1.0,
                repetition_penalty=10.0,
                top_k=30,
                top_p=0.85,
                # False: the stock (non-vendored) coqui TTS package's tokenizer has no
                # char-limit entry for "vi" and crashes here. We already split text into
                # sentences via underthesea above, so XTTS's own splitter isn't needed.
                enable_text_splitting=False,
            )
            keep_len = calculate_keep_len(sentence, language)
            wav = chunk["wav"][:keep_len] if keep_len != -1 else chunk["wav"]
            wav_chunks.append(torch.tensor(wav))

        out_wav = torch.cat(wav_chunks, dim=0).unsqueeze(0)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_tmp:
            out_path = out_tmp.name
        sf.write(out_path, out_wav.squeeze(0).numpy(), 24000)
        with open(out_path, "rb") as f:
            wav_bytes = f.read()
        return Response(content=wav_bytes, media_type="audio/wav")
    finally:
        if os.path.exists(ref_path):
            os.remove(ref_path)
        if out_path and os.path.exists(out_path):
            os.remove(out_path)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("VIXTTS_PORT", "8011"))
    uvicorn.run(app, host="127.0.0.1", port=port)
