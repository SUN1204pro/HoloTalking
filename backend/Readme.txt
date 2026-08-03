=== BACKEND ENVIRONMENT SETUP & QUICK START ===

1. Activate Virtual Environment:
   cd backend/SadTalker
   python3 -m venv venv
   source venv/bin/activate

2. Install Requirements:
   pip install -r requirements.txt

3. Configure Environment Variables (.env):
   cp .env.example .env
   Edit .env and fill in your GEMINI_API_KEY and REMOVE_BG_API_KEY.

4. Start Backend Server:
   python server_api.py

API Server running at: http://127.0.0.1:8000
API Docs: http://127.0.0.1:8000/docs
