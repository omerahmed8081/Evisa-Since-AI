"""Health and knowledge-base counters."""
import os

from fastapi import APIRouter

from pipeline import graph
from api.models import Stats

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(deep: bool = False):
    """{"status": "ok"}. With ?deep=true also checks Neo4j and that a Gemini key is set."""
    if not deep:
        return {"status": "ok"}
    out = {"status": "ok", "gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
           "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")}
    try:
        graph.run("RETURN 1")
        out["neo4j"] = "ok"
    except Exception as e:
        out.update(status="degraded", neo4j=f"{e.__class__.__name__}: {e}")
    return out


@router.get("/stats", response_model=Stats)
def stats():
    r = graph.run("""
        CALL { MATCH (a:Assertion) RETURN count(a) AS assertions }
        CALL { MATCH (a:Assertion) WHERE a.valid_to IS NULL RETURN count(a) AS valid_assertions }
        CALL { MATCH (d:Device) RETURN count(d) AS devices }
        CALL { MATCH (s:Source) RETURN count(s) AS sources }
        CALL { MATCH (t:Term) RETURN count(t) AS terms }
        CALL { MATCH (f:Feedback) RETURN count(f) AS feedback }
        RETURN assertions, valid_assertions, devices, sources, terms, feedback
    """)[0]
    return dict(r)
