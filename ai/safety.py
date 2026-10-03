def safety_notice(category="GENERAL"):
    notices = {
        "HEALTH": "Health information is educational only. It is not a diagnosis or prescription. For severe or urgent symptoms, contact local emergency/medical services.",
        "GOVERNMENT": "Government information should be verified against the relevant official government portal before applying.",
        "AGRICULTURE": "Agriculture suggestions are general guidance. Local crop, soil, weather and expert advice should be considered before action.",
        "EMERGENCY": "This assistant does not replace emergency services. If there is immediate danger, contact the appropriate local emergency service now."
    }
    return notices.get(category, "AI-generated information can be incomplete. Verify important decisions with a trusted official or qualified professional.")
