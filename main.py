from dotenv import load_dotenv
load_dotenv()

import os
import re
import csv
import json
import tempfile
import statistics
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pdfplumber
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

app = FastAPI(title="FinanceAgent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── LLM + Agent setup ─────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    google_api_key=os.environ.get("GOOGLE_API_KEY")
)

CATEGORY_RULES = {
    "Food & Dining":   ["zomato", "swiggy", "starbucks", "cafe", "restaurant", "pizza", "kfc", "dominos", "mcdonald", "burger", "bistro", "diner", "ubereats"],
    "Groceries":       ["bigbasket", "dmart", "zepto", "blinkit", "grofers", "grocery", "supermarket", "walmart", "nature basket", "reliance fresh"],
    "Transport":       ["uber", "ola", "rapido", "metro", "fuel", "petrol", "cab", "taxi", "lyft", "parking", "toll"],
    "Entertainment":   ["netflix", "spotify", "hotstar", "disney", "pvr", "bookmyshow", "inox", "youtube", "prime video", "apple tv", "hulu"],
    "Shopping":        ["amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho", "ebay", "clothing", "apparel"],
    "Utilities":       ["airtel", "jio", "electricity", "water", "broadband", "wifi", "bsnl", "vodafone", "mobile recharge"],
    "Health":          ["pharmacy", "apollo", "1mg", "gym", "fitness", "medplus", "healthkart", "cult.fit", "hospital", "clinic"],
    "Education":       ["udemy", "coursera", "edx", "skillshare", "book", "tuition", "school", "college"],
    "Finance":         ["emi", "loan", "insurance", "mutual fund", "sip", "zerodha", "groww", "credit card", "bank fee"],
    "Travel":          ["hotel", "airbnb", "oyo", "makemytrip", "goibibo", "booking.com", "airline", "indigo", "spicejet"],
}

def parse_transactions(filepath: str) -> list:
    txns = []
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    m = re.search(r"([\-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", line)
                    if m:
                        amt = float(m.group(1).replace(",", ""))
                        desc = line[:m.start()].strip()
                        if desc and abs(amt) > 10:
                            txns.append({"date": "", "description": desc, "amount": amt})
    elif ext == ".csv":
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                desc = row.get("description") or row.get("merchant") or row.get("narration") or ""
                amt_raw = row.get("amount") or row.get("debit") or row.get("credit") or "0"
                try:
                    amt = float(str(amt_raw).replace(",", ""))
                except:
                    amt = 0
                txns.append({"date": row.get("date", ""), "description": desc, "amount": amt})
    return txns

def categorize(txns: list) -> dict:
    cats = defaultdict(list)
    for t in txns:
        desc = t["description"].lower()
        matched = False
        for cat, keywords in CATEGORY_RULES.items():
            if any(kw in desc for kw in keywords):
                cats[cat].append(t)
                matched = True
                break
        if not matched:
            cats["Other"].append(t)
    return dict(cats)

def find_anomalies(txns: list) -> list:
    expenses = [t for t in txns if t["amount"] < 0]
    if len(expenses) < 3:
        return []
    amounts = [abs(t["amount"]) for t in expenses]
    mean = statistics.mean(amounts)
    stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
    anomalies = []
    seen = defaultdict(list)
    for t in expenses:
        key = (t["description"].lower()[:25], round(abs(t["amount"])))
        seen[key].append(t)
    for (desc, amt), group in seen.items():
        if len(group) > 1:
            anomalies.append({"type": "duplicate", "severity": "high",
                "message": f"'{group[0]['description']}' charged ₹{amt} appears {len(group)} times"})
    for t in expenses:
        amt = abs(t["amount"])
        if stdev > 0:
            z = (amt - mean) / stdev
            if z > 2.5:
                anomalies.append({"type": "large", "severity": "high" if z > 3 else "medium",
                    "message": f"{t['description']} — ₹{amt:,.0f} is {z:.1f}× above average (avg ₹{mean:,.0f})"})
    return anomalies[:8]

def savings_tips(cat_summary: dict) -> list:
    tips = []
    total = sum(v["total"] for v in cat_summary.values())
    if total == 0:
        return tips
    rules = [
        ("Food & Dining", 0.18, "Ordering food frequently. Cooking at home 3×/week could save ₹2,000+/month.", 2000),
        ("Entertainment", 0.10, "Multiple streaming subscriptions active. Audit and cancel unused ones.", 700),
        ("Transport", 0.15, "High cab/ride usage. A monthly transit pass could save ₹1,500/month.", 1500),
        ("Shopping", 0.20, "High impulse shopping. Try a 48-hour rule before non-essential purchases.", 1800),
    ]
    for cat, threshold, msg, est in rules:
        if cat in cat_summary:
            pct = cat_summary[cat]["total"] / total
            if pct > threshold:
                tips.append({"category": cat, "message": msg, "estimated_saving": est, "current_spend": cat_summary[cat]["total"]})
    return tips


# ── API Routes ────────────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        txns = parse_transactions(tmp_path)
        if not txns:
            raise HTTPException(status_code=422, detail="No transactions found in file")

        cats = categorize(txns)
        expenses = [t for t in txns if t["amount"] < 0]
        income = [t for t in txns if t["amount"] > 0]

        cat_summary = {}
        for cat, items in cats.items():
            total = round(sum(abs(t["amount"]) for t in items if t["amount"] < 0), 2)
            cat_summary[cat] = {"count": len(items), "total": total, "transactions": items[:5]}

        anomalies = find_anomalies(txns)
        tips = savings_tips(cat_summary)
        total_spent = round(sum(abs(t["amount"]) for t in expenses), 2)
        total_income = round(sum(t["amount"] for t in income), 2)
        potential_savings = sum(t["estimated_saving"] for t in tips)

        top_cat = max(cat_summary, key=lambda c: cat_summary[c]["total"]) if cat_summary else "—"

        return {
            "summary": {
                "total_spent": total_spent,
                "total_income": total_income,
                "transaction_count": len(txns),
                "top_category": top_cat,
                "anomaly_count": len(anomalies),
                "potential_savings": potential_savings,
            },
            "categories": cat_summary,
            "anomalies": anomalies,
            "tips": tips,
        }
    finally:
        os.unlink(tmp_path)


class ChatRequest(BaseModel):
    message: str
    context: dict = {}

@app.post("/chat")
async def chat(req: ChatRequest):
    ctx = req.context
    summary = ctx.get("summary", {})
    categories = ctx.get("categories", {})

    context_str = f"""
User's financial data:
- Total spent: ₹{summary.get('total_spent', 0):,.0f}
- Total income: ₹{summary.get('total_income', 0):,.0f}
- Transactions: {summary.get('transaction_count', 0)}
- Top category: {summary.get('top_category', 'Unknown')}
- Anomalies found: {summary.get('anomaly_count', 0)}
- Potential monthly savings: ₹{summary.get('potential_savings', 0):,.0f}
- Category breakdown: {json.dumps({k: v['total'] for k, v in categories.items()}, indent=2)}
"""

    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=(
            "You are a friendly, sharp Personal Finance Agent. "
            "Answer questions about the user's bank statement concisely. "
            "Use ₹ for amounts. Be encouraging, not judgmental. "
            "Keep responses under 120 words. Use bullet points when listing items.\n\n"
            + context_str
        )
    )

    result = agent.invoke({"messages": [("human", req.message)]})
    reply = result["messages"][-1].content
    return {"reply": reply}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
