import re

# No 0, 1, I or O, so a code copied by hand cannot be misread.
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_LENGTH = 16
GROUP_SIZE = 4

_WELL_FORMED = re.compile(f"[{ALPHABET}]{{{CODE_LENGTH}}}")


def normalize_recovery_code(text: str) -> str:
    """Upper-case and drop hyphens and spaces, so the code may be typed in any style."""
    return re.sub(r"[-\s]", "", text).upper()


def format_recovery_code(raw: str) -> str:
    groups = (raw[i : i + GROUP_SIZE] for i in range(0, len(raw), GROUP_SIZE))
    return "-".join(groups)


def is_well_formed(text: str) -> bool:
    return _WELL_FORMED.fullmatch(normalize_recovery_code(text)) is not None
