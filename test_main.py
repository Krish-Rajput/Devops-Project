from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main_ui():
    response = client.get("/")
    assert response.status_code == 200
    # Verify the HTML dashboard loads
    assert "DevOps Dashboard" in response.text 

def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    # Verify the backend JSON still works
    assert response.json() == {"status": "Online and Healthy", "version": "1.0.0"}