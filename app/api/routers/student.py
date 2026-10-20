from dataclasses import asdict

from fastapi import APIRouter, Depends, Response

from app.api.deps import Classrooms, CurrentStudent, Gamification, Play, require_student
from app.api.schemas.classrooms import ClassroomRefOut, JoinRequest, MyClassroomOut
from app.api.schemas.gamification import RankingOut, RankingPeriodIn, RankingScopeIn
from app.api.schemas.play import (
    ChallengeForStudentOut,
    DailyOut,
    MissionDetailOut,
    MissionsOut,
    ProfileOut,
    SettingsIn,
    SettingsOut,
    SubmissionIn,
    SubmissionOut,
)

router = APIRouter(tags=["student"], dependencies=[Depends(require_student)])


@router.get("/classrooms")
def my_classrooms(student: CurrentStudent, classrooms: Classrooms) -> list[MyClassroomOut]:
    return [MyClassroomOut(**asdict(item)) for item in classrooms.my_classrooms(student.id)]


@router.post("/classrooms/join")
def join_classroom(
    body: JoinRequest, student: CurrentStudent, classrooms: Classrooms
) -> ClassroomRefOut:
    classroom = classrooms.join(student.id, body.join_code)
    return ClassroomRefOut(id=classroom.id, name=classroom.name)


@router.delete("/classrooms/{classroom_id}/membership", status_code=204)
def leave_classroom(classroom_id: int, student: CurrentStudent, classrooms: Classrooms) -> Response:
    classrooms.leave(student.id, classroom_id)
    return Response(status_code=204)


@router.get("/me")
def my_profile(student: CurrentStudent, gamification: Gamification) -> ProfileOut:
    return ProfileOut(**asdict(gamification.profile(student.id)))


@router.put("/me/settings")
def update_settings(
    body: SettingsIn, student: CurrentStudent, gamification: Gamification
) -> SettingsOut:
    profile_public = gamification.set_profile_public(student.id, body.profile_public)
    return SettingsOut(profile_public=profile_public)


@router.get("/missions")
def list_missions(student: CurrentStudent, play: Play) -> MissionsOut:
    return MissionsOut(**asdict(play.list_missions(student.id)))


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int, student: CurrentStudent, play: Play) -> MissionDetailOut:
    return MissionDetailOut(**asdict(play.get_mission(student.id, mission_id)))


@router.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: int, student: CurrentStudent, play: Play) -> ChallengeForStudentOut:
    return ChallengeForStudentOut(**asdict(play.get_challenge(student.id, challenge_id)))


@router.post("/challenges/{challenge_id}/submissions")
def submit_answer(
    challenge_id: int, body: SubmissionIn, student: CurrentStudent, play: Play
) -> SubmissionOut:
    return SubmissionOut(**asdict(play.submit(student.id, challenge_id, body.answer)))


@router.get("/daily-challenge")
def daily_challenge(student: CurrentStudent, play: Play) -> DailyOut:
    return DailyOut(**asdict(play.daily_challenge(student.id)))


@router.get("/rankings")
def ranking(
    student: CurrentStudent,
    gamification: Gamification,
    scope: RankingScopeIn = "global",
    period: RankingPeriodIn = "week",
    classroom_id: int | None = None,
) -> RankingOut:
    result = gamification.ranking(student.id, scope, period, classroom_id)
    return RankingOut(**asdict(result))
