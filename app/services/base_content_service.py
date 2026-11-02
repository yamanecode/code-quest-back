import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.badges import BADGES
from app.domain.challenge_types import (
    ChallengeDraft,
    ChallengeType,
    challenge_errors,
    edit_is_structural,
)
from app.domain.content import mission_errors
from app.domain.enums import ContentStatus, Origin, Role
from app.infra.db.models import Challenge, Mission, User
from app.infra.repositories.badges import BadgeRepository
from app.infra.repositories.challenges import ChallengeRepository
from app.infra.repositories.missions import MissionRepository
from app.infra.repositories.users import UserRepository
from app.services.content_service import MissionDraft, add_published_mission, draft_of
from app.services.exceptions import Conflict, ServiceError, ValidationFailed

SYSTEM_USERNAME = "codequest"
# Not a bcrypt hash, so no password ever matches it and the account cannot log in.
UNUSABLE_HASH = "!"
KEY_MAX = 80


@dataclass(frozen=True)
class BaseChallenge:
    key: str
    draft: ChallengeDraft


@dataclass(frozen=True)
class BaseMission:
    key: str
    title: str
    description: str | None
    position: int
    challenges: list[BaseChallenge]

    def draft(self) -> MissionDraft:
        drafts = [challenge.draft for challenge in self.challenges]
        return MissionDraft(self.title, self.description, self.position, drafts)


