# 💰 FinanceAgent

AI-powered bank statement analyzer. Upload PDF or CSV → get instant spending breakdown, anomaly detection, savings advice, and an AI chat assistant.

**Stack:** FastAPI · LangGraph · Gemini 2.0 Flash · Chart.js

---

## 🚀 Run Locally

```bash
# 1. Clone / download the project
cd financeagent-app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Gemini API key
export GOOGLE_API_KEY=your_key_here   # Linux/Mac
set GOOGLE_API_KEY=your_key_here      # Windows

# 4. Start the server
uvicorn main:app --reload --port 8000

# 5. Open browser
# http://localhost:8000
```

---

## ☁️ Deploy to Render (Free)

1. Push this folder to a GitHub repo
2. Go to https://render.com → New Web Service
3. Connect your repo
4. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `GOOGLE_API_KEY = your_key`
6. Deploy → get a public URL instantly

---

## ☁️ Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set env variable
railway variables set GOOGLE_API_KEY=your_key
```

---

## 🔧 Run in Google Colab

```python
# Cell 1 — Install
!pip install fastapi uvicorn pdfplumber langchain langchain-google-genai langgraph python-multipart nest-asyncio pyngrok

# Cell 2 — Set API key
import os
from google.colab import userdata
os.environ["GOOGLE_API_KEY"] = userdata.get("GOOGLE_API_KEY")

# Cell 3 — Start server with public URL
import nest_asyncio
import uvicorn
from pyngrok import ngrok
from threading import Thread

nest_asyncio.apply()

def run():
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

Thread(target=run, daemon=True).start()

public_url = ngrok.connect(8000)
print(f"🌍 Public URL: {public_url}")
print(f"📊 Open this link to use FinanceAgent!")
```

---

## 📁 Project Structure

```
financeagent-app/
├── main.py              # FastAPI backend + agent logic
├── requirements.txt     # Dependencies
├── README.md
└── static/
    └── index.html       # Full frontend UI
```

---

## 🔑 Get a Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy and set as GOOGLE_API_KEY

Free tier: 15 requests/minute, 1M tokens/day — plenty for personal use.
