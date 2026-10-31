from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

# The domain may not import app.core, so it keeps its own copy of the game time zone.
TIMEZONE = ZoneInfo("America/Sao_Paulo")

XP_PER_LEVEL = 30
FIRST_TRY_XP = 10
PERSISTENT_XP = 2  # first solve after 3 or more wrong answers

# (lowest level of the band, title), highest band first.
LEVEL_TITLES = (
    (11, "Mestre"),
    (8, "Especialista"),
    (5, "Praticante"),
    (3, "Aprendiz"),
    (1, "Iniciante"),
)

# The same bands lowest first, as (title, first level, last level or None): the profile ladder.
_LOWEST_FIRST = tuple(reversed(LEVEL_TITLES))
TITLE_STEPS = tuple(
    (title, lowest, next_band[0] - 1 if next_band else None)
    for (lowest, title), next_band in zip(_LOWEST_FIRST, (*_LOWEST_FIRST[1:], None), strict=True)
)


def _to_local(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(TIMEZONE)


def xp_for_wrong_attempts(wrong_attempts: int) -> int:
    if wrong_attempts < 0:
        raise ValueError("wrong_attempts cannot be negative")
    if wrong_attempts == 0:
        return FIRST_TRY_XP
    if wrong_attempts <= 2:
        return 5
    return PERSISTENT_XP


def level_for(xp: int) -> int:
    return xp // XP_PER_LEVEL + 1


def xp_to_next_level(xp: int) -> int:
    return XP_PER_LEVEL - xp % XP_PER_LEVEL


def title_for(level: int) -> str:
    return next(title for lowest, title in LEVEL_TITLES if level >= lowest)


def mission_completed(challenge_ids: Iterable[int], solved_ids: set[int]) -> bool:
    """A mission counts as completed when it has challenges and all of them are solved."""
    ids = set(challenge_ids)
    return bool(ids) and ids <= solved_ids


def completed_every_mission(missions: Iterable[Iterable[int]], solved_ids: set[int]) -> bool:
    """A turma with no completable mission is never 'completed'."""
    challenge_lists = list(missions)
    return bool(challenge_lists) and all(
        mission_completed(ids, solved_ids) for ids in challenge_lists
    )


def solved_in_every_mission(missions: Iterable[Iterable[int]], solved_ids: set[int]) -> bool:
    """At least one solved challenge in each mission that has challenges."""
    challenge_sets = [set(ids) for ids in missions]
    challenge_sets = [ids for ids in challenge_sets if ids]
    return bool(challenge_sets) and all(ids & solved_ids for ids in challenge_sets)


def week_start(moment: datetime) -> datetime:
    local = _to_local(moment)
    monday = local.date() - timedelta(days=local.weekday())
    return datetime.combine(monday, time(), tzinfo=TIMEZONE)


def month_start(moment: datetime) -> datetime:
    local = _to_local(moment)
    return datetime(local.year, local.month, 1, tzinfo=TIMEZONE)


class RankingScope(StrEnum):
    GLOBAL = "global"
    CLASSROOM = "classroom"


class RankingPeriod(StrEnum):
    WEEK = "week"
    MONTH = "month"


def period_start(period: RankingPeriod, now: datetime) -> datetime:
    return week_start(now) if period == RankingPeriod.WEEK else month_start(now)


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


def goal_target(weekly_goal: int | None, member_count: int, available: int) -> int | None:
    """Weekly class goal; None when the turma has no open first solves this week."""
    if available <= 0:
        return None
    base_target = weekly_goal if weekly_goal is not None else max(10, 5 * member_count)
    return min(base_target, available)


def goal_reached(progress: int, target: int) -> bool:
    return progress >= target


def completion_pct(completed: int, total: int) -> int:
    """Whole percentage, rounding halves up; 0 when there is nobody to count."""
    if total == 0:
        return 0
    return (200 * completed + total) // (2 * total)
