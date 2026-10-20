from fastapi import APIRouter, Depends

from app.api.deps import require_professor

# Every professor route inherits the role check from the router.
router = APIRouter(
    prefix="/professor", tags=["professor"], dependencies=[Depends(require_professor)]
)
