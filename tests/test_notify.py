import requests

from granthound.notify import ORDER, format_cycle_summary, notify_cycle, read_telegram_target, send_telegram
from granthound.pipeline.finalize import ProgramOutcome, RunSummary
from granthound.store.models import Disposition, Verdict


def summary(run_id="run-20260906T113800Z", status="ok", verdicts=("APPLY", "PASS", "NEEDS_HUMAN")):
    outcomes = [ProgramOutcome(f"p{i}", Verdict(v), Disposition.VERIFIED_LIVE, "sk", []) for i, v in enumerate(verdicts)]
    counts = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    return RunSummary(run_id=run_id, status=status, outcomes=outcomes, run_item={"verdict_counts": counts}, errors=[])


def test_summary_text_is_counts_and_labels_only():
    text = format_cycle_summary([summary(), summary(run_id="run-20260906T113900Z", verdicts=("WATCH",))], site_url="https://d1.cloudfront.net")
    assert text.startswith("GrantHound evaluated 4 programs")
    assert "APPLY 1" in text and "PASS 1" in text and "NEEDS REVIEW 1" in text and "WATCH 1" in text
    assert "runs run-20260906T113800Z, run-20260906T113900Z" in text
    assert text.rstrip().endswith("https://d1.cloudfront.net")


def test_summary_marks_a_partial_run():
    text = format_cycle_summary([summary(status="partial")], site_url=None)
    assert "1 run did not finish" in text and "http" not in text


def test_program_count_is_correctly_pluralized():
    assert "GrantHound evaluated 1 program." in format_cycle_summary([summary(verdicts=("APPLY",))], site_url=None)
    assert "GrantHound evaluated 2 programs." in format_cycle_summary([summary(verdicts=("APPLY", "PASS"))], site_url=None)


def test_dropped_chunks_are_reported_even_when_some_summaries_are_missing():
    text = format_cycle_summary([summary()], site_url=None, chunks_attempted=2)
    assert "1 of 2 chunks did not report." in text


def test_all_chunks_missing_still_produces_a_message():
    text = format_cycle_summary([], site_url=None, chunks_attempted=2)
    assert "GrantHound evaluated 0 programs." in text
    assert "2 of 2 chunks did not report." in text


def test_mismatched_verdict_counts_are_flagged():
    s = summary(verdicts=("APPLY", "PASS", "NEEDS_HUMAN"))
    s.run_item["verdict_counts"] = {"APPLY": 1}  # 2 of the 3 outcomes have no counted verdict
    text = format_cycle_summary([s], site_url=None)
    assert "Verdict counts cover 1 of 3." in text


def test_order_covers_every_verdict():
    assert set(ORDER) == {v.value for v in Verdict}


def test_read_target_parses_token_and_chat_id():
    class FakeSSM:
        def get_parameter(self, Name, WithDecryption):
            assert WithDecryption is True and Name == "/granthound/telegram"
            return {"Parameter": {"Value": "123:abc|-1001"}}
    assert read_telegram_target("/granthound/telegram", ssm_client=FakeSSM()) == ("123:abc", "-1001")


def test_read_target_returns_none_when_parameter_is_missing():
    class Missing:
        class exceptions:
            class ParameterNotFound(Exception):
                pass
        def get_parameter(self, Name, WithDecryption):
            raise self.exceptions.ParameterNotFound()
    assert read_telegram_target("/granthound/telegram", ssm_client=Missing()) is None


def test_send_posts_to_the_bot_api_and_reports_http_failure():
    calls = []
    def ok(url, json, timeout):
        calls.append((url, json, timeout))
        class R:
            status_code = 200
            text = "ok"
        return R()
    assert send_telegram("123:abc", "-1001", "hello", post=ok) is True
    assert calls[0][0] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert calls[0][1] == {"chat_id": "-1001", "text": "hello", "disable_web_page_preview": True}
    def bad(url, json, timeout):
        class R:
            status_code = 403
            text = "forbidden"
        return R()
    assert send_telegram("123:abc", "-1001", "hello", post=bad) is False


def test_notify_cycle_skips_without_env_and_never_raises():
    assert notify_cycle([summary()], env={}) == "skipped: no GRANTHOUND_TELEGRAM_PARAM"
    class Boom:
        class exceptions:
            class ParameterNotFound(Exception):
                pass
        def get_parameter(self, **kw):
            raise RuntimeError("ssm down")
    result = notify_cycle([summary()], env={"GRANTHOUND_TELEGRAM_PARAM": "/x"}, ssm_client=Boom())
    assert result.startswith("failed: ") and "ssm down" in result


def test_send_failure_never_leaks_the_token_into_the_log():
    class FakeSSM:
        def get_parameter(self, Name, WithDecryption):
            return {"Parameter": {"Value": "123:abc|-1001"}}
    def boom(url, json, timeout):
        raise requests.ConnectionError(
            "HTTPSConnectionPool(host='api.telegram.org', port=443): "
            "Max retries exceeded with url: /bot123:abc/sendMessage (Caused by NewConnectionError(...))"
        )
    result = notify_cycle([summary()], env={"GRANTHOUND_TELEGRAM_PARAM": "/x"}, post=boom, ssm_client=FakeSSM())
    assert "123:abc" not in result
    assert result.startswith("failed: ConnectionError")


def test_outer_failures_also_scrub_any_bot_url_from_the_message():
    class LeakySSM:
        class exceptions:
            class ParameterNotFound(Exception):
                pass
        def get_parameter(self, Name, WithDecryption):
            raise RuntimeError("boom while calling https://api.telegram.org/bot123:abc/sendMessage")
    result = notify_cycle([summary()], env={"GRANTHOUND_TELEGRAM_PARAM": "/x"}, ssm_client=LeakySSM())
    assert "123:abc" not in result
    assert result.startswith("failed: RuntimeError")
