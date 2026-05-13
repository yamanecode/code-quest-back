from pydantic import BaseModel, EmailStr
from enum import Enum


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
    token_type: str = "bearer"


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