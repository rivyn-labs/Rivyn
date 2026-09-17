import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_marketing_root_route():
    res = client.get("/")
    assert res.status_code == 200
    assert "Rivyn | AI Log Intelligence & Noise Suppression Platform" in res.text
    assert "marketing.css" in res.text
    assert "Launch Live Console" in res.text

def test_product_and_marketing_aliases():
    res1 = client.get("/product")
    assert res1.status_code == 200
    assert "marketing.css" in res1.text

    res2 = client.get("/marketing")
    assert res2.status_code == 200
    assert "marketing.css" in res2.text

def test_app_and_console_routes():
    res_app = client.get("/app")
    assert res_app.status_code == 200
    assert "style.css" in res_app.text
    assert "Product Overview" in res_app.text

    res_console = client.get("/console")
    assert res_console.status_code == 200
    assert "style.css" in res_console.text

def test_health_check_remains_active():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_static_assets_accessible():
    res_css = client.get("/static/marketing.css")
    assert res_css.status_code == 200
    assert "--accent-cyan" in res_css.text

    res_js = client.get("/static/marketing.js")
    assert res_js.status_code == 200
    assert "sliderVolume" in res_js.text
