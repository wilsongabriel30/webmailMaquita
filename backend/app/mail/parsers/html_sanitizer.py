"""HTML sanitizer for email content — uses nh3 (Rust-based)."""
import nh3
import re

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "center", "cite",
    "code", "col", "colgroup", "dd", "div", "dl", "dt", "em", "font",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol",
    "p", "pre", "q", "s", "small", "span", "strong", "sub", "sup",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
    "big", "del", "ins", "mark",
}

ALLOWED_ATTRIBUTES = {
    "*": {"style", "class", "id", "dir", "lang", "title"},
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height", "style"},
    "td": {"colspan", "rowspan", "align", "valign", "width", "height", "style"},
    "th": {"colspan", "rowspan", "align", "valign", "width", "height", "style"},
    "table": {"border", "cellpadding", "cellspacing", "width", "style"},
    "col": {"span", "width"},
    "colgroup": {"span"},
    "font": {"color", "size", "face"},
    "div": {"align"},
    "p": {"align"},
    "span": {"style"},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML email content. Removes scripts, events, dangerous elements."""
    if not html:
        return ""
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*\S+', "", html, flags=re.IGNORECASE)
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto", "cid", "data"},
        link_rel="noopener noreferrer nofollow",
    )


def strip_html(html: str) -> str:
    """Strip all HTML tags, returning plain text."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
