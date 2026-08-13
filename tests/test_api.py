from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_config_and_home_are_available(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/config/public").json()["maps_enabled"] is False
    home = client.get("/")
    assert home.status_code == 200
    assert "CivicLens" in home.text


def test_create_list_read_and_nearby_preserve_geojson_order(client, create_report) -> None:
    report = create_report()

    assert report["location"] == {"type": "Point", "coordinates": [101.6869, 3.139]}
    assert report["before_photo"]["analysis"]["accepted"] is True
    assert client.get(f"/api/reports/{report['id']}").json()["title"] == report["title"]
    assert len(client.get("/api/reports", params={"category": "pothole"}).json()) == 1
    nearby = client.get(
        "/api/reports/nearby",
        params={"latitude": 3.139, "longitude": 101.6869, "radius_meters": 500},
    )
    assert [item["id"] for item in nearby.json()] == [report["id"]]


def test_admin_status_update_requires_key(client, create_report) -> None:
    report = create_report()
    endpoint = f"/api/reports/{report['id']}/status"

    assert client.patch(endpoint, json={"status": "in_progress"}).status_code == 401
    updated = client.patch(
        endpoint,
        json={"status": "in_progress"},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"


def test_after_photo_resolves_report_and_stores_change_metrics(
    client,
    create_report,
    after_image_bytes,
) -> None:
    report = create_report()
    response = client.post(
        f"/api/reports/{report['id']}/after-photo",
        files={"photo": ("after.jpg", after_image_bytes, "image/jpeg")},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["status"] == "resolved"
    assert updated["after_photo"] is not None
    assert updated["change_analysis"]["mean_difference_percent"] > 10


def test_delete_removes_report_and_photo(client, create_report) -> None:
    report = create_report()
    photo_path = report["before_photo"]["url"]
    assert client.get(photo_path).status_code == 200

    response = client.delete(
        f"/api/reports/{report['id']}",
        headers={"X-Admin-Key": "test-admin-key"},
    )

    assert response.status_code == 204
    assert client.get(f"/api/reports/{report['id']}").status_code == 404
    assert client.get(photo_path).status_code == 404


def test_upload_validation_rejects_unsupported_and_invalid_files(client) -> None:
    data = {
        "title": "Invalid evidence",
        "category": "other",
        "description": "Test",
        "latitude": "3.139",
        "longitude": "101.6869",
    }
    unsupported = client.post(
        "/api/reports",
        data=data,
        files={"photo": ("evidence.txt", b"hello", "text/plain")},
    )
    invalid = client.post(
        "/api/reports",
        data=data,
        files={"photo": ("evidence.jpg", b"not-an-image", "image/jpeg")},
    )

    assert unsupported.status_code == 415
    assert invalid.status_code == 422
