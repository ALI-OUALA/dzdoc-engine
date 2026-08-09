from io import BytesIO

import numpy as np
from PIL import Image

from dzdoc.ocr import DetectedRegion
from dzdoc.vlm import PaddleOcrVlFallback


class _Result:
    json = {
        "res": {
            "parsing_res_list": [{"block_content": "إجمالي TTC: 1 190,00 DZD"}],
            "score": 0.88,
        }
    }


class _Pipeline:
    def predict(self, image):
        assert image.shape[0] == 60
        return [_Result()]


def test_paddleocr_vl_adapter_is_local_pinned_and_parses_traceable_output(tmp_path) -> None:
    image_buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(image_buffer, "PNG")
    image = np.asarray(Image.open(BytesIO(image_buffer.getvalue())))
    adapter = PaddleOcrVlFallback(tmp_path, pipeline_factory=lambda _: _Pipeline())

    result = adapter.resolve(
        image,
        DetectedRegion(((10, 10), (110, 70)), 0.9),
    )

    assert result.text == "إجمالي TTC: 1 190,00 DZD"
    assert result.confidence == 0.88
    assert result.decoding["local_assets_only"] is True
    assert len(adapter.model_revision) == 40
