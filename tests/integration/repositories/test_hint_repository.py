from datetime import timedelta

from app.domain.enums import HintSource
from app.infra.repositories.hints import HintRepository, HintUsage
from tests.integration.factories import NOON, hint, make_challenge, make_user


def test_T_REPO_11_requested_hints_count_and_last_time(session):
    ana = make_user(session)
    challenge = make_challenge(session)
    hint(session, ana, challenge, at=NOON)
    hint(session, ana, challenge, at=NOON + timedelta(seconds=10))
    hint(session, ana, challenge, HintSource.AFTER_WRONG, at=NOON + timedelta(seconds=20))
    hint(session, make_user(session), challenge, at=NOON + timedelta(seconds=30))

    repo = HintRepository(session)
    assert repo.requested_hints(ana.id, challenge.id) == HintUsage(2, NOON + timedelta(seconds=10))
    assert repo.requested_hints(ana.id, make_challenge(session).id) == HintUsage(0, None)


def test_T_REPO_12_after_wrong_hint_exists(session):
    ana = make_user(session)
    challenge = make_challenge(session)
    repo = HintRepository(session)
    hint(session, ana, challenge, HintSource.REQUEST)
    assert repo.after_wrong_hint_exists(ana.id, challenge.id) is False

    hint(session, ana, challenge, HintSource.AFTER_WRONG)
    assert repo.after_wrong_hint_exists(ana.id, challenge.id) is True


def test_T_REPO_26_shown_texts_in_order_from_every_source(session):
    ana = make_user(session)
    challenge = make_challenge(session)
    hint(session, ana, challenge, HintSource.AFTER_WRONG, text="primeira")
    hint(session, ana, challenge, HintSource.REQUEST, text="segunda")
    hint(session, make_user(session), challenge, text="de outra pessoa")

    assert HintRepository(session).shown_texts(ana.id, challenge.id) == ["primeira", "segunda"]


def test_T_REPO_38_challenges_with_requested_hints(session):
    ana = make_user(session)
    asked, automatic, untouched = (make_challenge(session) for _ in range(3))
    hint(session, ana, asked, HintSource.REQUEST)
    hint(session, ana, automatic, HintSource.AFTER_WRONG)
    hint(session, make_user(session), untouched, HintSource.REQUEST)

    assert HintRepository(session).requested_challenge_ids(ana.id) == {asked.id}


def test_T_REPO_40_requested_hint_count_on_some_challenges(session):
    ana = make_user(session)
    first, second, elsewhere = (make_challenge(session) for _ in range(3))
    hint(session, ana, first, HintSource.REQUEST)
    hint(session, ana, first, HintSource.REQUEST)
    hint(session, ana, second, HintSource.REQUEST)
    hint(session, ana, second, HintSource.AFTER_WRONG)
    hint(session, ana, elsewhere, HintSource.REQUEST)
    hint(session, make_user(session), first, HintSource.REQUEST)

    repo = HintRepository(session)
    assert repo.requested_count(ana.id, [first.id, second.id]) == 3
    assert repo.requested_count(ana.id, []) == 0
