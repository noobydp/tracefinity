from __future__ import annotations

import asyncio
from datetime import datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import ensure_user_dirs
from app.models.schemas import Point, Polygon, Session
from app.services.tool_labeler import (
    ToolLabeler,
    ToolLabelerConfig,
    parse_labels_response,
    parse_label_response,
    validate_label,
)


def _square_poly(label: str = "tool 1") -> Polygon:
    return Polygon(
        id="poly-1",
        label=label,
        points=[
            Point(x=10, y=10),
            Point(x=90, y=10),
            Point(x=90, y=90),
            Point(x=10, y=90),
        ],
    )


def test_disabled_provider_keeps_fallback_labels(tmp_path):
    image_path = tmp_path / "tool.png"
    cv2.imwrite(str(image_path), np.full((120, 120, 3), 255, dtype=np.uint8))
    polygons = [_square_poly()]

    labeler = ToolLabeler(ToolLabelerConfig(provider="none"))

    result = asyncio.run(labeler.label_polygons(str(image_path), polygons))

    assert result[0].label == "tool 1"


def test_parse_valid_ollama_json_label():
    assert (
        parse_label_response('{"name":"Needle Nose Pliers","confidence":0.82}')
        == "needle nose pliers"
    )


def test_parse_batch_labels_from_contact_sheet_response():
    labels = parse_labels_response(
        '{"labels":[{"id":1,"name":"Needle Nose Pliers"},{"id":2,"name":"caliper"}]}',
        2,
    )

    assert labels == {1: "needle nose pliers", 2: "caliper"}


@pytest.mark.parametrize(
    "name",
    [
        "",
        "unknown",
        "object",
        "this name is far too long to be a useful short tool label",
        "one two three four five",
    ],
)
def test_rejects_unusable_names(name):
    assert validate_label(name) is None


def test_labeler_uses_fallback_when_ollama_fails(tmp_path, monkeypatch):
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tool.png"
    cv2.imwrite(str(image_path), image)

    async def fail_label(_self, _sheet, _provider):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(ToolLabeler, "_label_contact_sheet", fail_label)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama"))

    polygons = asyncio.run(labeler.label_polygons(str(image_path), [_square_poly("old")]))

    assert polygons[0].label == "tool 1"


def test_labeler_labels_polygons_in_one_batch(tmp_path, monkeypatch):
    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    cv2.rectangle(image, (130, 10), (210, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tools.png"
    cv2.imwrite(str(image_path), image)

    polygons = [
        _square_poly("tool 1"),
        Polygon(
            id="poly-2",
            label="tool 2",
            points=[
                Point(x=130, y=10),
                Point(x=210, y=10),
                Point(x=210, y=90),
                Point(x=130, y=90),
            ],
        ),
    ]
    calls = 0

    async def label_sheet(_self, sheet, provider):
        nonlocal calls
        calls += 1
        assert provider == "ollama"
        assert sheet.startswith(b"\x89PNG")
        return '{"labels":[{"id":1,"name":"pliers"},{"id":2,"name":"digital caliper"}]}'

    monkeypatch.setattr(ToolLabeler, "_label_contact_sheet", label_sheet)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama"))

    result = asyncio.run(labeler.label_polygons(str(image_path), polygons))

    assert calls == 1
    assert [p.label for p in result] == ["pliers", "digital caliper"]


def test_labeler_retries_empty_batch_response(tmp_path, monkeypatch):
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tool.png"
    cv2.imwrite(str(image_path), image)

    calls = 0

    async def label_sheet(_self, _sheet, _provider):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ""
        return '{"labels":[{"id":1,"name":"screwdriver"}]}'

    monkeypatch.setattr(ToolLabeler, "_label_contact_sheet", label_sheet)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama", attempts=2))

    result = asyncio.run(labeler.label_polygons(str(image_path), [_square_poly("tool 1")]))

    assert calls == 2
    assert result[0].label == "screwdriver"


def test_labeler_retries_partial_batch_response(tmp_path, monkeypatch):
    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    cv2.rectangle(image, (130, 10), (210, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tools.png"
    cv2.imwrite(str(image_path), image)

    polygons = [
        _square_poly("tool 1"),
        Polygon(
            id="poly-2",
            label="tool 2",
            points=[
                Point(x=130, y=10),
                Point(x=210, y=10),
                Point(x=210, y=90),
                Point(x=130, y=90),
            ],
        ),
    ]
    calls = 0

    async def label_sheet(_self, _sheet, _provider):
        nonlocal calls
        calls += 1
        if calls == 1:
            return '{"labels":[{"id":1,"name":"pliers"}]}'
        return '{"labels":[{"id":1,"name":"pliers"},{"id":2,"name":"caliper"}]}'

    monkeypatch.setattr(ToolLabeler, "_label_contact_sheet", label_sheet)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama", attempts=2))

    result = asyncio.run(labeler.label_polygons(str(image_path), polygons))

    assert calls == 2
    assert [p.label for p in result] == ["pliers", "caliper"]


def test_save_tools_from_session_persists_polygon_label(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    routes._store_cache.clear()

    sessions, tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[_square_poly("needle nose pliers")],
        ),
    )

    client = TestClient(app)
    response = client.post("/api/sessions/session-1/save-tools", json={"polygon_ids": ["poly-1"]})

    assert response.status_code == 200
    [tool_id] = response.json()["tool_ids"]
    assert tools.get(tool_id).name == "needle nose pliers"


def test_save_tools_from_session_cancels_pending_labels(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    routes._store_cache.clear()

    sessions, tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[_square_poly("tool 1")],
            tool_label_status="pending",
        ),
    )

    client = TestClient(app)
    response = client.post("/api/sessions/session-1/save-tools", json={"polygon_ids": ["poly-1"]})

    assert response.status_code == 200
    [tool_id] = response.json()["tool_ids"]
    assert tools.get(tool_id).name == "tool 1"
    assert sessions.get("session-1").tool_label_status == "idle"


def test_background_labeling_ignores_non_pending_session(tmp_path, monkeypatch):
    from app.api import routes

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    routes._store_cache.clear()

    image_path = tmp_path / "tool.png"
    cv2.imwrite(str(image_path), np.full((120, 120, 3), 255, dtype=np.uint8))

    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[_square_poly("tool 1")],
            tool_label_status="idle",
        ),
    )

    async def fail_if_called(_self, _image_path, _polygons):
        raise AssertionError("labeling should be ignored once the session is not pending")

    monkeypatch.setattr(ToolLabeler, "label_polygons", fail_if_called)

    asyncio.run(
        routes._label_session_polygons_background(
            "default",
            "session-1",
            str(image_path),
            ["poly-1"],
        )
    )

    session = sessions.get("session-1")
    assert session.tool_label_status == "idle"
    assert session.polygons[0].label == "tool 1"
