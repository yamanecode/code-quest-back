"""
Run once to populate the DB with challenges and badges.
Usage: python seed.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.models import Challenge, Badge, ChallengeType, ChallengeCategory

db = SessionLocal()

# ── Badges ────────────────────────────────────────────────────────────────────
badges = [
    Badge(name="Primeira Submissão", description="Submeteu um desafio pela primeira vez", icon="🎯", trigger_condition="first_submission"),
    Badge(name="Nível 5",            description="Alcançou o nível 5",                   icon="⭐", trigger_condition="level_5"),
    Badge(name="Nível 10",           description="Alcançou o nível 10",                  icon="🌟", trigger_condition="level_10"),
    Badge(name="Sequência de 3",     description="3 dias seguidos resolvendo desafios",  icon="🔥", trigger_condition="3_day_streak"),
    Badge(name="Sequência de 7",     description="7 dias seguidos!",                     icon="💎", trigger_condition="7_day_streak"),
    Badge(name="100 XP",             description="Acumulou 100 XP",                      icon="💯", trigger_condition="xp_100"),
    Badge(name="500 XP",             description="Acumulou 500 XP",                      icon="🏆", trigger_condition="xp_500"),
]

# ── Challenges ────────────────────────────────────────────────────────────────
challenges = [
    # --- TYPE: steps (decomposition) ---
    Challenge(
        title="Organizar Estudantes por Nota",
        description="Uma escola precisa organizar estudantes por nota. Decomponha o problema em etapas.",
        difficulty=1,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Qual é a entrada do problema?"},
                {"label": "Qual é o processamento necessário?"},
                {"label": "Qual é a saída esperada?"},
            ],
            "expected_keywords": [
                ["lista", "estudantes", "notas", "dados"],
                ["ordenar", "comparar", "classificar", "organizar"],
                ["lista ordenada", "resultado", "saída", "classificação"],
            ]
        },
        is_daily=True,
    ),
    Challenge(
        title="Sistema de Login",
        description="Decomponha o processo de login em um sistema web.",
        difficulty=2,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Quais dados o usuário fornece?"},
                {"label": "O que o sistema verifica?"},
                {"label": "O que acontece se a senha estiver correta?"},
                {"label": "O que acontece se a senha estiver incorreta?"},
            ],
            "expected_keywords": [
                ["email", "senha", "usuário", "credenciais"],
                ["verificar", "comparar", "banco", "dados", "validar"],
                ["acesso", "login", "entrar", "autenticado"],
                ["erro", "negado", "incorreta", "inválido", "tentar"],
            ]
        },
    ),

    # --- TYPE: pattern ---
    Challenge(
        title="Sequência Numérica 1",
        description="Observe a sequência: 2, 4, 8, 16, ___\nQual é o padrão? Qual é o próximo número?",
        difficulty=1,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "2, 4, 8, 16, ___",
            "answer": "32",
            "explanation": "Cada número é multiplicado por 2."
        },
        is_daily=False,
    ),
    Challenge(
        title="Sequência Numérica 2",
        description="Observe a sequência: 1, 1, 2, 3, 5, 8, ___\nQual é o padrão? Qual é o próximo número?",
        difficulty=2,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1, 1, 2, 3, 5, 8, ___",
            "answer": "13",
            "explanation": "Fibonacci: cada número é a soma dos dois anteriores."
        },
    ),
    Challenge(
        title="Padrão de Desconto",
        description="Uma loja dá desconto assim: R$100 → R$90, R$200 → R$180, R$300 → R$270.\nQual é o padrão? Quanto custaria um item de R$400?",
        difficulty=2,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "100→90, 200→180, 300→270",
            "answer": "360",
            "explanation": "10% de desconto. R$400 × 0.9 = R$360."
        },
    ),
    Challenge(
        title="Sequência de Potências",
        description="Observe: 1, 4, 9, 16, 25, ___\nQual é o padrão? Qual é o próximo número?",
        difficulty=1,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1, 4, 9, 16, 25, ___",
            "answer": "36",
            "explanation": "Quadrados perfeitos: 1², 2², 3², 4², 5², 6²=36."
        },
    ),
]

# ── Insert (skip if already seeded) ──────────────────────────────────────────
existing_challenges = db.query(Challenge).count()
existing_badges = db.query(Badge).count()

if existing_badges == 0:
    db.add_all(badges)
    print(f"✅ Inserted {len(badges)} badges")
else:
    print("⏭️  Badges already seeded")

if existing_challenges == 0:
    db.add_all(challenges)
    print(f"✅ Inserted {len(challenges)} challenges")
else:
    print("⏭️  Challenges already seeded")

db.commit()
db.close()
print("Done.")