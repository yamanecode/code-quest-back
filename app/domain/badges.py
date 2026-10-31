from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.challenge_types import SKILL_LABELS, ChallengeType


class Tier(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


@dataclass(frozen=True)
class Badge:
    code: str
    name: str
    description: str
    tier: Tier
    emoji: str
    hidden: bool = False
    # Locked badges with this flag tell the student they need turma challenges.
    requires_class: bool = False


@dataclass(frozen=True)
class BadgeStats:
    """A student's numbers at the moment badges are evaluated (solves are first solves)."""

    solved_total: int = 0
    solved_by_type: Mapping[str, int] = field(default_factory=dict)
    missions_completed: int = 0
    level: int = 1
    first_try_solves: int = 0
    persistent_solves: int = 0
    goals_contributed: int = 0
    types_first_solved_today: frozenset[str] = frozenset()
    explored_every_base_mission: bool = False


HIDDEN_BADGE_NAME = "Insígnia secreta"

Condition = Callable[[BadgeStats], bool]

SKILL_BADGES = (
    (ChallengeType.ORDERING, "Algoritmos", "🔢"),
    (ChallengeType.GROUPING, "Decomposição", "🧩"),
    (ChallengeType.FILTERING, "Abstração", "🔍"),
    (ChallengeType.PATTERN, "Padrões", "🔁"),
)
SKILL_STEPS = (("I", 3, Tier.BRONZE), ("II", 7, Tier.SILVER), ("III", 15, Tier.GOLD))

# Families of badges earned when one number reaches a threshold: (threshold, name, tier).
# In the graded families only gold is out of reach of the base game (spec 5.1).
LEVEL_STEPS = (
    (3, "Aprendiz", Tier.BRONZE),
    (6, "Praticante", Tier.SILVER),
    (11, "Mestre", Tier.GOLD),
)
MISSION_STEPS = (
    (1, "Primeira missão", Tier.BRONZE),
    (5, "Cinco missões", Tier.SILVER),
    (10, "Dez missões", Tier.GOLD),
)
FIRST_TRY_STEPS = ((5, "Precisão", Tier.BRONZE), (30, "Precisão afiada", Tier.GOLD))
CLASS_GOAL_STEPS = ((1, "Trabalho em equipe", Tier.BRONZE), (5, "Equipe afinada", Tier.SILVER))


def _at_least(stat: str, threshold: int) -> Condition:
    return lambda stats: getattr(stats, stat) >= threshold


def _solved_of_type(challenge_type: ChallengeType, threshold: int) -> Condition:
    return lambda stats: stats.solved_by_type.get(challenge_type, 0) >= threshold


def _skill_rules() -> list[tuple[Badge, Condition]]:
    rules = []
    for challenge_type, name, emoji in SKILL_BADGES:
        for numeral, threshold, tier in SKILL_STEPS:
            badge = Badge(
                f"skill_{challenge_type}_{threshold}",
                f"{name} {numeral}",
                f"Resolva {threshold} desafios de {SKILL_LABELS[challenge_type]}.",
                tier,
                emoji,
                requires_class=tier == Tier.GOLD,
            )
            rules.append((badge, _solved_of_type(challenge_type, threshold)))
    return rules


def _family(
    prefix: str,
    emoji: str,
    stat: str,
    steps: tuple[tuple[int, str, Tier], ...],
    describe: Callable[[int], str],
    always_requires_class: bool = False,
) -> list[tuple[Badge, Condition]]:
    return [
        (
            Badge(
                f"{prefix}_{n}",
                name,
                describe(n),
                tier,
                emoji,
                requires_class=always_requires_class or tier == Tier.GOLD,
            ),
            _at_least(stat, n),
        )
        for n, name, tier in steps
    ]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


_RULES: list[tuple[Badge, Condition]] = [
    (
        Badge(
            "first_solve", "Primeiro desafio", "Resolva seu primeiro desafio.", Tier.BRONZE, "⭐"
        ),
        _at_least("solved_total", 1),
    ),
    *_skill_rules(),
    *_family("level", "🧭", "level", LEVEL_STEPS, lambda n: f"Chegue ao nível {n}."),
    *_family(
        "mission",
        "🚩",
        "missions_completed",
        MISSION_STEPS,
        lambda n: f"Complete {_plural(n, 'missão', 'missões')}.",
    ),
    *_family(
        "first_try",
        "🎯",
        "first_try_solves",
        FIRST_TRY_STEPS,
        lambda n: f"Acerte {n} desafios na primeira tentativa.",
    ),
    *_family(
        "class_goal",
        "🤝",
        "goals_contributed",
        CLASS_GOAL_STEPS,
        lambda n: f"Ajude sua turma a cumprir {_plural(n, 'meta semanal', 'metas semanais')}.",
        always_requires_class=True,
    ),
    (
        Badge(
            "all_types_day",
            "Pensamento completo",
            "Resolva pela primeira vez desafios dos 4 tipos no mesmo dia.",
            Tier.GOLD,
            "🌈",
            hidden=True,
        ),
        lambda stats: set(ChallengeType) <= stats.types_first_solved_today,
    ),
    (
        Badge(
            "persistent",
            "Persistente",
            "Resolva um desafio depois de errar 3 vezes ou mais.",
            Tier.GOLD,
            "💪",
            hidden=True,
        ),
        _at_least("persistent_solves", 1),
    ),
    (
        Badge(
            "explorer_base",
            "Viajante",
            "Resolva pelo menos um desafio de cada missão do jogo base.",
            Tier.GOLD,
            "🗺️",
            hidden=True,
        ),
        lambda stats: stats.explored_every_base_mission,
    ),
]

BADGES: tuple[Badge, ...] = tuple(badge for badge, _ in _RULES)
_CONDITIONS: dict[str, Condition] = {badge.code: condition for badge, condition in _RULES}


def badge_codes_earned(stats: BadgeStats) -> set[str]:
    """Every badge whose condition holds; the caller removes the ones already awarded."""
    return {code for code, condition in _CONDITIONS.items() if condition(stats)}


def badge_display(badge: Badge, earned: bool) -> tuple[str, str]:
    """Name and description a student sees; hidden badges keep their condition secret."""
    if badge.hidden and not earned:
        return HIDDEN_BADGE_NAME, ""
    return badge.name, badge.description
