"""Telegram summary after a cycle. Counts and fixed labels only; nothing composed.

The bot token and chat id live in one SSM SecureString named by
GRANTHOUND_TELEGRAM_PARAM, value "<token>|<chat id>". They never touch the
repo. Every failure here is a return value the caller logs; a cycle is
never failed by a notification.

The token must never reach a log either. `send_telegram` posts to a URL that
contains it, so any connection-class failure there is reduced to the
exception's type name only -- never its message, which `requests` fills with
the failing URL. Any other failure on this path (SSM, formatting) is scrubbed
for a /bot<token>/ segment before its text is returned, on the chance a
lower-level library ever echoes the request back into its own error.
"""

import re
from collections import Counter
from collections.abc import Mapping

import requests

VERDICT_LABEL = {"APPLY": "APPLY", "PASS": "PASS", "WATCH": "WATCH", "NEEDS_HUMAN": "NEEDS REVIEW"}
ORDER = ("APPLY", "WATCH", "NEEDS_HUMAN", "PASS")

_BOT_URL = re.compile(r"/bot[^/\s]+/")


def format_cycle_summary(summaries: list, *, site_url: str | None, chunks_attempted: int | None = None) -> str:
    counts: Counter = Counter()
    for s in summaries:
        counts.update(s.run_item.get("verdict_counts") or {})
    pages = sum(len(s.outcomes) for s in summaries)
    unfinished = sum(1 for s in summaries if s.status != "ok")
    parts = [f"GrantHound evaluated {pages} program{'s' if pages != 1 else ''}."]
    verdict_bits = [f"{VERDICT_LABEL[v]} {counts[v]}" for v in ORDER if counts.get(v)]
    if verdict_bits:
        parts.append(" / ".join(verdict_bits) + ".")
    total_counted = sum(counts.values())
    if total_counted != pages:
        parts.append(f"Verdict counts cover {total_counted} of {pages}.")
    if unfinished:
        parts.append(f"{unfinished} run{'s' if unfinished != 1 else ''} did not finish.")
    if chunks_attempted is not None and chunks_attempted != len(summaries):
        missing = chunks_attempted - len(summaries)
        parts.append(f"{missing} of {chunks_attempted} chunks did not report.")
    if summaries:
        parts.append("runs " + ", ".join(s.run_id for s in summaries) + ".")
    if site_url:
        parts.append(site_url)
    return "\n".join(parts)


def read_telegram_target(param_name: str, *, ssm_client=None) -> tuple[str, str] | None:
    import boto3

    client = ssm_client or boto3.client("ssm")
    try:
        value = client.get_parameter(Name=param_name, WithDecryption=True)["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        return None
    token, sep, chat_id = value.partition("|")
    if not sep or not token.strip() or not chat_id.strip():
        raise ValueError("telegram parameter must be '<token>|<chat id>'")
    return token.strip(), chat_id.strip()


def send_telegram(token: str, chat_id: str, text: str, *, post=None) -> bool:
    poster = post or requests.post
    response = poster(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=15,
    )
    return response.status_code == 200


def notify_cycle(
    summaries: list,
    *,
    env: Mapping[str, str],
    chunks_attempted: int | None = None,
    post=None,
    ssm_client=None,
) -> str:
    param = (env.get("GRANTHOUND_TELEGRAM_PARAM") or "").strip()
    if not param:
        return "skipped: no GRANTHOUND_TELEGRAM_PARAM"
    try:
        target = read_telegram_target(param, ssm_client=ssm_client)
        if target is None:
            return "skipped: parameter not found"
        token, chat_id = target
        text = format_cycle_summary(
            summaries,
            site_url=(env.get("GRANTHOUND_SITE_URL") or "").strip() or None,
            chunks_attempted=chunks_attempted,
        )
        try:
            sent = send_telegram(token, chat_id, text, post=post)
        except Exception as exc:  # noqa: BLE001 -- the request URL carries the token; never surface its text
            return f"failed: {type(exc).__name__}"
        return "sent" if sent else "failed: telegram api rejected the message"
    except Exception as exc:  # noqa: BLE001 -- a notification must never fail the cycle
        return f"failed: {type(exc).__name__}: {_BOT_URL.sub('/bot[redacted]/', str(exc))}"
