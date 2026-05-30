from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import re
from dataclasses import dataclass

import cv2
import numpy as np

from app.config import settings
from app.models.schemas import Point, Polygon

logger = logging.getLogger(__name__)

LABEL_PROMPT = """Identify each numbered physical tool or object in this contact sheet.
Return only JSON with this shape:
{"labels":[{"id":1,"name":"short common tool name","confidence":0.0}]}

Rules:
- Include one label object for every visible number.
- Use the visible number as id.
- Use 1 to 4 words for each name.
- Prefer common workshop/tool names.
- Do not mention color, background, paper, photo, silhouette, contact sheet, or image.
- If unsure, use "tool"."""

_BAD_EXACT_NAMES = {
    "tool",
    "image",
    "object",
    "unknown",
    "not sure",
    "n/a",
    "none",
    "photo",
    "silhouette",
    "background",
    "object on paper",
    "contact sheet",
}

_BAD_NAME_FRAGMENTS = (
    "image",
    "photo",
    "silhouette",
    "background",
    "unknown",
    "object",
    "not sure",
    "can't identify",
    "cannot identify",
    "contact sheet",
)


@dataclass(frozen=True)
class ToolLabelerConfig:
    provider: str = "none"
    model: str = "qwen3-vl:2b"
    ollama_url: str = "http://localhost:11434"
    timeout_seconds: float = 30.0
    max_crop_px: int = 512
    context_tokens: int = 4096
    max_tokens: int = 256
    attempts: int = 2
    google_api_key: str | None = None
    openrouter_api_key: str | None = None
    gemini_label_model: str = "gemini-2.0-flash"
    openrouter_label_model: str = "google/gemini-2.0-flash-001"

    @classmethod
    def from_settings(cls) -> "ToolLabelerConfig":
        return cls(
            provider=settings.tool_label_provider,
            model=settings.tool_label_model,
            ollama_url=settings.tool_label_ollama_url,
            timeout_seconds=settings.tool_label_timeout_seconds,
            max_crop_px=settings.tool_label_max_crop_px,
            context_tokens=settings.tool_label_context_tokens,
            max_tokens=settings.tool_label_max_tokens,
            attempts=settings.tool_label_attempts,
            google_api_key=settings.google_api_key,
            openrouter_api_key=settings.openrouter_api_key,
            gemini_label_model=settings.gemini_label_model,
            openrouter_label_model=settings.openrouter_label_model,
        )


