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
    # Check that it returns a valid list, even if the database is currently empty
    assert isinstance(data, list) 

def test_add_progress_errors():
    # Test Error: Submitting an invalid problem number ensures the LeetCode API validation works
    invalid_response = client.post("/api/progress", json={"problem_number": 999999})
    assert invalid_response.status_code == 404
    assert "Invalid LeetCode problem" in invalid_response.json()["detail"]