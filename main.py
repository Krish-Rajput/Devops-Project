from fastapi import FastAPI, HTTPException, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import httpx
import os
import base64
from pymongo import MongoClient
import certifi
from typing import Optional

app = FastAPI()

MONGO_URI = os.getenv("MONGODB_URI")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client.dsa_tracker
collection = db.progress
users_collection = db.users 

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

def push_to_github(username: str, token: str, prob_id: int, title: str, topic: str, difficulty: str):
    repo_name = "DSA-Tracker-Progress"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    check_repo = httpx.get(f"https://api.github.com/repos/{username}/{repo_name}", headers=headers)
    if check_repo.status_code == 404:
        httpx.post("https://api.github.com/user/repos", json={
            "name": repo_name, 
            "private": False, 
            "description": "🚀 Auto-generated Daily DSA Progress Tracker"
        }, headers=headers)
    
    path = f"problems/LC_{prob_id}.md"
    content = f"# {title}\n- **Topic**: {topic}\n- **Difficulty**: {difficulty}\n\n*Logged automatically via DevOps DSA Tracker CI/CD pipeline.*"
    encoded_content = base64.b64encode(content.encode()).decode()
    
    data = {
        "message": f"Solved {title}",
        "content": encoded_content
    }
    
    httpx.put(f"https://api.github.com/repos/{username}/{repo_name}/contents/{path}", json=data, headers=headers)

# --- OAuth Authentication Routes ---

@app.get("/auth/login")
def login():
    return RedirectResponse(f"https://github.com/login/oauth/authorize?client_id={OAUTH_CLIENT_ID}&scope=repo")

@app.get("/auth/callback")
def callback(code: str):
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    data = {
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "code": code
    }
    
    with httpx.Client() as http_client:
        r = http_client.post(token_url, json=data, headers=headers)
        access_token = r.json().get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub authentication failed")
            
        user_r = http_client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})
        username = user_r.json().get("login")

    users_collection.update_one(
        {"username": username},
        {"$set": {"access_token": access_token}},
        upsert=True
    )

    response = RedirectResponse("/")
    response.set_cookie(key="github_user", value=username, httponly=False)
    return response

@app.get("/auth/logout")
def logout():
    response = RedirectResponse("/")
    response.delete_cookie("github_user")
    return response

# --- Application Routes ---