@dataclass
class LoadReport:
    """What a load did. Missions are named by title, challenges as "mission / challenge"."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    # Base rows stored before keys existed: matched to a file by title, or left without a key.
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    # Challenges still in a base mission but no longer in its file; they stay where they are.
    not_in_files: list[str] = field(default_factory=list)


def _key_ok(value: object) -> bool:
    return isinstance(value, str) and value.strip() != "" and len(value) <= KEY_MAX


def _read_challenge(raw: object, where: str, errors: list[str]) -> BaseChallenge | None:
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
    problems = challenge_errors(draft)
    if not _key_ok(raw.get("key")):
        problems.append(f"A chave do desafio deve ser um texto de 1 a {KEY_MAX} caracteres.")
    if problems:
        errors.append(f"{where} «{draft.title}»: " + " ".join(problems))
        return None
    return BaseChallenge(raw["key"], draft)


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
    if not _key_ok(data.get("key")):
        problems.append(f"A chave da missão deve ser um texto de 1 a {KEY_MAX} caracteres.")
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
    return BaseMission(data["key"], data["title"], data.get("description"), position, challenges)


def _check_unique(name: str, mission: BaseMission, seen: set[str], errors: list[str]) -> None:
    """Keys must be unique across all files, missions and challenges together."""
    for key in [mission.key, *(challenge.key for challenge in mission.challenges)]:
        if key in seen:
            errors.append(f"{name}: a chave «{key}» já foi usada em outra missão ou desafio.")
        seen.add(key)


def read_base_dir(directory: Path) -> list[BaseMission]:
    """Read and validate every base mission file; any problem rejects the whole directory."""
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValidationFailed(errors=[f"Nenhum arquivo .json encontrado em {directory}."])
    errors: list[str] = []
    missions: list[BaseMission] = []
    titles: set[str] = set()
    keys: set[str] = set()
    for path in paths:
        mission = _read_mission(path, errors)
        if mission is None:
            continue
        if mission.title in titles:
            errors.append(f"{path.name}: já existe outra missão com o título «{mission.title}».")
        titles.add(mission.title)
        _check_unique(path.name, mission, keys, errors)
        missions.append(mission)
    if errors:
        raise ValidationFailed(errors=errors)
    return missions


def _label(mission_title: str, challenge_title: str) -> str:
    return f"{mission_title} / {challenge_title}"


class BaseContentService:
    """Loads the base game: published missions without a turma, owned by the system account.

    Missions and challenges are matched to the files by key, so a second load updates what
    changed and creates only what is new (spec 11).
    """

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
        try:
            self._match_rows_without_key(owner.id, missions, report)
            for mission in missions:
                self._load_mission(owner.id, mission, report)
        except ServiceError:
            self.session.rollback()
            raise
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

    # Rows stored before keys existed: match them by title, once.

    def _match_rows_without_key(
        self, owner_id: int, missions: list[BaseMission], report: LoadReport
    ) -> None:
        by_title = {mission.title: mission for mission in missions}
        for row in self.missions.base_without_key():
            source = by_title.get(row.title)
            if source is None or self.missions.get_by_base_key(source.key) is not None:
                report.unmatched.append(row.title)
                continue
            row.base_key = source.key
            report.matched.append(row.title)
        self.session.flush()
        for source in missions:
            row = self.missions.get_by_base_key(source.key)
            if row is not None:
                self._match_challenges(owner_id, row, source, report)
        self.session.flush()

    def _match_challenges(
        self, owner_id: int, mission: Mission, source: BaseMission, report: LoadReport
    ) -> None:
        by_title = {challenge.draft.title: challenge for challenge in source.challenges}
        for challenge_id in self.missions.challenge_ids(mission.id):
            row = self.challenges.get(challenge_id)
            if row.base_key is not None or row.owner_id != owner_id:
                continue
            match = by_title.get(row.title)
            label = _label(mission.title, row.title)
            if match is None or self.challenges.get_by_base_key(match.key) is not None:
                report.unmatched.append(label)
                continue
            row.base_key = match.key
            report.matched.append(label)

    # Loading by key

    def _load_mission(self, owner_id: int, source: BaseMission, report: LoadReport) -> None:
        mission = self.missions.get_by_base_key(source.key)
        if mission is None:
            mission, rows = add_published_mission(
                self.session, owner_id, source.draft(), Origin.BASE
            )
            mission.base_key = source.key
            for row, challenge in zip(rows, source.challenges, strict=True):
                row.base_key = challenge.key
            self.session.flush()
            report.created.append(source.title)
            return

        fields = (source.title, source.description, source.position)
        if (mission.title, mission.description, mission.position) == fields:
            report.kept.append(mission.title)
        else:
            mission.title, mission.description, mission.position = fields
            report.updated.append(mission.title)

        linked = self.missions.challenge_ids(mission.id)
        ordered = [
            self._load_challenge(owner_id, mission, linked, challenge, report)
            for challenge in source.challenges
        ]
        for challenge_id in linked:
            if challenge_id not in ordered:
                title = self.challenges.get(challenge_id).title
                report.not_in_files.append(_label(mission.title, title))
                ordered.append(challenge_id)
        if ordered != linked:
            self.missions.set_challenges(mission.id, ordered)

    def _load_challenge(
        self,
        owner_id: int,
        mission: Mission,
        linked: list[int],
        source: BaseChallenge,
        report: LoadReport,
    ) -> int:
        draft = source.draft
        label = _label(mission.title, draft.title)
        row = self.challenges.get_by_base_key(source.key)
        if row is None:
            row = self._add_challenge(owner_id, source)
            report.created.append(label)
            return row.id
        if row.id not in linked:
            raise Conflict(
                "base_key_moved",
                f"O desafio «{draft.title}» (chave {source.key}) já está em outra missão. "
                "Mova-o de volta ou use uma chave nova.",
            )
        if draft_of(row) == draft:
            return row.id
        # The template rules already ran on every file in read_base_dir, so a structural
        # change is safe to apply while nobody has answered the challenge.
        structural = edit_is_structural(row.type, row.content, draft.type, draft.content)
        if structural and self.challenges.has_submissions(row.id):
            raise Conflict(
                "base_challenge_locked",
                f"O desafio «{row.title}» (chave {source.key}) já tem respostas e a "
                "estrutura dele mudou no arquivo. Altere só os textos ou use uma chave nova.",
            )
        row.title = draft.title
        row.statement = draft.statement
        row.type = ChallengeType(draft.type)
        row.content = draft.content
        row.explanation = draft.explanation
        report.updated.append(label)
        return row.id

    def _add_challenge(self, owner_id: int, source: BaseChallenge) -> Challenge:
        draft = source.draft
        row = self.challenges.add(
            owner_id=owner_id,
            title=draft.title,
            statement=draft.statement,
            challenge_type=ChallengeType(draft.type),
            content=draft.content,
            explanation=draft.explanation,
            origin=Origin.BASE,
            status=ContentStatus.PUBLISHED,
        )
        row.base_key = source.key
        return row
