from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "Daily DSA Tracker" in response.text 

def test_get_progress():
    response = client.get("/api/progress")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    assert data[0]["topic"] == "Singly Linked List"

def test_add_progress():
    new_item = {"problem": "Test LeetCode Problem", "topic": "Testing"}
    post_response = client.post("/api/progress", json=new_item)
    assert post_response.status_code == 200
    
    get_response = client.get("/api/progress")
    data = get_response.json()
    # Verify the new problem was successfully appended to the list
    assert any(item["problem"] == "Test LeetCode Problem" for item in data)