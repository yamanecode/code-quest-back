from dataclasses import asdict

from fastapi import APIRouter, Depends, Response

from app.api.deps import AI, Content, CurrentProfessor, Gamification, require_professor
from app.api.schemas.gamification import ClassroomProgressOut, RankingOut, RankingPeriodIn
from app.api.schemas.professor import (
    ChallengeIn,
    ChallengeOut,
    ClassroomIn,
    ClassroomOut,
    DraftIn,
    MissionChallengesIn,
    MissionIn,
    MissionOrderIn,
    MissionOut,
    MissionUpdate,
    ReviewOut,
)
from app.services.content_service import ChallengeDraft

# Every professor route inherits the role check from the router.
router = APIRouter(
    prefix="/professor", tags=["professor"], dependencies=[Depends(require_professor)]
)


@router.get("/classrooms")
def list_classrooms(professor: CurrentProfessor, content: Content) -> list[ClassroomOut]:
    return [ClassroomOut(**asdict(item)) for item in content.list_classrooms(professor.id)]


@router.post("/classrooms", status_code=201)
def create_classroom(
    body: ClassroomIn, professor: CurrentProfessor, content: Content
) -> ClassroomOut:
    classroom = content.create_classroom(professor.id, body.name, body.weekly_goal)
    return ClassroomOut(**asdict(classroom))


@router.get("/classrooms/{classroom_id}")
def get_classroom(classroom_id: int, professor: CurrentProfessor, content: Content) -> ClassroomOut:
    return ClassroomOut(**asdict(content.get_classroom(professor.id, classroom_id)))


@router.put("/classrooms/{classroom_id}")
def update_classroom(
    classroom_id: int, body: ClassroomIn, professor: CurrentProfessor, content: Content
) -> ClassroomOut:
    classroom = content.update_classroom(professor.id, classroom_id, body.name, body.weekly_goal)
    return ClassroomOut(**asdict(classroom))


@router.post("/classrooms/{classroom_id}/close")
def close_classroom(
    classroom_id: int, professor: CurrentProfessor, content: Content
) -> ClassroomOut:
    return ClassroomOut(**asdict(content.close_classroom(professor.id, classroom_id)))


@router.post("/classrooms/{classroom_id}/reopen")
def reopen_classroom(
    classroom_id: int, professor: CurrentProfessor, content: Content
) -> ClassroomOut:
    return ClassroomOut(**asdict(content.reopen_classroom(professor.id, classroom_id)))


@router.post("/classrooms/{classroom_id}/new-code")
def renew_join_code(
    classroom_id: int, professor: CurrentProfessor, content: Content
) -> ClassroomOut:
    return ClassroomOut(**asdict(content.renew_join_code(professor.id, classroom_id)))


@router.delete("/classrooms/{classroom_id}/members/{username}", status_code=204)
def remove_member(
    classroom_id: int, username: str, professor: CurrentProfessor, content: Content
) -> Response:
    content.remove_member(professor.id, classroom_id, username)
    return Response(status_code=204)


@router.get("/classrooms/{classroom_id}/progress")
def classroom_progress(
    classroom_id: int, professor: CurrentProfessor, gamification: Gamification
) -> ClassroomProgressOut:
    progress = gamification.classroom_progress(professor.id, classroom_id)
    return ClassroomProgressOut(**asdict(progress))


@router.get("/classrooms/{classroom_id}/rankings")
def classroom_ranking(
    classroom_id: int,
    professor: CurrentProfessor,
    gamification: Gamification,
    period: RankingPeriodIn = "week",
) -> RankingOut:
    ranking = gamification.classroom_ranking(professor.id, classroom_id, period)
    return RankingOut(**asdict(ranking))


@router.get("/classrooms/{classroom_id}/missions")
def list_missions(
    classroom_id: int, professor: CurrentProfessor, content: Content
) -> list[MissionOut]:
    missions = content.list_missions(professor.id, classroom_id)
    return [MissionOut(**asdict(mission)) for mission in missions]


@router.post("/classrooms/{classroom_id}/missions", status_code=201)
def create_mission(
    classroom_id: int, body: MissionIn, professor: CurrentProfessor, content: Content
) -> MissionOut:
    mission = content.create_mission(
        professor.id, classroom_id, body.title, body.description, body.position
    )
    return MissionOut(**asdict(mission))


