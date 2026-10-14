from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_professor
from app.database import get_db
from app.models.models import Challenge, User
from app.schemas.challenge import ChallengeCreate, ChallengeResponse

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("/", response_model=list[ChallengeResponse])
def list_challenges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Challenge).all()


@router.get("/{challenge_id}", response_model=ChallengeResponse)
def get_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


@router.post("/", response_model=ChallengeResponse, status_code=201)
def create_challenge(
    body: ChallengeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_professor),
):
    challenge = Challenge(**body.model_dump(), created_by=current_user.id)
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge
