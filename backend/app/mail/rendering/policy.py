"""Rendering policy for email HTML — image blocking, CID replacement, link safety."""
import re


def apply_render_policy(
    html: str,
    block_remote_images: bool = True,
    cid_map: dict[str, str] | None = None,
) -> dict:
    """Apply rendering policy to sanitized HTML.

    Returns: {"html": str, "has_remote_images": bool, "blocked_image_count": int}
    """
    if not html:
        return {"html": "", "has_remote_images": False, "blocked_image_count": 0}

    has_remote_images = False
    blocked_count = 0

    if cid_map:
        for cid, data_url in cid_map.items():
            html = html.replace(f"cid:{cid}", data_url)

    def replace_img(match):
        nonlocal has_remote_images, blocked_count
        full_tag = match.group(0)
        src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', full_tag)
        if not src_match:
            return full_tag
        src = src_match.group(1)
        if src.startswith(("cid:", "data:")):
            return full_tag
        has_remote_images = True
        if block_remote_images:
            blocked_count += 1
            alt = ""
            alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', full_tag)
            if alt_match:
                alt = alt_match.group(1)
            return f'<span class="blocked-image" data-original-src="{src}" title="{alt}">[Imagen bloqueada]</span>'
        return full_tag

    html = re.sub(r"<img\s[^>]*>", replace_img, html, flags=re.IGNORECASE)
    html = re.sub(r'<a\s', '<a target="_blank" rel="noopener noreferrer nofollow" ', html, flags=re.IGNORECASE)
    html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<object[^>]*>.*?</object>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<embed[^>]*>", "", html, flags=re.IGNORECASE)

    return {"html": html, "has_remote_images": has_remote_images, "blocked_image_count": blocked_count}
