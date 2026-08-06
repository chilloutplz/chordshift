from django.conf import settings


def _setting(name, default):
    return getattr(settings, name, default)


# =========================
# Chord
# =========================
DEFAULT_CHORD_FONT_SIZE = _setting("DEFAULT_CHORD_FONT_SIZE", 15)