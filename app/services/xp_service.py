from sqlalchemy.orm import Session
from app.models.models import User, XPEvent, Badge, UserBadge

# XP per difficulty
XP_TABLE = {1: 10, 2: 20, 3: 35}
STREAK_BONUS = 5  # bonus XP per day of streak


def calc_level(xp: int) -> int:
    """Simple level curve: every 100 XP = 1 level."""
    return max(1, xp // 100 + 1)


def grant_xp(db: Session, user: User, amount: int, reason: str):
    """Add XP, log event, recalculate level."""
    user.xp += amount
    user.level = calc_level(user.xp)
    event = XPEvent(user_id=user.id, amount=amount, reason=reason)
    db.add(event)


def check_badges(db: Session, user: User):
    """Check all badge conditions and award any not yet earned."""
    all_badges = db.query(Badge).all()
    earned_ids = {ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == user.id).all()}

    for badge in all_badges:
        if badge.id in earned_ids:
            continue
        if _meets_condition(badge.trigger_condition, user):
            db.add(UserBadge(user_id=user.id, badge_id=badge.id))


def _meets_condition(condition: str, user: User) -> bool:
    conditions = {
        "first_submission": user.xp >= 10,
        "level_5": user.level >= 5,
        "level_10": user.level >= 10,
        "3_day_streak": user.streak >= 3,
        "7_day_streak": user.streak >= 7,
        "xp_100": user.xp >= 100,
        "xp_500": user.xp >= 500,
    }
    return conditions.get(condition, False)