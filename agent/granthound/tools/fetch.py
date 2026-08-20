import hashlib
import re

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

_STRIP_TAGS = ("script", "style", "noscript", "nav", "footer", "iframe", "svg")
_WS_RE = re.compile(r"[ \t\xa0]+")
_NL_RE = re.compile(r"\n{3,}")


def normalize_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    md = markdownify(str(soup), heading_style="ATX")
    md = _WS_RE.sub(" ", md)
    md = "\n".join(line.strip() for line in md.splitlines())
    md = _NL_RE.sub("\n\n", md)
    return md.strip()


def digest(norm_text: str) -> str:
    return hashlib.sha256(norm_text.encode("utf-8")).hexdigest()


def fetch_page(url: str, timeout: int = 20) -> tuple[int, str]:
    """Fetch a page. Returns (status_code, body_text). Raises requests exceptions
    only for transport failures; HTTP error statuses are returned, not raised,
    so the pipeline can record PAGE_UNREACHABLE instead of crashing."""
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "GrantHound/0.1 (+nonprofit grant liveness checker)"},
    )
    return resp.status_code, resp.text
