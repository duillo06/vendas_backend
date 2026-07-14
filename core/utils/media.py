from urllib.parse import urlparse

from django.conf import settings


def media_path(url: str | None) -> str | None:
    """Extrai só o path /media/... (aceita absoluto ou relativo)."""
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        path = urlparse(url).path or ""
    else:
        path = url if url.startswith("/") else f"/{url}"
    return path or None


def absolutize_media_url(url: str | None, request=None) -> str | None:
    """
    URL pública de mídia.

    Em dev com Vite (proxy /media), path relativo evita ERR_CONNECTION_REFUSED
    quando o browser está em outro host (LAN / Windows → VM).
    """
    path = media_path(url)
    if not path:
        return None

    # relative = mesma origem do front (5174/5175) → Vite proxy → Django
    use_relative = getattr(settings, "MEDIA_USE_RELATIVE_URLS", True)
    if use_relative and path.startswith("/media"):
        return path

    if request is not None:
        return request.build_absolute_uri(path)

    base = getattr(settings, "MEDIA_PUBLIC_BASE_URL", None) or ""
    if base:
        return f"{base.rstrip('/')}{path}"
    return path
