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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #da291c;
                --primary-active: #b01e0a;
                --canvas: #181818;
                --canvas-elevated: #303030;
                --ink: #ffffff;
                --body: #969696;
                --hairline: #303030;
                --spacing-xs: 16px;
                --spacing-sm: 24px;
                --spacing-md: 32px;
                --spacing-lg: 48px;
                --spacing-xl: 64px;
                --spacing-xxl: 96px;
                --spacing-super: 128px;
            }
            body {
                font-family: 'Inter', -apple-system, sans-serif;
                background-color: var(--canvas);
                color: var(--body);
                margin: 0; padding: 0; min-height: 100vh;
                display: flex; flex-direction: column;
            }
            
            /* Cinematic Hero Band */
            .hero-band-cinema {
                width: 100%; box-sizing: border-box;
                background: linear-gradient(to bottom, rgba(24,24,24,0.4), rgba(24,24,24,1)), url('https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?q=80&w=2560&auto=format&fit=crop') center/cover;
                padding: var(--spacing-super) var(--spacing-lg) var(--spacing-xxl);
                border-bottom: 1px solid var(--hairline);
            }
            .hero-header {
                max-width: 1280px; margin: 0 auto;
                display: flex; justify-content: space-between; align-items: flex-end;
            }

            /* Dashboard Layout */
            .dashboard-layout {
                max-width: 1280px; margin: 0 auto; width: 100%; box-sizing: border-box;
                padding: var(--spacing-xl) var(--spacing-lg) var(--spacing-super);
                display: grid; grid-template-columns: 2fr 1fr; gap: var(--spacing-xl);
                flex: 1;
            }
            @media (max-width: 1024px) {
                .dashboard-layout { grid-template-columns: 1fr; }
                .hero-header { flex-direction: column; align-items: flex-start; gap: var(--spacing-md); }
            }

            /* Typography */
            h1 { font-size: 56px; font-weight: 500; color: var(--ink); margin: 0; line-height: 1.1; letter-spacing: -1.12px; text-transform: uppercase; }
            h2 { font-size: 26px; font-weight: 500; color: var(--ink); margin: 0 0 var(--spacing-sm) 0; line-height: 1.5; letter-spacing: 0.195px; text-transform: uppercase; }
            h3 { font-size: 18px; font-weight: 700; color: var(--ink); margin: 0 0 var(--spacing-xs) 0; text-transform: uppercase; }
            .subtitle { font-size: 18px; font-weight: 400; color: var(--body); margin-top: 8px; line-height: 1.5; }

            /* Buttons */
            .btn-primary {
                width: 100%; padding: 14px 32px; height: 48px;
                background: var(--primary); color: var(--ink);
                border: none; border-radius: 0px; 
                font-size: 14px; font-weight: 700; line-height: 1.0; letter-spacing: 1.4px; text-transform: uppercase;
                cursor: pointer; font-family: inherit; display: flex; justify-content: center; align-items: center;
                transition: background 0.2s;
            }
            .btn-primary:hover { background: var(--primary-active); }
            
            .btn-outline {
                background: transparent; color: var(--ink); border: 1px solid var(--ink); 
                font-size: 13px; font-weight: 600; line-height: 1.4; letter-spacing: 0.65px; text-transform: uppercase;
                cursor: pointer; font-family: inherit; padding: 12px 24px; border-radius: 0px;
                transition: background 0.2s;
            }
            .btn-outline:hover { background: var(--canvas-elevated); }

            /* Telemetry Dash */
            .telemetry-board { display: flex; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
            .spec-cell { flex: 1; }
            .stat-value { font-size: 80px; font-weight: 700; color: var(--primary); margin-bottom: 4px; line-height: 1.0; letter-spacing: -1.6px; }
            .stat-label { font-size: 11px; color: var(--ink); font-weight: 600; letter-spacing: 1.1px; text-transform: uppercase; }
            
            .progress-bar-container { width: 100%; height: 4px; background: var(--canvas-elevated); margin-top: 12px; }
            .progress-bar { height: 100%; background: var(--ink); transition: width 0.5s ease; }
            .progress-bar.hard { background: var(--primary); }
            .progress-bar.medium { background: var(--body); }

            /* Forms */
            .form-row { margin-bottom: var(--spacing-sm); }
            input {
                width: 100%; padding: 14px 16px; box-sizing: border-box;
                background: var(--canvas-elevated); border: 1px solid var(--hairline);
                border-radius: 0px; color: var(--ink); font-size: 14px; font-family: inherit; font-weight: 400;
                height: 48px;
            }
            input::placeholder { color: var(--body); }
            input:focus { outline: none; border-color: var(--ink); }

            /* Lists & Feed */
            .progress-list { padding: 0; list-style: none; display: flex; flex-direction: column; gap: var(--spacing-xs); margin: 0;}
            .progress-item {
                background: transparent; padding: var(--spacing-sm) 0;
                border-bottom: 1px solid var(--hairline); border-radius: 0px; 
                display: flex; justify-content: space-between; align-items: center;
            }
            .item-info { display: flex; flex-direction: column; gap: 4px; }
            .problem-name { font-weight: 700; color: var(--ink); font-size: 18px; line-height: 1.2; }
            .topic-tag { font-size: 13px; color: var(--body); font-weight: 400;}
            .feed-user { color: var(--primary); font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.65px;}
            
            .badge-pill { 
                font-size: 11px; font-weight: 600; color: var(--ink); text-transform: uppercase; letter-spacing: 1.1px;
                background: var(--canvas-elevated); padding: 4px 12px; border-radius: 9999px;
            }

            /* Architecture Footer */
            .footer-dark {
                background: var(--canvas); border-top: 1px solid var(--hairline);
                padding: var(--spacing-xl) var(--spacing-lg); width: 100%; box-sizing: border-box;
            }
            .footer-grid {
                max-width: 1280px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--spacing-lg);
            }
            .footer-col h4 { color: var(--ink); font-size: 11px; text-transform: uppercase; letter-spacing: 1.1px; margin: 0 0 var(--spacing-sm) 0; }
            .footer-col p { color: var(--body); font-size: 13px; margin: 0 0 8px 0; }
        </style>
    </head>
    <body>
        
        <!-- Login Screen -->
        <div id="login-view" style="display: none;">
            <div class="hero-band-cinema" style="min-height: 100vh; display: flex; flex-direction: column; justify-content: flex-end;">
                <div class="hero-header" style="flex-direction: column; align-items: flex-start;">
                    <div>
                        <h1>Scuderia Tracker</h1>
                        <div class="subtitle">Secure CI/CD Portfolio Project</div>
                    </div>
                    <button class="btn-primary" style="max-width: 300px; margin-top: var(--spacing-md);" onclick="window.location.href='/auth/login'">
                        Connect GitHub
                    </button>
                </div>
            </div>
        </div>

        <!-- Dashboard Screen -->
        <div id="dashboard-view" style="display: none; width: 100%;">
            
            <div class="hero-band-cinema">
                <div class="hero-header">
                    <div>
                        <h1>DSA Progress Tracker</h1>
                        <div class="subtitle">Engineering precision. Automated streaks.</div>
                    </div>
                    <button class="btn-outline" onclick="window.location.href='/auth/logout'">Sign out <span id="username-display" style="text-transform: none; letter-spacing: 0;"></span></button>
                </div>
            </div>

            <div class="dashboard-layout">
                <!-- Left Column: Telemetry & Input -->
                <div class="main-column">
                    <h2>Telemetry Profile</h2>
                    
                    <div class="telemetry-board">
                        <div class="spec-cell">
                            <div class="stat-value" id="total-solved">0</div>
                            <div class="stat-label">Total Completed</div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" style="color: var(--ink);" id="easy-solved">0</div>
                            <div class="stat-label">Easy</div>
                            <div class="progress-bar-container"><div class="progress-bar" id="bar-easy" style="width: 0%;"></div></div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" style="color: var(--body);" id="med-solved">0</div>
                            <div class="stat-label">Medium</div>
                            <div class="progress-bar-container"><div class="progress-bar medium" id="bar-med" style="width: 0%;"></div></div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" style="color: var(--primary);" id="hard-solved">0</div>
                            <div class="stat-label">Hard</div>
                            <div class="progress-bar-container"><div class="progress-bar hard" id="bar-hard" style="width: 0%;"></div></div>
                        </div>
                    </div>
                    
                    <div class="form-row" style="margin-top: var(--spacing-lg);">
                        <input type="number" id="problem" placeholder="Enter LeetCode Problem Number (e.g., 462)" min="1">
                    </div>
                    <button class="btn-primary" id="submit-btn" onclick="addProgress()">
                        <span id="btn-text">Push to GitHub Streak</span>
                    </button>
                    
                    <h3 style="margin-top: var(--spacing-xl); border-bottom: 1px solid var(--hairline); padding-bottom: var(--spacing-xs);">Your Logs</h3>
                    <ul class="progress-list" id="list"></ul>
                </div>

                <!-- Right Column: Live Feed & Leaderboard -->
                <div class="side-column">
                    <h2>Room 101 Leaderboard</h2>
                    <ul class="progress-list" id="leaderboard-list" style="margin-bottom: var(--spacing-xl);"></ul>
                    
                    <h2>Live Activity Feed</h2>
                    <ul class="progress-list" id="activity-list"></ul>
                </div>
            </div>
            
            <!-- Architecture Footer -->
            <footer class="footer-dark">
                <div class="footer-grid">
                    <div class="footer-col">
                        <h4>Frontend UI</h4>
                        <p>Ferrari Design System</p>
                        <p>Vanilla JS & CSS3</p>
                        <p>HTMLResponse Rendering</p>
                    </div>
                    <div class="footer-col">
                        <h4>Backend Core</h4>
                        <p>Python 3.11</p>
                        <p>FastAPI Framework</p>
                        <p>LeetCode GraphQL API</p>
                    </div>
                    <div class="footer-col">
                        <h4>Database & Auth</h4>
                        <p>MongoDB Atlas Cluster</p>
                        <p>GitHub OAuth App</p>
                        <p>Pymongo Driver</p>
                    </div>
                    <div class="footer-col">
                        <h4>DevOps Pipeline</h4>
                        <p>GitHub Actions CI/CD</p>
                        <p>Docker Containerization</p>
                        <p>Vercel Production Hosting</p>
                    </div>
                </div>
            </footer>
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
                document.getElementById('dashboard-view').style.display = 'flex';
                document.getElementById('username-display').innerText = `(${activeUser})`;
                loadDashboard();
            }

            async function loadDashboard() {
                await Promise.all([loadProgress(), loadLeaderboard(), loadActivity()]);
            }

            async function loadProgress() {
                const response = await fetch('/api/progress');
                if (response.status === 401) { window.location.href = '/auth/login'; return; }
                const data = await response.json();
                
                let easy = 0, med = 0, hard = 0;
                const list = document.getElementById('list');
                list.innerHTML = '';
                
                data.slice().reverse().forEach((item) => {
                    if (item.difficulty === 'Easy') easy++;
                    if (item.difficulty === 'Medium') med++;
                    if (item.difficulty === 'Hard') hard++;
                    
                    list.innerHTML += `
                    <li class="progress-item">
                        <div class="item-info">
                            <span class="problem-name">${item.problem}</span>
                            <span class="topic-tag">${item.topic}</span>
                        </div>
                        <span class="badge-pill">${item.difficulty}</span>
                    </li>`;
                });
                
                const total = data.length;
                document.getElementById('total-solved').innerText = total;
                document.getElementById('easy-solved').innerText = easy;
                document.getElementById('med-solved').innerText = med;
                document.getElementById('hard-solved').innerText = hard;
                
                document.getElementById('bar-easy').style.width = total ? (easy/total)*100 + '%' : '0%';
                document.getElementById('bar-med').style.width = total ? (med/total)*100 + '%' : '0%';
                document.getElementById('bar-hard').style.width = total ? (hard/total)*100 + '%' : '0%';
            }

            async function loadLeaderboard() {
                const response = await fetch('/api/leaderboard');
                if (response.ok) {
                    const data = await response.json();
                    const list = document.getElementById('leaderboard-list');
                    list.innerHTML = '';
                    
                    data.forEach((user, index) => {
                        list.innerHTML += `
                        <li class="progress-item" style="border:none; padding: 8px 0;">
                            <div style="font-size: 26px; font-weight: 700; color: var(--primary); width: 30px; letter-spacing: -0.36px;">${index + 1}</div>
                            <div class="problem-name" style="flex: 1;">${user.username}</div>
                            <div class="stat-label">${user.solved} solved</div>
                        </li>`;
                    });
                }
            }
            
            async function loadActivity() {
                const response = await fetch('/api/activity');
                if (response.ok) {
                    const data = await response.json();
                    const list = document.getElementById('activity-list');
                    list.innerHTML = '';
                    
                    data.forEach((item) => {
                        list.innerHTML += `
                        <li class="progress-item">
                            <div class="item-info">
                                <span class="feed-user">${item.username}</span>
                                <span class="problem-name" style="font-size: 14px; font-weight: 500;">Solved ${item.problem}</span>
                            </div>
                            <span class="badge-pill" style="background: transparent; border: 1px solid var(--hairline);">${item.difficulty}</span>
                        </li>`;
                    });
                }
            }

            async function addProgress() {
                const problemNum = document.getElementById('problem').value;
                if (!problemNum) { alert("Please enter a problem number."); return; }

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
                
                if (!response.ok) { alert("Error: " + (data.detail || "Authentication required")); return; }
                
                document.getElementById('problem').value = '';
                loadDashboard();
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

@app.get("/api/activity")
def get_activity(github_user: Optional[str] = Cookie(None)):
    if not github_user:
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in.")
    
    # Fetches the 10 most recent globally solved problems across all users
    results = list(collection.find({}, {"_id": 0}).sort("_id", -1).limit(10))
    return results