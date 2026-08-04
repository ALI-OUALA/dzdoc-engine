from dzdoc.text import (
    assess_native_text,
    classify_text,
    normalization_warnings,
    normalize_display,
    normalize_search,
)


def test_mixed_text_keeps_logical_order_and_normalizes_search_only():
    value = "المبلغ ١٢٣,٤٥ EUR"
    assert normalize_display(value) == value
    assert normalize_search(value) == "المبلغ 123,45 eur"
    assert classify_text(value)[1].value == "mixed"


def test_native_quality_does_not_reject_arabic_presentation_forms():
    quality = assess_native_text("\ufee3\ufee0\ufee0")
    assert quality.accepted is True


def test_corrupt_text_routes_to_ocr():
    quality = assess_native_text("bad\ufffdtext")
    assert quality.route == "ocr_required"


def test_phantom_native_layers_route_to_ocr():
    assert assess_native_text("x\n" * 8).reason == "phantom_repeated_lines"
    assert assess_native_text("#" * 30).reason == "implausible_glyphs"


def test_watermark_only_text_over_a_scan_routes_to_ocr():
    quality = assess_native_text("www.dzexams.com", image_coverage=0.20)
    assert quality.reason == "sparse_overlay_on_image"


def test_private_use_math_glyphs_route_to_ocr():
    quality = assess_native_text("معادلة طويلة وواضحة " * 4 + "\uf028\uf029")
    assert quality.reason == "private_use_glyphs"


def test_native_gate_clamps_image_coverage():
    assert assess_native_text("text", image_coverage=2).image_coverage == 1


def test_display_repairs_are_reported_without_changing_raw_text():
    assert normalization_warnings("\u200fنص")[0].code == "bidi_controls_removed"
