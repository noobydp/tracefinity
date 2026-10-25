"""Measured tool height is optional metadata, never inferred from a photo."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import routes
from app.config import ensure_user_dirs
from app.main import app
from app.models.schemas import Point, Tool, ToolUpdateRequest
from app.services.tool_store import ToolStore


@pytest.mark.parametrize("height", [0, -1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("model", [Tool, ToolUpdateRequest])
def test_height_rejects_invalid_values(height, model):
    kwargs = {"id": "tool", "name": "Tool", "points": []} if model is Tool else {}
    with pytest.raises(ValidationError):
        model(height_mm=height, **kwargs)


def test_old_tool_height_is_unknown():
    assert Tool(id="old", name="Old tool", points=[]).height_mm is None


def test_height_updates_round_trip_without_changing_tool_or_bin_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.settings, "storage_path", tmp_path)
    monkeypatch.setattr(routes, "_store_cache", {})
    user_path = tmp_path / "default"
    ensure_user_dirs(user_path)
    _, tools, bins = routes.get_stores("default")
    points = [Point(x=-15, y=-40), Point(x=15, y=-40), Point(x=15, y=40), Point(x=-15, y=40)]
    tools.set("tool", Tool(id="tool", name="Tool", points=points, smoothed=False))
    with TestClient(app) as client:
        old = client.get("/api/tools/tool").json()
        assert old["height_mm"] is None
        created = client.post("/api/bins", json={"tool_ids": ["tool"]}).json()
        bin_before = bins.get(created["id"]).model_dump()
        assert client.put("/api/tools/tool", json={"height_mm": 12.5}).status_code == 200
        assert client.get("/api/tools/tool").json()["height_mm"] == 12.5
        assert client.get("/api/tools").json()["tools"][0]["height_mm"] == 12.5
        assert ToolStore(user_path).get("tool").height_mm == 12.5
        assert client.put("/api/tools/tool", json={"name": "Renamed"}).status_code == 200
        assert ToolStore(user_path).get("tool").height_mm == 12.5
        assert client.put("/api/tools/tool", json={"height_mm": -1}).status_code == 422
        assert ToolStore(user_path).get("tool").height_mm == 12.5
        assert client.put("/api/tools/tool", json={"height_mm": None}).status_code == 200
        assert ToolStore(user_path).get("tool").height_mm is None
        assert ToolStore(user_path).get("tool").points == points
        assert bins.get(created["id"]).model_dump() == bin_before
