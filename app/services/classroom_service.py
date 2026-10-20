from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.infra.repositories.classrooms import ClassroomRepository
from app.services.exceptions import NotFound


@dataclass(frozen=True)
class ClassroomRef:
    id: int
    name: str


@dataclass(frozen=True)
class MyClassroom:
    id: int
    name: str
    goal: dict | None


class ClassroomService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.classrooms = ClassroomRepository(session)

    def join(self, user_id: int, join_code: str) -> ClassroomRef:
        classroom = self.classrooms.get_by_join_code(join_code.strip().upper())
        if classroom is None:
            raise NotFound("invalid_join_code", "Código de turma inválido.")
        if self.classrooms.get_membership(user_id, classroom.id) is None:
            self.classrooms.add_member(user_id, classroom.id)
            self.session.commit()
        return ClassroomRef(classroom.id, classroom.name)

    def leave(self, user_id: int, classroom_id: int) -> None:
        membership = self.classrooms.get_membership(user_id, classroom_id)
        if membership is None:
            raise NotFound("classroom_not_found", "Turma não encontrada.")
        # Only the membership goes away; XP, badges and submissions belong to the student.
        self.classrooms.remove_member(membership)
        self.session.commit()

    def my_classrooms(self, user_id: int) -> list[MyClassroom]:
        # The weekly goal is filled in with the class-goal rules (phase B6).
        return [
            MyClassroom(classroom.id, classroom.name, goal=None)
            for classroom in self.classrooms.member_classrooms(user_id)
        ]
