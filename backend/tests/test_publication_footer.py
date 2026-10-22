"""Small publication notices remain readable but cannot become answer evidence."""

from app.modules.documents.reader import classify_publication_footers


def test_small_first_page_publication_notice_has_separate_role():
    words = [
        {"text": "Evidence", "box": [0.1, 0.7, 0.2, 0.713]},
        {"text": "continues", "box": [0.21, 0.7, 0.32, 0.713]},
        {"text": "This", "box": [0.1, 0.91, 0.14, 0.919]},
        {"text": "is", "box": [0.15, 0.91, 0.17, 0.919]},
        {"text": "an", "box": [0.18, 0.91, 0.2, 0.919]},
        {"text": "open", "box": [0.21, 0.91, 0.25, 0.919]},
        {"text": "access", "box": [0.26, 0.91, 0.33, 0.919]},
        {"text": "article", "box": [0.34, 0.91, 0.41, 0.919]},
    ]
    layout = {
        "words": words,
        "passages": [
            {"role": "abstract", "text": "Abstract", "word_indices": []},
            {"text": "Evidence continues", "word_indices": [0, 1]},
            {"text": "This is an open access article", "word_indices": [2, 3, 4, 5, 6, 7]},
        ],
    }
    classify_publication_footers(layout)
    assert layout["passages"][1].get("role", "body") == "body"
    assert layout["passages"][2]["role"] == "publication_metadata"
