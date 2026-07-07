from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")  # noqa: F405
