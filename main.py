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
    <html lang="en">
    <head>
        <title>DSA Progress Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            
            /* Animated Background */
            @keyframes gradientBG {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            body {
                font-family: 'Inter', sans-serif;
                margin: 0; padding: 20px; min-height: 100vh;
                display: flex; justify-content: center; align-items: flex-start;
                background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #1e293b);
                background-size: 400% 400%;
                animation: gradientBG 15s ease infinite;
                color: #f8fafc;
            }

            /* Glassmorphism Container */
            .container {
                background: rgba(15, 23, 42, 0.6);
                backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 40px; border-radius: 24px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                width: 100%; max-width: 650px; margin-top: 4vh;
                animation: slideUp 0.6s ease-out;
            }
            @keyframes slideUp {
                from { opacity: 0; transform: translateY(40px); }
                to { opacity: 1; transform: translateY(0); }
            }

            h1 { text-align: center; font-size: 32px; font-weight: 800; margin: 0 0 5px 0; background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .subtitle { text-align: center; color: #94a3b8; font-size: 14px; margin-bottom: 30px; }

            /* Stats */
            .stats-row { display: flex; gap: 20px; margin-bottom: 30px; }
            .stat-box {
                flex: 1; background: rgba(255, 255, 255, 0.03); padding: 20px;
                border-radius: 16px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.05);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }
            .stat-box:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px -5px rgba(56, 189, 248, 0.2);
                border-color: rgba(56, 189, 248, 0.4);
            }
            .stat-value { font-size: 36px; font-weight: 800; color: #e0e7ff; margin-bottom: 5px; }
            .stat-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;}

            /* Inputs & Buttons */
            .form-row { margin-bottom: 20px; }
            input {
                width: 100%; padding: 15px; box-sizing: border-box;
                background: rgba(0, 0, 0, 0.2); border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px; color: white; font-size: 16px; text-align: center;
                transition: all 0.3s ease;
            }
            input:focus { outline: none; border-color: #38bdf8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.3); }
            input::placeholder { color: #64748b; }

            .submit-btn {
                width: 100%; padding: 15px;
                background: linear-gradient(45deg, #2563eb, #4f46e5); color: white;
                border: none; border-radius: 12px; font-size: 16px; font-weight: bold;
                cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
                display: flex; justify-content: center; align-items: center; gap: 10px;
            }
            .submit-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(37, 99, 235, 0.6); }
            .submit-btn:active { transform: scale(0.98); }

            .auth-btn { 
                width: 100%; padding: 15px; background: rgba(255,255,255,0.1); color: white; 
                border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; font-size: 16px; 
                font-weight: 600; cursor: pointer; transition: all 0.3s ease; 
                display: flex; justify-content: center; align-items: center; gap: 10px; 
            }
            .auth-btn:hover { background: rgba(255,255,255,0.2); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(255,255,255,0.1);}

            /* Lists */
            .progress-list { margin-top: 30px; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 12px;}
            .progress-item {
                background: rgba(255, 255, 255, 0.03); padding: 18px 20px;
                border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px;
                display: flex; justify-content: space-between; align-items: center;
                transition: all 0.3s ease; animation: fadeIn 0.5s ease-out forwards; opacity: 0;
            }
            .progress-item:hover { transform: translateX(5px); background: rgba(255, 255, 255, 0.06); border-color: rgba(255, 255, 255, 0.1); }
            @keyframes fadeIn { to { opacity: 1; } }

            .item-info { display: flex; flex-direction: column; gap: 6px; }
            .problem-name { font-weight: 600; color: #f8fafc; font-size: 15px; }
            .topic-tag { font-size: 12px; color: #94a3b8; display: flex; align-items: center; gap: 5px;}

            /* Badges */
            .badge { padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
            .badge.easy { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
            .badge.medium { background: rgba(234, 179, 8, 0.15); color: #fde047; border: 1px solid rgba(234, 179, 8, 0.3); }
            .badge.hard { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }

            /* Header Controls */
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 20px;}
            .nav-btn { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: bold; transition: all 0.3s ease;}
            .nav-btn:hover { background: rgba(16, 185, 129, 0.25); transform: translateY(-2px); box-shadow: 0 4px 10px rgba(16,185,129,0.2);}
            .logout-btn { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: bold; transition: all 0.3s ease;}
            .logout-btn:hover { background: rgba(239, 68, 68, 0.25); transform: translateY(-2px); box-shadow: 0 4px 10px rgba(239,68,68,0.2);}

            #leaderboard-section { display: none; background: rgba(0,0,0,0.2); padding: 25px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 30px; animation: slideDown 0.4s ease-out; }
            @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
            
            /* Loading Spinner */
            .spinner { display: inline-block; width: 18px; height: 18px; border: 3px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite;}
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        
        <div class="container" id="login-view" style="display: none;">
            <div style="text-align: center; font-size: 40px; margin-bottom: 10px;">⚡</div>
            <h1>DSA Tracker</h1>
            <div class="subtitle">Secure CI/CD Portfolio Project</div>
            <button class="auth-btn" onclick="window.location.href='/auth/login'">
                <i class="fa-brands fa-github" style="font-size: 20px;"></i> Connect GitHub to Continue
            </button>
        </div>

        <div class="container" id="dashboard-view" style="display: none;">
            <div class="header-bar">
                <h1 style="margin: 0; font-size: 22px;">⚡ Tracker</h1>
                <div style="display: flex; gap: 10px;">
                    <button class="nav-btn" onclick="toggleLeaderboard()"><i class="fa-solid fa-trophy"></i> Rank</button>
                    <button class="logout-btn" onclick="window.location.href='/auth/logout'"><i class="fa-solid fa-right-from-bracket"></i> <span id="username-display"></span></button>
                </div>
            </div>
            
            <div id="leaderboard-section">
                <h2 style="margin-top: 0; font-size: 18px; color: #e0e7ff; text-align: center;"><i class="fa-solid fa-crown" style="color: #fbbf24;"></i> Leaderboard</h2>
                <ul class="progress-list" id="leaderboard-list" style="margin-top: 15px;"></ul>
            </div>

            <div class="stats-row">
                <div class="stat-box">
                    <div class="stat-value" id="total-solved">0</div>
                    <div class="stat-label">Problems Solved</div>
                </div>
            </div>
            
            <div class="form-row">
                <input type="number" id="problem" placeholder="Enter LeetCode Problem Number (e.g., 462)" min="1">
            </div>
            <button class="submit-btn" id="submit-btn" onclick="addProgress()">
                <div class="spinner" id="spinner" style="display: none;"></div>
                <span id="btn-text">Push to GitHub Streak</span>
            </button>
            
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
                document.getElementById('username-display').innerText = `${activeUser}`;
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
                        const medals = ['<i class="fa-solid fa-medal" style="color: #fbbf24; font-size: 20px;"></i>', '<i class="fa-solid fa-medal" style="color: #94a3b8; font-size: 20px;"></i>', '<i class="fa-solid fa-medal" style="color: #b45309; font-size: 20px;"></i>'];
                        
                        data.forEach((user, index) => {
                            let rank = index < 3 ? medals[index] : `<span style="font-size: 16px; font-weight: 800; color: #475569;">${index + 1}</span>`;
                            list.innerHTML += `
                            <li class="progress-item" style="justify-content: flex-start; gap: 20px; padding: 12px 20px;">
                                <div style="width: 30px; text-align: center;">${rank}</div>
                                <strong style="color: #f8fafc; font-size: 17px; letter-spacing: 0.5px;">${user.username}</strong>
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
                
                data.slice().reverse().forEach((item, index) => {
                    let badgeClass = item.difficulty.toLowerCase();
                    let delay = index * 0.1;
                    list.innerHTML += `
                    <li class="progress-item" style="animation-delay: ${delay}s">
                        <div class="item-info">
                            <span class="problem-name">${item.problem}</span>
                            <span class="topic-tag"><i class="fa-solid fa-code" style="font-size: 10px;"></i> ${item.topic}</span>
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

                const btn = document.getElementById('submit-btn');
                const btnText = document.getElementById('btn-text');
                const spinner = document.getElementById('spinner');
                
                // Loading State Animation
                btn.style.background = "rgba(255,255,255,0.1)";
                btn.style.pointerEvents = "none";
                btnText.innerText = "Processing...";
                spinner.style.display = "inline-block";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                
                // Reset Button State
                btn.style.background = "linear-gradient(45deg, #2563eb, #4f46e5)";
                btn.style.pointerEvents = "auto";
                btnText.innerText = "Push to GitHub Streak";
                spinner.style.display = "none";
                
                if (!response.ok) {
                    alert("Error: " + (data.detail || "Authentication required")); 
                    return;
                }
                
                document.getElementById('problem').value = '';
                loadProgress();
                
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
    
    pipeline = [
        {"$group": {"_id": "$username", "solved": {"$sum": 1}}},
        {"$sort": {"solved": -1}},
        {"$limit": 10}
    ]
    results = list(collection.aggregate(pipeline))
    
    leaderboard = [{"username": r["_id"], "solved": r["solved"]} for r in results]
    return leaderboard