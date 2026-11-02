from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "DSA Tracker" in response.text 

def test_get_progress():
    response = client.get("/api/progress")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

def test_add_progress():
    new_item = {"problem": "Test Problem", "topic": "Testing", "difficulty": "Medium"}
    post_response = client.post("/api/progress", json=new_item)
    assert post_response.status_code == 200