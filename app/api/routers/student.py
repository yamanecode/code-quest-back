from fastapi import APIRouter, Depends, Response

from app.api.deps import Classrooms, CurrentStudent, require_student
from app.api.schemas.classrooms import ClassroomRefOut, JoinRequest, MyClassroomOut

router = APIRouter(tags=["student"], dependencies=[Depends(require_student)])


@router.get("/classrooms")
def my_classrooms(student: CurrentStudent, classrooms: Classrooms) -> list[MyClassroomOut]:
    return [
        MyClassroomOut(id=item.id, name=item.name, goal=item.goal)
        for item in classrooms.my_classrooms(student.id)
    ]


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
