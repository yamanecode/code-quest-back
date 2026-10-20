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


@dataclass(frozen=True)
class BadgeStats:
    """A student's numbers at the moment badges are evaluated (solves are first solves)."""

    solved_total: int = 0
    solved_by_type: Mapping[str, int] = field(default_factory=dict)
    missions_completed: int = 0
    missions_completed_without_hints: int = 0
    streak: int = 0
    level: int = 1
    first_try_solves: int = 0
    dailies_solved: int = 0
    goals_contributed: int = 0
    types_first_solved_today: frozenset[str] = frozenset()


HIDDEN_BADGE_NAME = "Insígnia secreta"

Condition = Callable[[BadgeStats], bool]

SKILL_BADGES = (
    (ChallengeType.ORDERING, "Algoritmos", "🔢"),
    (ChallengeType.GROUPING, "Decomposição", "🧩"),
    (ChallengeType.FILTERING, "Abstração", "🔍"),
    (ChallengeType.PATTERN, "Padrões", "🔁"),
)
SKILL_STEPS = (("I", 3, Tier.BRONZE), ("II", 7, Tier.SILVER), ("III", 15, Tier.GOLD))


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
            )
            rules.append((badge, _solved_of_type(challenge_type, threshold)))
    return rules


_RULES: list[tuple[Badge, Condition]] = [
    (
        Badge(
            "first_solve", "Primeiro desafio", "Resolva seu primeiro desafio.", Tier.BRONZE, "⭐"
        ),
        lambda stats: stats.solved_total >= 1,
    ),
    *_skill_rules(),
    (
        Badge("level_3", "Explorador(a)", "Chegue ao nível 3.", Tier.BRONZE, "🧭"),
        lambda stats: stats.level >= 3,
    ),
    (
        Badge("level_5", "Estrategista", "Chegue ao nível 5.", Tier.SILVER, "🧭"),
        lambda stats: stats.level >= 5,
    ),
    (
        Badge("level_8", "Arquiteto(a) de soluções", "Chegue ao nível 8.", Tier.SILVER, "🧭"),
        lambda stats: stats.level >= 8,
    ),
    (
        Badge("level_11", "Mestre do pensamento", "Chegue ao nível 11.", Tier.GOLD, "🧭"),
        lambda stats: stats.level >= 11,
    ),
    (
        Badge("mission_1", "Primeira missão", "Complete 1 missão.", Tier.BRONZE, "🚩"),
        lambda stats: stats.missions_completed >= 1,
    ),
    (
        Badge("mission_5", "Cinco missões", "Complete 5 missões.", Tier.SILVER, "🚩"),
        lambda stats: stats.missions_completed >= 5,
    ),
    (
        Badge("mission_10", "Dez missões", "Complete 10 missões.", Tier.GOLD, "🚩"),
        lambda stats: stats.missions_completed >= 10,
    ),
    (
        Badge(
            "streak_3",
            "Três dias seguidos",
            "Resolva desafios em 3 dias seguidos.",
            Tier.BRONZE,
            "🔥",
        ),
        lambda stats: stats.streak >= 3,
    ),
    (
        Badge(
            "streak_7",
            "Sete dias seguidos",
            "Resolva desafios em 7 dias seguidos.",
            Tier.SILVER,
            "🔥",
        ),
        lambda stats: stats.streak >= 7,
    ),
    (
        Badge(
            "streak_14",
            "Catorze dias seguidos",
            "Resolva desafios em 14 dias seguidos.",
            Tier.GOLD,
            "🔥",
        ),
        lambda stats: stats.streak >= 14,
    ),
    (
        Badge(
            "first_try_5",
            "Precisão",
            "Acerte 5 desafios na primeira tentativa.",
            Tier.SILVER,
            "🎯",
        ),
        lambda stats: stats.first_try_solves >= 5,
    ),
    (
        Badge(
            "first_try_20",
            "Precisão afiada",
            "Acerte 20 desafios na primeira tentativa.",
            Tier.GOLD,
            "🎯",
        ),
        lambda stats: stats.first_try_solves >= 20,
    ),
    (
        Badge(
            "daily_7",
            "Compromisso diário",
            "Resolva 7 desafios diários, cada um no seu próprio dia.",
            Tier.SILVER,
            "📅",
        ),
        lambda stats: stats.dailies_solved >= 7,
    ),
    (
        Badge(
            "class_goal_1",
            "Trabalho em equipe",
            "Ajude sua turma a cumprir 1 meta semanal.",
            Tier.BRONZE,
            "🤝",
        ),
        lambda stats: stats.goals_contributed >= 1,
    ),
    (
        Badge(
            "class_goal_5",
            "Equipe afinada",
            "Ajude sua turma a cumprir 5 metas semanais.",
            Tier.SILVER,
            "🤝",
        ),
        lambda stats: stats.goals_contributed >= 5,
    ),
    (
        Badge(
            "all_types_day",
            "Pensamento completo",
            "Resolva pela primeira vez desafios dos 4 tipos no mesmo dia.",
            Tier.SILVER,
            "🌈",
            hidden=True,
        ),
        lambda stats: set(ChallengeType) <= stats.types_first_solved_today,
    ),
    (
        Badge(
            "no_hint_mission",
            "Por conta própria",
            "Complete uma missão sem pedir nenhuma dica.",
            Tier.SILVER,
            "🦉",
            hidden=True,
        ),
        lambda stats: stats.missions_completed_without_hints >= 1,
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
