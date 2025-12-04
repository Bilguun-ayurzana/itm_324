from urllib.parse import urljoin, urlparse, urlunparse

def normalize_url(raw, base=None):
    """Normalize URL and remove fragments, trailing slashes"""
    try:
        full = urljoin(base or "", raw)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None

        parsed = parsed._replace(fragment="")
        path = parsed.path.rstrip("/") if parsed.path not in ("/", "") else parsed.path
        parsed = parsed._replace(path=path)

        return urlunparse(parsed)
    except:
        return None
