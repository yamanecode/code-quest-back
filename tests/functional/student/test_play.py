import pytest

from tests.functional.helpers import (
    TYPES,
    Account,
    LlmLog,
    assert_error,
    base_challenge,
    base_files,
    correct_answer,
    create_challenge,
    fail,
    has_key,
    item_texts,
    join,
    new_classroom,
    new_mission,
    profile,
    publish_mission,
    request_hint,
    send,
    solve,
    submit,
    turma_with_mission,
    unique,
    wrong_answer,
)

pytestmark = pytest.mark.functional


def missions(student: Account) -> dict:
    response = student.client.get("/api/missions")
    assert response.status_code == 200, response.text
    return response.json()


def mission_detail(student: Account, mission_id: int) -> dict:
    response = student.client.get(f"/api/missions/{mission_id}")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.req("RF-05")
def test_FT_STU_01_student_sees_base_missions_and_joined_class_missions(
    professor: Account, student: Account
):
    before = missions(student)
    assert len(before["base"]) >= 1
    assert before["classrooms"] == []
    turma = turma_with_mission(professor, ("ordering", "pattern"))

    join(student, turma.join_code)

    after = missions(student)
    assert [m["id"] for m in after["base"]] == [m["id"] for m in before["base"]]
    assert after["classrooms"] == [
        {
            "id": turma.id,
            "name": turma.classroom["name"],
            "missions": [
                {
                    "id": turma.mission["id"],
                    "title": turma.mission["title"],
                    "description": turma.mission["description"],
                    "total": 2,
                    "solved": 0,
                }
            ],
        }
    ]
    detail = mission_detail(student, turma.mission["id"])
    assert [c["id"] for c in detail["challenges"]] == [c["id"] for c in turma.challenges]


@pytest.mark.req("RF-05")
def test_FT_STU_02_drafts_and_other_classes_never_appear(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("pattern",))
    draft_challenge = create_challenge(professor, "ordering", publish=False)
    professor.client.put(
        f"/api/professor/missions/{turma.mission['id']}/challenges",
        json={"challenge_ids": [turma.challenges[0]["id"], draft_challenge["id"]]},
    )
    hidden_challenge = create_challenge(professor, "filtering")
    draft_mission = new_mission(professor, turma.id, [hidden_challenge["id"]])
    other = turma_with_mission(professor, ("grouping",))
    join(student, turma.join_code)

    visible = missions(student)
    mission_ids = [m["id"] for c in visible["classrooms"] for m in c["missions"]]
    assert mission_ids == [turma.mission["id"]]
    detail = mission_detail(student, turma.mission["id"])
    assert [c["id"] for c in detail["challenges"]] == [turma.challenges[0]["id"]]
    for mission_id in (draft_mission["id"], other.mission["id"]):
        assert_error(student.client.get(f"/api/missions/{mission_id}"), 404)
    for challenge in (draft_challenge, hidden_challenge, other.challenges[0]):
        assert_error(student.client.get(f"/api/challenges/{challenge['id']}"), 404)


@pytest.mark.req("RF-05")
def test_FT_STU_03_any_challenge_can_be_opened_in_any_order(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("ordering", "grouping", "pattern"))
    join(student, turma.join_code)
    last = turma.challenges[-1]

    assert student.client.get(f"/api/challenges/{last['id']}").status_code == 200
    result = solve(student, last)

    assert result["xp_earned"] == 10
    solved = [c["solved"] for c in mission_detail(student, turma.mission["id"])["challenges"]]
    assert solved == [False, False, True]


@pytest.mark.req("RF-06")
@pytest.mark.parametrize("challenge_type", TYPES)
def test_FT_STU_04_correct_and_wrong_answers_per_type(
    professor: Account, student: Account, challenge_type: str
):
    turma = turma_with_mission(professor, (challenge_type,))
    challenge = turma.challenges[0]
    join(student, turma.join_code)

    wrong = send(student, challenge, wrong_answer(challenge_type, challenge["content"]))
    right = send(student, challenge, correct_answer(challenge_type, challenge["content"]))

    assert wrong.status_code == 200 and wrong.json()["is_correct"] is False
    assert right.status_code == 200 and right.json()["is_correct"] is True


