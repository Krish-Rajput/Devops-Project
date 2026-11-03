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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --canvas: #000000;
                --surface-card: #1a1a1a;
                --surface-soft: #0d0d0d;
                --ink: #ffffff;
                --body: #bbbbbb;
                --hairline: #3c3c3c;
                --m-blue-light: #0066b1;
                --m-blue-dark: #1c69d4;
                --m-red: #e22718;
                --spacing-md: 16px;
                --spacing-lg: 24px;
                --spacing-xl: 40px;
                --spacing-section: 96px;
            }
            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--canvas);
                color: var(--body);
                margin: 0; padding: 0; min-height: 100vh;
                display: flex; flex-direction: column;
                font-weight: 300;
            }
            
            /* Typography */
            h1 { font-size: 56px; font-weight: 700; color: var(--ink); margin: 0; line-height: 1.05; text-transform: uppercase; letter-spacing: -0.5px; }
            h2 { font-size: 40px; font-weight: 700; color: var(--ink); margin: 0 0 var(--spacing-lg) 0; line-height: 1.1; text-transform: uppercase; }
            h3 { font-size: 24px; font-weight: 700; color: var(--ink); margin: 0 0 var(--spacing-md) 0; text-transform: uppercase; }
            .subtitle { font-size: 16px; font-weight: 300; color: var(--body); margin-top: 16px; line-height: 1.5; }

            /* M Tricolor Divider */
            .m-stripe-divider {
                width: 100%; height: 4px;
                background: linear-gradient(90deg, var(--m-blue-light) 0%, var(--m-blue-light) 33.3%, var(--m-blue-dark) 33.3%, var(--m-blue-dark) 66.6%, var(--m-red) 66.6%, var(--m-red) 100%);
            }

            /* Global Header */
            .top-nav {
                background-color: var(--canvas);
                height: 64px; display: flex; align-items: center; justify-content: center;
                border-bottom: 1px solid var(--hairline);
                position: sticky; top: 0; z-index: 100;
            }
            .nav-content {
                width: 100%; max-width: 1440px;
                display: flex; justify-content: space-between; align-items: center;
                padding: 0 var(--spacing-lg);
            }
            .nav-title { font-size: 20px; font-weight: 700; color: var(--ink); text-transform: uppercase; }
            .nav-actions { display: flex; gap: 24px; align-items: center; }

            /* Buttons */
            .button-primary {
                background-color: var(--ink); color: var(--canvas);
                border: none; border-radius: 0px; 
                font-size: 14px; font-weight: 700; line-height: 1.0; letter-spacing: 1.5px; text-transform: uppercase;
                padding: 16px 32px; height: 48px; cursor: pointer; font-family: inherit;
                display: flex; justify-content: center; align-items: center; transition: opacity 0.2s;
            }
            .button-primary:hover { opacity: 0.8; }
            
            .button-outline {
                background: transparent; color: var(--ink); border: 1px solid var(--ink); 
                font-size: 14px; font-weight: 700; line-height: 1.0; letter-spacing: 1.5px; text-transform: uppercase;
                padding: 15px 32px; height: 48px; cursor: pointer; font-family: inherit;
                transition: background 0.2s; border-radius: 0px;
            }
            .button-outline:hover { background: var(--surface-card); }
            
            .text-link {
                background: transparent; color: var(--ink); border: none; 
                font-size: 14px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
                cursor: pointer; font-family: inherit; padding: 0;
            }

            /* Dashboard Layout */
            .dashboard-layout {
                max-width: 1440px; margin: 0 auto; width: 100%; box-sizing: border-box;
                display: grid; grid-template-columns: 2fr 1fr; gap: var(--spacing-xl); padding: var(--spacing-section) var(--spacing-lg);
            }
            @media (max-width: 1024px) {
                .dashboard-layout { grid-template-columns: 1fr; }
            }

            /* Hero Image Band */
            .hero-photo-band {
                width: 100%; min-height: 50vh;
                background: linear-gradient(to right, rgba(0,0,0,0.9) 10%, rgba(0,0,0,0.3)), url('https://images.unsplash.com/photo-1555626906-fcf10d6851b4?q=80&w=2560&auto=format&fit=crop') center/cover;
                display: flex; align-items: center; padding: 0 var(--spacing-lg);
                border-bottom: 1px solid var(--hairline);
            }

            /* Spec Cells (Telemetry) */
            .telemetry-board { display: flex; gap: 2px; margin-bottom: var(--spacing-xl); background: var(--hairline); }
            .spec-cell {
                flex: 1; background-color: var(--surface-soft); padding: var(--spacing-lg);
                display: flex; flex-direction: column; align-items: flex-start;
            }
            .stat-value { font-size: 32px; font-weight: 700; color: var(--ink); margin-bottom: 8px; }
            .stat-label { font-size: 14px; font-weight: 700; color: var(--body); letter-spacing: 1.5px; text-transform: uppercase; }

            /* Forms */
            .form-row { margin-bottom: var(--spacing-md); }
            .text-input {
                width: 100%; padding: 12px 16px; box-sizing: border-box;
                background-color: var(--surface-card); border: 1px solid var(--hairline);
                border-radius: 0px; color: var(--ink); font-size: 16px; font-weight: 300; font-family: inherit;
                height: 48px;
            }
            .text-input::placeholder { color: var(--muted); }
            .text-input:focus { outline: none; border-color: var(--ink); }

            /* Grids & Cards */
            .progress-list { padding: 0; list-style: none; display: flex; flex-direction: column; gap: var(--spacing-md); margin: 0;}
            .feature-photo-card {
                background-color: var(--surface-card); padding: var(--spacing-lg);
                border-radius: 0px; display: flex; justify-content: space-between; align-items: center;
                border: 1px solid var(--hairline);
            }
            .item-info { display: flex; flex-direction: column; gap: 4px; }
            .problem-name { font-weight: 700; color: var(--ink); font-size: 20px; line-height: 1.4; text-transform: uppercase; }
            .topic-tag { font-size: 14px; font-weight: 300; color: var(--body); }
            
            .label-uppercase { 
                font-size: 14px; font-weight: 700; color: var(--ink); text-transform: uppercase; letter-spacing: 1.5px;
            }

            /* Architecture Footer */
            .footer {
                background-color: var(--canvas); padding: 64px var(--spacing-lg); width: 100%; box-sizing: border-box;
                border-top: 1px solid var(--hairline); margin-top: auto;
            }
            .footer-grid {
                max-width: 1440px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--spacing-xl);
            }
            .footer-col h4 { color: var(--ink); font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; margin: 0 0 var(--spacing-md) 0; }
            .footer-col p { color: var(--body); font-size: 14px; font-weight: 300; margin: 0 0 12px 0; }
        </style>
    </head>
    <body>
        
        <div class="m-stripe-divider"></div>
        <div class="top-nav">
            <div class="nav-content">
                <div class="nav-title">DSA PROGRESS TRACKER</div>
                <div class="nav-actions" id="nav-actions-container"></div>
            </div>
        </div>

        <!-- Login Screen -->
        <div id="login-view" style="display: none;">
            <div class="hero-photo-band">
                <div style="max-width: 1440px; margin: 0 auto; width: 100%;">
                    <h1>ENGINEERED<br>FOR STREAKS.</h1>
                    <div class="subtitle" style="max-width: 400px; margin-bottom: 40px;">Secure CI/CD Portfolio Project. True black canvas, sharp geometry, automated tracking.</div>
                    <button class="button-primary" style="width: auto;" onclick="window.location.href='/auth/login'">CONNECT GITHUB</button>
                </div>
            </div>
        </div>

        <!-- Dashboard Screen -->
        <div id="dashboard-view" style="display: none; width: 100%;">
            
            <div class="dashboard-layout">
                <!-- Left Column: Telemetry & Input -->
                <div class="main-column">
                    <h2>TELEMETRY PROFILE</h2>
                    
                    <div class="telemetry-board">
                        <div class="spec-cell">
                            <div class="stat-value" id="total-solved">0</div>
                            <div class="stat-label">TOTAL SOLVED</div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" id="easy-solved">0</div>
                            <div class="stat-label">EASY</div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" id="med-solved">0</div>
                            <div class="stat-label">MEDIUM</div>
                        </div>
                        <div class="spec-cell">
                            <div class="stat-value" id="hard-solved" style="color: var(--m-red);">0</div>
                            <div class="stat-label" style="color: var(--ink);">HARD</div>
                        </div>
                    </div>
                    
                    <div class="feature-photo-card" style="margin-top: var(--spacing-lg); flex-direction: column; align-items: stretch; gap: var(--spacing-md);">
                        <h3 style="font-size: 18px; margin: 0;">LOG PROGRESS</h3>
                        <div class="form-row" style="margin: 0;">
                            <input type="number" id="problem" class="text-input" placeholder="Enter LeetCode Problem Number (e.g., 462)" min="1">
                        </div>
                        <button class="button-outline" id="submit-btn" style="width: 100%;" onclick="addProgress()">
                            <span id="btn-text">PUSH TO GITHUB STREAK</span>
                        </button>
                    </div>
                    
                    <h2 style="margin-top: var(--spacing-section);">YOUR LOGS</h2>
                    <div class="m-stripe-divider" style="margin-bottom: var(--spacing-lg);"></div>
                    <ul class="progress-list" id="list"></ul>
                </div>

                <!-- Right Column: Live Feed & Leaderboard -->
                <div class="side-column">
                    <h2>ROOM 101 LEADERBOARD</h2>
                    <ul class="progress-list" id="leaderboard-list" style="margin-bottom: var(--spacing-section);"></ul>
                    
                    <h2>LIVE FEED</h2>
                    <div class="m-stripe-divider" style="margin-bottom: var(--spacing-lg);"></div>
                    <ul class="progress-list" id="activity-list"></ul>
                </div>
            </div>
            
            <footer class="footer">
                <div class="footer-grid">
                    <div class="footer-col">
                        <h4>FRONTEND UI</h4>
                        <p>BMW M Design System</p>
                        <p>Vanilla JS & CSS3</p>
                        <p>HTMLResponse Rendering</p>
                    </div>
                    <div class="footer-col">
                        <h4>BACKEND CORE</h4>
                        <p>Python 3.11</p>
                        <p>FastAPI Framework</p>
                        <p>LeetCode GraphQL API</p>
                    </div>
                    <div class="footer-col">
                        <h4>DATABASE & AUTH</h4>
                        <p>MongoDB Atlas Cluster</p>
                        <p>GitHub OAuth App</p>
                        <p>Pymongo Driver</p>
                    </div>
                    <div class="footer-col">
                        <h4>DEVOPS PIPELINE</h4>
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
                navActions.innerHTML = `<button class="text-link" onclick="window.location.href='/auth/login'">LOGIN</button>`;
            } else {
                document.getElementById('dashboard-view').style.display = 'block';
                navActions.innerHTML = `
                    <span class="label-uppercase" style="color: var(--body);">${activeUser}</span>
                    <button class="text-link" onclick="window.location.href='/auth/logout'">SIGN OUT</button>
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
                    <li class="feature-photo-card">
                        <div class="item-info">
                            <span class="problem-name">${item.problem}</span>
                            <span class="topic-tag">${item.topic}</span>
                        </div>
                        <span class="label-uppercase">${item.difficulty}</span>
                    </li>`;
                });
                
                document.getElementById('total-solved').innerText = data.length;
                document.getElementById('easy-solved').innerText = easy;
                document.getElementById('med-solved').innerText = med;
                document.getElementById('hard-solved').innerText = hard;
            }

            async function loadLeaderboard() {
                const response = await fetch('/api/leaderboard');
                if (response.ok) {
                    const data = await response.json();
                    const list = document.getElementById('leaderboard-list');
                    list.innerHTML = '';
                    
                    data.forEach((user, index) => {
                        let rankColor = index === 0 ? 'var(--m-red)' : 'var(--ink)';
                        list.innerHTML += `
                        <li class="feature-photo-card" style="padding: 16px 24px; border: none; background: transparent; border-bottom: 1px solid var(--hairline);">
                            <div class="item-info" style="flex-direction: row; align-items: center; gap: 24px;">
                                <div style="font-size: 24px; font-weight: 700; color: ${rankColor}; width: 24px;">${index + 1}</div>
                                <div class="problem-name" style="font-size: 16px;">${user.username}</div>
                            </div>
                            <div class="label-uppercase" style="color: var(--body);">${user.solved} SOLVED</div>
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
                        <li class="feature-photo-card" style="padding: 16px 24px; border: none; background: transparent; flex-direction: column; align-items: flex-start; gap: 8px;">
                            <div class="label-uppercase" style="color: var(--m-blue-light);">${item.username}</div>
                            <div class="subtitle" style="margin: 0; color: var(--ink);">Solved <span style="font-weight: 700;">${item.problem}</span></div>
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
                btnText.innerText = "PROCESSING...";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                
                btn.style.opacity = "1";
                btn.style.pointerEvents = "auto";
                btnText.innerText = "PUSH TO GITHUB STREAK";
                
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