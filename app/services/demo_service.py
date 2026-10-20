from collections.abc import Callable
from typing import NoReturn

from sqlalchemy.orm import Session

from app.domain.accounts import account_errors
from app.domain.badges import BADGES
from app.domain.challenge_types import ChallengeType
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Classroom, User
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.users import UserRepository
from app.infra.security import hash_password
from app.services.content_service import ChallengeDraft, rule_errors
from app.services.exceptions import Conflict, ValidationFailed

DEMO_PROFESSOR = "prof_demo"
DEMO_CLASSROOM = "Turma Demo"
DEMO_JOIN_CODE = "DEMO01"
DEMO_MISSION = "Missão de exemplo"
DEMO_MISSION_DESCRIPTION = "Um desafio de cada tipo, um para cada habilidade."

DEMO_CHALLENGES = (
    ChallengeDraft(
        title="Montar um sanduíche",
        statement="Lia quer montar um sanduíche de queijo. Coloque os passos na ordem certa.",
        type=ChallengeType.ORDERING,
        content={
            "items": [
                {"id": "a", "text": "Passar manteiga em uma fatia"},
                {"id": "b", "text": "Fechar com a outra fatia"},
                {"id": "c", "text": "Pegar duas fatias de pão"},
                {"id": "d", "text": "Colocar o queijo sobre a manteiga"},
            ],
            "solution": ["c", "a", "d", "b"],
        },
        explanation="Cada passo usa o resultado do anterior: sem o pão não há onde passar "
        "a manteiga, e o sanduíche só é fechado no fim.",
    ),
    ChallengeDraft(
        title="Festa de aniversário",
        statement="A turma vai organizar uma festa. Divida as tarefas entre as três "
        "equipes: comida, decoração e convidados.",
        type=ChallengeType.GROUPING,
        content={
            "groups": [
                {"id": "g1", "text": "Comida"},
                {"id": "g2", "text": "Decoração"},
                {"id": "g3", "text": "Convidados"},
            ],
            "items": [
                {"id": "a", "text": "Encomendar o bolo"},
                {"id": "b", "text": "Encher os balões"},
                {"id": "c", "text": "Enviar os convites"},
                {"id": "d", "text": "Comprar os salgados"},
                {"id": "e", "text": "Pendurar a faixa de parabéns"},
                {"id": "f", "text": "Confirmar quem vai"},
            ],
            "solution": {"a": "g1", "b": "g2", "c": "g3", "d": "g1", "e": "g2", "f": "g3"},
        },
        explanation="Dividir a festa em partes menores deixa cada equipe com um problema "
        "pequeno e claro para resolver.",
    ),
    ChallengeDraft(
        title="Lanche antes da aula",
        statement="Pedro passou na lanchonete antes da aula. Marque somente as informações "
        "necessárias para responder à pergunta.",
        type=ChallengeType.FILTERING,
        content={
            "question": "Quanto Pedro vai gastar no lanche?",
            "items": [
                {"id": "a", "text": "O suco custa 5 reais"},
                {"id": "b", "text": "A lanchonete abre às 7 horas"},
                {"id": "c", "text": "O pão de queijo custa 4 reais"},
                {"id": "d", "text": "A lanchonete fica perto da escola"},
                {"id": "e", "text": "Pedro vai pedir um suco e um pão de queijo"},
            ],
            "solution": ["a", "c", "e"],
        },
        explanation="Para saber o gasto basta o pedido e o preço de cada item; o horário "
        "e o endereço não mudam a conta.",
    ),
    ChallengeDraft(
        title="Contando de três em três",
        statement="Os números abaixo seguem uma regra. Escolha o próximo número da sequência.",
        type=ChallengeType.PATTERN,
        content={
            "sequence": ["3", "6", "9", "12"],
            "options": [
                {"id": "a", "text": "14"},
                {"id": "b", "text": "15"},
                {"id": "c", "text": "16"},
                {"id": "d", "text": "18"},
            ],
            "solution": "b",
        },
        explanation="A regra é somar 3 a cada termo: 12 + 3 = 15.",
    ),
)


class DemoService:
    """Demonstration data (spec §11): one professor, one turma and one challenge per type."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.classrooms = ClassroomRepository(session)
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)

    def seed(self, read_password: Callable[[], str | None]) -> list[str]:
        """Create what is missing and return what was created; `read_password` is only
        called when prof_demo does not exist yet."""
        created: list[str] = []
        BadgeRepository(self.session).sync(BADGES)
        professor = self._professor(read_password, created)
        classroom = self._classroom(professor, created)
        titles = {mission.title for mission in self.missions.list_for_classroom(classroom.id)}
        if DEMO_MISSION not in titles:
            self._add_mission(professor.id, classroom.id)
            created.append(DEMO_MISSION)
        self.session.commit()
        return created

    def _abort(self, error: Exception) -> NoReturn:
        self.session.rollback()
        raise error

    def _professor(self, read_password: Callable[[], str | None], created: list[str]) -> User:
        user = self.users.get_by_username(DEMO_PROFESSOR)
        if user is not None:
            if user.role != Role.PROFESSOR:
                self._abort(
                    Conflict(
                        "demo_username_taken",
                        f"O nome de usuário {DEMO_PROFESSOR} já pertence a outra conta.",
                    )
                )
            return user
        password = read_password()
        if password is None:
            self._abort(ValidationFailed(errors=["As senhas não conferem."]))
        errors = account_errors(DEMO_PROFESSOR, password)
        if errors:
            self._abort(ValidationFailed(errors=errors))
        created.append(f"professor {DEMO_PROFESSOR}")
        return self.users.add(DEMO_PROFESSOR, hash_password(password), Role.PROFESSOR)

    def _classroom(self, professor: User, created: list[str]) -> Classroom:
        classroom = self.classrooms.get_by_join_code(DEMO_JOIN_CODE)
        if classroom is None:
            created.append(f"turma {DEMO_CLASSROOM} ({DEMO_JOIN_CODE})")
            return self.classrooms.add(DEMO_CLASSROOM, DEMO_JOIN_CODE, professor.id)
        if classroom.professor_id != professor.id:
            self._abort(
                Conflict(
                    "demo_join_code_taken",
                    f"O código {DEMO_JOIN_CODE} já é usado por outra turma.",
                )
            )
        return classroom

    def _add_mission(self, professor_id: int, classroom_id: int) -> None:
        mission = self.missions.add(
            title=DEMO_MISSION,
            position=1,
            classroom_id=classroom_id,
            description=DEMO_MISSION_DESCRIPTION,
            status=ContentStatus.PUBLISHED,
        )
        challenge_ids = []
        for draft in DEMO_CHALLENGES:
            errors = rule_errors(draft)
            if errors:
                self._abort(ValidationFailed(errors=errors))
            challenge = self.challenges.add(
                owner_id=professor_id,
                title=draft.title,
                statement=draft.statement,
                challenge_type=ChallengeType(draft.type),
                content=draft.content,
                explanation=draft.explanation,
                origin=Origin.PROFESSOR,
                status=ContentStatus.PUBLISHED,
            )
            challenge_ids.append(challenge.id)
        self.missions.set_challenges(mission.id, challenge_ids)
