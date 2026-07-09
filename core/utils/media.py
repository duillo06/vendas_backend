from django.conf import settings


def absolutize_media_url(url: str | None, request=None) -> str | None:
    """Converte /media/... em URL absoluta pra o front (Vite) conseguir carregar."""
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url

    path = url if url.startswith("/") else f"/{url}"

    if request is not None:
        return request.build_absolute_uri(path)

    base = getattr(settings, "MEDIA_PUBLIC_BASE_URL", None) or "http://localhost:8001"
    return f"{base.rstrip('/')}{path}"
