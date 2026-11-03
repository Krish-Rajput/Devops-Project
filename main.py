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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --install-green-top: #a4d007;
                --install-green-mid: #799905;
                --install-green-bottom: #5c7e10;
                --install-highlight: #beee11;
                --cta-cyan-bright: #06bfff;
                --cta-cyan-mid: #2881a7;
                --cta-blue: #2d73ff;
                --canvas: #1b2838;
                --rail: #141f2c;
                --tile: #283645;
                --inset: #384959;
                --on-canvas: #ffffff;
                --subtitle: #c6d4df;
                --body-mute: #8b929a;
                --shadow: #000000;
                --radius-xs: 2px;
            }
            body {
                font-family: Arial, Helvetica, sans-serif;
                background-color: var(--canvas);
                color: var(--subtitle);
                margin: 0; padding: 0; min-height: 100vh;
                display: flex; flex-direction: column;
                font-size: 13px;
            }
            
            h1, h2, h3, .brand-font {
                font-family: 'Inter', sans-serif; /* Motiva Sans fallback */
                color: var(--on-canvas);
                margin: 0;
            }

            /* Global Rail (Header) */
            .primary-nav {
                background-color: var(--rail);
                height: 104px;
                display: flex; align-items: center; justify-content: center;
                box-shadow: inset 0 -1px 0 var(--shadow);
            }
            .nav-content {
                width: 100%; max-width: 940px;
                display: flex; justify-content: space-between; align-items: center;
                padding: 0 16px;
            }
            .nav-title {
                font-size: 26px; font-weight: 500; letter-spacing: 1.104px; text-transform: uppercase;
            }
            .nav-actions { display: flex; gap: 10px; }

            /* Buttons */
            .button-install {
                background: linear-gradient(to bottom, var(--install-green-top), var(--install-green-bottom));
                border: none; border-top: 1px solid var(--install-highlight);
                color: var(--on-canvas); font-family: 'Inter', Arial, sans-serif;
                font-size: 13px; font-weight: 400; border-radius: var(--radius-xs);
                padding: 6px 15px; height: 31px; cursor: pointer;
                display: flex; justify-content: center; align-items: center;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            }
            .button-install:hover { background: var(--install-green-top); }

            .button-cta {
                background: linear-gradient(to bottom, var(--cta-cyan-bright), var(--cta-cyan-mid));
                border: none; border-radius: var(--radius-xs);
                color: var(--on-canvas); font-family: 'Inter', Arial, sans-serif;
                font-size: 13px; font-weight: 400; padding: 6px 12px; height: 31px;
                cursor: pointer; display: flex; justify-content: center; align-items: center;
            }
            .button-cta:hover { background: var(--cta-cyan-bright); }
            
            .button-secondary {
                background-color: var(--inset); border: none; border-radius: var(--radius-xs);
                color: var(--subtitle); font-family: 'Inter', Arial, sans-serif;
                font-size: 13px; font-weight: 400; padding: 6px 12px; height: 31px;
                cursor: pointer;
            }
            .button-secondary:hover { color: var(--on-canvas); }

            /* Dashboard Layout */
            .dashboard-layout {
                max-width: 940px; margin: 24px auto 96px; width: 100%; box-sizing: border-box;
                display: grid; grid-template-columns: 2fr 1fr; gap: 24px; padding: 0 16px;
            }
            @media (max-width: 768px) {
                .dashboard-layout { grid-template-columns: 1fr; }
            }

            /* Featured Strip / Sections */
            .featured-strip {
                background-color: var(--inset); color: var(--on-canvas);
                padding: 16px 24px; border-radius: var(--radius-xs); margin-bottom: 16px;
            }
            .featured-strip h2 { font-size: 24px; font-weight: 300; }
            
            .section-header { font-size: 14px; font-weight: 500; color: var(--on-canvas); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;}

            /* Telemetry Dash (Game Tiles) */
            .telemetry-board { display: flex; gap: 10px; margin-bottom: 24px; }
            .game-tile {
                flex: 1; background-color: var(--tile); padding: 12px;
                border-radius: var(--radius-xs);
            }
            .stat-value { font-family: 'Inter', sans-serif; font-size: 26px; font-weight: 300; color: var(--on-canvas); margin-bottom: 4px; }
            .stat-label { font-size: 11px; color: var(--body-mute); text-transform: uppercase; }
            
            .progress-bar-container { width: 100%; height: 4px; background: var(--rail); margin-top: 8px; border-radius: var(--radius-xs); }
            .progress-bar { height: 100%; background: var(--cta-cyan-mid); border-radius: var(--radius-xs); transition: width 0.5s ease; }
            .progress-bar.hard { background: var(--install-green-mid); }
            .progress-bar.medium { background: var(--cta-blue); }

            /* Forms */
            .form-row { margin-bottom: 16px; }
            .text-input {
                width: 100%; padding: 0 10px; box-sizing: border-box;
                background-color: var(--rail); border: 1px solid var(--inset);
                border-radius: var(--radius-xs); color: var(--on-canvas); font-size: 13px; font-family: Arial, sans-serif;
                height: 34px;
            }
            .text-input::placeholder { color: var(--body-mute); }
            .text-input:focus { outline: none; border-color: var(--cta-cyan-mid); }

            /* Lists & Feed */
            .progress-list { padding: 0; list-style: none; display: flex; flex-direction: column; gap: 5px; margin: 0;}
            .progress-item {
                background-color: var(--tile); padding: 8px 12px;
                border-radius: var(--radius-xs); display: flex; justify-content: space-between; align-items: center;
            }
            .item-info { display: flex; flex-direction: column; gap: 2px; }
            .problem-name { font-family: 'Inter', sans-serif; font-weight: 500; color: var(--on-canvas); font-size: 15px; }
            .topic-tag { font-size: 12px; color: var(--subtitle); }
            .feed-user { color: var(--cta-cyan-link); font-weight: 400; font-size: 12px; }
            
            .category-pill { 
                font-size: 12px; font-weight: 500; color: var(--subtitle); 
                background-color: var(--inset); padding: 4px 8px; border-radius: var(--radius-xs);
            }

            /* Architecture Footer */
            .footer-section {
                background-color: var(--rail); padding: 24px 16px; width: 100%; box-sizing: border-box;
                margin-top: auto; border-top: 1px solid var(--shadow);
            }
            .footer-grid {
                max-width: 940px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px;
            }
            .footer-col h4 { color: var(--on-canvas); font-size: 12px; text-transform: uppercase; margin: 0 0 10px 0; }
            .footer-col p { color: var(--body-mute); font-size: 11px; margin: 0 0 6px 0; line-height: 12px; }
        </style>
    </head>
    <body>
        
        <!-- Global Header -->
        <div class="primary-nav">
            <div class="nav-content">
                <div class="nav-title">DSA PROGRESS TRACKER</div>
                <div class="nav-actions" id="nav-actions-container">
                    <!-- Injected via JS based on auth state -->
                </div>
            </div>
        </div>

        <!-- Login Screen -->
        <div id="login-view" style="display: none;">
            <div class="dashboard-layout" style="grid-template-columns: 1fr; max-width: 600px; text-align: center;">
                <div class="featured-strip">
                    <h2 style="margin-bottom: 16px;">Welcome to the Tracker</h2>
                    <p style="color: var(--subtitle); font-size: 15px; margin-bottom: 24px;">Secure CI/CD Portfolio Project.</p>
                    <button class="button-install" style="margin: 0 auto; width: auto; padding: 6px 32px;" onclick="window.location.href='/auth/login'">
                        Connect GitHub
                    </button>
                </div>
            </div>
        </div>

        <!-- Dashboard Screen -->
        <div id="dashboard-view" style="display: none; width: 100%;">
            
            <div class="dashboard-layout">
                <!-- Left Column: Telemetry & Input -->
                <div class="main-column">
                    <div class="section-header">Telemetry Profile</div>
                    
                    <div class="telemetry-board">
                        <div class="game-tile">
                            <div class="stat-value" id="total-solved">0</div>
                            <div class="stat-label">Total Completed</div>
                        </div>
                        <div class="game-tile">
                            <div class="stat-value" id="easy-solved">0</div>
                            <div class="stat-label">Easy</div>
                            <div class="progress-bar-container"><div class="progress-bar" id="bar-easy" style="width: 0%;"></div></div>
                        </div>
                        <div class="game-tile">
                            <div class="stat-value" id="med-solved">0</div>
                            <div class="stat-label">Medium</div>
                            <div class="progress-bar-container"><div class="progress-bar medium" id="bar-med" style="width: 0%;"></div></div>
                        </div>
                        <div class="game-tile">
                            <div class="stat-value" id="hard-solved">0</div>
                            <div class="stat-label">Hard</div>
                            <div class="progress-bar-container"><div class="progress-bar hard" id="bar-hard" style="width: 0%;"></div></div>
                        </div>
                    </div>
                    
                    <div class="featured-strip" style="background-color: var(--tile);">
                        <div class="form-row">
                            <input type="number" id="problem" class="text-input" placeholder="Enter LeetCode Problem Number (e.g., 462)" min="1">
                        </div>
                        <button class="button-install" id="submit-btn" style="width: 100%;" onclick="addProgress()">
                            <span id="btn-text">Push to GitHub Streak</span>
                        </button>
                    </div>
                    
                    <div class="section-header" style="margin-top: 24px;">Your Library</div>
                    <ul class="progress-list" id="list"></ul>
                </div>

                <!-- Right Column: Live Feed & Leaderboard -->
                <div class="side-column">
                    <div class="section-header">Room 101 Leaderboard</div>
                    <ul class="progress-list" id="leaderboard-list" style="margin-bottom: 24px;"></ul>
                    
                    <div class="section-header">Community Activity</div>
                    <ul class="progress-list" id="activity-list"></ul>
                </div>
            </div>
            
            <!-- Architecture Footer -->
            <footer class="footer-section">
                <div class="footer-grid">
                    <div class="footer-col">
                        <h4 class="brand-font">Frontend UI</h4>
                        <p>Steam Design System</p>
                        <p>Vanilla JS & CSS3</p>
                        <p>HTMLResponse Rendering</p>
                    </div>
                    <div class="footer-col">
                        <h4 class="brand-font">Backend Core</h4>
                        <p>Python 3.11</p>
                        <p>FastAPI Framework</p>
                        <p>LeetCode GraphQL API</p>
                    </div>
                    <div class="footer-col">
                        <h4 class="brand-font">Database & Auth</h4>
                        <p>MongoDB Atlas Cluster</p>
                        <p>GitHub OAuth App</p>
                        <p>Pymongo Driver</p>
                    </div>
                    <div class="footer-col">
                        <h4 class="brand-font">DevOps Pipeline</h4>
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
            const navActions = document.getElementById('nav-actions-container');

            if (!activeUser) {
                document.getElementById('login-view').style.display = 'block';
                navActions.innerHTML = `<button class="button-install" onclick="window.location.href='/auth/login'">Login</button>`;
            } else {
                document.getElementById('dashboard-view').style.display = 'block';
                navActions.innerHTML = `
                    <button class="button-cta" style="pointer-events: none;">${activeUser}</button>
                    <button class="button-secondary" onclick="window.location.href='/auth/logout'">Logout</button>
                `;
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
                        <span class="category-pill">${item.difficulty}</span>
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
                        <li class="progress-item">
                            <div class="item-info" style="flex-direction: row; align-items: center; gap: 12px;">
                                <div style="font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 500; color: var(--on-canvas);">${index + 1}</div>
                                <div class="problem-name" style="font-size: 14px;">${user.username}</div>
                            </div>
                            <div class="topic-tag">${user.solved} solved</div>
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
                        <li class="progress-item" style="flex-direction: column; align-items: flex-start; gap: 4px;">
                            <div class="feed-user">${item.username}</div>
                            <div class="topic-tag">Solved <span style="color: var(--on-canvas); font-family: 'Inter', sans-serif;">${item.problem}</span></div>
                        </li>`;
                    });
                }
            }

            async function addProgress() {
                const problemNum = document.getElementById('problem').value;
                if (!problemNum) { alert("Please enter a problem number."); return; }

                const btn = document.getElementById('submit-btn');
                const btnText = document.getElementById('btn-text');
                
                btn.style.opacity = "0.5";
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
    
    results = list(collection.find({}, {"_id": 0}).sort("_id", -1).limit(10))
    return results