import asyncio

import numpy as np
from PIL import Image

from app.services.ai_tracer import AITracer


def test_expand_paper_rect_adds_margin_and_clamps_to_image_bounds():
    rect = (100, 80, 400, 300)

    expanded = AITracer._expand_paper_rect(rect, image_width=520, image_height=390)

    assert expanded == (36, 16, 484, 374)


def test_local_mask_generation_uses_expanded_paper_rect(tmp_path, monkeypatch):
    image_path = tmp_path / "corrected.png"
    output_path = tmp_path / "mask.png"
    Image.new("RGB", (500, 400), "white").save(image_path)

    tracer = AITracer(local_model=False)
    monkeypatch.setattr(tracer, "_detect_paper_rect", lambda _img: (100, 80, 300, 200))

    seen_crop_sizes = []

    def fake_saliency(pil_img):
        seen_crop_sizes.append(pil_img.size)
        return np.full((pil_img.height, pil_img.width), 255, dtype=np.uint8)

    monkeypatch.setattr(tracer, "_saliency_on_image", fake_saliency)

    asyncio.run(tracer._generate_mask_local(str(image_path), str(output_path)))

    assert seen_crop_sizes == [(428, 328)]
    assert output_path.exists()
