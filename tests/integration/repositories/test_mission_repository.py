from app.domain.enums import ContentStatus
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.missions import MissionRepository
from tests.integration.factories import (
    add_member,
    link,
    make_challenge,
    make_classroom,
    make_mission,
    make_user,
    submit,
)

DRAFT = ContentStatus.DRAFT


def test_T_REPO_09_visible_missions_are_published_base_and_member_turmas(session):
    ana = make_user(session)
    mine, other = make_classroom(session), make_classroom(session)
    add_member(session, ana, mine)
    base = make_mission(session)
    make_mission(session, status=DRAFT)
    turma_mission = make_mission(session, mine)
    make_mission(session, mine, status=DRAFT)
    make_mission(session, other)

    assert MissionRepository(session).visible_mission_ids(ana.id) == {base.id, turma_mission.id}


def test_T_REPO_10_visible_challenges_are_published_in_visible_missions(session):
    ana = make_user(session)
    mine, other = make_classroom(session), make_classroom(session)
    add_member(session, ana, mine)
    base, turma_mission = make_mission(session), make_mission(session, mine)
    visible_base = make_challenge(session, missions=(base,))
    visible_turma = make_challenge(session, missions=(turma_mission,))
    make_challenge(session, status=DRAFT, missions=(base,))
    make_challenge(session, missions=(make_mission(session, status=DRAFT),))
    make_challenge(session, missions=(make_mission(session, other),))

    visible = MissionRepository(session).visible_published_challenge_ids(ana.id)
    assert visible == {visible_base.id, visible_turma.id}


def test_T_REPO_30_set_challenges_replaces_links_in_the_given_order(session):
    mission = make_mission(session)
    first, second, third = (make_challenge(session) for _ in range(3))
    repo = MissionRepository(session)

    repo.set_challenges(mission.id, [first.id, second.id])
    repo.set_challenges(mission.id, [third.id, first.id])

    assert repo.challenge_ids(mission.id) == [third.id, first.id]


def test_T_REPO_23_deleting_a_challenge_removes_its_mission_links(session):
    mission = make_mission(session)
    kept, removed = make_challenge(session, missions=(mission,)), make_challenge(session)
    missions = MissionRepository(session)
    missions.set_challenges(mission.id, [kept.id, removed.id])

    ChallengeRepository(session).delete(removed)
    session.expire_all()

    assert missions.challenge_ids(mission.id) == [kept.id]


def test_T_REPO_31_mission_has_submissions_through_its_challenges(session):
    mission = make_mission(session)
    challenge = make_challenge(session, missions=(mission,))
    repo = MissionRepository(session)
    assert repo.has_submissions(mission.id) is False

    submit(session, make_user(session), challenge, correct=False)
    assert repo.has_submissions(mission.id) is True


def test_T_REPO_33_mission_has_published_challenge(session):
    repository = MissionRepository(session)
    empty = make_mission(session, status=DRAFT)
    drafts_only = make_mission(session, status=DRAFT)
    make_challenge(session, status=DRAFT, missions=(drafts_only,))
    ready = make_mission(session, status=DRAFT)
    make_challenge(session, status=DRAFT, missions=(ready,))
    make_challenge(session, missions=(ready,))

    assert repository.has_published_challenge(empty.id) is False
    assert repository.has_published_challenge(drafts_only.id) is False
    assert repository.has_published_challenge(ready.id) is True


def test_T_REPO_35_visible_missions_in_position_order(session):
    ana = make_user(session)
    mine = make_classroom(session)
    add_member(session, ana, mine)
    second = make_mission(session, position=2)
    first = make_mission(session, position=1)
    turma_mission = make_mission(session, mine, position=0)
    make_mission(session, status=DRAFT, position=0)
    make_mission(session, make_classroom(session), position=0)

    missions = MissionRepository(session).visible_missions(ana.id)

    assert [m.id for m in missions] == [turma_mission.id, first.id, second.id]


def test_T_REPO_36_published_challenge_ids_by_mission_in_mission_order(session):
    first, second, empty = make_mission(session), make_mission(session), make_mission(session)
    c1, c2, c3 = (make_challenge(session) for _ in range(3))
    draft = make_challenge(session, status=DRAFT)
    link(session, first, c2, position=0)
    link(session, first, draft, position=1)
    link(session, first, c1, position=2)
    link(session, second, c3, position=0)
    link(session, second, c1, position=1)

    by_mission = MissionRepository(session).published_challenge_ids_by_mission(
        [first.id, second.id, empty.id]
    )

    assert by_mission == {first.id: [c2.id, c1.id], second.id: [c3.id, c1.id], empty.id: []}


def test_T_REPO_37_published_challenges_of_one_mission_in_order(session):
    mission = make_mission(session)
    c1, c2 = make_challenge(session), make_challenge(session)
    draft = make_challenge(session, status=DRAFT)
    link(session, mission, c2, position=0)
    link(session, mission, draft, position=1)
    link(session, mission, c1, position=2)

    challenges = MissionRepository(session).published_challenges(mission.id)

    assert [c.id for c in challenges] == [c2.id, c1.id]
