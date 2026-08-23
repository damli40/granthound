import pytest

from granthound.config import HAIKU_MODEL_ID, SONNET_MODEL_ID, Settings


def test_defaults_fill_in_when_optional_vars_are_absent():
    s = Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b"})
    assert s.region == "us-east-1"
    assert s.haiku_model_id == HAIKU_MODEL_ID == "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert s.analyst_model_id == SONNET_MODEL_ID == "global.anthropic.claude-sonnet-5"


def test_every_missing_variable_is_named_at_once():
    with pytest.raises(KeyError) as exc:
        Settings.from_env({})
    assert "GRANTHOUND_TABLE" in str(exc.value) and "GRANTHOUND_BUCKET" in str(exc.value)


def test_empty_string_counts_as_missing():
    with pytest.raises(KeyError, match="GRANTHOUND_BUCKET"):
        Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "   "})


def test_overrides_are_honored_and_stripped():
    s = Settings.from_env({
        "GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b", "AWS_REGION": " us-west-2 ",
        "GRANTHOUND_ANALYST_MODEL_ID": HAIKU_MODEL_ID,
    })
    assert s.region == "us-west-2" and s.analyst_model_id == HAIKU_MODEL_ID