class ToolLabeler:
    def __init__(self, config: ToolLabelerConfig | None = None):
        self.config = config or ToolLabelerConfig.from_settings()

    def enabled(self) -> bool:
        provider = self.config.provider.strip().lower()
        return provider not in ("", "none", "off", "disabled")

    async def label_polygons(self, image_path: str, polygons: list[Polygon]) -> list[Polygon]:
        """Populate polygon labels when configured; never fail tracing."""
        if not polygons or not self.enabled():
            return polygons

        provider = self.config.provider.strip().lower()
        if provider not in ("ollama", "gemini", "google", "openrouter", "hosted"):
            logger.warning("unsupported tool label provider '%s'; using fallback labels", provider)
            return _apply_fallback_labels(polygons)

        image = cv2.imread(image_path)
        if image is None:
            logger.warning("tool labeling skipped; failed to read corrected image")
            return _apply_fallback_labels(polygons)

        logger.info(
            "labeling %d tools provider=%s model=%s mode=batch-contact-sheet",
            len(polygons),
            provider,
            self._model_name(provider),
        )

        try:
            sheet = build_contact_sheet(image, polygons, self.config.max_crop_px)
            if sheet is None:
                return _apply_fallback_labels(polygons)

            logger.info(
                "tool label request provider=%s tools=%d sheet_bytes=%d",
                provider,
                len(sheet.entries),
                len(sheet.png),
            )
            raw_labels, labels = await self._label_contact_sheet_with_retries(
                sheet.png,
                provider,
                len(sheet.entries),
            )

            for sheet_id, polygon_index in sheet.entries:
                fallback = fallback_label(polygon_index)
                polygons[polygon_index].label = labels.get(sheet_id) or fallback
                logger.info(
                    "tool label result polygon=%d sheet_id=%d final=%r",
                    polygon_index + 1,
                    sheet_id,
                    polygons[polygon_index].label,
                )

            for index, poly in enumerate(polygons):
                if not poly.label:
                    poly.label = fallback_label(index)
        except Exception as exc:
            logger.warning("tool batch label failed: %s", exc)
            _apply_fallback_labels(polygons)

        return polygons

    async def _label_contact_sheet(self, sheet_png: bytes, provider: str) -> str:
        if provider == "ollama":
            return await self._label_contact_sheet_ollama(sheet_png)
        if provider == "openrouter":
            return await self._label_contact_sheet_openrouter(sheet_png)
        if provider in ("gemini", "google"):
            return await self._label_contact_sheet_google(sheet_png)
        if provider == "hosted":
            if self.config.google_api_key:
                return await self._label_contact_sheet_google(sheet_png)
            if self.config.openrouter_api_key:
                return await self._label_contact_sheet_openrouter(sheet_png)
            raise RuntimeError("hosted tool labeling requires GOOGLE_API_KEY or OPENROUTER_API_KEY")
        raise RuntimeError(f"unsupported tool label provider: {provider}")

    async def _label_contact_sheet_with_retries(
        self,
        sheet_png: bytes,
        provider: str,
        count: int,
    ) -> tuple[str, dict[int, str]]:
        attempts = max(1, self.config.attempts)
        last_raw = ""
        last_labels: dict[int, str] = {}

        for attempt in range(1, attempts + 1):
            raw = await self._label_contact_sheet(sheet_png, provider)
            labels = parse_labels_response(raw, count)
            logger.info(
                "tool label raw response attempt=%d raw=%r parsed=%s",
                attempt,
                raw,
                labels,
            )
            last_raw = raw
            last_labels = labels
            if len(labels) == count:
                return raw, labels

            if attempt < attempts:
                if labels:
                    logger.warning(
                        "tool label attempt %d returned partial labels (%d/%d); retrying",
                        attempt,
                        len(labels),
                        count,
                    )
                else:
                    logger.warning(
                        "tool label attempt %d returned no usable labels; retrying",
                        attempt,
                    )
                await asyncio.sleep(0.5)

        return last_raw, last_labels

    async def _label_contact_sheet_ollama(self, sheet_png: bytes) -> str:
        import httpx

        image_b64 = base64.b64encode(sheet_png).decode("ascii")
        payload = {
            "model": self.config.model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": LABEL_PROMPT,
                    "images": [image_b64],
                }
            ],
            "options": {
                "temperature": 0,
                "num_ctx": self.config.context_tokens,
                "num_predict": self.config.max_tokens,
            },
        }
        url = self.config.ollama_url.rstrip("/") + "/api/chat"

        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()

        result = await asyncio.wait_for(_call(), timeout=self.config.timeout_seconds)
        return result.get("message", {}).get("content", "")

    async def _label_contact_sheet_openrouter(self, sheet_png: bytes) -> str:
        import httpx

        if not self.config.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter tool labeling")

        image_b64 = base64.b64encode(sheet_png).decode("ascii")
        payload = {
            "model": self.config.openrouter_label_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": LABEL_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0,
        }

        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.config.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                return resp.json()

        result = await asyncio.wait_for(_call(), timeout=self.config.timeout_seconds)
        return result["choices"][0]["message"]["content"]

    async def _label_contact_sheet_google(self, sheet_png: bytes) -> str:
        if not self.config.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is required for Gemini tool labeling")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.config.google_api_key)
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=self.config.gemini_label_model,
                contents=[
                    LABEL_PROMPT,
                    types.Part.from_bytes(data=sheet_png, mime_type="image/png"),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            ),
            timeout=self.config.timeout_seconds,
        )
        return response.text or ""

    def _model_name(self, provider: str) -> str:
        if provider == "openrouter":
            return self.config.openrouter_label_model
        if provider in ("gemini", "google"):
            return self.config.gemini_label_model
        if provider == "hosted":
            return self.config.gemini_label_model if self.config.google_api_key else self.config.openrouter_label_model
        return self.config.model


@dataclass(frozen=True)
class ContactSheet:
    png: bytes
    entries: list[tuple[int, int]]


def fallback_label(index: int) -> str:
    return f"tool {index + 1}"


def is_fallback_label(label: str | None) -> bool:
    return bool(label and re.fullmatch(r"tool\s+\d+", label.strip().lower()))


