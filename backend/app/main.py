from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import Base, SessionLocal, engine
from .documents import models as document_models  # noqa: F401 - registriert die Tabellen bei create_all
from .documents.router import router as documents_router
from .documents.seed import seed_defaults as seed_document_defaults
from .routers import agenda, agents, achievements, categories, chat, contact, files, goals
from .seed import seed_defaults

app = FastAPI(title="Nauteron Cockpit")

# Lokale Nutzung: Frontend laeuft auf einem anderen Port (Vite-Dev-Server),
# daher muss der Browser Anfragen von dort zum Backend zulassen duerfen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
        seed_document_defaults(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(agenda.router)
app.include_router(categories.router)
app.include_router(goals.router)
app.include_router(achievements.router)
app.include_router(contact.router)
app.include_router(files.router)
app.include_router(documents_router)
