from dzdoc.document_packs.invoice_dz import InvoiceDzPack
from dzdoc.models import (
    Block,
    BlockType,
    BoundingBox,
    Checksum,
    Confidence,
    Document,
    Page,
    Provenance,
    TableCell,
    TableStructure,
    TextDirection,
    TextLine,
    TextSpan,
)

PROVENANCE = Provenance(kind="ocr", source="fixture")
CONFIDENCE = Confidence(score=0.92, calibrated=False)


def _block(index: int, text: str, y: float, block_type: BlockType = BlockType.PARAGRAPH) -> Block:
    bbox = BoundingBox(x=50, y=y, width=1100, height=80)
    span = TextSpan(
        span_id=f"s{index}",
        raw_text=text,
        normalized_text=text,
        language="mixed",
        script="mixed",
        direction=TextDirection.MIXED,
        bbox=bbox,
        confidence=CONFIDENCE,
        provenance=PROVENANCE,
    )
    line = TextLine(
        line_id=f"l{index}",
        raw_text=text,
        normalized_text=text,
        language="mixed",
        script="mixed",
        direction=TextDirection.MIXED,
        bbox=bbox,
        reading_order_index=index,
        confidence=CONFIDENCE,
        provenance=PROVENANCE,
        spans=[span],
    )
    return Block(
        block_id=f"b{index}",
        block_type=block_type,
        bbox=bbox,
        reading_order_index=index,
        confidence=CONFIDENCE,
        provenance=PROVENANCE,
        lines=[line],
    )


def _invoice(total_ttc: str = "1 190,00") -> Document:
    blocks = [
        _block(
            0,
            "شركة الأطلس / SARL Atlas Fournitures NIF: 001626089123456 "
            "NIS: 001626089123457 RC: 16/00-1234567B12",
            50,
            BlockType.HEADER,
        ),
        _block(1, "Client / الزبون: EURL El Bahdja Distribution", 150),
        _block(2, "FACTURE N° FA-2026-0042", 250, BlockType.TITLE),
        _block(3, "Date: 09/08/2026", 350),
    ]
    table_bbox = BoundingBox(x=50, y=450, width=1100, height=400)
    values = [
        ["Désignation", "Qté", "P.U. HT", "Montant HT"],
        ["Ramette papier A4", "2", "250,00", "500,00"],
        ["Cartouche imprimante", "1", "500,00", "500,00"],
    ]
    cells = [
        TableCell(
            cell_id=f"c{row}{column}",
            row_index=row,
            column_index=column,
            bbox=BoundingBox(x=50 + column * 275, y=450 + row * 130, width=275, height=130),
            raw_text=value,
            normalized_text=value,
        )
        for row, values_row in enumerate(values)
        for column, value in enumerate(values_row)
    ]
    blocks.append(
        Block(
            block_id="table",
            block_type=BlockType.TABLE,
            bbox=table_bbox,
            reading_order_index=4,
            confidence=CONFIDENCE,
            provenance=PROVENANCE,
            table=TableStructure(rows=3, columns=4, cells=cells),
        )
    )
    blocks.extend(
        [
            _block(5, "Total HT: 1 000,00 DZD", 900),
            _block(6, "TVA 19%: 190,00 DZD", 1000),
            _block(7, f"Total TTC: {total_ttc} DZD", 1100),
        ]
    )
    page = Page(
        page_id="invoice-page-1",
        page_index=0,
        checksum=Checksum(value="a" * 64),
        width=1200,
        height=1600,
        blocks=blocks,
        reading_order=[block.block_id for block in blocks],
        provenance=PROVENANCE,
    )
    return Document(
        document_id="invoice-1",
        source_name="invoice.png",
        source_kind="image",
        source_checksum=Checksum(value="b" * 64),
        pages=[page],
    )


def test_invoice_pack_extracts_algerian_fields_tables_and_evidence() -> None:
    result = InvoiceDzPack().extract(_invoice())
    fields = {field.field_name: field for field in result.fields}

    assert fields["supplier_company"].normalized_value == "SARL Atlas Fournitures"
    assert fields["buyer_company"].normalized_value == "EURL El Bahdja Distribution"
    assert fields["invoice_date"].normalized_value == "2026-08-09"
    assert fields["invoice_number"].normalized_value == "FA-2026-0042"
    assert fields["nif"].normalized_value == "001626089123456"
    assert fields["nis"].normalized_value == "001626089123457"
    assert fields["rc"].normalized_value == "16/00-1234567B12"
    assert fields["line_items[0].quantity"].normalized_value == "2"
    assert fields["line_items[1].line_total_ht"].normalized_value == "500.00"
    assert fields["total_ht"].normalized_value == "1000.00"
    assert fields["tva_rate"].normalized_value == "19.00"
    assert fields["total_ttc"].normalized_value == "1190.00"
    assert fields["currency"].normalized_value == "DZD"
    assert all(field.page_id == "invoice-page-1" and field.bbox for field in result.fields)
    assert {validation.status for validation in result.validations} == {"pass"}


def test_invoice_pack_flags_inconsistent_totals() -> None:
    result = InvoiceDzPack().extract(_invoice(total_ttc="1 290,00"))

    arithmetic = next(value for value in result.validations if value.rule == "invoice-arithmetic")
    assert arithmetic.status == "fail"
    assert arithmetic.confidence == 1.0


def test_invoice_pack_recovers_split_ocr_invoice_evidence() -> None:
    document = _invoice()
    texts = [
        "Client / : EURL El Bahdja",
        "Distribution",
        "FA-2026-5749",
        "Date / 09/08/2026 :",
        "Ramette papier A4",
        "2",
        "250,00",
        "500,00",
        "Total HT: 1 000,00 DZD",
        "TVA 19%: 190,00 DZD",
        "1 190,00",
    ]
    blocks = [_block(index, text, 50 + index * 90) for index, text in enumerate(texts)]
    page = document.pages[0].model_copy(
        update={"blocks": blocks, "reading_order": [block.block_id for block in blocks]}
    )
    split = document.model_copy(update={"pages": [page]})

    fields = {
        field.field_name: field.normalized_value for field in InvoiceDzPack().extract(split).fields
    }

    assert fields["buyer_company"] == "EURL El Bahdja Distribution"
    assert fields["invoice_number"] == "FA-2026-5749"
    assert fields["invoice_date"] == "2026-08-09"
    assert fields["line_items[0].description"] == "Ramette papier A4"
    assert fields["line_items[0].quantity"] == "2"
    assert fields["total_ttc"] == "1190.00"
