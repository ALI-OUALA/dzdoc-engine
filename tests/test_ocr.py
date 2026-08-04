import pytest

from dzdoc.ocr import OcrDependencyError, PaddleOcrEngine, Recognition, fuse_recognitions


def test_fusion_prefers_script_consistency_and_preserves_close_alternative():
    result = fuse_recognitions(
        [
            Recognition("Exercice 12", 0.90, "latin", "latin"),
            Recognition("ا13", 0.89, "arabic", "arabic"),
        ],
        ambiguity_margin=0.2,
    )
    assert result.selected.text == "Exercice 12"
    assert result.alternatives[0].text == "ا13"
    assert {warning.code for warning in result.warnings} == {
        "ambiguous_recognition",
        "digit_disagreement",
    }


def test_pinned_model_root_fails_closed_when_an_asset_is_missing(tmp_path):
    engine = PaddleOcrEngine(model_root=tmp_path)
    with pytest.raises(OcrDependencyError, match="pinned model directory is missing"):
        engine._model_args("PP-OCRv5_mobile_det")


def test_unpinned_model_download_is_opt_in():
    with pytest.raises(OcrDependencyError, match="pinned OCR assets are required"):
        PaddleOcrEngine()._model_args("PP-OCRv5_mobile_det")


def test_recognition_baseline_mode_is_explicit():
    assert PaddleOcrEngine(recognition_mode="arabic").name == "paddleocr-arabic"
    with pytest.raises(ValueError, match="recognition_mode"):
        PaddleOcrEngine(recognition_mode="magic")
