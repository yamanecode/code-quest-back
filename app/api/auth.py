from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User
from app.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.role.value)
    return {"access_token": token}


@router.get("/me", response_model=UserResponse)
def me(db: Session = Depends(get_db), token: str = Depends(lambda: None)):
    # placeholder — we'll add proper token dependency next
    raise HTTPException(status_code=501, detail="Use /me after adding auth dependency")