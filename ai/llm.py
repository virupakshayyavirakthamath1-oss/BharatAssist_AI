"""Gemini AI adapter for BharatAssist.

The app uses the Gemini Developer API through its HTTPS REST endpoint.
A Gemini API key is optional for local/offline demo mode, but required for
full AI answers. Keep the key in the GEMINI_API_KEY environment variable.
"""

import json
import os
import urllib.error
import urllib.request

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")


def _should_use_search(query: str) -> bool:
    """Use Google Search grounding for questions where freshness matters."""
    if os.environ.get("GEMINI_USE_SEARCH", "auto").lower() in {"0", "false", "no", "off"}:
        return False
    if os.environ.get("GEMINI_USE_SEARCH", "auto").lower() in {"1", "true", "yes", "on", "always"}:
        return True
    q = query.lower()
    freshness_terms = [
        "today", "now", "current", "latest", "recent", "news", "this week",
        "this month", "price", "cost", "weather", "who is the current",
        "minister", "president", "chief minister", "scheme", "eligibility",
        "deadline", "2026", "2027"
    ]
    return any(term in q for term in freshness_terms)


def _extract_sources(payload):
    sources = []
    try:
        candidates = payload.get("candidates", [])
        metadata = candidates[0].get("groundingMetadata", {}) if candidates else {}
        for chunk in metadata.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            uri = web.get("uri")
            title = web.get("title") or uri
            if uri and not any(s.get("url") == uri for s in sources):
                sources.append({"title": title, "url": uri})
    except Exception:
        pass
    return sources


def generate_answer(prompt, language="English", query="", context="", category="GENERAL"):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "answer": (
                "BharatAssist is ready, but the free Gemini API key is not configured. "
                "Set GEMINI_API_KEY in your environment/Render settings to enable full AI answers."
            ),
            "sources": [],
            "provider": "offline",
        }

    system = f"""You are BharatAssist AI, a careful multilingual public-assistance assistant.
Answer the user's question in {language}. If the user uses a mixed English/Hindi/Kannada style, answer naturally and clearly.
Category: {category}.

Accuracy rules:
- Give a direct, useful answer first.
- Do not invent facts, laws, eligibility rules, statistics, citations, or URLs.
- For current or changing facts, prefer grounded web information when available.
- If the supplied context is insufficient, say what is uncertain instead of pretending.
- For health questions, provide educational information only and do not diagnose or prescribe.
- For emergencies, tell the user to contact appropriate local emergency services first.
- For government schemes/services, distinguish general guidance from official eligibility and tell the user to verify the final rule on the official portal.
- Use simple language suitable for a college/public-assistance application.

Local knowledge context:
{context[:12000] if context else 'No local knowledge was retrieved.'}

{prompt}
"""

    body = {
        "contents": [{"parts": [{"text": system}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1200,
        },
    }
    if _should_use_search(query):
        body["tools"] = [{"google_search": {}}]

    url = f"{API_BASE}/{DEFAULT_MODEL}:generateContent"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = ""
        for candidate in payload.get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                if part.get("text"):
                    text += part["text"]
        if not text.strip():
            raise RuntimeError("Gemini returned an empty answer.")
        return {
            "answer": text.strip(),
            "sources": _extract_sources(payload),
            "provider": "Google Gemini",
        }
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        if exc.code == 429:
            message = (
                "The free Gemini usage limit was reached temporarily. "
                "Please wait and try again later."
            )
        elif exc.code in (401, 403):
            message = "The Gemini API key is invalid or does not have API access. Check GEMINI_API_KEY."
        else:
            message = f"Gemini API returned HTTP {exc.code}."
        return {"answer": f"{message}\n\nTechnical detail: {detail[:500]}", "sources": [], "provider": "Google Gemini"}
    except Exception as exc:
        return {
            "answer": "The AI service could not be reached right now. The website itself is still running. Please try again.",
            "sources": [],
            "provider": "Google Gemini",
            "error": str(exc),
        }
