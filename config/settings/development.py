from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
