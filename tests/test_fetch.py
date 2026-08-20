from granthound.tools.fetch import digest, normalize_html

PAGE = """
<html><head><title>Grants</title><script>var x=1;</script>
<style>.a{color:red}</style></head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<main>
  <h1>Community Grants</h1>
  <p>Applications are due   October 15, 2026.</p>
</main>
<footer>Copyright 2020 Example Org</footer>
</body></html>
"""


def test_script_and_style_stripped():
    norm = normalize_html(PAGE)
    assert "var x=1" not in norm
    assert "color:red" not in norm


def test_deadline_sentence_survives():
    norm = normalize_html(PAGE)
    assert "October 15, 2026" in norm


def test_nav_stripped_main_kept():
    norm = normalize_html(PAGE)
    assert "Community Grants" in norm
    assert "About" not in norm


def test_whitespace_runs_collapse_to_stable_digest():
    variant = PAGE.replace("due   October", "due October")
    assert digest(normalize_html(PAGE)) == digest(normalize_html(variant))


def test_digest_is_sha256_hex():
    d = digest("hello")
    assert len(d) == 64 and all(c in "0123456789abcdef" for c in d)


def test_nbsp_collapses_like_regular_space():
    a = "<p>Applications are due October 15, 2026.</p>"
    b = "<p>Applications are due October&nbsp;15,&nbsp;2026.</p>"
    assert digest(normalize_html(a)) == digest(normalize_html(b))


def test_nbsp_runs_collapse_to_single_space():
    html = "<p>Due&nbsp;&nbsp;&nbsp;October 15, 2026</p>"
    norm = normalize_html(html)
    assert "Due October 15, 2026" in norm
