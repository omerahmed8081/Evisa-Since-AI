"""FastAPI app. Run from backend/: uvicorn api.main:app --reload --port 8000 (docs at /docs)."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

from api.config import CORS_ORIGIN_REGEX, CORS_ORIGINS
from api.routes import chat, feedback, nodes, system

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Network Knowledge Assistant API",
    version="0.1.0",
    description="Backend for the Elisa × Since AI 2026 knowledge chatbot: "
                "understand (Gemini) → retrieve (Neo4j) → answer (Gemini), plus feedback.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (chat.router, nodes.router, feedback.router, system.router):
    app.include_router(r)


@app.exception_handler(ServiceUnavailable)
@app.exception_handler(SessionExpired)
@app.exception_handler(AuthError)
async def neo4j_down(_: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"detail": f"Knowledge graph unavailable: {exc.__class__.__name__}"})


SETTINGS = {"NEO4J_URI", "NEO4J_PASSWORD", "GEMINI_API_KEY"}


@app.exception_handler(KeyError)
async def missing_setting(_: Request, exc: KeyError):
    if exc.args and exc.args[0] in SETTINGS:
        return JSONResponse(status_code=500, content={"detail": f"Missing setting {exc.args[0]}; check your .env"})
    raise exc


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")
