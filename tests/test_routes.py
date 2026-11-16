def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_index_renders_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "观云台" in response.get_data(as_text=True)


def test_location_presets_do_not_require_network(client):
    response = client.get("/api/locations?q=长春")
    assert response.status_code == 200
    assert response.get_json()["locations"][0]["name"] == "长春"


def test_weather_endpoint_with_fake_service(app, client):
    class FakeWeatherClient:
        def get_dashboard(self, location):
            return {"location": location.to_dict(), "current": {"temperature_2m": 18}}

    app.extensions["weather_client"] = FakeWeatherClient()
    response = client.get("/api/weather?city=长春")
    assert response.status_code == 200
    assert response.get_json()["current"]["temperature_2m"] == 18
