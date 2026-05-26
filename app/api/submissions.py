from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, Challenge, Submission
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.core.deps import get_current_user
from app.services.xp_service import XP_TABLE, grant_xp, check_badges
from app.ai.ai_service import feedback_agent

router = APIRouter(prefix="/submissions", tags=["submissions"])


def evaluate_answer(challenge: Challenge, answer: dict) -> tuple[bool, str]:
    ctype = challenge.type.value
    content = challenge.content

    if ctype == "steps":
        expected = content.get("expected_keywords", [])
        student_steps = answer.get("steps", [])
        correct_count = 0
        for i, keywords in enumerate(expected):
            if i < len(student_steps):
                if any(kw.lower() in student_steps[i].lower() for kw in keywords):
                    correct_count += 1
        is_correct = correct_count >= len(expected) * 0.6
        return is_correct, ""

    elif ctype == "pattern":
        expected = str(content.get("answer", "")).lower().strip()
        given = str(answer.get("answer", "")).lower().strip()
        is_correct = expected in given or given in expected
        return is_correct, ""

    return False, ""


@router.post("/", response_model=SubmissionResponse, status_code=201)
async def submit(
    body: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    challenge = db.query(Challenge).filter(Challenge.id == body.challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    attempt_number = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.challenge_id == body.challenge_id,
    ).count() + 1

    is_correct, _ = evaluate_answer(challenge, body.answer)

    # AI feedback (non-blocking fallback)
    try:
        ai_feedback = await feedback_agent(
            challenge.title,
            challenge.description,
            body.answer,
            is_correct,
        )
    except Exception as e:
        print(f"Error occurred while generating AI feedback: {e}")
        ai_feedback = "Correto!" if is_correct else "Resposta incorreta. Tente novamente!"

    xp_earned = 0
    if is_correct and attempt_number == 1:
        xp_earned = XP_TABLE.get(challenge.difficulty, 10)
        grant_xp(db, current_user, xp_earned, f"challenge_{challenge.id}_correct")
    elif is_correct:
        xp_earned = XP_TABLE.get(challenge.difficulty, 10) // 2
        grant_xp(db, current_user, xp_earned, f"challenge_{challenge.id}_retry")

    check_badges(db, current_user)

    submission = Submission(
        user_id=current_user.id,
        challenge_id=body.challenge_id,
        answer=body.answer,
        is_correct=is_correct,
        xp_earned=xp_earned,
        attempt_number=attempt_number,
        ai_feedback=ai_feedback,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission