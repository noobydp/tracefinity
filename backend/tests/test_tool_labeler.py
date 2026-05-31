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
    parse_label_response,
    validate_label,
    warmup_image_png,
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
    assert parse_label_response('{"name":"Needle Nose Pliers"}') == "needle nose pliers"


def test_warmup_image_exercises_vision_payload():
    png = warmup_image_png()

    assert png.startswith(b"\x89PNG")
    assert len(png) > 100


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

    async def fail_label(_self, _crop, _provider):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(ToolLabeler, "_label_crop", fail_label)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama"))

    polygons = asyncio.run(labeler.label_polygons(str(image_path), [_square_poly("old")]))

    assert polygons[0].label == "tool 1"


def test_labeler_labels_polygons_with_one_query_per_tool(tmp_path, monkeypatch):
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
    calls: list[bytes] = []
    responses = ['{"name":"pliers"}', '{"name":"digital caliper"}']

    async def label_crop(_self, crop, provider):
        assert provider == "ollama"
        assert crop.startswith(b"\x89PNG")
        calls.append(crop)
        return responses[len(calls) - 1]

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama"))

    result = asyncio.run(labeler.label_polygons(str(image_path), polygons))

    assert len(calls) == 2
    assert [p.label for p in result] == ["pliers", "digital caliper"]


def test_labeler_retries_empty_tool_response(tmp_path, monkeypatch):
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tool.png"
    cv2.imwrite(str(image_path), image)

    calls = 0

    async def label_crop(_self, _crop, _provider):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ""
        return '{"name":"screwdriver"}'

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama", attempts=2))

    result = asyncio.run(labeler.label_polygons(str(image_path), [_square_poly("tool 1")]))

    assert calls == 2
    assert result[0].label == "screwdriver"


def test_labeler_keeps_fallback_for_unusable_tool_response(tmp_path, monkeypatch):
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
    responses = ["", '{"name":"caliper"}']
    calls = 0

    async def label_crop(_self, _crop, _provider):
        nonlocal calls
        calls += 1
        return responses[calls - 1]

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)
    labeler = ToolLabeler(ToolLabelerConfig(provider="ollama", attempts=1))

    result = asyncio.run(labeler.label_polygons(str(image_path), polygons))

    assert calls == 2
    assert [p.label for p in result] == ["tool 1", "caliper"]


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


def test_update_polygons_allows_manual_generic_label_and_cancels_pending(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    routes._store_cache.clear()

    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[_square_poly("digital caliper")],
            tool_label_status="pending",
        ),
    )

    client = TestClient(app)
    response = client.put(
        "/api/sessions/session-1/polygons",
        json={"polygons": [_square_poly("tool 1").model_dump()]},
    )

    assert response.status_code == 200
    session = sessions.get("session-1")
    assert session.polygons[0].label == "tool 1"
    assert session.tool_label_status == "idle"


def test_update_polygons_handles_session_without_existing_polygons(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    routes._store_cache.clear()

    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=None,
        ),
    )

    client = TestClient(app)
    response = client.put(
        "/api/sessions/session-1/polygons",
        json={"polygons": [_square_poly("manual name").model_dump()]},
    )

    assert response.status_code == 200
    assert sessions.get("session-1").polygons[0].label == "manual name"


def test_retry_tool_labels_only_retries_generic_names(tmp_path, monkeypatch):
    from app.api import routes
    from app.main import app

    storage_path = tmp_path / "storage"
    user_path = storage_path / "default"
    ensure_user_dirs(user_path)
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    monkeypatch.setattr(routes.settings, "tool_label_provider", "ollama")
    monkeypatch.setattr(routes, "_start_tool_label_warmup", lambda: None)
    routes._store_cache.clear()

    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    cv2.rectangle(image, (130, 10), (210, 90), (0, 0, 0), -1)
    image_path = user_path / "processed" / "corrected.png"
    cv2.imwrite(str(image_path), image)

    poly_2 = Polygon(
        id="poly-2",
        label="tool 2",
        points=[
            Point(x=130, y=10),
            Point(x=210, y=10),
            Point(x=210, y=90),
            Point(x=130, y=90),
        ],
    )
    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            corrected_image_path="default/processed/corrected.png",
            polygons=[_square_poly("manual name"), poly_2],
            tool_label_status="failed",
            tool_label_error="Tool naming failed",
        ),
    )

    calls = 0

    async def label_crop(_self, _crop, _provider):
        nonlocal calls
        calls += 1
        return '{"name":"digital laser measure"}'

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)

    client = TestClient(app)
    response = client.post("/api/sessions/session-1/tool-labels/retry")

    assert response.status_code == 200
    session = sessions.get("session-1")
    assert calls == 1
    assert session.tool_label_status == "complete"
    assert session.tool_label_error is None
    assert [poly.label for poly in session.polygons] == ["manual name", "digital laser measure"]


