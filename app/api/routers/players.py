from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.api.deps import Gamification, get_current_user
from app.api.schemas.gamification import PublicProfileOut

# Public profiles are open to any logged-in user, students and professors alike.
router = APIRouter(tags=["players"], dependencies=[Depends(get_current_user)])


@router.get("/players/{username}")
def public_profile(username: str, gamification: Gamification) -> PublicProfileOut:
    return PublicProfileOut(**asdict(gamification.public_profile(username)))
