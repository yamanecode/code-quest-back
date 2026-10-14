import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.ai_service import generate_challenge, generate_daily_challenge, tutor_agent
from app.core.deps import get_current_user, require_professor
from app.database import get_db
from app.models.models import Challenge, ChallengeCategory, ChallengeType, User

router = APIRouter(prefix="/tutor", tags=["tutor"])


class HintRequest(BaseModel):
    challenge_id: int
    current_answer: dict[str, Any] = {}


class HintResponse(BaseModel):
    hint: str


class GenerateRequest(BaseModel):
    topic: str
    type: str  # "steps" or "pattern"
    difficulty: int  # 1-5


class GenerateResponse(BaseModel):
    raw: str  # professor reviews before saving


@router.post("/hint", response_model=HintResponse)
async def get_hint(
    body: HintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    hint = await tutor_agent(
        challenge.title,
        challenge.description,
        body.current_answer,
    )
    return {"hint": hint}


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    current_user: User = Depends(require_professor),
):
    result = await generate_challenge(body.topic, body.type, body.difficulty)
    return {"raw": result}


@router.post("/generate-daily")
async def generate_daily(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = await generate_daily_challenge()

    # Strip markdown fences if Gemini wraps it
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(clean)
    except Exception:
        raise HTTPException(
            status_code=500, detail=f"AI returned invalid JSON: {raw[:200]}"
        ) from None

    # Replace current daily
    db.query(Challenge).filter(Challenge.is_daily.is_(True)).update({"is_daily": False})

    challenge = Challenge(
        title=data["title"],
        description=data["description"],
        difficulty=4,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.steps,
        content=data["content"],
        is_daily=True,
        created_by=current_user.id,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge
