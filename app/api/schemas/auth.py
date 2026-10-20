from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Credentials(BaseModel):
    # Only these two fields are accepted: no other personal data is collected (SG-09).
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class AccountOut(BaseModel):
    id: int
    username: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")
    role: str
