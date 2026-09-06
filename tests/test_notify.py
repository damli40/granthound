from granthound.notify import format_cycle_summary, notify_cycle, read_telegram_target, send_telegram
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
    assert text.startswith("GrantHound checked 4 pages")
    assert "APPLY 1" in text and "PASS 1" in text and "NEEDS REVIEW 1" in text and "WATCH 1" in text
    assert "runs run-20260906T113800Z, run-20260906T113900Z" in text
    assert text.rstrip().endswith("https://d1.cloudfront.net")


def test_summary_marks_a_partial_run():
    text = format_cycle_summary([summary(status="partial")], site_url=None)
    assert "1 run did not finish" in text and "http" not in text


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
        def get_parameter(self, **kw):
            raise RuntimeError("ssm down")
    assert notify_cycle([summary()], env={"GRANTHOUND_TELEGRAM_PARAM": "/x"}, ssm_client=Boom()).startswith("failed: ")
