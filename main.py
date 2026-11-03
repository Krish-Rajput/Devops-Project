from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import os
from pymongo import MongoClient
import certifi

app = FastAPI()

# Connect to MongoDB using the Environment Variable
MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client.dsa_tracker
collection = db.progress

class ProgressRequest(BaseModel):
    problem_number: int

leetcode_cache = {}

def fetch_leetcode_data(problem_number: int):
    if problem_number in leetcode_cache:
        return leetcode_cache[problem_number]
        
    url = "https://leetcode.com/graphql"
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        data { difficulty, questionFrontendId, title, topicTags { name } }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "categorySlug": "", "skip": 0, "limit": 10,
            "filters": {"searchKeywords": str(problem_number)}
        }
    }
    
    try:
        resp = httpx.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=8.0)
        if resp.status_code == 200:
            questions = resp.json().get("data", {}).get("problemsetQuestionList", {}).get("data", [])
            for q in questions:
                if str(q.get("questionFrontendId")) == str(problem_number):
                    topics = q.get("topicTags", [])
                    topic_name = topics[0]["name"] if topics else "Algorithms"
                    result = {
                        "title": f"LeetCode {problem_number}: {q.get('title')}",
                        "difficulty": q.get("difficulty"),
                        "topic": topic_name
                    }
                    leetcode_cache[problem_number] = result
                    return result
    except Exception:
        pass
    return None

@app.get("/", response_class=HTMLResponse)
def read_root():
    # Frontend HTML remains exactly the same as the previous step!
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DSA Progress Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f4f7f6; margin: 0; padding: 20px; display: flex; justify-content: center; }
            .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); width: 100%; max-width: 600px; }
            h1 { color: #111827; font-size: 24px; text-align: center; margin-bottom: 5px; }
            .subtitle { text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 25px; }
            .stats-row { display: flex; gap: 15px; margin-bottom: 25px; }
            .stat-box { flex: 1; background: #f9fafb; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e5e7eb; }
            .stat-value { font-size: 28px; font-weight: bold; color: #3b82f6; }
            .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
            .form-row { display: flex; gap: 10px; margin-bottom: 15px; }
            .form-group { flex: 1; }
            input { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; font-size: 14px; text-align: center; }
            button { width: 100%; background: #3b82f6; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }
            button:hover { background: #2563eb; }
            .progress-list { margin-top: 30px; padding: 0; list-style: none; }
            .progress-item { background: white; padding: 15px; border: 1px solid #e5e7eb; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; transition: 0.2s;}
            .item-info { display: flex; flex-direction: column; gap: 4px; }
            .problem-name { font-weight: 600; color: #1f2937; }
            .topic-tag { font-size: 12px; color: #6b7280; }
            .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
            .badge.easy { background: #dcfce7; color: #166534; }
            .badge.medium { background: #fef08a; color: #854d0e; }
            .badge.hard { background: #fee2e2; color: #991b1b; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 DSA Tracker</h1>
            <div class="subtitle">Log your daily LeetCode and coding problems</div>
            <div class="stats-row">
                <div class="stat-box">
                    <div class="stat-value" id="total-solved">0</div>
                    <div class="stat-label">Total Solved</div>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <input type="number" id="problem" placeholder="Enter LeetCode Problem Number (e.g., 462)" min="1">
                </div>
            </div>
            <button onclick="addProgress()">Log Progress</button>
            <ul class="progress-list" id="list"></ul>
        </div>
        <script>
            async function loadProgress() {
                const response = await fetch('/api/progress');
                const data = await response.json();
                document.getElementById('total-solved').innerText = data.length;
                const list = document.getElementById('list');
                list.innerHTML = '';
                data.slice().reverse().forEach(item => {
                    let badgeClass = item.difficulty.toLowerCase();
                    list.innerHTML += `
                    <li class="progress-item">
                        <div class="item-info">
                            <span class="problem-name">${item.problem}</span>
                            <span class="topic-tag">📚 ${item.topic}</span>
                        </div>
                        <span class="badge ${badgeClass}">${item.difficulty}</span>
                    </li>`;
                });
            }
            async function addProgress() {
                const problemNum = document.getElementById('problem').value;
                if (!problemNum) { alert("Please enter a problem number."); return; }
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                const data = await response.json();
                if (!response.ok) { alert("Error: " + data.detail); return; }
                document.getElementById('problem').value = '';
                loadProgress();
            }
            loadProgress();
        </script>
    </body>
    </html>
    """

@app.get("/api/progress")
def get_progress():
    # Fetch all items from MongoDB, excluding the internal _id field
    items = list(collection.find({}, {"_id": 0}))
    return items

@app.post("/api/progress")
def add_progress(req: ProgressRequest):
    # Check MongoDB for duplicate
    if collection.find_one({"frontend_id": req.problem_number}):
        raise HTTPException(status_code=400, detail=f"LeetCode {req.problem_number} is already marked as solved!")
    
    prob_data = fetch_leetcode_data(req.problem_number)
    if not prob_data:
        raise HTTPException(status_code=404, detail="Invalid LeetCode problem number or LeetCode API timeout.")
    
    # Insert into MongoDB
    new_doc = {
        "frontend_id": req.problem_number,
        "problem": prob_data["title"], 
        "topic": prob_data["topic"], 
        "difficulty": prob_data["difficulty"]
    }
    collection.insert_one(new_doc)
    return {"status": "success", "added": prob_data["title"]}