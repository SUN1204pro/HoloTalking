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

Create and activate a Python virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate on macOS/Linux:
source venv/bin/activate

# Activate on Windows:
# venv\Scripts\activate
```

Install Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

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
```

---

### 4. Running the Backend Server

With the virtual environment activated, run:

```bash
python server_api.py
```

The server will start at:
- **API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### 5. Frontend Setup & Launch

Open a new terminal window and navigate to the `frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

Open the displayed URL (typically [http://localhost:5173](http://localhost:5173)) in your browser to interact with the AI Talking Avatar application.

---

## 🔒 Security Note
- Never check your `.env` file containing private API keys into Git. `.env` is listed in `.gitignore` by default.
