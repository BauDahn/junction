from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_incluye_transcription():
    body = client.get("/api/health").json()
    assert {"provider", "model", "cala", "transcription"} <= body.keys()
    assert isinstance(body["transcription"], str)


def test_error_404_con_formato_del_contrato():
    response = client.get("/api/no-existe")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_ruta_inexistente_tambien_usa_el_formato():
    response = client.get("/api/no-existe")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_endpoint_de_verificacion_eliminado():
    response = client.post("/api/no-existe")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found" and error["message"]
