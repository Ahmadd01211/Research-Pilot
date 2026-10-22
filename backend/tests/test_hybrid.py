from app.modules.documents.hybrid import route_page
from app.modules.documents.quality import assess_page


def test_clean_page_stays_on_fast_native_route():
    result = route_page({"block_page": False, "findings": []})
    assert result["route"] == "native"
    assert result["status"] == "trusted"


def test_uncertain_table_is_a_docling_candidate():
    result = route_page(
        {
            "block_page": False,
            "findings": [{"code": "uncertain_table"}],
        }
    )
    assert result["route"] == "docling"
    assert result["status"] == "candidate"


def test_missing_text_is_a_docling_candidate():
    result = route_page(
        {
            "block_page": True,
            "findings": [{"code": "no_measured_text"}],
        }
    )
    assert result["route"] == "docling"


def test_figure_quality_failures_route_to_docling():
    for code in {
        "uncertain_figure_boundary",
        "invalid_figure_anchor",
        "oversized_figure_region",
        "misaligned_figure_caption",
        "caption_crosses_columns",
    }:
        result = route_page({"block_page": False, "findings": [{"code": code}]})
        assert result["route"] == "docling"
        assert result["status"] == "candidate"


def test_oversized_figure_is_detected_from_measured_geometry():
    layout = {
        "words": [
            {"text": "FIGURE", "box": [0.1, 0.05, 0.2, 0.07], "margin": False},
            {"text": "1", "box": [0.21, 0.05, 0.23, 0.07], "margin": False},
        ],
        "passages": [],
        "tables": [],
        "links": [],
        "figures": [
            {
                "caption": "FIGURE 1",
                "caption_word_indices": [0, 1],
                "box": [0.01, 0.08, 0.99, 0.75],
            }
        ],
    }
    result = assess_page(layout)
    assert "oversized_figure_region" in {item["code"] for item in result["findings"]}
    assert result["hybrid"]["route"] == "docling"
