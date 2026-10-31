from dataclasses import asdict

from fastapi import APIRouter, Depends, Response

from app.api.deps import AI, Auth, Classrooms, CurrentStudent, Gamification, Play, require_student
from app.api.schemas.auth import IssuedRecoveryCodeOut, PasswordIn
from app.api.schemas.classrooms import ClassroomRefOut, JoinRequest, MyClassroomOut
from app.api.schemas.gamification import RankingOut, RankingPeriodIn, RankingScopeIn
from app.api.schemas.play import (
    ChallengeForStudentOut,
    ContinueOut,
    HintOut,
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


@router.post("/me/recovery-code")
def new_recovery_code(
    body: PasswordIn, student: CurrentStudent, auth: Auth
) -> IssuedRecoveryCodeOut:
    issued = auth.regenerate_recovery_code(student.id, body.password)
    return IssuedRecoveryCodeOut(**asdict(issued))


@router.post("/me/recovery-code/confirm", status_code=204)
def confirm_recovery_code(student: CurrentStudent, auth: Auth) -> Response:
    auth.confirm_recovery_code(student.id)
    return Response(status_code=204)


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


@router.post("/challenges/{challenge_id}/hints")
def request_hint(challenge_id: int, student: CurrentStudent, ai: AI) -> HintOut:
    return HintOut(**asdict(ai.request_hint(student.id, challenge_id)))


@router.get("/me/continue", response_model=ContinueOut, responses={204: {}})
def continue_playing(student: CurrentStudent, play: Play) -> ContinueOut | Response:
    next_up = play.continue_for(student.id)
    if next_up is None:
        return Response(status_code=204)
    return ContinueOut(**asdict(next_up))


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
