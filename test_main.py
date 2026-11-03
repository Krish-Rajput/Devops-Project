from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main_ui():
    response = client.get("/")
    assert response.status_code == 200
    # Updated to match the new UI's <title> tag
    assert "DSA Progress Tracker" in response.text 

def test_get_progress_unauthorized():
    response = client.get("/api/progress")
    assert response.status_code == 401

def test_get_progress_authorized():
    response = client.get("/api/progress", cookies={"github_user": "test_pipeline_user"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_add_progress_errors():
    invalid_response = client.post(
        "/api/progress", 
        json={"problem_number": 999999}, 
        cookies={"github_user": "test_pipeline_user"}
    )
    assert invalid_response.status_code == 404
    assert "Invalid LeetCode problem" in invalid_response.json()["detail"]

def test_get_leaderboard_authorized():
    response = client.get("/api/leaderboard", cookies={"github_user": "test_pipeline_user"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)