from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    OPENAI_API_KEY: str = ""  # optional for now

    class Config:
        env_file = ".env"


settings = Settings()