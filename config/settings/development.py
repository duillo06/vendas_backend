from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", ".localhost", "*"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]

# acesso pelo IP da LAN (ex: http://192.168.x.x:5175) e Tailscale (100.x)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://[\w-]+\.localhost:5174$",
    r"^http://192\.168\.\d{1,3}\.\d{1,3}:517[45]$",
    r"^http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}:517[45]$",
    r"^http://100\.\d{1,3}\.\d{1,3}\.\d{1,3}:517[45]$",
    r"^https://[\w-]+\.ngrok-free\.app$",
    r"^https://[\w-]+\.ngrok\.app$",
    r"^https://[\w-]+\.ngrok\.io$",
    r"^https://[\w-]+\.ngrok-free\.dev$",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "https://*.ngrok-free.app",
    "https://*.ngrok.app",
    "https://*.ngrok.io",
    "https://*.ngrok-free.dev",
    "http://*.ts.net",
]
