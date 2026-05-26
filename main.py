from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.challenges import router as challenges_router
from app.api.submissions import router as submissions_router
from app.api.users import router as users_router
from app.api.tutor import router as tutor_router


app = FastAPI(title="CodeQuest API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router)
app.include_router(challenges_router)
app.include_router(submissions_router)
app.include_router(users_router)
app.include_router(tutor_router)