def build_contact_sheet(image: np.ndarray, polygons: list[Polygon], max_crop_px: int) -> ContactSheet | None:
    crops: list[tuple[int, int, np.ndarray]] = []
    for polygon_index, polygon in enumerate(polygons):
        crop = crop_polygon_array(image, polygon, max_crop_px)
        if crop is not None:
            crops.append((len(crops) + 1, polygon_index, crop))
        else:
            polygons[polygon_index].label = fallback_label(polygon_index)

    if not crops:
        return None

    tile_size = max(160, min(max_crop_px if max_crop_px > 0 else 512, 512))
    label_h = 34
    gap = 12
    cols = max(1, math.ceil(math.sqrt(len(crops))))
    rows = math.ceil(len(crops) / cols)
    sheet_w = cols * tile_size + (cols + 1) * gap
    sheet_h = rows * (tile_size + label_h) + (rows + 1) * gap
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)

    entries: list[tuple[int, int]] = []
    for pos, (sheet_id, polygon_index, crop) in enumerate(crops):
        row, col = divmod(pos, cols)
        x = gap + col * (tile_size + gap)
        y = gap + row * (tile_size + label_h + gap)
        cv2.putText(
            sheet,
            str(sheet_id),
            (x + 8, y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

        h, w = crop.shape[:2]
        scale = min(tile_size / max(1, w), tile_size / max(1, h), 1.0)
        resized_w = max(1, int(w * scale))
        resized_h = max(1, int(h * scale))
        resized = cv2.resize(crop, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        paste_x = x + (tile_size - resized_w) // 2
        paste_y = y + label_h + (tile_size - resized_h) // 2
        sheet[paste_y:paste_y + resized_h, paste_x:paste_x + resized_w] = resized
        entries.append((sheet_id, polygon_index))

    ok, encoded = cv2.imencode(".png", sheet)
    if not ok:
        return None
    return ContactSheet(png=encoded.tobytes(), entries=entries)


def crop_polygon_image(image: np.ndarray, polygon: Polygon, max_crop_px: int) -> bytes | None:
    crop = crop_polygon_array(image, polygon, max_crop_px)
    if crop is None:
        return None
    ok, encoded = cv2.imencode(".png", crop)
    if not ok:
        return None
    return encoded.tobytes()


def crop_polygon_array(image: np.ndarray, polygon: Polygon, max_crop_px: int) -> np.ndarray | None:
    if not polygon.points:
        return None

    height, width = image.shape[:2]
    xs = [p.x for p in polygon.points]
    ys = [p.y for p in polygon.points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    box_w = max_x - min_x
    box_h = max_y - min_y
    if box_w <= 1 or box_h <= 1:
        return None

    pad = max(8, int(max(box_w, box_h) * 0.18))
    x1 = max(0, int(np.floor(min_x)) - pad)
    y1 = max(0, int(np.floor(min_y)) - pad)
    x2 = min(width, int(np.ceil(max_x)) + pad)
    y2 = min(height, int(np.ceil(max_y)) + pad)
    if x2 <= x1 or y2 <= y1:
        return None

    crop = image[y1:y2, x1:x2]
    mask = np.zeros(crop.shape[:2], dtype=np.uint8)

    exterior = _points_to_cv2(polygon.points, x1, y1)
    cv2.fillPoly(mask, [exterior], 255)
    for ring in polygon.interior_rings:
        if len(ring) >= 3:
            cv2.fillPoly(mask, [_points_to_cv2(ring, x1, y1)], 0)

    white = np.full_like(crop, 255)
    isolated = np.where(mask[:, :, None] > 0, crop, white)

    longest = max(isolated.shape[:2])
    if longest > max_crop_px > 0:
        scale = max_crop_px / longest
        new_w = max(1, int(isolated.shape[1] * scale))
        new_h = max(1, int(isolated.shape[0] * scale))
        isolated = cv2.resize(isolated, (new_w, new_h), interpolation=cv2.INTER_AREA)

    return isolated


def _points_to_cv2(points: list[Point], offset_x: int, offset_y: int) -> np.ndarray:
    return np.array(
        [[round(p.x - offset_x), round(p.y - offset_y)] for p in points],
        dtype=np.int32,
    )


def parse_label_response(response: str) -> str | None:
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            response = response[start:end]
        data = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        return None

    name = data.get("name")
    if not isinstance(name, str):
        return None
    return validate_label(name)


def parse_labels_response(response: str, count: int) -> dict[int, str]:
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            response = response[start:end]
        data = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        return {}

    labels = data.get("labels") if isinstance(data, dict) else data
    if not isinstance(labels, list):
        return {}

    parsed: dict[int, str] = {}
    for index, item in enumerate(labels, start=1):
        label_id = index
        name: str | None = None
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            raw_id = item.get("id", index)
            if isinstance(raw_id, int):
                label_id = raw_id
            elif isinstance(raw_id, str) and raw_id.isdigit():
                label_id = int(raw_id)
            raw_name = item.get("name") or item.get("label")
            if isinstance(raw_name, str):
                name = raw_name

        if label_id < 1 or label_id > count:
            continue
        valid = validate_label(name or "")
        if valid:
            parsed[label_id] = valid

    return parsed


def validate_label(name: str) -> str | None:
    normalized = re.sub(r"\s+", " ", name.strip().lower())
    normalized = normalized.strip(" .,:;\"'")
    if not normalized:
        return None
    if len(normalized) > 40:
        return None
    if len(normalized.split()) > 4:
        return None
    if normalized in _BAD_EXACT_NAMES:
        return None
    if any(fragment in normalized for fragment in _BAD_NAME_FRAGMENTS):
        return None
    if not re.search(r"[a-z0-9]", normalized):
        return None
    return normalized


def _apply_fallback_labels(polygons: list[Polygon]) -> list[Polygon]:
    for index, polygon in enumerate(polygons):
        polygon.label = fallback_label(index)
    return polygons
