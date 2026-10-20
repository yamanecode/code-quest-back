from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    PROFESSOR = "professor"
    SYSTEM = "system"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Origin(StrEnum):
    PROFESSOR = "professor"
    AI = "ai"
    BASE = "base"


class HintSource(StrEnum):
    REQUEST = "request"
    AFTER_WRONG = "after_wrong"


class XPReason(StrEnum):
    FIRST_SOLVE = "first_solve"
