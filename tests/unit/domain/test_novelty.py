from datetime import UTC, datetime, timedelta

from app.domain.novelty import MissionCandidate, is_new, next_challenge

NOW = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def mission(
    id: int,
    challenge_ids: tuple[int, ...],
    *,
    is_base: bool = False,
    published_days_ago: float | None = 30,
    position: int = 0,
) -> MissionCandidate:
    published_at = None if published_days_ago is None else days_ago(published_days_ago)
    return MissionCandidate(id, is_base, published_at, position, challenge_ids)


# "Novo" label


def test_T_DOM_NEW_01_recent_and_unanswered_turma_content_is_new():
    assert is_new(days_ago(1), NOW, is_base=False, answered=False)
    assert is_new(days_ago(7), NOW, is_base=False, answered=False)


def test_T_DOM_NEW_02_older_than_seven_days_is_not_new():
    assert not is_new(days_ago(7) - timedelta(seconds=1), NOW, is_base=False, answered=False)
    assert not is_new(days_ago(8), NOW, is_base=False, answered=False)


def test_T_DOM_NEW_03_answered_content_is_not_new():
    assert not is_new(days_ago(1), NOW, is_base=False, answered=True)


def test_T_DOM_NEW_04_base_content_is_never_new():
    assert not is_new(days_ago(0), NOW, is_base=True, answered=False)


def test_T_DOM_NEW_05_never_published_is_not_new():
    assert not is_new(None, NOW, is_base=False, answered=False)


# Continuar card


def test_T_DOM_CONT_01_continues_the_mission_of_the_latest_answer():
    missions = [
        mission(1, (10, 11), is_base=True, position=0),
        mission(2, (20, 21, 22), is_base=True, position=1),
    ]
    assert next_challenge(missions, solved={20}, last_challenge_id=20) == (2, 21)


def test_T_DOM_CONT_02_challenge_in_several_missions_prefers_turma_then_newest():
    missions = [
        mission(1, (5, 6), is_base=True),
        mission(2, (5, 7), published_days_ago=10),
        mission(3, (5, 8), published_days_ago=2, position=4),
        mission(4, (5, 9), published_days_ago=2, position=1),
    ]
    assert next_challenge(missions, solved={5}, last_challenge_id=5) == (4, 9)


def test_T_DOM_CONT_03_finished_last_mission_goes_to_turma_missions_newest_first():
    missions = [
        mission(1, (10,), is_base=True),
        mission(2, (20, 21), is_base=True, position=1),
        mission(3, (30, 31), published_days_ago=9),
        mission(4, (40, 41), published_days_ago=1),
        mission(5, (50,), published_days_ago=None),
    ]
    assert next_challenge(missions, solved={10, 40}, last_challenge_id=10) == (4, 41)
    assert next_challenge(missions, solved={10, 40, 41}, last_challenge_id=41) == (3, 30)
    solved = {10, 30, 31, 40, 41}
    assert next_challenge(missions, solved=solved, last_challenge_id=10) == (5, 50)


def test_T_DOM_CONT_04_without_turma_work_goes_to_base_in_mission_order():
    missions = [
        mission(7, (70, 71), is_base=True, position=2),
        mission(8, (80, 81), is_base=True, position=1),
        mission(9, (90,), published_days_ago=3),
    ]
    assert next_challenge(missions, solved={90, 80}, last_challenge_id=None) == (8, 81)
    assert next_challenge(missions, solved={90, 80, 81}, last_challenge_id=90) == (7, 70)


def test_T_DOM_CONT_05_everything_solved_gives_none():
    missions = [mission(1, (10, 11), is_base=True), mission(2, (20,))]
    assert next_challenge(missions, solved={10, 11, 20}, last_challenge_id=20) is None
    assert next_challenge([], solved=set(), last_challenge_id=None) is None


def test_T_DOM_CONT_06_latest_answer_outside_every_mission_is_ignored():
    missions = [mission(1, (10, 11), is_base=True)]
    assert next_challenge(missions, solved={10}, last_challenge_id=99) == (1, 11)


def test_T_DOM_CONT_07_first_unsolved_follows_mission_order_not_ids():
    missions = [mission(1, (30, 10, 20), is_base=True)]
    assert next_challenge(missions, solved={30}, last_challenge_id=30) == (1, 10)