MALFORMED = {
    "ordering": [
        {"order": ["c", "e", "a"]},
        {"order": ["c", "e", "a", "d", "zz"]},
        {"order": ["c", "c", "a", "d", "b"]},
        {"selected": ["a"]},
    ],
    "grouping": [
        {"assignment": {"a": "g1", "b": "g1", "c": "g2"}},
        {"assignment": {"a": "g1", "b": "g1", "c": "g2", "d": "g9"}},
        {"assignment": ["g1", "g2"]},
    ],
    "filtering": [{"selected": ["a", "zz"]}, {"selected": "a"}, {"option": "a"}],
    "pattern": [{"option": "zz"}, {"option": ["a"]}, {}],
}


@pytest.mark.req("RF-06")
@pytest.mark.parametrize("challenge_type", TYPES)
def test_FT_STU_05_malformed_answer_returns_422_and_is_not_counted(
    professor: Account, student: Account, challenge_type: str
):
    turma = turma_with_mission(professor, (challenge_type,))
    challenge = turma.challenges[0]
    join(student, turma.join_code)

    for answer in MALFORMED[challenge_type]:
        assert_error(submit(student, challenge["id"], answer), 422)

    stats = professor.client.get(f"/api/professor/challenges/{challenge['id']}").json()
    assert stats["solve_stats"] == {"attempted": 0, "solved": 0}
    assert solve(student, challenge)["xp_earned"] == 10