@router.put("/classrooms/{classroom_id}/missions/order")
def set_mission_order(
    classroom_id: int, body: MissionOrderIn, professor: CurrentProfessor, content: Content
) -> list[MissionOut]:
    missions = content.set_mission_order(professor.id, classroom_id, body.mission_ids)
    return [MissionOut(**asdict(mission)) for mission in missions]


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int, professor: CurrentProfessor, content: Content) -> MissionOut:
    return MissionOut(**asdict(content.get_mission(professor.id, mission_id)))


@router.put("/missions/{mission_id}")
def update_mission(
    mission_id: int, body: MissionUpdate, professor: CurrentProfessor, content: Content
) -> MissionOut:
    mission = content.update_mission(
        professor.id, mission_id, body.title, body.description, body.position
    )
    return MissionOut(**asdict(mission))


@router.delete("/missions/{mission_id}", status_code=204)
def delete_mission(mission_id: int, professor: CurrentProfessor, content: Content) -> Response:
    content.delete_mission(professor.id, mission_id)
    return Response(status_code=204)


@router.put("/missions/{mission_id}/challenges")
def set_mission_challenges(
    mission_id: int, body: MissionChallengesIn, professor: CurrentProfessor, content: Content
) -> MissionOut:
    mission = content.set_mission_challenges(professor.id, mission_id, body.challenge_ids)
    return MissionOut(**asdict(mission))


@router.post("/missions/{mission_id}/publish")
def publish_mission(mission_id: int, professor: CurrentProfessor, content: Content) -> MissionOut:
    return MissionOut(**asdict(content.publish_mission(professor.id, mission_id)))


@router.post("/missions/{mission_id}/unpublish")
def unpublish_mission(mission_id: int, professor: CurrentProfessor, content: Content) -> MissionOut:
    return MissionOut(**asdict(content.unpublish_mission(professor.id, mission_id)))


@router.get("/challenges")
def list_challenges(professor: CurrentProfessor, content: Content) -> list[ChallengeOut]:
    return [ChallengeOut(**asdict(item)) for item in content.list_challenges(professor.id)]


@router.post("/challenges", status_code=201)
def create_challenge(
    body: ChallengeIn, professor: CurrentProfessor, content: Content
) -> ChallengeOut:
    challenge = content.create_challenge(professor.id, ChallengeDraft(**body.model_dump()))
    return ChallengeOut(**asdict(challenge))


@router.post("/challenges/ai-draft", status_code=201)
def ai_draft(body: DraftIn, professor: CurrentProfessor, ai: AI) -> ChallengeOut:
    challenge = ai.draft(professor.id, body.type, body.topic, body.mission_id)
    return ChallengeOut(**asdict(challenge))


@router.post("/challenges/{challenge_id}/ai-review")
def ai_review(challenge_id: int, professor: CurrentProfessor, ai: AI) -> ReviewOut:
    return ReviewOut(**asdict(ai.review(professor.id, challenge_id)))


@router.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: int, professor: CurrentProfessor, content: Content) -> ChallengeOut:
    return ChallengeOut(**asdict(content.get_challenge(professor.id, challenge_id)))


@router.put("/challenges/{challenge_id}")
def update_challenge(
    challenge_id: int, body: ChallengeIn, professor: CurrentProfessor, content: Content
) -> ChallengeOut:
    draft = ChallengeDraft(**body.model_dump())
    return ChallengeOut(**asdict(content.update_challenge(professor.id, challenge_id, draft)))


@router.delete("/challenges/{challenge_id}", status_code=204)
def delete_challenge(challenge_id: int, professor: CurrentProfessor, content: Content) -> Response:
    content.delete_challenge(professor.id, challenge_id)
    return Response(status_code=204)


@router.post("/challenges/{challenge_id}/duplicate", status_code=201)
def duplicate_challenge(
    challenge_id: int, professor: CurrentProfessor, content: Content
) -> ChallengeOut:
    return ChallengeOut(**asdict(content.duplicate_challenge(professor.id, challenge_id)))


@router.post("/challenges/{challenge_id}/publish")
def publish_challenge(
    challenge_id: int, professor: CurrentProfessor, content: Content
) -> ChallengeOut:
    return ChallengeOut(**asdict(content.publish_challenge(professor.id, challenge_id)))


@router.post("/challenges/{challenge_id}/unpublish")
def unpublish_challenge(
    challenge_id: int, professor: CurrentProfessor, content: Content
) -> ChallengeOut:
    return ChallengeOut(**asdict(content.unpublish_challenge(professor.id, challenge_id)))
