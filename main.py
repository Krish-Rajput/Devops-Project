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
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-gradient-start: #2477aa;
                --primary-gradient-end: #6461e0;
                --hero-ink: #1a3e6f;
                --body-text: #000000;
                --canvas: #ffffff;
                --surface-lavender: #e2eaff;
                --hairline: #1a3e6f;
                --hairline-soft: #383838;
            }
            body {
                font-family: 'Figtree', 'Helvetica Neue', Helvetica, Arial, sans-serif;
                background-color: var(--canvas);
                color: var(--body-text);
                margin: 0; padding: 60px 20px; min-height: 100vh;
                display: flex; justify-content: center; align-items: flex-start;
            }
            
            .container {
                width: 100%; max-width: 720px;
                background: var(--canvas);
                /* Flat design: No box-shadows */
            }

            /* Typography */
            h1 { font-size: 49.5px; font-weight: 700; color: var(--hero-ink); margin: 0 0 16px 0; line-height: 1.5; }
            h2 { font-size: 36px; font-weight: 700; color: var(--hero-ink); margin: 0 0 24px 0; line-height: 1.67; }
            .subtitle { font-size: 22.5px; font-weight: 500; color: var(--body-text); margin-bottom: 60px; line-height: 1.5; }

            /* Buttons */
            .btn-primary {
                width: 100%; padding: 14px 18px; height: 60px;
                background: linear-gradient(90deg, var(--primary-gradient-start), var(--primary-gradient-end)); 
                color: white;
                border: none; border-radius: 100px; font-size: 18px; font-weight: 700; line-height: 1.56;
                cursor: pointer; font-family: inherit; display: flex; justify-content: center; align-items: center;
                transition: opacity 0.2s;
            }
            .btn-primary:hover { opacity: 0.9; }
            
            .btn-tertiary {
                background: transparent; color: var(--hero-ink); border: none; 
                font-size: 18px; font-weight: 500; line-height: 1.56;
                cursor: pointer; font-family: inherit; padding: 10px 16px; border-radius: 100px;
            }
            .btn-tertiary:hover { background: var(--surface-lavender); }

            /* Stats */
            .stats-row { display: flex; gap: 20px; margin-bottom: 40px; }
            .stat-box {
                flex: 1; background: var(--canvas); padding: 40px 32px;
                border-radius: 20px; border: 1px solid var(--hairline-soft);
                text-align: center;
            }
            .stat-value { font-size: 31.5px; font-weight: 700; color: var(--hero-ink); margin-bottom: 12px; }
            .stat-label { font-size: 18px; color: var(--body-text); font-weight: 400; }

            /* Forms */
            .form-row { margin-bottom: 24px; }
            input {
                width: 100%; padding: 12px 16px; box-sizing: border-box;
                background: var(--canvas); border: 1px solid var(--hairline);
                border-radius: 10px; color: var(--hero-ink); font-size: 18px; font-family: inherit; font-weight: 400;
                height: 48px;
            }
            input::placeholder { color: var(--hairline-soft); }
            input:focus { outline: none; border-width: 2px; }

            /* Lists */
            .progress-list { margin-top: 40px; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 16px;}
            .progress-item {
                background: var(--surface-lavender); padding: 32px 40px;
                border-radius: 20px; display: flex; justify-content: space-between; align-items: center;
            }
            .item-info { display: flex; flex-direction: column; gap: 8px; }
            .problem-name { font-weight: 700; color: var(--hero-ink); font-size: 22.5px; }
            .topic-tag { font-size: 16px; color: var(--body-text); font-weight: 400;}
            
            .badge { font-size: 13.5px; font-weight: 700; color: var(--hero-ink); text-transform: capitalize;}

            /* Leaderboard */
            #leaderboard-section { 
                display: none; background: var(--canvas); 
                border: 1px solid var(--hairline-soft);
                padding: 40px 44px; border-radius: 20px; margin-bottom: 60px; 
            }
            #leaderboard-section h2 { text-align: center; margin-bottom: 32px; }
            #leaderboard-section .progress-item { 
                background: var(--canvas); border: 1px solid var(--hairline-soft); 
                padding: 24px; border-radius: 20px;
            }

            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
        </style>
    </head>
    <body>
        
        <div class="container" id="login-view" style="display: none; text-align: center; margin-top: 10vh;">
            <h1>Tracker your progress. Build your streak.</h1>
            <div class="subtitle">Secure CI/CD Portfolio Project</div>
            <button class="btn-primary" onclick="window.location.href='/auth/login'">
                Connect GitHub to Continue
            </button>
        </div>

        <div class="container" id="dashboard-view" style="display: none;">
            <div class="header-bar">
                <h1 style="margin: 0; font-size: 36px;">Tracker</h1>
                <div style="display: flex; gap: 8px;">
                    <button class="btn-tertiary" onclick="toggleLeaderboard()">Leaderboard</button>
                    <button class="btn-tertiary" onclick="window.location.href='/auth/logout'">Sign out <span id="username-display"></span></button>
                </div>
            </div>
            
            <div id="leaderboard-section">
                <h2>Room 101 Leaderboard</h2>
                <ul class="progress-list" id="leaderboard-list" style="margin-top: 0;"></ul>
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
            <button class="btn-primary" id="submit-btn" onclick="addProgress()">
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
                        
                        data.forEach((user, index) => {
                            list.innerHTML += `
                            <li class="progress-item" style="justify-content: flex-start; gap: 24px;">
                                <div style="font-size: 22.5px; font-weight: 700; color: var(--hero-ink); width: 30px;">${index + 1}</div>
                                <div class="problem-name">${user.username}</div>
                                <div class="badge" style="margin-left: auto;">${user.solved} solved</div>
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
                
                data.slice().reverse().forEach((item) => {
                    list.innerHTML += `
                    <li class="progress-item">
                        <div class="item-info">
                            <span class="problem-name">${item.problem}</span>
                            <span class="topic-tag">${item.topic}</span>
                        </div>
                        <span class="badge">${item.difficulty}</span>
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
                
                btn.style.opacity = "0.7";
                btn.style.pointerEvents = "none";
                btnText.innerText = "Processing...";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                
                btn.style.opacity = "1";
                btn.style.pointerEvents = "auto";
                btnText.innerText = "Push to GitHub Streak";
                
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