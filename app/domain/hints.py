import math
from datetime import datetime

HINT_MAX_LEVEL = 3


def hint_level(requested_shown: int) -> int:
    """1 orientation, 2 instrumental, 3 worked example (and it stays at 3)."""
    return min(requested_shown + 1, HINT_MAX_LEVEL)


def pick_variant(variants: tuple[str, ...], shown: list[str]) -> str:
    """The first variant not shown yet; once all were shown, the one shown longest ago."""
    last_shown = {text: position for position, text in enumerate(shown)}
    return min(variants, key=lambda text: last_shown.get(text, -1))


def cooldown_left(last_shown_at: datetime | None, now: datetime, cooldown_seconds: int) -> int:
    """Whole seconds until another hint may be requested; 0 means it may be requested now."""
    if last_shown_at is None:
        return 0
    remaining = cooldown_seconds - (now - last_shown_at).total_seconds()
    return max(math.ceil(remaining), 0)
