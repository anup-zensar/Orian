"""Allow-list HTML sanitiser (PLAN A-56, VAPT)."""

from __future__ import annotations

from app.domain.html_sanitize import sanitize_html


def test_strips_script_with_content():
    out = sanitize_html("<p>Hi</p><script>alert(1)</script><p>there</p>")
    assert out == "<p>Hi</p><p>there</p>"


def test_strips_javascript_links_and_handlers():
    out = sanitize_html('<a href="javascript:alert(1)" onclick="x()">go</a>')
    assert "javascript" not in out and "onclick" not in out and "go" in out
    assert "href" not in sanitize_html('<a href="  JaVa\tScript:alert(1)">go</a>')
    assert "href" not in sanitize_html('<a href="data:text/html,x">x</a>')
    assert "href" not in sanitize_html('<a href="//evil.example/x">x</a>')


def test_keeps_safe_links_and_markup():
    out = sanitize_html(
        '<ul><li><a href="https://x.example/a?b=1&amp;c=2" target="_blank" style="x">A</a></li></ul>'
        '<a href="mailto:a@b.co">m</a><a href="/transitions/TR-0001/gates">r</a>'
    )
    assert 'href="https://x.example/a?b=1&amp;c=2"' in out
    assert "target" not in out and "style" not in out
    assert 'href="mailto:a@b.co"' in out and 'href="/transitions/TR-0001/gates"' in out
    assert "<ul><li>" in out


def test_drops_disallowed_tags_keeps_text_and_escapes():
    out = sanitize_html('<iframe src="x">bad</iframe><img src=x onerror=y>t<h1>H</h1> 1 < 2 <b>b')
    assert "iframe" not in out and "img" not in out and "<h1" not in out and "bad" not in out
    assert "H" in out and "1 &lt; 2" in out
    assert out.endswith("<b>b</b>")


def test_idempotent_and_empty():
    once = sanitize_html('<p>a<br>b <a href="http://e.co">l</a></p>')
    assert sanitize_html(once) == once
    assert sanitize_html("") == "" and sanitize_html(None) == ""
