from enum import Enum

from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    student = "student"
    professor = "professor"


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.student


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type label, not a secret


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    xp: int
    level: int
    streak: int

    class Config:
        from_attributes = True
