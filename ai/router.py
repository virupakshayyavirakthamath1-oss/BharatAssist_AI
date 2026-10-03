from ai.safety import safety_notice
from ai.rag import retrieve, context_text
from ai.llm import generate_answer

KEYWORDS = {
    "HEALTH": ["health", "symptom", "fever", "medicine", "doctor", "pain", "blood", "disease", "hospital", "ಆರೋಗ್ಯ", "ಜ್ವರ"],
    "EDUCATION": ["study", "exam", "learn", "subject", "python", "java", "math", "quiz", "student", "education", "ಶಿಕ್ಷಣ", "ಅಧ್ಯಯನ"],
    "GOVERNMENT": ["scheme", "government", "aadhaar", "passport", "certificate", "subsidy", "pension", "ration", "ಯೋಜನೆ", "ಸರ್ಕಾರ"],
    "AGRICULTURE": ["crop", "farmer", "farm", "pest", "soil", "irrigation", "wheat", "rice", "cotton", "ಕೃಷಿ", "ರೈತ", "ಬೆಳೆ"],
    "CAREER": ["career", "job", "resume", "cv", "interview", "skill", "internship", "developer", "career", "ಉದ್ಯೋಗ"],
    "DOCUMENT": ["document", "pdf", "agreement", "certificate", "report", "file", "ದಾಖಲೆ"],
    "EMERGENCY": ["emergency", "accident", "fire", "danger", "ambulance", "police", "ತುರ್ತು"],
}


def classify(text):
    low = text.lower()
    scores = {k: sum(1 for w in words if w in low) for k, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "GENERAL"


def route_query(query, language="English"):
    category = classify(query)
    rag_results = retrieve(query, category=category, top_k=5)
    context = context_text(rag_results)
    prompt = f"User question: {query}\n\nGive the best answer you can."
    ai_result = generate_answer(
        prompt,
        language=language,
        query=query,
        context=context,
        category=category,
    )

    sources = list(ai_result.get("sources", []))
    for item in rag_results:
        sources.append({
            "title": f"BharatAssist knowledge: {item['title']}",
            "url": "",
        })

    if category == "GOVERNMENT" and not sources:
        sources.append({"title": "Verify final details on the relevant official government portal.", "url": ""})
    if category == "HEALTH" and not sources:
        sources.append({"title": "Use a qualified healthcare professional for personal medical decisions.", "url": ""})

    return {
        "answer": ai_result["answer"],
        "category": category,
        "language": language,
        "sources": sources,
        "provider": ai_result.get("provider", "unknown"),
    }
