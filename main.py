from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# Added 'difficulty' to our database structure
progress_db = [
    {"id": 1, "problem": "LeetCode 141: Linked List Cycle", "topic": "Singly Linked List", "difficulty": "Easy"},
    {"id": 2, "problem": "LeetCode 206: Reverse Linked List", "topic": "Singly Linked List", "difficulty": "Easy"},
]

class ProgressItem(BaseModel):
    problem: str
    topic: str
    difficulty: str

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
            
            /* Dashboard Stats */
            .stats-row { display: flex; gap: 15px; margin-bottom: 25px; }
            .stat-box { flex: 1; background: #f9fafb; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e5e7eb; }
            .stat-value { font-size: 28px; font-weight: bold; color: #3b82f6; }
            .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }

            /* Form Styles */
            .form-row { display: flex; gap: 10px; margin-bottom: 15px; }
            .form-group { flex: 1; }
            input, select { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; font-size: 14px; }
            button { width: 100%; background: #3b82f6; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }
            button:hover { background: #2563eb; }
            
            /* List Styles */
            .progress-list { margin-top: 30px; padding: 0; list-style: none; }
            .progress-item { background: white; padding: 15px; border: 1px solid #e5e7eb; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; transition: 0.2s;}
            .progress-item:hover { box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            
            .item-info { display: flex; flex-direction: column; gap: 4px; }
            .problem-name { font-weight: 600; color: #1f2937; }
            .topic-tag { font-size: 12px; color: #6b7280; }
            
            /* Difficulty Badges */
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
                    <input type="text" id="problem" placeholder="Problem (e.g., LC 234)">
                </div>
                <div class="form-group">
                    <input type="text" id="topic" placeholder="Topic (e.g., Linked List)">
                </div>
                <div class="form-group">
                    <select id="difficulty">
                        <option value="Easy">Easy</option>
                        <option value="Medium">Medium</option>
                        <option value="Hard">Hard</option>
                    </select>
                </div>
            </div>
            <button onclick="addProgress()">Log Progress</button>
            
            <ul class="progress-list" id="list"></ul>
        </div>
        
        <script>
            async function loadProgress() {
                const response = await fetch('/api/progress');
                const data = await response.json();
                
                // Update stats
                document.getElementById('total-solved').innerText = data.length;
                
                const list = document.getElementById('list');
                list.innerHTML = '';
                
                // Reverse data to show newest first
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
                const problem = document.getElementById('problem').value;
                const topic = document.getElementById('topic').value;
                const difficulty = document.getElementById('difficulty').value;
                
                if (!problem || !topic) {
                    alert("Please fill in both the problem and topic.");
                    return;
                }

                await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem, topic, difficulty })
                });
                
                document.getElementById('problem').value = '';
                document.getElementById('topic').value = '';
                loadProgress();
            }

            loadProgress();
        </script>
    </body>
    </html>
    """

@app.get("/api/progress")
def get_progress():
    return progress_db

@app.post("/api/progress")
def add_progress(item: ProgressItem):
    new_id = len(progress_db) + 1
    progress_db.append({"id": new_id, "problem": item.problem, "topic": item.topic, "difficulty": item.difficulty})
    return {"status": "success", "added": item.problem}