@pytest.mark.req("RF-06")
def test_FT_STU_06_wrong_answers_can_be_repeated_without_limit(
    professor: Account, student: Account
):
    turma = turma_with_mission(professor, ("filtering",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)

    for _ in range(12):
        fail(student, challenge)

    assert solve(student, challenge)["is_correct"] is True


@pytest.mark.req("RF-17")
def test_FT_STU_07_profile_has_every_field(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("ordering", "pattern"))
    join(student, turma.join_code)
    solve(student, turma.challenges[0])
    fail(student, turma.challenges[1])
    solve(student, turma.challenges[1])

    me = profile(student)

    assert me["username"] == student.username
    assert me["role"] == "student"
    assert me["xp"] == 15
    assert me["level"] == 1
    assert me["title"] == "Aprendiz"
    assert me["xp_to_next_level"] == 35
    assert me["streak"] == 1
    assert me["missions_completed"] == 1
    assert me["solved_by_skill"] == {"ordering": 1, "grouping": 0, "filtering": 0, "pattern": 1}
    assert me["first_try_solves"] == 1
    assert me["profile_public"] is False
    assert len(me["badges"]) == 30


@pytest.mark.req("RF-21")
def test_FT_STU_08_base_game_from_the_files_is_visible_once(student: Account):
    files = base_files()

    base = missions(student)["base"]

    assert sorted(m["title"] for m in base) == sorted(f["title"] for f in files)
    totals = {m["title"]: m["total"] for m in base}
    assert totals == {f["title"]: len(f["challenges"]) for f in files}
    types = set()
    for mission in base:
        detail = mission_detail(student, mission["id"])
        types |= {challenge["type"] for challenge in detail["challenges"]}
    assert types == set(TYPES)


@pytest.mark.req("SG-02")
def test_FT_STU_09_no_free_text_reaches_the_ai(
    professor: Account, student: Account, llm_log: LlmLog
):
    spec = student.client.get("/openapi.json").json()
    student_bodies = {
        operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        for path, item in spec["paths"].items()
        if not path.startswith("/api/professor")
        for operation in item.values()
        if "requestBody" in operation
    }
    assert "requestBody" not in spec["paths"]["/api/challenges/{challenge_id}/hints"]["post"]
    assert student_bodies == {"Credentials", "JoinRequest", "SettingsIn", "SubmissionIn"}

    turma = turma_with_mission(professor, ("ordering",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)
    secret = f"mensagem livre {unique()}"
    mark = llm_log.mark()

    hint = student.client.post(
        f"/api/challenges/{challenge['id']}/hints", json={"pergunta": secret, "texto": secret}
    )
    answer = wrong_answer("ordering", challenge["content"]) | {"mensagem": secret}
    submission = submit(student, challenge["id"], answer)

    assert hint.status_code == 200, hint.text
    assert submission.status_code in (200, 422), submission.text
    prompts = llm_log.since(mark)
    assert prompts, "the hint request did not reach the language model"
    assert all(secret not in prompt for prompt in prompts)


@pytest.mark.req("SG-08")
@pytest.mark.parametrize("challenge_type", TYPES)
def test_FT_STU_10_no_student_response_contains_the_solution(
    professor: Account, student: Account, challenge_type: str
):
    turma = turma_with_mission(professor, (challenge_type,))
    challenge = turma.challenges[0]
    join(student, turma.join_code)
    content = challenge["content"]

    responses = [
        student.client.get("/api/missions"),
        student.client.get(f"/api/missions/{turma.mission['id']}"),
        student.client.get(f"/api/challenges/{challenge['id']}"),
        student.client.get("/api/daily-challenge"),
        request_hint(student, challenge["id"]),
        send(student, challenge, wrong_answer(challenge_type, content)),
        send(student, challenge, correct_answer(challenge_type, content)),
        student.client.get(f"/api/challenges/{challenge['id']}"),
    ]

    for response in responses:
        assert response.status_code == 200, response.text
        assert not has_key(response.json(), "solution"), response.text
    view = responses[2].json()
    assert view["skill"]
    if challenge_type == "ordering":
        shown = view["content"]["items"]
        texts = item_texts(content)
        assert [item["id"] for item in shown] == ["a", "b", "c", "d", "e"]
        assert [item["text"] for item in shown] != [texts[i] for i in content["solution"]]


@pytest.mark.req("SG-08")
def test_FT_STU_11_explanation_only_after_a_correct_answer(professor: Account, student: Account):
    turma = turma_with_mission(professor, ("grouping",))
    challenge = turma.challenges[0]
    join(student, turma.join_code)

    view = student.client.get(f"/api/challenges/{challenge['id']}").json()
    wrong = fail(student, challenge)
    right = solve(student, challenge)

    assert not has_key(view, "explanation")
    assert wrong["explanation"] is None
    assert right["explanation"] == challenge["explanation"]
    assert not has_key(
        student.client.get(f"/api/challenges/{challenge['id']}").json(), "explanation"
    )


@pytest.mark.req("RF-05")
def test_FT_STU_12_new_class_mission_appears_after_publishing(professor: Account, student: Account):
    classroom = new_classroom(professor)
    join(student, classroom["join_code"])
    assert missions(student)["classrooms"][0]["missions"] == []

    challenge = create_challenge(professor, "pattern")
    mission = publish_mission(professor, classroom["id"], [challenge["id"]])

    listed = missions(student)["classrooms"][0]["missions"]
    assert [m["id"] for m in listed] == [mission["id"]]


@pytest.mark.req("SG-08")
def test_FT_STU_13_item_ids_and_order_do_not_give_the_answer_away(new_student):
    first, second = new_student(), new_student()
    shuffled = {"ordering", "grouping", "filtering"}
    orders_differ = False
    real_answer_checked = False

    for mission in missions(first)["base"]:
        for summary in mission_detail(first, mission["id"])["challenges"]:
            if summary["type"] not in shuffled:
                continue
            path = f"/api/challenges/{summary['id']}"
            views = [student.client.get(path).json() for student in (first, second)]
            for view in views:
                ids = [item["id"] for item in view["content"]["items"]]
                assert ids == [chr(ord("a") + i) for i in range(len(ids))], view["title"]
            texts = [[item["text"] for item in view["content"]["items"]] for view in views]
            orders_differ = orders_differ or texts[0] != texts[1]
            if summary["type"] == "ordering":
                shown = [item["id"] for item in views[0]["content"]["items"]]
                shortcut = submit(first, summary["id"], {"order": sorted(shown)})
                assert shortcut.json()["is_correct"] is False, views[0]["title"]
                if not real_answer_checked:
                    source = base_challenge(views[0]["title"], views[0]["statement"])
                    content = source["content"]
                    challenge = {"id": summary["id"], "type": "ordering", "content": content}
                    real = send(first, challenge, correct_answer("ordering", content))
                    assert real.json()["is_correct"] is True
                    real_answer_checked = True

    assert real_answer_checked
    assert orders_differ
