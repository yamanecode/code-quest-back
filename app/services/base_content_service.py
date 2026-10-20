import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.badges import BADGES
from app.domain.challenge_types import ChallengeType
from app.domain.content import mission_errors
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import User
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.users import UserRepository
from app.services.content_service import ChallengeDraft, rule_errors
from app.services.exceptions import Conflict, ValidationFailed

SYSTEM_USERNAME = "codequest"
# Not a bcrypt hash, so no password ever matches it and the account cannot log in.
UNUSABLE_HASH = "!"


@dataclass(frozen=True)
class BaseMission:
    file_name: str
    title: str
    description: str | None
    position: int
    challenges: list[ChallengeDraft]


@dataclass
class LoadReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _read_challenge(raw: object, where: str, errors: list[str]) -> ChallengeDraft | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: o desafio deve ser um objeto.")
        return None
    challenge_type = raw.get("type")
    draft = ChallengeDraft(
        title=raw.get("title"),
        statement=raw.get("statement"),
        type=challenge_type if isinstance(challenge_type, str) else "",
        content=raw.get("content"),
        explanation=raw.get("explanation"),
    )
    problems = rule_errors(draft)
    if problems:
        errors.append(f"{where} «{draft.title}»: " + " ".join(problems))
        return None
    return draft


def _read_mission(path: Path, errors: list[str]) -> BaseMission | None:
    name = path.name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"{name}: o arquivo não é um JSON válido.")
        return None
    if not isinstance(data, dict):
        errors.append(f"{name}: o arquivo deve conter um objeto de missão.")
        return None

    problems = mission_errors(data.get("title"), data.get("description"))
    position = data.get("position")
    if not isinstance(position, int) or isinstance(position, bool):
        problems.append("A posição da missão deve ser um número inteiro.")
    raw_challenges = data.get("challenges")
    if not isinstance(raw_challenges, list) or not raw_challenges:
        problems.append("A missão deve ter pelo menos um desafio.")
        raw_challenges = []
    errors.extend(f"{name}: {problem}" for problem in problems)

    before = len(errors)
    challenges = [
        _read_challenge(raw, f"{name}, desafio {number}", errors)
        for number, raw in enumerate(raw_challenges, start=1)
    ]
    if problems or len(errors) > before:
        return None
    return BaseMission(name, data["title"], data.get("description"), position, challenges)


def read_base_dir(directory: Path) -> list[BaseMission]:
    """Read and validate every base mission file; any problem rejects the whole directory."""
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValidationFailed(errors=[f"Nenhum arquivo .json encontrado em {directory}."])
    errors: list[str] = []
    missions: list[BaseMission] = []
    titles: set[str] = set()
    for path in paths:
        mission = _read_mission(path, errors)
        if mission is None:
            continue
        if mission.title in titles:
            errors.append(f"{path.name}: já existe outra missão com o título «{mission.title}».")
        titles.add(mission.title)
        missions.append(mission)
    if errors:
        raise ValidationFailed(errors=errors)
    return missions


class BaseContentService:
    """Loads the base game: published missions without a turma, owned by the system account."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.missions = MissionRepository(session)
        self.challenges = ChallengeRepository(session)

    def load(self, directory: Path) -> LoadReport:
        missions = read_base_dir(directory)
        BadgeRepository(self.session).sync(BADGES)
        owner = self._system_account()
        report = LoadReport()
        for mission in missions:
            # Idempotent by title: a mission that is already there is left as it is.
            if self.missions.get_base_by_title(mission.title):
                report.skipped.append(mission.title)
                continue
            self._add_mission(owner.id, mission)
            report.created.append(mission.title)
        self.session.commit()
        return report

    def _system_account(self) -> User:
        user = self.users.get_by_username(SYSTEM_USERNAME)
        if user is None:
            return self.users.add(SYSTEM_USERNAME, UNUSABLE_HASH, Role.SYSTEM)
        if user.role != Role.SYSTEM:
            self.session.rollback()
            raise Conflict(
                "system_username_taken",
                f"O nome de usuário {SYSTEM_USERNAME} já pertence a outra conta.",
            )
        return user

    def _add_mission(self, owner_id: int, mission: BaseMission) -> None:
        row = self.missions.add(
            title=mission.title,
            position=mission.position,
            description=mission.description,
            status=ContentStatus.PUBLISHED,
        )
        challenge_ids = [
            self.challenges.add(
                owner_id=owner_id,
                title=draft.title,
                statement=draft.statement,
                challenge_type=ChallengeType(draft.type),
                content=draft.content,
                explanation=draft.explanation,
                origin=Origin.BASE,
                status=ContentStatus.PUBLISHED,
            ).id
            for draft in mission.challenges
        ]
        self.missions.set_challenges(row.id, challenge_ids)
