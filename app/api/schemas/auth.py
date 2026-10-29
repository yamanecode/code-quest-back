from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Credentials(BaseModel):
    # Only these two fields are accepted: no other personal data is collected (SG-09).
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class RegisterOut(BaseModel):
    id: int
    username: str
    role: str
    recovery_code: str


class ResetPasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    recovery_code: str
    new_password: str


class RecoveryCodeOut(BaseModel):
    recovery_code: str


class PasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str


class IssuedRecoveryCodeOut(BaseModel):
    recovery_code: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")
    role: str