@app.get("/", response_class=HTMLResponse)
def read_root():
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
            
            .auth-btn { width: 100%; background: #24292e; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; display: flex; justify-content: center; align-items: center; gap: 8px;}
            .auth-btn:hover { background: #1b1f23; }
            
            .stats-row { display: flex; gap: 15px; margin-bottom: 25px; }
            .stat-box { flex: 1; background: #f9fafb; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e5e7eb; }
            .stat-value { font-size: 28px; font-weight: bold; color: #3b82f6; }
            .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
            
            .form-row { display: flex; gap: 10px; margin-bottom: 15px; }
            .form-group { flex: 1; }
            input { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; font-size: 14px; text-align: center; }
            .submit-btn { width: 100%; background: #3b82f6; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }
            .submit-btn:hover { background: #2563eb; }
            
            .progress-list { margin-top: 30px; padding: 0; list-style: none; }
            .progress-item { background: white; padding: 15px; border: 1px solid #e5e7eb; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; transition: 0.2s;}
            .item-info { display: flex; flex-direction: column; gap: 4px; }
            .problem-name { font-weight: 600; color: #1f2937; }
            .topic-tag { font-size: 12px; color: #6b7280; }
            
            .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
            .badge.easy { background: #dcfce7; color: #166534; }
            .badge.medium { background: #fef08a; color: #854d0e; }
            .badge.hard { background: #fee2e2; color: #991b1b; }
            
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .nav-btn { background: #10b981; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold;}
            .logout-btn { background: #dc2626; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold;}
            
            #leaderboard-section { display: none; background: #f8fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 25px; }
        </style>
    </head>
    <body>
        
        <div class="container" id="login-view" style="display: none;">
            <h1>🚀 DSA Tracker</h1>
            <div class="subtitle">Secure your progress with GitHub</div>
            <button class="auth-btn" onclick="window.location.href='/auth/login'">Sign in with GitHub</button>
        </div>

        <div class="container" id="dashboard-view" style="display: none;">
            <div class="header-bar">
                <h1 style="margin: 0;">🚀 DSA Tracker</h1>
                <div style="display: flex; gap: 10px;">
                    <button class="nav-btn" onclick="toggleLeaderboard()">🏆 Leaderboard</button>
                    <button class="logout-btn" onclick="window.location.href='/auth/logout'">Logout <span id="username-display"></span></button>
                </div>
            </div>
            <div class="subtitle">Log your daily LeetCode and coding problems</div>
            
            <!-- Leaderboard View -->
            <div id="leaderboard-section">
                <h2 style="margin-top: 0; font-size: 18px; color: #1e293b; text-align: center;">🏆 Palm Hostel Room 101 Leaderboard</h2>
                <ul class="progress-list" id="leaderboard-list" style="margin-top: 15px;"></ul>
            </div>

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
            <button class="submit-btn" onclick="addProgress()">Log Progress</button>
            
            <ul class="progress-list" id="list"></ul>
        </div>
        
        <script>
            function getCookie(name) {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return null;
            }

            const activeUser = getCookie('github_user');

            if (!activeUser) {
                document.getElementById('login-view').style.display = 'block';
            } else {
                document.getElementById('dashboard-view').style.display = 'block';
                document.getElementById('username-display').innerText = `(${activeUser})`;
                loadProgress();
            }

            async function toggleLeaderboard() {
                const lbSection = document.getElementById('leaderboard-section');
                if (lbSection.style.display === 'none') {
                    lbSection.style.display = 'block';
                    
                    const response = await fetch('/api/leaderboard');
                    if (response.ok) {
                        const data = await response.json();
                        const list = document.getElementById('leaderboard-list');
                        list.innerHTML = '';
                        const medals = ['🥇', '🥈', '🥉'];
                        
                        data.forEach((user, index) => {
                            let rank = index < 3 ? medals[index] : `<span style="font-size: 14px; font-weight: bold; color: #64748b;">${index + 1}.</span>`;
                            list.innerHTML += `
                            <li class="progress-item" style="justify-content: flex-start; gap: 15px; padding: 10px 15px;">
                                <div style="width: 25px; text-align: center;">${rank}</div>
                                <strong style="color: #1f2937; font-size: 16px;">${user.username}</strong>
                                <span class="badge easy" style="margin-left: auto;">${user.solved} solved</span>
                            </li>`;
                        });
                    }
                } else {
                    lbSection.style.display = 'none';
                }
            }

            async function loadProgress() {
                const response = await fetch('/api/progress');
                if (response.status === 401) {
                    window.location.href = '/auth/login';
                    return;
                }
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
                if (!problemNum) {
                    alert("Please enter a problem number.");
                    return;
                }

                const btn = document.querySelector('.submit-btn');
                btn.innerText = "Pushing to GitHub...";
                btn.style.background = "#6b7280";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                btn.innerText = "Log Progress";
                btn.style.background = "#3b82f6";
                
                if (!response.ok) {
                    alert("Error: " + (data.detail || "Authentication required")); 
                    return;
                }
                
                document.getElementById('problem').value = '';
                loadProgress();
                
                // Refresh leaderboard if it is currently open
                if (document.getElementById('leaderboard-section').style.display === 'block') {
                    document.getElementById('leaderboard-section').style.display = 'none';
                    toggleLeaderboard();
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/progress")
def get_progress(github_user: Optional[str] = Cookie(None)):
    if not github_user:
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")
    
    items = list(collection.find({"username": github_user}, {"_id": 0}))
    return items

@app.post("/api/progress")
def add_progress(req: ProgressRequest, github_user: Optional[str] = Cookie(None)):
    if not github_user:
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")

    if collection.find_one({"username": github_user, "frontend_id": req.problem_number}):
        raise HTTPException(status_code=400, detail=f"LeetCode {req.problem_number} is already marked as solved!")
    
    prob_data = fetch_leetcode_data(req.problem_number)
    if not prob_data:
        raise HTTPException(status_code=404, detail="Invalid LeetCode problem number.")
    
    new_doc = {
        "username": github_user,
        "frontend_id": req.problem_number,
        "problem": prob_data["title"], 
        "topic": prob_data["topic"], 
        "difficulty": prob_data["difficulty"]
    }
    collection.insert_one(new_doc)

    user_record = users_collection.find_one({"username": github_user})
    if user_record and "access_token" in user_record:
        push_to_github(
            username=github_user, 
            token=user_record["access_token"], 
            prob_id=req.problem_number, 
            title=prob_data["title"], 
            topic=prob_data["topic"], 
            difficulty=prob_data["difficulty"]
        )

    return {"status": "success", "added": prob_data["title"]}

@app.get("/api/leaderboard")
def get_leaderboard(github_user: Optional[str] = Cookie(None)):
    if not github_user:
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")
    
    # Run an aggregation pipeline to group by username and sum the total solved problems
    pipeline = [
        {"$group": {"_id": "$username", "solved": {"$sum": 1}}},
        {"$sort": {"solved": -1}},
        {"$limit": 10}
    ]
    results = list(collection.aggregate(pipeline))
    
    # Format the data cleanly for the frontend
    leaderboard = [{"username": r["_id"], "solved": r["solved"]} for r in results]
    return leaderboard