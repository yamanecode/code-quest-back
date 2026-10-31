from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

NEW_FOR = timedelta(days=7)


def is_new(published_at: datetime | None, now: datetime, *, is_base: bool, answered: bool) -> bool:
    """Turma content published in the last 7 days that the student has not answered yet."""
    if is_base or answered or published_at is None:
        return False
    return now - published_at <= NEW_FOR


@dataclass(frozen=True)
class MissionCandidate:
    """A visible published mission with its published challenge ids in mission order."""

    id: int
    is_base: bool
    published_at: datetime | None
    position: int
    challenge_ids: tuple[int, ...]


def _newest_first(mission: MissionCandidate) -> tuple:
    # A mission without a publish date sorts after every dated one.
    published = mission.published_at
    return (published is None, -published.timestamp() if published else 0.0)


def _turma_order(mission: MissionCandidate) -> tuple:
    return (*_newest_first(mission), mission.position, mission.id)


def _first_unsolved(mission: MissionCandidate, solved: set[int]) -> int | None:
    return next((cid for cid in mission.challenge_ids if cid not in solved), None)


def next_challenge(
    missions: Iterable[MissionCandidate], solved: set[int], last_challenge_id: int | None
) -> tuple[int, int] | None:
    """(mission id, challenge id) for the Continuar card, or None when everything is solved."""
    open_missions = [m for m in missions if _first_unsolved(m, solved) is not None]

    # (a) the missions of the latest answer; a turma mission wins over a base one.
    current = [m for m in open_missions if last_challenge_id in m.challenge_ids]
    current.sort(key=lambda m: (m.is_base, *_turma_order(m)))
    # (b) turma missions, newest first; (c) base missions in mission order.
    turma = sorted((m for m in open_missions if not m.is_base), key=_turma_order)
    base = sorted((m for m in open_missions if m.is_base), key=lambda m: (m.position, m.id))

    ordered = [*current, *turma, *base]
    if not ordered:
        return None
    chosen = ordered[0]
    return chosen.id, _first_unsolved(chosen, solved)
