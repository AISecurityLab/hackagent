from hackagent.tracking.serialize import sanitize_for_json


def test_usage_detail_objects_are_recursively_sanitized():
    payload = {
        "usage": {
            "prompt_tokens": 12,
            "prompt_tokens_details": {"cached_tokens": 3, "audio_tokens": 2},
            "completion_tokens": 7,
            "completion_tokens_details": {
                "reasoning_tokens": 4,
                "api_key": "synthetic-secret",
            },
            "input_tokens_details": {"cached_tokens": 5},
            "output_tokens_details": {"reasoning_tokens": 6},
        }
    }

    assert sanitize_for_json(payload) == {
        "usage": {
            "prompt_tokens": 12,
            "prompt_tokens_details": {"cached_tokens": 3, "audio_tokens": 2},
            "completion_tokens": 7,
            "completion_tokens_details": {
                "reasoning_tokens": 4,
                "api_key": "***REDACTED***",
            },
            "input_tokens_details": {"cached_tokens": 5},
            "output_tokens_details": {"reasoning_tokens": 6},
        }
    }
