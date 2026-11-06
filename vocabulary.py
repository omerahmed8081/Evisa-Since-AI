"""
The growing vocabulary.

- Seed terms (schema.SEED_VOCABULARY) are loaded into Neo4j once as (:Term) nodes.
- Before each Gemini call, the CURRENT vocabulary is read and put in the prompt.
- Every term Gemini returns is normalised:
    exact match                -> keep
    very similar existing term -> map to it (and remember the alias), e.g. BOUNCE_PORT -> BOUNCE_INTERFACE
    genuinely new              -> add as a new (:Term {status: "new"}) so later chats can reuse it

Similarity uses Gemini embeddings. Tune VOCAB_MERGE_THRESHOLD in .env after looking at
the printed similarity scores (too low = different things merged, too high = duplicates).
"""
import math
import os
import re

from schema import SEED_VOCABULARY

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")


def clean_term(term: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]+", "_", term.strip()).strip("_").upper()
    return t


def _embed_text(name: str, category: str) -> str:
    return f"{name.replace('_', ' ').lower()} ({category} in telecom network operations)"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed(texts: list[str]) -> list[list[float]]:
    """Embeddings with a disk cache: each text is only ever sent to Gemini once."""
    import cache
    from extract import client  # same Gemini client as extraction
    keys = [cache.make_key(EMBED_MODEL, t) for t in texts]
    vectors = [cache.get("embed", k) for k in keys]
    missing = [i for i, v in enumerate(vectors) if v is None]
    for start in range(0, len(missing), 50):
        batch = missing[start:start + 50]
        result = client().models.embed_content(model=EMBED_MODEL, contents=[texts[i] for i in batch])
        for i, e in zip(batch, result.embeddings):
            vectors[i] = list(e.values)
            cache.put("embed", keys[i], vectors[i])
    return vectors


class Vocabulary:
    """use_graph=False keeps everything in memory (for --dry-run, nothing is saved)."""

    def __init__(self, use_graph: bool = True):
        self.use_graph = use_graph
        self.threshold = float(os.environ.get("VOCAB_MERGE_THRESHOLD", "0.88"))
        # category -> {name: embedding or None}
        self.terms: dict[str, dict[str, list[float] | None]] = {}

    # ---------- loading ----------
    def load(self):
        if self.use_graph:
            import graph
            self._seed_graph(graph)
            for r in graph.run("MATCH (t:Term) RETURN t.name AS name, t.category AS cat, t.embedding AS emb"):
                self.terms.setdefault(r["cat"], {})[r["name"]] = r["emb"]
        else:
            self.terms = {cat: {n: None for n in names} for cat, names in SEED_VOCABULARY.items()}
        return self

    def _seed_graph(self, graph):
        rows = [{"name": n, "category": c} for c, names in SEED_VOCABULARY.items() for n in names]
        existing = {r["key"] for r in graph.run("MATCH (t:Term) RETURN t.key AS key")}
        missing = [r for r in rows if f"{r['category']}:{r['name']}" not in existing]
        if not missing:
            return
        vectors = embed([_embed_text(r["name"], r["category"]) for r in missing])
        for r, v in zip(missing, vectors):
            r["embedding"] = v
        graph.run(
            """
            UNWIND $rows AS r
            MERGE (t:Term {key: r.category + ':' + r.name})
            ON CREATE SET t.name = r.name, t.category = r.category, t.status = 'seed',
                          t.embedding = r.embedding, t.aliases = []
            """,
            rows=missing,
        )
        print(f"Seeded {len(missing)} vocabulary terms into Neo4j")

    # ---------- prompt ----------
    def prompt_text(self) -> str:
        return "\n".join(f"{cat}: {', '.join(sorted(names))}" for cat, names in sorted(self.terms.items()))

    # ---------- normalisation ----------
    def normalize_list(self, raw_terms: list[str], category: str, source_id: str) -> list[str]:
        result = []
        for raw in raw_terms:
            name = self.normalize(raw, category, source_id)
            if name and name not in result:
                result.append(name)
        return result

    def normalize(self, raw: str, category: str, source_id: str) -> str | None:
        name = clean_term(raw)
        if not name or name in ("OTHER", "NONE"):
            return None
        known = self.terms.setdefault(category, {})
        if name in known:
            return name

        vector = embed([_embed_text(name, category)])[0]
        self._ensure_embeddings(category)
        best_name, best_score = None, -1.0
        for other, other_vec in known.items():
            score = _cosine(vector, other_vec)
            if score > best_score:
                best_name, best_score = other, score

        if best_name and best_score >= self.threshold:
            print(f"  vocab: {name} -> {best_name} (similarity {best_score:.2f})")
            if self.use_graph:
                import graph
                graph.run(
                    "MATCH (t:Term {key: $key}) "
                    "SET t.aliases = CASE WHEN $alias IN t.aliases THEN t.aliases ELSE t.aliases + $alias END",
                    key=f"{category}:{best_name}", alias=name,
                )
            return best_name

        closest = f", closest: {best_name} {best_score:.2f}" if best_name else ""
        print(f"  vocab: + NEW {category} term {name}{closest}")
        known[name] = vector
        if self.use_graph:
            import graph
            graph.run(
                """
                MERGE (t:Term {key: $key})
                ON CREATE SET t.name = $name, t.category = $cat, t.status = 'new',
                              t.embedding = $emb, t.aliases = [], t.first_seen_in = $src,
                              t.created_at = datetime()
                """,
                key=f"{category}:{name}", name=name, cat=category, emb=vector, src=source_id,
            )
        return name

    def _ensure_embeddings(self, category: str):
        known = self.terms[category]
        missing = [n for n, v in known.items() if v is None]
        if missing:
            for n, v in zip(missing, embed([_embed_text(n, category) for n in missing])):
                known[n] = v
