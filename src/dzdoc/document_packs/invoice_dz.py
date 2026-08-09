"""Deterministic Algerian invoice and purchase-document extraction pack."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from ..models import (
    BoundingBox,
    Confidence,
    Document,
    DocumentExtraction,
    Provenance,
    StructuredField,
    TableCell,
    ValidationResult,
)
from ..text import normalize_search


@dataclass(frozen=True, slots=True)
class _Evidence:
    page_id: str
    bbox: BoundingBox
    text: str
    confidence: float
    block_id: str


_IDENTIFIERS = {
    "nif": re.compile(r"\bNIF\s*[:#-]?\s*([0-9٠-٩۰-۹ ]{15,20})", re.IGNORECASE),
    "nis": re.compile(r"\bNIS\s*[:#-]?\s*([0-9٠-٩۰-۹ ]{15,20})", re.IGNORECASE),
    "rc": re.compile(r"\bRC\s*[:#-]?\s*([A-Z0-9][A-Z0-9/.-]{5,30})", re.IGNORECASE),
}
_INVOICE_NUMBER = re.compile(
    r"(?:facture|فاتورة).*?(?:n[°ºo]?|num(?:éro)?|رقم)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]+)",
    re.IGNORECASE,
)
_STANDALONE_INVOICE_NUMBER = re.compile(r"\b[A-Z]{1,5}[-/]\d{2,4}[-/]\d{2,8}\b", re.I)
_DATE = re.compile(
    r"(?:date|التاريخ)[^\d\n]{0,20}(\d{1,4}[./-]\d{1,2}[./-]\d{1,4})",
    re.IGNORECASE,
)
_COMPANY = re.compile(
    r"\b(?:SARL|EURL|SPA|SNC|SCS|ETS)\s+[^:\n]+?"
    r"(?=\s+(?:NIF|NIS|RC|FACTURE|فاتورة|DATE)\b|$)",
    re.IGNORECASE,
)
_TOTAL_HT = re.compile(r"(?:total\s+HT|المجموع\s+دون\s+رسم)\s*[:#-]?\s*([^A-Z\n]+)", re.I)
_TVA = re.compile(r"TVA\s*([0-9٠-٩۰-۹., ]+)?\s*%?\s*[:#-]?\s*([^A-Z\n]+)", re.I)
_TOTAL_TTC = re.compile(
    r"(?:total\s+TTC|net\s+[àa]\s+payer|المبلغ\s+الإجمالي)\s*[:#-]?\s*([^A-Z\n]+)",
    re.I,
)
_CURRENCY = re.compile(r"\b(DZD|DA|EUR|USD)\b", re.IGNORECASE)
_NUMBER_TOKEN = re.compile(r"[0-9٠-٩۰-۹][0-9٠-٩۰-۹., ]*")


class InvoiceDzPack:
    name = "invoice-dz"
    version = "1.0.0"

    def extract(self, document: Document) -> DocumentExtraction:
        evidence = _document_evidence(document)
        fields: list[StructuredField] = []
        occurrence: dict[str, int] = {}

        def add(
            name: str,
            value: str,
            normalized: str,
            value_type: Literal["string", "date", "identifier", "decimal", "currency"],
            source: _Evidence,
        ) -> None:
            occurrence[name] = occurrence.get(name, 0) + 1
            safe_name = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
            fields.append(
                StructuredField(
                    field_id=f"{document.document_id}-{safe_name}-{occurrence[name]}",
                    field_name=name,
                    value=value.strip(),
                    normalized_value=normalized,
                    value_type=value_type,
                    confidence=Confidence(
                        score=source.confidence,
                        calibrated=False,
                        method="invoice_alias_regex_and_geometry",
                    ),
                    page_id=source.page_id,
                    bbox=source.bbox,
                    provenance=Provenance(
                        kind="derived",
                        source="dzdoc.invoice-dz",
                        version=self.version,
                        stage="field_extraction",
                        details={"source_block_id": source.block_id},
                    ),
                )
            )

        for source in evidence:
            for name, pattern in _IDENTIFIERS.items():
                if match := pattern.search(source.text):
                    raw = match.group(1).strip()
                    normalized = _logical_digits(raw).replace(" ", "")
                    add(name, raw, normalized, "identifier", source)
            if match := _INVOICE_NUMBER.search(source.text):
                add("invoice_number", match.group(1), match.group(1).upper(), "identifier", source)
            if match := _DATE.search(source.text):
                if normalized := _date(match.group(1)):
                    add("invoice_date", match.group(1), normalized, "date", source)
            companies = [match.group(0).strip() for match in _COMPANY.finditer(source.text)]
            if companies:
                role = "buyer_company" if _is_buyer_line(source.text) else "supplier_company"
                add(role, companies[-1], companies[-1], "string", source)
            if match := _TOTAL_HT.search(source.text):
                if value := _money(match.group(1)):
                    add("total_ht", match.group(1), _decimal_text(value), "decimal", source)
            if match := _TVA.search(source.text):
                rate = _money(match.group(1) or "")
                amount = _money(match.group(2))
                if rate is not None:
                    add("tva_rate", match.group(1), _decimal_text(rate), "decimal", source)
                if amount is not None:
                    add("tva_amount", match.group(2), _decimal_text(amount), "decimal", source)
            if match := _TOTAL_TTC.search(source.text):
                if value := _money(match.group(1)):
                    add("total_ttc", match.group(1), _decimal_text(value), "decimal", source)
            if match := _CURRENCY.search(source.text) if re.search(r"\d", source.text) else None:
                currency = "DZD" if match.group(1).upper() == "DA" else match.group(1).upper()
                if not any(field.field_name == "currency" for field in fields):
                    add("currency", match.group(1), currency, "currency", source)

        for index, source in enumerate(evidence):
            if not _has_field(fields, "invoice_number"):
                if match := _STANDALONE_INVOICE_NUMBER.search(source.text):
                    add(
                        "invoice_number",
                        match.group(0),
                        match.group(0).upper(),
                        "identifier",
                        source,
                    )
            if not _has_field(fields, "invoice_date"):
                if match := re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", source.text):
                    if normalized := _date(match.group(0)):
                        add("invoice_date", match.group(0), normalized, "date", source)
            if index + 1 < len(evidence):
                merged = f"{source.text} {evidence[index + 1].text}"
                if _is_buyer_line(merged) and (company := _COMPANY.search(merged)):
                    existing = next(
                        (field for field in fields if field.field_name == "buyer_company"), None
                    )
                    if existing is None or len(company.group(0)) > len(existing.value):
                        fields[:] = [
                            field for field in fields if field.field_name != "buyer_company"
                        ]
                        add("buyer_company", company.group(0), company.group(0), "string", source)

        _recover_sequence_line_items(evidence, fields, add)
        _recover_validated_ttc(evidence, fields, add)

        for source, table in _tables(document):
            for name, value, cell in _line_item_fields(table):
                cell_source = _Evidence(
                    page_id=source.page_id,
                    bbox=cell.bbox,
                    text=cell.normalized_text,
                    confidence=source.confidence,
                    block_id=source.block_id,
                )
                normalized = (
                    value
                    if name.rsplit(".", 1)[-1] == "description"
                    else _decimal_text(
                        _money(value),
                        integer=name.rsplit(".", 1)[-1] == "quantity",
                    )
                )
                add(
                    name,
                    value,
                    normalized,
                    "string" if name.endswith("description") else "decimal",
                    cell_source,
                )

        return DocumentExtraction(
            document_id=document.document_id,
            schema_name=self.name,
            schema_version=self.version,
            fields=fields,
            validations=_validate(fields),
        )


def _document_evidence(document: Document) -> list[_Evidence]:
    return [
        _Evidence(
            page_id=page.page_id,
            bbox=block.bbox,
            text="\n".join(line.normalized_text for line in block.lines),
            confidence=block.confidence.score,
            block_id=block.block_id,
        )
        for page in document.pages
        for block in sorted(page.blocks, key=lambda value: value.reading_order_index)
        if block.lines
    ]


def _tables(document: Document):
    for page in document.pages:
        for block in page.blocks:
            if block.table is not None:
                yield (
                    _Evidence(
                        page.page_id,
                        block.bbox,
                        "",
                        block.confidence.score,
                        block.block_id,
                    ),
                    block.table,
                )


def _line_item_fields(table) -> list[tuple[str, str, TableCell]]:
    rows: dict[int, dict[int, TableCell]] = {}
    for cell in table.cells:
        rows.setdefault(cell.row_index, {})[cell.column_index] = cell
    header = rows.get(0, {})
    columns: dict[str, int] = {}
    for column, cell in header.items():
        text = normalize_search(cell.normalized_text)
        if "designation" in text or "désignation" in text or "البيان" in text:
            columns["description"] = column
        elif any(alias in text for alias in ("qte", "qté", "quantite", "quantité", "كمية")):
            columns["quantity"] = column
        elif "montant" in text or "total" in text:
            columns["line_total_ht"] = column
        elif "p.u" in text or "prix" in text or "unit" in text:
            columns["unit_price_ht"] = column
    required = {"description", "quantity", "unit_price_ht", "line_total_ht"}
    if not required <= columns.keys():
        return []
    result: list[tuple[str, str, TableCell]] = []
    for item_index, row_index in enumerate(sorted(index for index in rows if index > 0)):
        row = rows[row_index]
        for name in ("description", "quantity", "unit_price_ht", "line_total_ht"):
            if cell := row.get(columns[name]):
                result.append(
                    (f"line_items[{item_index}].{name}", cell.normalized_text.strip(), cell)
                )
    return result


def _has_field(fields: list[StructuredField], name: str) -> bool:
    return any(field.field_name == name for field in fields)


def _recover_sequence_line_items(evidence, fields, add) -> None:
    if any(field.field_name.startswith("line_items[") for field in fields):
        return
    item_index = 0
    for index in range(len(evidence) - 3):
        description, quantity, unit_price, line_total = evidence[index : index + 4]
        if (
            re.fullmatch(r"\d{1,4}", quantity.text.strip())
            and _full_money(unit_price.text) is not None
            and _full_money(line_total.text) is not None
            and re.search(r"[A-Za-zÀ-ÿ\u0600-\u06ff]", description.text)
            and not any(alias in normalize_search(description.text) for alias in ("qte", "qté"))
        ):
            values = (
                ("description", description.text, "string", description),
                ("quantity", quantity.text, "decimal", quantity),
                ("unit_price_ht", unit_price.text, "decimal", unit_price),
                ("line_total_ht", line_total.text, "decimal", line_total),
            )
            for name, value, value_type, source in values:
                normalized = (
                    value
                    if name == "description"
                    else _decimal_text(_money(value), integer=name == "quantity")
                )
                add(f"line_items[{item_index}].{name}", value, normalized, value_type, source)
            item_index += 1


def _full_money(text: str) -> Decimal | None:
    if re.fullmatch(r"\s*[0-9٠-٩۰-۹][0-9٠-٩۰-۹., ]*\s*", text) is None:
        return None
    return _money(text)


def _recover_validated_ttc(evidence, fields, add) -> None:
    if _has_field(fields, "total_ttc"):
        return
    values = {field.field_name: field.normalized_value for field in fields}
    total_ht = _field_decimal(values, "total_ht")
    tva = _field_decimal(values, "tva_amount")
    if total_ht is None or tva is None:
        return
    expected = total_ht + tva
    for source in evidence:
        for token in _NUMBER_TOKEN.findall(source.text):
            if _money(token) == expected:
                add("total_ttc", token, _decimal_text(expected), "decimal", source)
                return


def _logical_digits(value: str) -> str:
    return "".join(
        str(unicodedata.digit(character)) if character.isdecimal() else character
        for character in value
    )


def _money(value: str) -> Decimal | None:
    token = re.sub(r"[^0-9٠-٩۰-۹.,\s\u00a0]", "", value)
    token = _logical_digits(token).replace(" ", "").replace("\u00a0", "")
    if not token:
        return None
    if "," in token and "." in token:
        decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
        token = token.replace("." if decimal_mark == "," else ",", "")
        token = token.replace(decimal_mark, ".")
    elif "," in token or "." in token:
        mark = "," if "," in token else "."
        parts = token.split(mark)
        token = "".join(parts) if len(parts) > 2 or len(parts[-1]) == 3 else ".".join(parts)
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal | None, *, integer: bool = False) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("1" if integer else "0.01")), "f")


def _date(value: str) -> str | None:
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _is_buyer_line(text: str) -> bool:
    normalized = normalize_search(text)
    return any(alias in normalized for alias in ("client", "acheteur", "الزبون", "المشتري"))


def _validate(fields: list[StructuredField]) -> list[ValidationResult]:
    by_name = {field.field_name: field.normalized_value for field in fields}
    validations: list[ValidationResult] = []
    for name in ("nif", "nis"):
        value = by_name.get(name)
        valid = value is not None and len(value) == 15 and value.isdecimal()
        validations.append(
            ValidationResult(
                rule=f"{name}-format",
                status="pass" if valid else "review",
                message=(
                    f"{name.upper()} is a 15-digit Algerian identifier."
                    if valid
                    else f"{name.upper()} missing or malformed."
                ),
                confidence=1.0 if value is not None else 0.0,
            )
        )
    line_totals = [
        Decimal(field.normalized_value)
        for field in fields
        if field.field_name.endswith("line_total_ht") and field.normalized_value
    ]
    total_ht = _field_decimal(by_name, "total_ht")
    tva = _field_decimal(by_name, "tva_amount")
    total_ttc = _field_decimal(by_name, "total_ttc")
    validations.append(
        _arithmetic_validation(
            "line-items-sum-ht",
            sum(line_totals, Decimal(0)) if line_totals else None,
            total_ht,
            "Line totals equal total HT.",
        )
    )
    validations.append(
        _arithmetic_validation(
            "invoice-arithmetic",
            total_ht + tva if total_ht is not None and tva is not None else None,
            total_ttc,
            "HT plus TVA equals TTC.",
        )
    )
    return validations


def _field_decimal(values: dict[str, str], name: str) -> Decimal | None:
    try:
        return Decimal(values[name])
    except (KeyError, InvalidOperation):
        return None


def _arithmetic_validation(
    rule: str, calculated: Decimal | None, reported: Decimal | None, message: str
) -> ValidationResult:
    if calculated is None or reported is None:
        return ValidationResult(
            rule=rule,
            status="review",
            message=f"{message} Required values missing.",
            confidence=0.0,
        )
    valid = abs(calculated - reported) <= Decimal("0.01")
    return ValidationResult(
        rule=rule,
        status="pass" if valid else "fail",
        message=message if valid else f"{message} Values disagree.",
        confidence=1.0,
    )


__all__ = ["InvoiceDzPack"]