def test_background_labeling_resolves_pending_session_without_polygons(tmp_path, monkeypatch):
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
            polygons=[],
            tool_label_status="pending",
        ),
    )

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
    assert session.tool_label_error is None


def test_background_labeling_streams_each_returned_label(tmp_path, monkeypatch):
    from app.api import routes

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    monkeypatch.setattr(routes.settings, "tool_label_provider", "ollama")
    routes._store_cache.clear()

    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    cv2.rectangle(image, (130, 10), (210, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tools.png"
    cv2.imwrite(str(image_path), image)

    poly_1 = _square_poly("tool 1")
    poly_2 = Polygon(
        id="poly-2",
        label="tool 2",
        points=[
            Point(x=130, y=10),
            Point(x=210, y=10),
            Point(x=210, y=90),
            Point(x=130, y=90),
        ],
    )
    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[poly_1, poly_2],
            tool_label_status="pending",
        ),
    )

    calls = 0

    async def label_crop(_self, _crop, _provider):
        nonlocal calls
        calls += 1
        if calls == 1:
            return '{"name":"pliers"}'

        current = sessions.get("session-1")
        assert current.tool_label_status == "pending"
        assert [poly.label for poly in current.polygons] == ["pliers", "tool 2"]
        return '{"name":"caliper"}'

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)

    asyncio.run(
        routes._label_session_polygons_background(
            "default",
            "session-1",
            str(image_path),
            ["poly-1", "poly-2"],
        )
    )

    session = sessions.get("session-1")
    assert calls == 2
    assert session.tool_label_status == "complete"
    assert [poly.label for poly in session.polygons] == ["pliers", "caliper"]


def test_background_labeling_does_not_fail_replaced_trace(tmp_path, monkeypatch):
    from app.api import routes

    storage_path = tmp_path / "storage"
    ensure_user_dirs(storage_path / "default")
    monkeypatch.setattr(routes.settings, "storage_path", storage_path)
    monkeypatch.setattr(routes.settings, "tool_label_provider", "ollama")
    routes._store_cache.clear()

    image = np.full((120, 220, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (10, 10), (90, 90), (0, 0, 0), -1)
    image_path = tmp_path / "tools.png"
    cv2.imwrite(str(image_path), image)

    old_poly = _square_poly("tool 1")
    new_poly = Polygon(
        id="poly-new",
        label="tool 1",
        points=[
            Point(x=130, y=10),
            Point(x=210, y=10),
            Point(x=210, y=90),
            Point(x=130, y=90),
        ],
    )
    sessions, _tools, _bins = routes.get_stores("default")
    sessions.set(
        "session-1",
        Session(
            id="session-1",
            created_at=datetime.utcnow().isoformat(),
            scale_factor=1.0,
            polygons=[old_poly],
            tool_label_status="pending",
        ),
    )

    async def label_crop(_self, _crop, _provider):
        current = sessions.get("session-1")
        current.polygons = [new_poly]
        current.tool_label_status = "pending"
        sessions.set("session-1", current)
        return '{"name":"pliers"}'

    monkeypatch.setattr(ToolLabeler, "_label_crop", label_crop)

    asyncio.run(
        routes._label_session_polygons_background(
            "default",
            "session-1",
            str(image_path),
            ["poly-1"],
        )
    )

    session = sessions.get("session-1")
    assert session.tool_label_status == "pending"
    assert session.polygons[0].id == "poly-new"
    assert session.polygons[0].label == "tool 1"


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
