#!/usr/bin/env python
"""Atalho pro comando seed_dev."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ENV", "development")

if __name__ == "__main__":
    django.setup()
    from django.core.management import call_command

    call_command("seed_dev")
