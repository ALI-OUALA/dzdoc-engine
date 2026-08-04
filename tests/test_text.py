from dzdoc.text import assess_native_text, classify_text, normalize_display, normalize_search


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
