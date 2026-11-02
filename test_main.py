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
    assert len(data) >= 4

def test_add_progress():
    # Test adding a valid problem (using our pre-cached LeetCode 1)
    post_response = client.post("/api/progress", json={"problem_number": 1})
    assert post_response.status_code == 200
    
    # Verify it was added
    get_response = client.get("/api/progress")
    data = get_response.json()
    assert any(item["frontend_id"] == 1 for item in data)
    
    # Test Error 1: Submitting a duplicate problem
    duplicate_response = client.post("/api/progress", json={"problem_number": 1})
    assert duplicate_response.status_code == 400
    assert "already marked as solved" in duplicate_response.json()["detail"]
    
    # Test Error 2: Submitting an invalid problem number
    invalid_response = client.post("/api/progress", json={"problem_number": 999999})
    assert invalid_response.status_code == 404
    assert "Invalid LeetCode problem" in invalid_response.json()["detail"]