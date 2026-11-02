from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

# 1. The Frontend (Web UI)
@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DevOps Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }
            h1 { color: #1a1a1a; font-size: 24px; }
            p { color: #555; }
            button { background-color: #0070f3; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; margin-top: 20px; transition: background 0.3s; }
            button:hover { background-color: #005bb5; }
            #result { margin-top: 25px; font-weight: bold; color: #0070f3; font-size: 18px; min-height: 25px;}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 DevOps Dashboard</h1>
            <p>Deployed automatically via GitHub Actions, Docker, and Vercel.</p>
            <button onclick="checkStatus()">Ping Backend API</button>
            <p id="result"></p>
        </div>
        <script>
            async function checkStatus() {
                document.getElementById('result').innerText = "Pinging server...";
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    document.getElementById('result').innerText = "Status: " + data.status + " 🟢";
                } catch (error) {
                    document.getElementById('result').innerText = "Error connecting to API 🔴";
                }
            }
        </script>
    </body>
    </html>
    """

# 2. The Backend API Endpoint
@app.get("/api/status")
def get_status():
    return {"status": "Online and Healthy", "version": "1.0.0"}