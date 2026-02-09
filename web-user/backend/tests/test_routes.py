"""Tests for API routes."""
import pytest
from main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'message' in data


def test_analyze_image_no_file(client):
    """Test image analysis without file."""
    response = client.post('/api/analyze/image')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'error' in data


def test_analyze_video_no_file(client):
    """Test video analysis without file."""
    response = client.post('/api/analyze/video')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'error' in data


def test_traffic_data_endpoint(client):
    """Test traffic data endpoint."""
    response = client.get('/api/traffic/data')
    assert response.status_code == 200
    data = response.get_json()
    # API returns a list of traffic routes
    assert isinstance(data, list)
