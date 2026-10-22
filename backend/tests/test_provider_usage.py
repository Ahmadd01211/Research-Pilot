from app.modules.documents.provider_usage import record_usage


def test_usage_events_include_counts_without_source_text_or_credentials(caplog):
    record_usage("generateContent", "gemini-test", 200, {
        "usageMetadata": {"promptTokenCount": 42, "candidatesTokenCount": 8, "totalTokenCount": 50},
        "source": "private research text", "key": "private-api-key",
    })
    assert "prompt_tokens=42 output_tokens=8 total_tokens=50" in caplog.text
    assert "private" not in caplog.text


def test_missing_or_invalid_usage_is_unknown_not_zero(caplog):
    record_usage("embedContent", "gemini-test", 200, {"usageMetadata": {
        "promptTokenCount": True, "candidatesTokenCount": -1, "totalTokenCount": "50",
    }})
    assert "prompt_tokens=None output_tokens=None total_tokens=None" in caplog.text
    record_usage("embedContent", "gemini-test", 200, None)
