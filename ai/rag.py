"""Small dependency-free retrieval layer for BharatAssist.

It searches the bundled text knowledge base using token overlap. This is
intentionally lightweight so the project can run on small Render instances.
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _tokens(text):
    words = re.findall(r"[a-zA-Z0-9\u0900-\u097F\u0C80-\u0CFF]+", text.lower())
    stop = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to", "was", "what", "when", "where", "which", "who", "why", "with", "you", "your"}
    return {w for w in words if len(w) > 2 and w not in stop}


def _load_documents():
    docs = []
    for path in DATA_DIR.rglob("*.txt"):
        if path.name.lower() == "readme.txt":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if text:
            docs.append({"title": path.stem.replace("_", " ").title(), "path": str(path), "text": text})
    return docs


def retrieve(query, category=None, top_k=5):
    query_tokens = _tokens(query)
    results = []
    for doc in _load_documents():
        hay = _tokens(doc["text"])
        overlap = len(query_tokens & hay)
        category_bonus = 0
        if category and category.lower() in doc["path"].lower():
            category_bonus = 3
        score = overlap + category_bonus
        if score > 0:
            results.append((score, doc))
    results.sort(key=lambda item: item[0], reverse=True)
    selected = []
    for score, doc in results[:top_k]:
        selected.append({
            "title": doc["title"],
            "score": score,
            "text": doc["text"][:4000],
            "source": doc["path"],
        })
    return selected


def context_text(results):
    return "\n\n".join(
        f"SOURCE: {item['title']}\n{item['text']}" for item in results
    )
