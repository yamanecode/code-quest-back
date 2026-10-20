import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# The domain may not import app.core, so it keeps its own copy of the game time zone.
TIMEZONE = ZoneInfo("America/Sao_Paulo")

XP_PER_LEVEL = 50

# (lowest level of the band, title), highest band first.
LEVEL_TITLES = (
    (11, "Mestre do pensamento"),
    (8, "Arquiteto(a) de soluções"),
    (5, "Estrategista"),
    (3, "Explorador(a)"),
    (1, "Aprendiz"),
)


def _to_local(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(TIMEZONE)


def local_date(moment: datetime) -> date:
    return _to_local(moment).date()


def xp_for_wrong_attempts(wrong_attempts: int) -> int:
    if wrong_attempts < 0:
        raise ValueError("wrong_attempts cannot be negative")
    if wrong_attempts == 0:
        return 10
    if wrong_attempts <= 2:
        return 5
    return 2


def level_for(xp: int) -> int:
    return xp // XP_PER_LEVEL + 1


def xp_to_next_level(xp: int) -> int:
    return XP_PER_LEVEL - xp % XP_PER_LEVEL


def title_for(level: int) -> str:
    return next(title for lowest, title in LEVEL_TITLES if level >= lowest)


def streak(days_with_solve: set[date], today: date) -> int:
    """Consecutive days with a solve, ending today or yesterday."""
    day = today if today in days_with_solve else today - timedelta(days=1)
    count = 0
    while day in days_with_solve:
        count += 1
        day -= timedelta(days=1)
    return count


def mission_completed(challenge_ids: Iterable[int], solved_ids: set[int]) -> bool:
    """A mission counts as completed when it has challenges and all of them are solved."""
    ids = set(challenge_ids)
    return bool(ids) and ids <= solved_ids


def week_start(moment: datetime) -> datetime:
    local = _to_local(moment)
    monday = local.date() - timedelta(days=local.weekday())
    return datetime.combine(monday, time(), tzinfo=TIMEZONE)


def month_start(moment: datetime) -> datetime:
    local = _to_local(moment)
    return datetime(local.year, local.month, 1, tzinfo=TIMEZONE)


@dataclass(frozen=True)
class RankRow:
    user_id: int
    username: str
    xp: int


@dataclass(frozen=True)
class RankedRow:
    position: int
    user_id: int
    username: str
    xp: int


def dense_rank(rows: Iterable[RankRow]) -> list[RankedRow]:
    """Highest XP first; equal XP share a position and are listed by username."""
    ranked = []
    position = 0
    previous_xp = None
    for row in sorted(rows, key=lambda row: (-row.xp, row.username)):
        if row.xp != previous_xp:
            position += 1
            previous_xp = row.xp
        ranked.append(RankedRow(position, row.user_id, row.username, row.xp))
    return ranked


def window_around(ranked: list[RankedRow], user_id: int, k: int = 2) -> list[RankedRow]:
    """The user's row with up to k rows above and k rows below."""
    index = next((i for i, row in enumerate(ranked) if row.user_id == user_id), None)
    if index is None:
        return []
    return ranked[max(0, index - k) : index + k + 1]


def daily_pick(user_id: int, day: date, candidate_ids: Iterable[int]) -> int | None:
    candidates = sorted(candidate_ids)
    if not candidates:
        return None
    digest = hashlib.sha256(f"{user_id}:{day.isoformat()}".encode()).hexdigest()
    return candidates[int(digest, 16) % len(candidates)]


def goal_target(weekly_goal: int | None, member_count: int, available: int) -> int | None:
    """Weekly class goal; None when the turma has no open first solves this week."""
    if available <= 0:
        return None
    base_target = weekly_goal if weekly_goal is not None else max(10, 5 * member_count)
    return min(base_target, available)
