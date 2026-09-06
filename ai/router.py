from ai.safety import safety_notice


KEYWORDS = {
    "HEALTH": [
        "health", "symptom", "fever", "medicine", "doctor",
        "pain", "blood", "disease", "hospital", "sleep",
        "diet", "exercise", "infection", "wellness"
    ],

    "EDUCATION": [
        "study", "exam", "learn", "subject", "python",
        "django", "java", "c", "c++", "programming",
        "program", "code", "coding", "computer science",
        "machine learning", "artificial intelligence",
        "ai", "database", "sql", "html", "css", "javascript",
        "algorithm", "data structure", "quiz", "student",
        "college", "course", "tutorial", "framework"
    ],

    "GOVERNMENT": [
        "scheme", "government", "aadhaar", "passport",
        "certificate", "subsidy", "pension", "ration",
        "government service", "official portal",
        "citizenship", "voter", "driving licence"
    ],

    "AGRICULTURE": [
        "crop", "farmer", "farm", "farming", "pest",
        "soil", "irrigation", "wheat", "rice", "cotton",
        "fertilizer", "fertiliser", "harvest", "seed",
        "agriculture", "agricultural", "plant", "cultivation"
    ],

    "CAREER": [
        "career", "job", "resume", "cv", "interview",
        "skill", "internship", "developer", "employment",
        "salary", "profession", "placement", "work",
        "freelancing", "linkedin"
    ],

    "DOCUMENT": [
        "document", "pdf", "agreement", "certificate",
        "report", "file", "upload", "summarize document",
        "explain document"
    ],

    "EMERGENCY": [
        "emergency", "accident", "fire", "danger",
        "ambulance", "police", "urgent", "help"
    ]
}


def classify(text):
    low = text.lower()

    scores = {}

    for category, words in KEYWORDS.items():
        score = 0

        for word in words:
            if word in low:
                # Give multi-word phrases a slightly higher score
                if " " in word:
                    score += 2
                else:
                    score += 1

        scores[category] = score

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "GENERAL"

    return best


def route_query(query, language="English"):
    category = classify(query)

    answer = build_answer(
        query,
        category,
        language
    )

    sources = []

    if category == "GOVERNMENT":
        sources = [
            "Verify details on the relevant official "
            "Government of India or state government portal."
        ]

    elif category == "HEALTH":
        sources = [
            "Use a qualified healthcare professional "
            "or official health service for personal "
            "medical decisions."
        ]

    return {
        "answer": answer,
        "category": category,
        "language": language,
        "sources": sources
    }


def build_answer(query, category, language):

    intro = {
        "HEALTH":
            "I can help explain general health information, "
            "but I cannot diagnose a condition or prescribe treatment.",

        "EDUCATION":
            "I can explain this topic clearly and provide "
            "examples, quizzes, summaries, or a learning plan.",

        "GOVERNMENT":
            "I can explain government-service terminology "
            "and help make a checklist. Final eligibility "
            "and application rules must be verified from "
            "the official source.",

        "AGRICULTURE":
            "I can provide general farming guidance and "
            "explain crop-care concepts. Local agricultural "
            "conditions should be checked before acting.",

        "CAREER":
            "I can help convert your career goal into "
            "skills, projects, learning resources and "
            "interview preparation.",

        "DOCUMENT":
            "I can help summarize and explain a document "
            "when its text is provided or uploaded.",

        "EMERGENCY":
            "If this is an immediate emergency, contact "
            "the appropriate local emergency service first. "
            "I can provide general safety information, "
            "but I cannot dispatch help.",

        "GENERAL":
            "I can help with education, government information, "
            "careers, agriculture, general health information, "
            "documents and everyday questions."
    }[category]

    return (
        f"{intro}\n\n"
        f"Your question: {query}\n\n"
        "Demo response: This starter version uses a local "
        "intent router. Add an LLM/RAG provider through "
        "ai/llm.py and ai/rag.py for production-quality answers."
    )