import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"


def clean_text(text):
    """Clean unnecessary whitespace."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text, chunk_size=700):
    """Split text into small chunks."""
    text = clean_text(text)

    if not text:
        return []

    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def load_documents():
    """Load TXT files from the knowledge folders."""

    documents = []

    if not KNOWLEDGE_DIR.exists():
        return documents

    for file_path in KNOWLEDGE_DIR.rglob("*.txt"):

        try:
            text = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            chunks = split_text(text)

            category = file_path.parent.name

            for chunk in chunks:
                documents.append({
                    "text": chunk,
                    "source": file_path.name,
                    "category": category
                })

        except Exception as e:
            print("RAG document error:", file_path, e)

    return documents


def retrieve_documents(query, top_k=3):
    """Find the most relevant knowledge chunks."""

    documents = load_documents()

    if not documents:
        return []

    texts = [doc["text"] for doc in documents]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english"
    )

    try:
        matrix = vectorizer.fit_transform(texts)
        query_vector = vectorizer.transform([query])

        scores = cosine_similarity(
            query_vector,
            matrix
        ).flatten()

    except Exception as e:
        print("RAG search error:", e)
        return []

    ranked_indexes = scores.argsort()[::-1]

    results = []

    for index in ranked_indexes[:top_k]:

        if scores[index] <= 0:
            continue

        document = documents[index].copy()
        document["score"] = float(scores[index])

        results.append(document)

    return results


def retrieve(query, category=None, top_k=5):
    """
    Main RAG retrieval interface.

    Returns relevant knowledge-base documents.
    """

    results = retrieve_documents(
        query,
        top_k=top_k
    )

    if category:
        filtered = [
            result
            for result in results
            if result["category"].lower() == category.lower()
        ]

        if filtered:
            results = filtered

    return results


def build_context(query, top_k=3):
    """Create context that can be sent to the AI model."""

    results = retrieve_documents(
        query,
        top_k=top_k
    )

    if not results:
        return "", []

    context_parts = []
    sources = []

    for result in results:

        context_parts.append(
            f"Source: {result['source']}\n"
            f"Category: {result['category']}\n"
            f"Information: {result['text']}"
        )

        sources.append({
            "source": result["source"],
            "category": result["category"],
            "score": round(result["score"], 3)
        })

    context = "\n\n---\n\n".join(context_parts)

    return context, sources