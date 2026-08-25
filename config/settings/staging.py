"""Staging = mesmas travas de prod, ambiente Sentry separado."""

import os

# antes do import de production (Sentry lê SENTRY_ENVIRONMENT no init)
os.environ.setdefault("SENTRY_ENVIRONMENT", "staging")

from .production import *  # noqa: F403, E402
