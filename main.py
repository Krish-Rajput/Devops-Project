from fastapi import FastAPI, HTTPException, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import httpx
import os
import base64
from pymongo import MongoClient
import certifi
from typing import Optional
import math

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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --brand-green: #1ed760;
                --brand-green-press: #1db954;
                --bg-base: #121212;
                --surface-dark: #181818;
                --surface-mid: #1f1f1f;
                --surface-card: #252525;
                --text-base: #ffffff;
                --text-secondary: #b3b3b3;
                --border-gray: #4d4d4d;
                
                --lc-easy: #00b8a3;
                --lc-med: #ffc01e;
                --lc-hard: #ff375f;
                --lc-track: #2c2c2c;
            }
            body {
                font-family: "Inter", sans-serif;
                background-color: var(--bg-base);
                color: var(--text-base);
                margin: 0; padding: 0; min-height: 100vh;
                display: flex;
            }

            /* Spotify Layout Sidebar */
            .sidebar {
                width: 240px; background-color: var(--bg-base);
                display: flex; flex-direction: column; padding: 24px 12px;
                position: fixed; height: 100vh; box-sizing: border-box;
            }
            .sidebar-logo {
                font-size: 24px; font-weight: 700; color: var(--text-base);
                padding: 0 12px; margin-bottom: 32px; display: flex; align-items: center; gap: 8px;
            }
            .sidebar-nav-item {
                font-size: 14px; font-weight: 700; color: var(--text-secondary);
                padding: 12px; cursor: pointer; border-radius: 4px; transition: color 0.2s;
                text-decoration: none; display: flex; align-items: center;
            }
            .sidebar-nav-item:hover, .sidebar-nav-item.active { color: var(--text-base); }

            /* Main Content Area */
            .main-content {
                margin-left: 240px; flex: 1; display: flex; flex-direction: column;
                background: linear-gradient(180deg, #2b2b2b 0%, var(--bg-base) 100%);
                background-size: 100% 300px; background-repeat: no-repeat;
                min-height: 100vh;
            }
            .top-bar {
                height: 64px; padding: 0 24px; display: flex; justify-content: flex-end; align-items: center;
                position: sticky; top: 0; z-index: 10; background: rgba(18,18,18,0.7); backdrop-filter: blur(8px);
            }
            .user-pill {
                background-color: var(--surface-dark); color: var(--text-base);
                border-radius: 500px; padding: 4px 16px 4px 4px; font-size: 14px; font-weight: 700;
                display: flex; align-items: center; gap: 8px; cursor: pointer;
            }
            .user-avatar { width: 28px; height: 28px; border-radius: 50%; background-color: var(--surface-card); display: flex; align-items: center; justify-content: center; }

            .content-wrapper { padding: 24px; max-width: 1200px; width: 100%; box-sizing: border-box; }

            /* Spotify Typography */
            h1 { font-size: 32px; font-weight: 700; margin: 0 0 24px 0; letter-spacing: -0.5px; }
            h2 { font-size: 24px; font-weight: 700; margin: 0 0 16px 0; letter-spacing: -0.5px; }
            .section-title { margin-top: 32px; margin-bottom: 16px; }

            /* Buttons */
            .button-primary-green {
                background-color: var(--brand-green); color: #000000;
                border: none; border-radius: 500px; 
                font-size: 14px; font-weight: 700; line-height: 1; letter-spacing: 1.4px; text-transform: uppercase;
                padding: 14px 32px; cursor: pointer; font-family: inherit;
                display: inline-flex; justify-content: center; align-items: center; transition: transform 0.1s, background 0.2s;
            }
            .button-primary-green:hover { background-color: #1fdf64; transform: scale(1.04); }
            .button-primary-green:active { background-color: var(--brand-green-press); transform: scale(1); }

            .button-outlined-pill {
                background: transparent; color: var(--text-base); border: 1px solid var(--border-gray); 
                font-size: 12px; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase;
                padding: 8px 16px; border-radius: 500px; cursor: pointer; transition: border 0.2s;
            }
            .button-outlined-pill:hover { border-color: var(--text-base); }

            /* Cards & Inputs */
            .card {
                background-color: var(--surface-dark); border-radius: 8px; padding: 16px;
                transition: background 0.2s;
            }
            .card:hover { background-color: var(--surface-card); }
            
            .text-input-pill {
                width: 100%; padding: 14px 20px; box-sizing: border-box;
                background-color: var(--surface-mid); border: 1px solid transparent;
                border-radius: 500px; color: var(--text-base); font-size: 14px; font-family: inherit;
                box-shadow: inset 0 0 0 1px transparent; transition: box-shadow 0.2s;
            }
            .text-input-pill::placeholder { color: var(--text-secondary); }
            .text-input-pill:focus { outline: none; box-shadow: inset 0 0 0 1px var(--text-secondary); }

            /* LeetCode Telemetry UI - 3 Concentric Rings */
            .lc-dashboard {
                display: flex; gap: 32px; background-color: var(--surface-dark);
                border-radius: 8px; padding: 24px; align-items: center; flex-wrap: wrap;
            }
            .lc-ring-container { position: relative; width: 180px; height: 180px; }
            .lc-ring-svg { transform: rotate(-90deg); width: 100%; height: 100%; }
            .lc-ring-center {
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                display: flex; flex-direction: column; justify-content: center; align-items: center;
            }
            .lc-number-large { font-size: 32px; font-weight: 700; color: var(--text-base); line-height: 1; }
            .lc-number-small { font-size: 14px; font-weight: 600; color: var(--text-secondary); }
            
            .lc-stats-bars { display: flex; flex-direction: column; gap: 12px; flex: 1; min-width: 200px; }
            .lc-stat-block {
                background-color: var(--surface-mid); border-radius: 8px; padding: 12px 16px;
                display: flex; justify-content: space-between; align-items: center;
            }
            .lc-stat-label { font-size: 14px; font-weight: 600; }
            .lc-stat-value { font-size: 16px; font-weight: 700; color: var(--text-base); }

            /* Track Rows */
            .track-row {
                display: flex; align-items: center; padding: 8px 16px; border-radius: 4px;
                transition: background 0.2s;
            }
            .track-row:hover { background-color: var(--surface-card); }
            .track-col-index { width: 32px; color: var(--text-secondary); font-size: 14px; }
            .track-col-main { flex: 1; display: flex; flex-direction: column; }
            .track-title { font-size: 16px; font-weight: 600; color: var(--text-base); margin-bottom: 4px; }
            .track-subtitle { font-size: 14px; font-weight: 400; color: var(--text-secondary); }
            
            .badge {
                font-size: 10.5px; font-weight: 700; text-transform: uppercase;
                background-color: var(--surface-mid); color: var(--text-base);
                padding: 4px 8px; border-radius: 500px; letter-spacing: 1px;
            }
        </style>
    </head>
    <body>

        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="var(--brand-green)"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424c-.18.295-.563.387-.857.207-2.35-1.434-5.305-1.76-8.786-.963-.335.077-.67-.133-.746-.467-.077-.334.132-.67.467-.746 3.805-.873 7.077-.496 9.715 1.115.293.18.386.563.207.854zm1.226-2.735c-.226.368-.7.485-1.07.258-2.686-1.65-6.786-2.13-9.967-1.166-.413.125-.845-.108-.97-.52-.126-.413.107-.845.52-.97 3.65-1.106 8.19-.57 11.23 1.298.37.226.486.7.257 1.07zm.106-2.83c-3.228-1.916-8.544-2.093-11.616-1.16-.498.15-1.018-.13-1.168-.627-.15-.497.13-1.018.628-1.168 3.53-1.07 9.41-.87 13.13 1.344.444.264.59.84.327 1.285-.264.443-.84.59-1.286.326z"/></svg>
                DSA Tracker
            </div>
            <a class="sidebar-nav-item active">Home</a>
            <a class="sidebar-nav-item">Search</a>
            <a class="sidebar-nav-item">Your Library</a>
        </div>

        <!-- Main View -->
        <div class="main-content">
            
            <div class="top-bar">
                <div id="auth-container">
                    <!-- Dynamic Auth UI -->
                </div>
            </div>

            <!-- Login View -->
            <div id="login-view" class="content-wrapper" style="display: none; align-items: center; justify-content: center; min-height: 70vh;">
                <div style="text-align: center; max-width: 400px;">
                    <h1 style="font-size: 48px; margin-bottom: 16px;">Log your progress.</h1>
                    <p style="color: var(--text-secondary); margin-bottom: 32px; font-size: 16px;">Automated CI/CD commits directly to your GitHub streak.</p>
                    <button class="button-primary-green" onclick="window.location.href='/auth/login'">Connect GitHub</button>
                </div>
            </div>

            <!-- Dashboard View -->
            <div id="dashboard-view" class="content-wrapper" style="display: none;">
                <h1 id="greeting-title">Good evening</h1>

                <!-- LeetCode Exact Progress Replica (3 Concentric Rings) -->
                <div class="lc-dashboard" style="margin-bottom: 32px;">
                    <div class="lc-ring-container">
                        <svg class="lc-ring-svg" viewBox="0 0 200 200">
                            <!-- Easy Track & Ring (Outer) -->
                            <circle cx="100" cy="100" r="85" stroke="var(--lc-track)" stroke-width="6" fill="none" />
                            <circle id="svg-easy" cx="100" cy="100" r="85" stroke="var(--lc-easy)" stroke-width="6" fill="none" stroke-linecap="round" />
                            
                            <!-- Medium Track & Ring (Middle) -->
                            <circle cx="100" cy="100" r="75" stroke="var(--lc-track)" stroke-width="6" fill="none" />
                            <circle id="svg-med" cx="100" cy="100" r="75" stroke="var(--lc-med)" stroke-width="6" fill="none" stroke-linecap="round" />
                            
                            <!-- Hard Track & Ring (Inner) -->
                            <circle cx="100" cy="100" r="65" stroke="var(--lc-track)" stroke-width="6" fill="none" />
                            <circle id="svg-hard" cx="100" cy="100" r="65" stroke="var(--lc-hard)" stroke-width="6" fill="none" stroke-linecap="round" />
                        </svg>
                        <div class="lc-ring-center">
                            <div><span class="lc-number-large" id="lc-total-num">0</span><span class="lc-number-small">/4100</span></div>
                            <div style="font-size: 14px; color: var(--text-secondary); margin-top: 4px;">✓ Solved</div>
                        </div>
                    </div>
                    
                    <div class="lc-stats-bars">
                        <div class="lc-stat-block">
                            <span class="lc-stat-label" style="color: var(--lc-easy);">Easy</span>
                            <span class="lc-stat-value"><span id="lc-easy-num">0</span><span style="color:var(--text-secondary); font-size: 12px; font-weight:600;">/975</span></span>
                        </div>
                        <div class="lc-stat-block">
                            <span class="lc-stat-label" style="color: var(--lc-med);">Med.</span>
                            <span class="lc-stat-value"><span id="lc-med-num">0</span><span style="color:var(--text-secondary); font-size: 12px; font-weight:600;">/2138</span></span>
                        </div>
                        <div class="lc-stat-block">
                            <span class="lc-stat-label" style="color: var(--lc-hard);">Hard</span>
                            <span class="lc-stat-value"><span id="lc-hard-num">0</span><span style="color:var(--text-secondary); font-size: 12px; font-weight:600;">/987</span></span>
                        </div>
                    </div>
                </div>

                <!-- Control Panel -->
                <div style="display: flex; gap: 24px; margin-bottom: 40px; align-items: center;">
                    <button class="button-primary-green" id="submit-btn" onclick="addProgress()" style="padding: 14px 48px; border-radius: 500px; font-size: 16px;">Commit to Streak</button>
                    <input type="number" id="problem" class="text-input-pill" style="max-width: 300px;" placeholder="LeetCode Problem ID (e.g., 462)" min="1">
                </div>

                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 32px;">
                    <!-- Track List (Logs) -->
                    <div>
                        <h2 class="section-title" style="margin-top: 0;">Your Top Tracks</h2>
                        <div id="list" style="display: flex; flex-direction: column; gap: 4px;"></div>
                    </div>
                    
                    <!-- Right Rail (Leaderboard & Feed) -->
                    <div>
                        <h2 class="section-title" style="margin-top: 0;">Room 101 Leaderboard</h2>
                        <div id="leaderboard-list" style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 32px;"></div>
                        
                        <h2 class="section-title">Friend Activity</h2>
                        <div id="activity-list" style="display: flex; flex-direction: column; gap: 4px;"></div>
                    </div>
                </div>

            </div>
        </div>
        
        <script>
            // LeetCode Max Constants
            const MAX_EASY = 975;
            const MAX_MED = 2138;
            const MAX_HARD = 987;
            
            // Circumferences for the 3 distinct rings
            const CIRC_EASY = 2 * Math.PI * 85;
            const CIRC_MED = 2 * Math.PI * 75;
            const CIRC_HARD = 2 * Math.PI * 65;

            function getCookie(name) {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return null;
            }

            const activeUser = getCookie('github_user');
            const authContainer = document.getElementById('auth-container');

            if (!activeUser) {
                document.getElementById('login-view').style.display = 'flex';
                authContainer.innerHTML = `<button class="button-outlined-pill" onclick="window.location.href='/auth/login'">Log In</button>`;
            } else {
                document.getElementById('dashboard-view').style.display = 'block';
                
                let hour = new Date().getHours();
                let greet = "Good evening";
                if(hour < 12) greet = "Good morning";
                else if (hour < 17) greet = "Good afternoon";
                document.getElementById('greeting-title').innerText = greet;
                
                authContainer.innerHTML = `
                    <div class="user-pill" onclick="window.location.href='/auth/logout'">
                        <div class="user-avatar"><svg width="16" height="16" fill="#fff" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg></div>
                        ${activeUser}
                    </div>
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
                
                data.slice().reverse().forEach((item, index) => {
                    if (item.difficulty === 'Easy') easy++;
                    if (item.difficulty === 'Medium') med++;
                    if (item.difficulty === 'Hard') hard++;
                    
                    list.innerHTML += `
                    <div class="track-row">
                        <div class="track-col-index">${index + 1}</div>
                        <div class="track-col-main">
                            <div class="track-title">${item.problem}</div>
                            <div class="track-subtitle">${item.topic}</div>
                        </div>
                        <div class="badge">${item.difficulty}</div>
                    </div>`;
                });
                
                const total = data.length;
                
                document.getElementById('lc-total-num').innerText = total;
                document.getElementById('lc-easy-num').innerText = easy;
                document.getElementById('lc-med-num').innerText = med;
                document.getElementById('lc-hard-num').innerText = hard;

                // Update Concentric Rings Independently
                const easyArc = (easy / MAX_EASY) * CIRC_EASY;
                const medArc = (med / MAX_MED) * CIRC_MED;
                const hardArc = (hard / MAX_HARD) * CIRC_HARD;

                const easyRing = document.getElementById('svg-easy');
                const medRing = document.getElementById('svg-med');
                const hardRing = document.getElementById('svg-hard');

                easyRing.style.strokeDasharray = `${easyArc} ${CIRC_EASY}`;
                easyRing.style.strokeDashoffset = `0`;
                
                medRing.style.strokeDasharray = `${medArc} ${CIRC_MED}`;
                medRing.style.strokeDashoffset = `0`;
                
                hardRing.style.strokeDasharray = `${hardArc} ${CIRC_HARD}`;
                hardRing.style.strokeDashoffset = `0`;
            }

            async function loadLeaderboard() {
                const response = await fetch('/api/leaderboard');
                if (response.ok) {
                    const data = await response.json();
                    const list = document.getElementById('leaderboard-list');
                    list.innerHTML = '';
                    
                    data.forEach((user, index) => {
                        list.innerHTML += `
                        <div class="track-row" style="padding: 12px 16px;">
                            <div class="track-col-index" style="width: 24px; font-weight:700;">${index + 1}</div>
                            <div class="track-col-main">
                                <div class="track-title" style="font-size: 14px;">${user.username}</div>
                            </div>
                            <div style="font-size: 14px; font-weight: 700;">${user.solved}</div>
                        </div>`;
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
                        <div class="track-row" style="padding: 12px 16px;">
                            <div class="track-col-main">
                                <div class="track-title" style="font-size: 14px;">${item.username}</div>
                                <div class="track-subtitle">Solved ${item.problem}</div>
                            </div>
                        </div>`;
                    });
                }
            }

            async function addProgress() {
                const problemNum = document.getElementById('problem').value;
                if (!problemNum) { alert("Please enter a problem number."); return; }

                const btn = document.getElementById('submit-btn');
                
                btn.style.pointerEvents = "none";
                btn.style.transform = "scale(0.95)";
                btn.innerText = "COMMITTING...";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                
                btn.style.pointerEvents = "auto";
                btn.style.transform = "scale(1)";
                btn.innerText = "COMMIT TO STREAK";
                
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