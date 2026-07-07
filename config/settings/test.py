from .base import *  # noqa: F403

DATABASES = {  # noqa: F811
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {  # noqa: F811
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
