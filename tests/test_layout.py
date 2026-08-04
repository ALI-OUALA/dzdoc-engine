import pytest

from dzdoc.layout import classify_block_type
from dzdoc.models import BlockType, BoundingBox, TableCell, TableStructure


def test_bac_block_semantics_are_deterministic():
    top = BoundingBox(x=10, y=10, width=500, height=40)
    body = BoundingBox(x=10, y=300, width=500, height=40)
    assert (
        classify_block_type("اختبار البكالوريا 2026", top, page_width=600, page_height=800)
        == BlockType.TITLE
    )
    assert (
        classify_block_type("Exercice 2 : étude", body, page_width=600, page_height=800)
        == BlockType.EXERCISE
    )
    assert (
        classify_block_type("f(x)=x²+1", body, page_width=600, page_height=800)
        == BlockType.EQUATION
    )


def test_table_structure_rejects_cells_outside_grid():
    with pytest.raises(ValueError, match="exceeds row count"):
        TableStructure(
            rows=1,
            columns=1,
            cells=[
                TableCell(
                    cell_id="c1",
                    row_index=1,
                    column_index=0,
                    bbox=BoundingBox(x=0, y=0, width=1, height=1),
                )
            ],
        )
