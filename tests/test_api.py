from fastapi.testclient import TestClient

from aliexpress_deals.api import app


def test_health_and_mock_search() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    search_resp = client.get(
        "/search",
        params={"keyword": "keyboard", "provider": "mock", "max_total_cost": 50.0, "free_shipping_only": True},
    )
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert len(data) >= 1
    assert all(item["total_cost"] <= 50.0 for item in data)
    assert all(item["free_shipping"] is True for item in data)
