from datetime import date

from sqlalchemy.orm import Session

from app.models.models import Badge, User, UserBadge, XPEvent

XP_TABLE = {1: 10, 2: 20, 3: 35, 4: 50, 5: 75}
STREAK_BONUS = 5


def calc_level(xp: int) -> int:
    return max(1, xp // 100 + 1)


def grant_xp(db: Session, user: User, amount: int, reason: str):
    exists = (
        db.query(XPEvent)
        .filter(
            XPEvent.user_id == user.id,
            XPEvent.reason == reason,
        )
        .first()
    )
    if exists:
        return
    user.xp += amount
    user.level = calc_level(user.xp)
    db.add(XPEvent(user_id=user.id, amount=amount, reason=reason))


def update_streak(db: Session, user: User):
    today = date.today()
    last_event = (
        db.query(XPEvent)
        .filter(XPEvent.user_id == user.id)
        .order_by(XPEvent.created_at.desc())
        .offset(1)  # skip the event just added
        .first()
    )
    if last_event is None:
        user.streak = 1
        return

    last_date = last_event.created_at.date()
    delta = (today - last_date).days

    if delta == 0:
        pass  # same day, no change
    elif delta == 1:
        user.streak += 1
        if user.streak % 7 == 0:
            grant_xp(db, user, STREAK_BONUS * 7, f"streak_bonus_{user.streak}_days")
    else:
        user.streak = 1  # streak broken


def check_badges(db: Session, user: User):
    all_badges = db.query(Badge).all()
    earned_ids = {
        ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == user.id).all()
    }
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
