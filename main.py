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
        <style>
            :root {
                --brand-blue: #0067b8;
                --brand-blue-hover: #004a7f;
                --ink: #000000;
                --ink-soft: #171717;
                --ink-quiet: #262626;
                --ink-muted: #616161;
                --canvas: #ffffff;
                --surface-1: #f2f2f2;
                --fluent-radius: 2px;
                --fluent-shadow: 0 .1875rem .4375rem 0 rgba(0,0,0,.13), 0 .0625rem .125rem 0 rgba(0,0,0,.11);
                
                --spacing-xs: 7px;
                --spacing-sm: 8px;
                --spacing-md: 12px;
                --spacing-base: 16px;
                --spacing-lg: 20px;
                --spacing-xl: 24px;
                --spacing-2xl: 36px;
                --spacing-3xl: 48px;
                --spacing-4xl: 72px;
            }
            body {
                font-family: "Segoe UI", SegoeUI, "Helvetica Neue", Helvetica, Arial, sans-serif;
                background-color: var(--canvas);
                color: var(--ink);
                margin: 0; padding: 0; min-height: 100vh;
                display: flex; flex-direction: column;
                font-weight: 400;
            }
            
            /* Typography */
            h1 { font-size: 37px; font-weight: 600; color: var(--canvas); margin: 0; line-height: 44.4px; letter-spacing: 0; }
            h2 { font-size: 29px; font-weight: 600; color: var(--ink); margin: 0 0 var(--spacing-md) 0; line-height: 34.8px; letter-spacing: 0; }
            h3 { font-size: 16px; font-weight: 600; color: var(--ink); margin: 0 0 var(--spacing-sm) 0; line-height: 24px; letter-spacing: 0; }
            .subtitle { font-size: 16px; font-weight: 400; color: var(--canvas); margin: 8px 0 var(--spacing-xl) 0; line-height: 24px; }
            .body-text { font-size: 16px; font-weight: 400; color: var(--ink); line-height: 24px; margin-bottom: var(--spacing-md); }
            .body-muted { font-size: 13px; font-weight: 400; color: var(--ink-muted); line-height: 19.5px; }

            /* Global Header */
            .top-nav {
                background-color: var(--canvas);
                height: 54px; display: flex; align-items: center;
                padding: 0 var(--spacing-xl);
                position: sticky; top: 0; z-index: 100;
                box-shadow: 0 1px 0 0 rgba(0,0,0,0.05);
            }
            .nav-content {
                width: 100%; max-width: 1280px; margin: 0 auto;
                display: flex; justify-content: space-between; align-items: center;
            }
            .nav-brand { font-size: 16px; font-weight: 600; color: var(--ink-quiet); display: flex; align-items: center; gap: 8px;}
            .nav-links { display: flex; gap: var(--spacing-base); }
            .nav-link { 
                background: transparent; color: var(--ink-quiet); border: none; 
                font-family: inherit; font-size: 13px; font-weight: 400; line-height: 19.5px;
                padding: 0 var(--spacing-sm); height: 54px; cursor: pointer;
            }

            /* Buttons */
            .button-primary {
                background-color: var(--brand-blue); color: var(--canvas);
                border: none; border-radius: var(--fluent-radius); 
                font-size: 16px; font-weight: 600; line-height: 16px; letter-spacing: 0;
                padding: 10px var(--spacing-md); height: 40px; cursor: pointer; font-family: inherit;
                display: flex; justify-content: center; align-items: center; transition: background 0.2s;
            }
            .button-primary:hover { background-color: var(--brand-blue-hover); }

            /* Hero Section */
            .hero-section {
                width: 100%; background-color: var(--ink);
                background-image: linear-gradient(to right, var(--ink) 35%, rgba(0,0,0,0) 65%), url('https://images.unsplash.com/photo-1627856013091-fed6e4e30025?q=80&w=2560&auto=format&fit=crop');
                background-position: right center; background-size: cover; background-repeat: no-repeat;
                padding: var(--spacing-3xl) var(--spacing-2xl); box-sizing: border-box;
                display: flex; align-items: center; min-height: 480px;
            }
            .hero-content {
                width: 100%; max-width: 1280px; margin: 0 auto;
            }

            /* Product Tile Grid (4-up) */
            .tile-band {
                width: 100%; max-width: 1280px; margin: 0 auto;
                padding: var(--spacing-3xl) 0; box-sizing: border-box;
            }
            .grid-4up {
                display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--spacing-xl);
                padding: 0 var(--spacing-xl);
            }
            @media (max-width: 1024px) { .grid-4up { grid-template-columns: repeat(2, 1fr); } }
            @media (max-width: 640px) { .grid-4up { grid-template-columns: 1fr; } }

            .product-tile {
                background-color: var(--canvas); border-radius: var(--fluent-radius);
                box-shadow: var(--fluent-shadow); display: flex; flex-direction: column;
                height: 100%; overflow: hidden;
            }
            .tile-photo {
                width: 100%; height: 180px; background-color: var(--surface-1);
                object-fit: cover; display: flex; align-items: center; justify-content: center;
                border-bottom: 1px solid rgba(0,0,0,0.05);
            }
            .tile-content {
                padding: var(--spacing-base) var(--spacing-xl) var(--spacing-xl);
                display: flex; flex-direction: column; flex: 1;
            }
            .tile-content h2 { margin-top: var(--spacing-sm); }
            
            /* Business Band (Gray tinted background) */
            .business-band {
                background-color: var(--surface-1); width: 100%;
                padding: var(--spacing-2xl) 0;
            }

            /* Forms */
            .form-row { margin-bottom: var(--spacing-base); width: 100%; }
            .text-input {
                width: 100%; padding: 8px 12px; box-sizing: border-box;
                background-color: var(--canvas); border: 1px solid var(--ink-muted);
                border-radius: var(--fluent-radius); color: var(--ink); font-size: 16px; font-weight: 400; font-family: inherit;
                height: 40px;
            }
            .text-input::placeholder { color: var(--ink-muted); }
            .text-input:focus { outline: none; border: 2px solid var(--brand-blue); padding: 7px 11px; }

            /* Tags */
            .fluent-badge { 
                font-size: 13px; font-weight: 600; color: var(--brand-blue); 
                background-color: transparent; padding: 0; 
                display: inline-block; margin-top: 4px;
            }

            /* Footer */
            .footer {
                background-color: var(--ink-soft); padding: var(--spacing-3xl) var(--spacing-4xl);
                width: 100%; box-sizing: border-box; margin-top: auto;
            }
            .footer-grid {
                max-width: 1280px; margin: 0 auto; display: grid; grid-template-columns: repeat(6, 1fr); gap: var(--spacing-xl);
                margin-bottom: var(--spacing-3xl);
            }
            @media (max-width: 1024px) { .footer-grid { grid-template-columns: repeat(3, 1fr); } }
            @media (max-width: 640px) { .footer-grid { grid-template-columns: 1fr; } }
            
            .footer-col h4 { color: var(--canvas); font-size: 15px; font-weight: 600; margin: 0 0 var(--spacing-base) 0; }
            .footer-col p { margin: 0; }
            .footer-link {
                background: transparent; color: var(--canvas); border: none; 
                font-family: inherit; font-size: 11px; font-weight: 400; line-height: 16px;
                padding: var(--spacing-sm) 0; cursor: pointer; display: block; text-align: left;
            }
            .footer-link:hover { text-decoration: underline; }
            
            .footer-meta {
                max-width: 1280px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center;
                border-top: 1px solid rgba(255,255,255,0.1); padding-top: var(--spacing-xl);
            }
            .language-pill {
                background: transparent; color: var(--canvas); border: none; 
                font-family: inherit; font-size: 11px; font-weight: 400;
                padding: 0 var(--spacing-md); height: 32px; border-radius: 9999px; cursor: pointer;
                display: flex; align-items: center; gap: 8px;
            }
            .language-pill:hover { background-color: rgba(255,255,255,0.1); }
        </style>
    </head>
    <body>
        
        <!-- Global Header -->
        <div class="top-nav">
            <div class="nav-content">
                <div class="nav-brand">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 23 23">
                        <path fill="#f35325" d="M1 1h10v10H1z"/><path fill="#81bc06" d="M12 1h10v10H12z"/><path fill="#05a6f0" d="M1 12h10v10H1z"/><path fill="#ffba08" d="M12 12h10v10H12z"/>
                    </svg>
                    DSA Tracker
                </div>
                <div class="nav-links" id="nav-actions-container"></div>
            </div>
        </div>

        <!-- Login Screen -->
        <div id="login-view" style="display: none;">
            <div class="hero-section">
                <div class="hero-content">
                    <div style="max-width: 500px;">
                        <h1>Automated Progress Tracking</h1>
                        <div class="subtitle">Connect your account to enable CI/CD GitHub streak commits and join the Room 101 leaderboard.</div>
                        <button class="button-primary" style="width: fit-content;" onclick="window.location.href='/auth/login'">Join now</button>
                    </div>
                </div>
            </div>
            
            <div class="tile-band">
                <div style="padding: 0 var(--spacing-xl); max-width: 1280px; margin: 0 auto;"><h2 style="font-size: 24px;">Built for scale</h2></div>
                <div class="grid-4up" style="margin-top: var(--spacing-xl);">
                    <div class="product-tile">
                        <div class="tile-photo"><div style="font-size: 48px;">🚀</div></div>
                        <div class="tile-content">
                            <h3>FastAPI Core</h3>
                            <div class="body-text">High-performance asynchronous backend engineered in Python 3.11.</div>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-photo"><div style="font-size: 48px;">🔒</div></div>
                        <div class="tile-content">
                            <h3>OAuth Security</h3>
                            <div class="body-text">Secure repository access handled entirely via GitHub token federation.</div>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-photo"><div style="font-size: 48px;">🗄️</div></div>
                        <div class="tile-content">
                            <h3>MongoDB Atlas</h3>
                            <div class="body-text">Persistent cloud storage scaling across multiple user documents.</div>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-photo"><div style="font-size: 48px;">⚡</div></div>
                        <div class="tile-content">
                            <h3>Vercel CI/CD</h3>
                            <div class="body-text">Automated testing and zero-downtime deployment pipelines.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Dashboard Screen -->
        <div id="dashboard-view" style="display: none; width: 100%;">
            
            <div class="hero-section" style="min-height: 320px; background-position: center;">
                <div class="hero-content">
                    <div style="max-width: 500px;">
                        <h1 id="hero-title">Welcome back</h1>
                        <div class="subtitle">Your engineering dashboard is active.</div>
                    </div>
                </div>
            </div>

            <!-- Telemetry Row (Consumer Band) -->
            <div class="tile-band">
                <div class="grid-4up">
                    <div class="product-tile">
                        <div class="tile-content" style="padding-top: var(--spacing-xl);">
                            <div class="body-muted">TOTAL COMPLETED</div>
                            <h2 style="font-size: 48px; margin-top: 8px;" id="total-solved">0</h2>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-content" style="padding-top: var(--spacing-xl);">
                            <div class="body-muted">EASY</div>
                            <h2 style="font-size: 48px; margin-top: 8px;" id="easy-solved">0</h2>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-content" style="padding-top: var(--spacing-xl);">
                            <div class="body-muted">MEDIUM</div>
                            <h2 style="font-size: 48px; margin-top: 8px;" id="med-solved">0</h2>
                        </div>
                    </div>
                    <div class="product-tile">
                        <div class="tile-content" style="padding-top: var(--spacing-xl);">
                            <div class="body-muted">HARD</div>
                            <h2 style="font-size: 48px; margin-top: 8px; color: var(--brand-blue);" id="hard-solved">0</h2>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Actions Row (Business Band) -->
            <div class="business-band">
                <div class="tile-band" style="padding: 0;">
                    <div class="grid-4up" style="grid-template-columns: 1fr 2fr;">
                        
                        <!-- Log Progress Tile -->
                        <div class="product-tile">
                            <div class="tile-photo" style="height: 120px; background-color: var(--brand-blue);"><div style="color: white; font-size: 32px; font-weight: 600;">+</div></div>
                            <div class="tile-content">
                                <h2>Log problem</h2>
                                <div class="body-text">Commit to your GitHub streak.</div>
                                <div class="form-row" style="margin-top: auto;">
                                    <input type="number" id="problem" class="text-input" placeholder="LeetCode Number" min="1">
                                </div>
                                <button class="button-primary" id="submit-btn" style="width: 100%;" onclick="addProgress()">
                                    Download now
                                </button>
                            </div>
                        </div>

                        <!-- Leaderboard / Feed Tiles -->
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-xl);">
                            <div class="product-tile" style="box-shadow: none; border: 1px solid rgba(0,0,0,0.1);">
                                <div class="tile-content">
                                    <h3>Room 101 Leaderboard</h3>
                                    <div id="leaderboard-list" style="display: flex; flex-direction: column; gap: var(--spacing-md); margin-top: var(--spacing-md);"></div>
                                </div>
                            </div>
                            
                            <div class="product-tile" style="box-shadow: none; border: 1px solid rgba(0,0,0,0.1);">
                                <div class="tile-content">
                                    <h3>Recent Activity</h3>
                                    <div id="activity-list" style="display: flex; flex-direction: column; gap: var(--spacing-md); margin-top: var(--spacing-md);"></div>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
            
            <!-- Library Row (Enterprise Band) -->
            <div class="tile-band">
                <div style="padding: 0 var(--spacing-xl); max-width: 1280px; margin: 0 auto; margin-bottom: var(--spacing-xl);"><h2>Your Library</h2></div>
                <div class="grid-4up" id="list">
                    <!-- Progress tiles injected here -->
                </div>
            </div>
            
            <footer class="footer">
                <div class="footer-grid">
                    <div class="footer-col">
                        <h4>Frontend UI</h4>
                        <button class="footer-link">Fluent Design System</button>
                        <button class="footer-link">Vanilla JS & CSS3</button>
                        <button class="footer-link">HTMLResponse</button>
                    </div>
                    <div class="footer-col">
                        <h4>Backend Core</h4>
                        <button class="footer-link">Python 3.11</button>
                        <button class="footer-link">FastAPI Framework</button>
                        <button class="footer-link">LeetCode API</button>
                    </div>
                    <div class="footer-col">
                        <h4>Database</h4>
                        <button class="footer-link">MongoDB Atlas</button>
                        <button class="footer-link">Pymongo Driver</button>
                        <button class="footer-link">GitHub OAuth</button>
                    </div>
                    <div class="footer-col">
                        <h4>DevOps</h4>
                        <button class="footer-link">GitHub Actions</button>
                        <button class="footer-link">Docker</button>
                        <button class="footer-link">Vercel</button>
                    </div>
                </div>
                <div class="footer-meta">
                    <button class="language-pill">🌍 English (India)</button>
                    <div style="display: flex; gap: 24px;">
                        <span style="color: var(--canvas); font-size: 11px;">Privacy</span>
                        <span style="color: var(--canvas); font-size: 11px;">Terms</span>
                        <span style="color: var(--canvas); font-size: 11px;">© 2026</span>
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
                navActions.innerHTML = `<button class="nav-link" onclick="window.location.href='/auth/login'">Sign in</button>`;
            } else {
                document.getElementById('dashboard-view').style.display = 'block';
                document.getElementById('hero-title').innerText = activeUser;
                navActions.innerHTML = `<button class="nav-link" onclick="window.location.href='/auth/logout'">Sign out</button>`;
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
                    <div class="product-tile">
                        <div class="tile-content" style="padding-top: var(--spacing-xl);">
                            <h3>${item.problem}</h3>
                            <div class="body-text" style="flex: 1;">${item.topic}</div>
                            <div class="fluent-badge">${item.difficulty}</div>
                        </div>
                    </div>`;
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
                        list.innerHTML += `
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--surface-1); padding-bottom: 8px;">
                            <div style="display: flex; gap: 16px; align-items: center;">
                                <div style="font-size: 16px; font-weight: 600; color: var(--ink-muted); width: 16px;">${index + 1}</div>
                                <div style="font-size: 16px; font-weight: 600;">${user.username}</div>
                            </div>
                            <div class="fluent-badge">${user.solved} solved</div>
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
                        <div style="display: flex; flex-direction: column; gap: 4px; border-bottom: 1px solid var(--surface-1); padding-bottom: 8px;">
                            <div style="font-size: 13px; font-weight: 600; color: var(--brand-blue);">${item.username}</div>
                            <div style="font-size: 13px; color: var(--ink);">Solved ${item.problem}</div>
                        </div>`;
                    });
                }
            }

            async function addProgress() {
                const problemNum = document.getElementById('problem').value;
                if (!problemNum) { alert("Please enter a problem number."); return; }

                const btn = document.getElementById('submit-btn');
                
                btn.style.opacity = "0.7";
                btn.style.pointerEvents = "none";
                btn.innerText = "Processing...";
                
                const response = await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem_number: parseInt(problemNum) })
                });
                
                const data = await response.json();
                
                btn.style.opacity = "1";
                btn.style.pointerEvents = "auto";
                btn.innerText = "Download now";
                
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