# AI Talking Avatar Project (OpenTalking + SadTalker + ViEneu)

Interactive voice-driven AI Agent application combining React Vite frontend, FastAPI backend, ViEneu Vietnamese TTS, Gemini AI Chatbot, and SadTalker talking head video generation.

---

## 🛠️ Project Structure

```
app/
├── backend/
│   └── SadTalker/
│       ├── .env                # Secret API key configuration (DO NOT COMMIT)
│       ├── .env.example        # Environment variable template
│       ├── server_api.py       # FastAPI backend server
│       ├── requirements.txt    # Python dependencies list
│       ├── checkpoints/        # SadTalker ML model weights
│       ├── gfpgan/             # Face enhancement model
│       └── temp_files/         # Generated video outputs
└── frontend/
    ├── src/                    # React UI components
    ├── package.json
    └── vite.config.js
```

---

## 🚀 Environment Setup & Installation

### 1. Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: v18+ and npm
- **FFmpeg**: Required for audio/video processing
  - *macOS*: `brew install ffmpeg`
  - *Linux*: `sudo apt install ffmpeg`

---

### 2. Backend Setup

Navigate to the `backend/SadTalker` directory:

```bash
cd backend/SadTalker
```

Create and activate a Python environment. A **conda environment is recommended**
over a plain venv: `requirements.txt` covers the web/API layer, but heavier
dependencies aren't pinned there and are easier to get right via conda,
especially `torch` on Apple Silicon (see the MPS note below):

```bash
# Recommended: conda
conda create -n sadtalker python=3.10
conda activate sadtalker

# Or: plain venv
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

Install PyTorch first (pick the build for your platform from
[pytorch.org/get-started](https://pytorch.org/get-started/locally/)), then the
rest of the Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Needed for the ElevenLabs-powered custom voice features (see section 6),
# not covered by requirements.txt:
pip install voxcpm elevenlabs
```

> **Apple Silicon (M-series) users**: SadTalker's face-render pipeline runs on
> MPS (Apple's GPU backend) automatically when CUDA isn't available, which is
> substantially faster than CPU. No extra setup needed as long as your PyTorch
> build supports MPS (true for standard `pip`/`conda` installs on macOS 12.3+).

---

### 3. API Keys Environment Configuration (`.env`)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` in a text editor and add your API keys:

```env
# Gemini API Key for AI Avatar Chatbot (Required for /api/agent mode)
GEMINI_API_KEY=your_gemini_api_key_here

# Remove.bg API Key for automatic avatar background removal (Optional)
REMOVE_BG_API_KEY=your_remove_bg_api_key_here

# ElevenLabs API Key for custom voice cloning and the Voice Changer feature (Optional)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
```

---

### 4. ML Model Checkpoints

SadTalker and its optional Wav2Lip lip-sync refinement pass need their model
weights present under `backend/SadTalker/checkpoints/` and
`backend/SadTalker/gfpgan/weights/` (SadTalker's own download script/instructions
apply here — see [SadTalker's repo](https://github.com/OpenTalker/SadTalker) if
these aren't already populated). In particular, `checkpoints/wav2lip_gan.pth`
is required for the Wav2Lip refinement pass (`lipsync_engine=wav2lip`, the
default) to actually run — without it, that step silently no-ops and falls
back to SadTalker's own head-motion output.

---

### 5. Running the Backend Server

With your environment activated, run:

```bash
python server_api.py
```

The server will start at:
- **API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### 6. Frontend Setup & Launch

Open a new terminal window and navigate to the `frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

Open the displayed URL (typically [http://localhost:5173](http://localhost:5173)) in your browser to interact with the AI Talking Avatar application.

---

## 🗣️ Custom Voice Cloning (ElevenLabs + VoxCPM)

Beyond the built-in ViEneu preset voices, the "Custom Voice" TTS engine lets you
clone the timbre of any ElevenLabs voice locally via VoxCPM:
- Pick a voice from your ElevenLabs library and generate speech in that voice's
  timbre without hitting ElevenLabs' TTS API per-request.
- **Voice Changer**: upload a recording of any speech; it's converted into the
  selected ElevenLabs voice's timbre (via ElevenLabs Speech-to-Speech) and cached
  as a richer local cloning reference for VoxCPM.

Requires `ELEVENLABS_API_KEY` in `.env` and the `voxcpm`/`elevenlabs` Python
packages (see step 2).

---

## 🔒 Security Note
- Never check your `.env` file containing private API keys into Git. `.env` is listed in `.gitignore` by default.
