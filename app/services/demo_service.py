from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import NoReturn

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import get_settings
from app.core.ports import LLMClient
from app.domain.accounts import account_errors
from app.domain.badges import BADGES
from app.domain.challenge_types import ChallengeDraft, ChallengeType, student_ids
from app.domain.enums import Origin, Role
from app.domain.gamification import week_start
from app.infra.db.models import Challenge, Classroom, Mission, User
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.classrooms import ClassroomRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.users import UserRepository
from app.infra.security import hash_password
from app.services.ai_service import AIService
from app.services.auth_service import AuthService
from app.services.classroom_service import ClassroomService
from app.services.content_service import ContentService, MissionDraft, add_published_mission
from app.services.exceptions import Conflict, ValidationFailed
from app.services.gamification_service import GamificationService
from app.services.play_service import PlayService, view_seed

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


@dataclass(frozen=True)
class DemoStudent:
    """Wrong answers before each solve: `demo` on the demo mission, `base` on the base game,
    both in mission order. 0, 1-2 and 3+ wrong answers give 10, 5 and 2 XP."""

    username: str
    demo: tuple[int, ...]
    base: tuple[int, ...]


DEMO_STUDENTS = (
    DemoStudent("demo_aluno1", demo=(0, 0, 0, 0), base=(0, 0, 0, 0, 0, 0)),
    DemoStudent("demo_aluno2", demo=(0, 1, 0, 0), base=(0, 0, 1, 0)),
    DemoStudent("demo_aluno3", demo=(1, 0, 2), base=(0, 0, 3)),
    DemoStudent("demo_aluno4", demo=(0, 3, 1), base=(0,)),
    DemoStudent("demo_aluno5", demo=(2, 0), base=()),
    DemoStudent("demo_aluno6", demo=(3,), base=()),
)


class _SeedClock:
    """The clock the seeded services read; the seed sets it before each answer."""

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment

    def today(self) -> date:
        return self.moment.date()


def _spread(start: datetime, end: datetime, count: int) -> list[datetime]:
    """`count` moments after `start`, evenly spaced, the last one exactly `end`."""
    return [start + (end - start) * step / count for step in range(1, count + 1)]


def _stored_answer(challenge: Challenge, correct: bool) -> dict:
    """The solution, or a well-formed answer that is wrong for sure."""
    content = challenge.content
    solution = content["solution"]
    if challenge.type == ChallengeType.ORDERING:
        return {"order": solution if correct else solution[::-1]}
    if challenge.type == ChallengeType.GROUPING:
        # Every group has at least one item, so putting all items in one group is wrong.
        first_group = content["groups"][0]["id"]
        everything_in_one = {item["id"]: first_group for item in content["items"]}
        return {"assignment": solution if correct else everything_in_one}
    if challenge.type == ChallengeType.FILTERING:
        # At least one item is not needed, so selecting all of them is wrong.
        return {"selected": solution if correct else [item["id"] for item in content["items"]]}
    other = next(option["id"] for option in content["options"] if option["id"] != solution)
    return {"option": solution if correct else other}


def _as_shown(challenge: Challenge, user_id: int, answer: dict) -> dict:
    """The answer with the ids this student is shown, as their browser would send it."""
    shown = student_ids(challenge.type, challenge.content, view_seed(challenge.id, user_id))
    ((key, value),) = answer.items()
    if isinstance(value, str):
        return {key: shown[value]}
    if isinstance(value, dict):
        return {key: {shown[item]: group for item, group in value.items()}}
    return {key: [shown[item] for item in value]}


