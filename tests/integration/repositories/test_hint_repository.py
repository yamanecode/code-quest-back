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
