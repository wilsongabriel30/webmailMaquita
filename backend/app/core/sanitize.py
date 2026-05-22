"""Server-side HTML sanitization using nh3 (already a dependency)."""
import nh3
import html


def sanitize_html(dirty: str) -> str:
    """Sanitize HTML — allow safe tags for email/signature content."""
    if not dirty:
        return dirty
    return nh3.clean(
        dirty,
        tags={
            "a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2",
            "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p",
            "pre", "s", "small", "span", "strong", "table", "tbody", "td",
            "tfoot", "th", "thead", "tr", "u", "ul", "sub", "sup", "center",
            "font",
        },
        attributes={
            "*": {"style", "class", "id", "dir", "lang"},
            "a": {"href", "target", "title"},
            "img": {"src", "alt", "title", "width", "height"},
            "td": {"colspan", "rowspan", "align", "valign"},
            "th": {"colspan", "rowspan", "align", "valign"},
            "table": {"border", "cellpadding", "cellspacing", "bgcolor", "width"},
            "font": {"color", "size", "face"},
        },
        url_schemes={"http", "https", "mailto", "cid"},
    )


def strip_html(dirty: str) -> str:
    """Strip ALL HTML tags — for plain text fields like subject, title."""
    if not dirty:
        return dirty
    # First strip with nh3, then html.unescape for entities
    cleaned = nh3.clean(dirty, tags=set())
    return html.unescape(cleaned).strip()


def sanitize_calendar_field(value: str, allow_html: bool = False) -> str:
    """Sanitize calendar event fields."""
    if not value:
        return value
    if allow_html:
        return sanitize_html(value)
    return strip_html(value)