class DemoService:
    """Demonstration data: one professor, one turma, one challenge per type and, on
    request, six students with progress dated in the current week."""

    def __init__(self, session: Session, clock: Clock, llm: LLMClient) -> None:
        self.session = session
        self.clock = clock
        self.llm = llm
        self.users = UserRepository(session)
        self.classrooms = ClassroomRepository(session)
        self.missions = MissionRepository(session)

    def seed(
        self,
        read_password: Callable[[], str | None],
        read_student_password: Callable[[], str | None] | None = None,
    ) -> list[str]:
        """Create what is missing and return what was created. Passwords are only read for
        accounts that do not exist yet; students are seeded only with `read_student_password`."""
        created: list[str] = []
        missing: list[DemoStudent] = []
        student_password = ""
        if read_student_password is not None:
            # Checked before anything is written, so a refused run creates nothing.
            if not self.missions.visible_base():
                self._abort(
                    Conflict(
                        "base_game_missing", "Carregue o jogo base antes: load-base content/base"
                    )
                )
            missing = self._missing_students()
            if missing:
                student_password = self._student_password(read_student_password)
        BadgeRepository(self.session).sync(BADGES)
        professor = self._professor(read_password, created)
        classroom = self._classroom(professor, created)
        demo_mission = self._demo_mission(professor, classroom, created)
        self.session.commit()
        if missing:
            self._seed_students(missing, student_password, demo_mission, created)
        return created

    def _demo_mission(self, professor: User, classroom: Classroom, created: list[str]) -> Mission:
        for mission in self.missions.list_for_classroom(classroom.id):
            if mission.title == DEMO_MISSION:
                return mission
        draft = MissionDraft(DEMO_MISSION, DEMO_MISSION_DESCRIPTION, 1, list(DEMO_CHALLENGES))
        created.append(DEMO_MISSION)
        mission, _ = add_published_mission(
            self.session, professor.id, draft, Origin.PROFESSOR, classroom.id
        )
        return mission

    def _missing_students(self) -> list[DemoStudent]:
        missing = []
        for student in DEMO_STUDENTS:
            user = self.users.get_by_username(student.username)
            if user is None:
                missing.append(student)
            elif user.role != Role.STUDENT:
                self._abort(
                    Conflict(
                        "demo_username_taken",
                        f"O nome de usuário {student.username} já pertence a outra conta.",
                    )
                )
        return missing

    def _student_password(self, read_password: Callable[[], str | None]) -> str:
        password = read_password()
        if password is None:
            self._abort(ValidationFailed(errors=["As senhas não conferem."]))
        errors = account_errors(DEMO_STUDENTS[0].username, password)
        if errors:
            self._abort(ValidationFailed(errors=errors))
        return password

    def _seed_students(
        self, students: list[DemoStudent], password: str, mission: Mission, created: list[str]
    ) -> None:
        """Sign up, join and answer through the normal services, so XP, badges, rankings and
        the class goal follow the rules. Each service commits, so this part is not one
        transaction; a student that exists is skipped on the next run."""
        now = self.clock.now()
        clock = _SeedClock(now)
        gamification = GamificationService(self.session, clock)
        goals = ClassroomService(self.session, clock, gamification)
        cooldown = get_settings().HINT_COOLDOWN_SECONDS
        ai = AIService(self.session, clock, self.llm, ContentService(self.session, clock), cooldown)
        play = PlayService(self.session, clock, gamification, goals, ai)
        auth = AuthService(self.session, clock)

        demo_challenges = self.missions.published_challenges(mission.id)
        base_challenges = [
            challenge
            for base_mission in self.missions.visible_base()
            for challenge in self.missions.published_challenges(base_mission.id)
        ]
        attempts = {
            student.username: [
                (challenge, attempt == wrong)
                for challenge, wrong in [
                    *zip(demo_challenges, student.demo, strict=False),
                    *zip(base_challenges, student.base, strict=False),
                ]
                for attempt in range(wrong + 1)
            ]
            for student in students
        }
        # Every answer dated this week, never after now, even if the week began minutes ago.
        total = sum(len(answers) for answers in attempts.values())
        moments = iter(_spread(week_start(now), now, total))

        for student in students:
            answers = [
                (challenge, correct, next(moments))
                for challenge, correct in attempts[student.username]
            ]
            clock.moment = answers[0][2]
            # The recovery code is dropped: it is never printed (spec 3).
            account = auth.register_student(student.username, password).account
            goals.join(account.id, DEMO_JOIN_CODE)
            for challenge, correct, moment in answers:
                clock.moment = moment
                answer = _as_shown(challenge, account.id, _stored_answer(challenge, correct))
                play.submit(account.id, challenge.id, answer, hint_after_wrong=False)
            created.append(f"estudante {student.username}")

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
