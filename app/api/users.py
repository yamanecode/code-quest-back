from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.models import Badge, Challenge, User, UserBadge

router = APIRouter(prefix="/users", tags=["users"])


class BadgeOut(BaseModel):
    id: int
    name: str
    description: str
    icon: str

    class Config:
        from_attributes = True


class UserMeResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    xp: int
    level: int
    streak: int
    badges: list[BadgeOut] = []

    class Config:
        from_attributes = True


class RankingEntry(BaseModel):
    id: int
    name: str
    xp: int
    level: int

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserMeResponse)
def get_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    badge_ids = [
        ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == current_user.id).all()
    ]
    badges = db.query(Badge).filter(Badge.id.in_(badge_ids)).all() if badge_ids else []
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "xp": current_user.xp,
        "level": current_user.level,
        "streak": current_user.streak,
        "badges": badges,
    }


@router.get("/ranking", response_model=list[RankingEntry])
def get_ranking(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).order_by(User.xp.desc()).limit(10).all()


@router.get("/daily-challenge")
def get_daily(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    challenge = db.query(Challenge).filter(Challenge.is_daily.is_(True)).first()
    if not challenge:
        return {"message": "No daily challenge today"}
    return challenge
