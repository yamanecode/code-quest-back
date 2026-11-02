"""Checks shared by several services; each one raises the error the student or professor sees."""

from app.infra.db.models import Classroom
from app.infra.repositories.classrooms import ClassroomRepository
from app.services.exceptions import Conflict, NotFound


def own_classroom(
    classrooms: ClassroomRepository, professor_id: int, classroom_id: int
) -> Classroom:
    classroom = classrooms.get(classroom_id)
    # Another professor's turma looks exactly like a missing one.
    if classroom is None or classroom.professor_id != professor_id:
        raise NotFound("classroom_not_found", "Turma não encontrada.")
    return classroom


def already_solved() -> Conflict:
    return Conflict("already_solved", "Você já resolveu este desafio.")
