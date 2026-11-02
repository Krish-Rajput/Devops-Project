from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# In-memory database to store progress
progress_db = [
    {"id": 1, "problem": "LeetCode 141: Linked List Cycle", "topic": "Singly Linked List"},
    {"id": 2, "problem": "LeetCode 206: Reverse Linked List", "topic": "Singly Linked List"},
    {"id": 3, "problem": "LeetCode 234: Palindrome Linked List", "topic": "Singly Linked List"},
    {"id": 4, "problem": "LeetCode 876: Middle of the Linked List", "topic": "Singly Linked List"}
]

class ProgressItem(BaseModel):
    problem: str
    topic: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DSA Progress Tracker</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; display: flex; justify-content: center; }
            .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 100%; max-width: 500px; }
            h1 { color: #1a1a1a; font-size: 22px; text-align: center; }
            .form-group { margin-bottom: 15px; }
            input { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; margin-top: 5px; }
            button { width: 100%; background: #0070f3; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; cursor: pointer; transition: background 0.3s; margin-top: 10px; }
            button:hover { background: #005bb5; }
            .progress-list { margin-top: 25px; padding: 0; list-style: none; }
            .progress-item { background: #f9f9f9; padding: 12px; border-left: 4px solid #0070f3; margin-bottom: 10px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;}
            .topic-tag { font-size: 12px; background: #e0e0e0; padding: 4px 8px; border-radius: 12px; color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Daily DSA Tracker</h1>
            
            <div class="form-group">
                <label>Problem Name</label>
                <input type="text" id="problem" placeholder="e.g., Doubly Linked List Insertion">
            </div>
            <div class="form-group">
                <label>Topic</label>
                <input type="text" id="topic" placeholder="e.g., Data Structures">
            </div>
            <button onclick="addProgress()">Log Progress</button>
            
            <ul class="progress-list" id="list"></ul>
        </div>
        <script>
            // Fetch and display the list of completed problems
            async function loadProgress() {
                const response = await fetch('/api/progress');
                const data = await response.json();
                const list = document.getElementById('list');
                list.innerHTML = '';
                data.forEach(item => {
                    list.innerHTML += `<li class="progress-item">
                        <strong>${item.problem}</strong>
                        <span class="topic-tag">${item.topic}</span>
                    </li>`;
                });
            }

            // Submit a new problem to the API
            async function addProgress() {
                const problem = document.getElementById('problem').value;
                const topic = document.getElementById('topic').value;
                if (!problem || !topic) return;

                await fetch('/api/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ problem, topic })
                });
                
                document.getElementById('problem').value = '';
                document.getElementById('topic').value = '';
                loadProgress();
            }

            // Load the initial list when the page opens
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
    progress_db.append({"id": new_id, "problem": item.problem, "topic": item.topic})
    return {"status": "success", "added": item.problem}