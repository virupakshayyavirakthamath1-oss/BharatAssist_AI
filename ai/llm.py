import os
import requests

from ai.rag import build_context


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_URL = "https://api.openai.com/v1/responses"

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna"
)


# ============================================================
# RAG KNOWLEDGE
# ============================================================

def get_knowledge(prompt):
    """
    Retrieve relevant information from the BharatAssist
    knowledge base.
    """

    try:
        context, sources = build_context(prompt, top_k=2)

        return context, sources

    except Exception as e:
        print("RAG ERROR:", e)

        return "", []


# ============================================================
# SYSTEM PROMPT
# ============================================================

def create_system_prompt(language, context):

    if context:

        knowledge_instruction = f"""
Use the following BharatAssist knowledge when relevant.

KNOWLEDGE:

{context}

Rules for the knowledge:

- Prefer the supplied knowledge for factual information.
- Do not invent facts.
- Do not contradict the supplied knowledge.
- If the supplied knowledge is insufficient, say so.
"""

    else:

        knowledge_instruction = """
No relevant BharatAssist knowledge was found.

Use general knowledge carefully.

Do not invent:
- government schemes
- eligibility rules
- benefits
- deadlines
- medical diagnoses
- medicines
- official procedures
"""


    return f"""
You are BharatAssist AI, a helpful AI assistant designed
for users in India.

Answer in {language}.

Give clear, simple and useful answers.

Use Markdown.

Rules:

- Start with a ## heading.
- Use short paragraphs.
- Use bullet points when useful.
- Use numbered steps when useful.
- Use **bold** for important information.
- Never generate HTML.
- For programming questions, use Markdown code blocks.
- Do not invent information.

Government:

- Do not invent schemes.
- Do not invent eligibility requirements.
- Do not invent benefits or deadlines.
- Recommend checking official government sources for important details.

Health:

- Give general educational information only.
- Do not diagnose diseases.
- Do not prescribe medicines.
- Encourage professional medical help when appropriate.

Agriculture:

- Explain general farming concepts.
- Mention that local conditions can affect recommendations.

Career:

- Give practical guidance.
- Do not guarantee jobs or salaries.

{knowledge_instruction}
"""


# ============================================================
# OPENAI CLOUD AI
# ============================================================

def generate_openai_answer(prompt, language, context):

    if not OPENAI_API_KEY:

        return None


    system_prompt = create_system_prompt(
        language,
        context
    )


    user_prompt = f"""
User question:

{prompt}

Answer the question directly.

Keep the response reasonably short.
"""


    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }


    payload = {
        "model": OPENAI_MODEL,
        "instructions": system_prompt,
        "input": user_prompt,
        "max_output_tokens": 500
    }


    try:

        response = requests.post(
            OPENAI_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        data = response.json()


        # ----------------------------------------------------
        # Extract text from Responses API
        # ----------------------------------------------------

        output_text = data.get("output_text")

        if output_text:
            return output_text.strip()


        # Fallback parser
        output = data.get("output", [])

        text_parts = []


        for item in output:

            for content in item.get("content", []):

                text = content.get("text")

                if text:
                    text_parts.append(text)


        answer = "\n".join(text_parts).strip()


        if answer:
            return answer


        return (
            "## No Response\n\n"
            "OpenAI did not return a text response."
        )


    except requests.exceptions.Timeout:

        return (
            "## Response Timeout\n\n"
            "The cloud AI model took too long to respond.\n\n"
            "Please try asking a shorter question."
        )


    except requests.exceptions.HTTPError as e:

        print("OPENAI HTTP ERROR:", e)

        try:
            error_data = response.json()
            print("OPENAI ERROR DETAILS:", error_data)

        except Exception:
            pass


        return (
            "## AI Server Error\n\n"
            "The cloud AI service returned an error.\n\n"
            "Please try again in a moment."
        )


    except requests.exceptions.ConnectionError as e:

        print("OPENAI CONNECTION ERROR:", e)

        return (
            "## AI Connection Error\n\n"
            "BharatAssist could not connect to the cloud AI service.\n\n"
            "Please try again later."
        )


    except Exception as e:

        print("OPENAI ERROR:", e)

        return (
            "## BharatAssist AI Error\n\n"
            "Sorry, BharatAssist could not generate a response."
        )


# ============================================================
# LOCAL OLLAMA AI
# ============================================================

def generate_ollama_answer(prompt, language, context):

    system_prompt = create_system_prompt(
        language,
        context
    )


    user_prompt = f"""
User question:

{prompt}

Answer the question directly and keep the response reasonably short.
"""


    try:

        response = requests.post(

            OLLAMA_URL,

            json={
                "model": OLLAMA_MODEL,

                "messages": [

                    {
                        "role": "system",
                        "content": system_prompt
                    },

                    {
                        "role": "user",
                        "content": user_prompt
                    }

                ],

                "stream": False,

                "options": {
                    "num_ctx": 1024,
                    "temperature": 0.2,
                    "num_predict": 300
                }
            },

            timeout=180
        )


        response.raise_for_status()

        data = response.json()


        answer = data.get(
            "message",
            {}
        ).get(
            "content",
            ""
        )


        if not answer:

            return (
                "## No Response\n\n"
                "BharatAssist did not receive a response "
                "from the local AI model."
            )


        return answer.strip()


    except requests.exceptions.Timeout:

        return (
            "## Response Timeout\n\n"
            "The local AI model is taking too long to respond.\n\n"
            "- Try asking a shorter question.\n"
            "- Make sure Ollama is running."
        )


    except requests.exceptions.ConnectionError:

        return (
            "## AI Connection Error\n\n"
            "BharatAssist could not connect to Ollama.\n\n"
            "Make sure Ollama is running on your computer."
        )


    except Exception as e:

        print("OLLAMA ERROR:", e)

        return (
            "## Local AI Error\n\n"
            "BharatAssist could not generate a response."
        )


# ============================================================
# MAIN AI FUNCTION
# ============================================================

def generate_answer(prompt, language="English"):

    # --------------------------------------------------------
    # Get RAG knowledge first
    # --------------------------------------------------------

    context, sources = get_knowledge(prompt)


    # --------------------------------------------------------
    # CLOUD MODE
    #
    # Render has OPENAI_API_KEY
    # --------------------------------------------------------

    if OPENAI_API_KEY:

        print("BharatAssist AI: Using OpenAI Cloud AI")

        answer = generate_openai_answer(
            prompt,
            language,
            context
        )

        if answer:

            return answer


    # --------------------------------------------------------
    # LOCAL MODE
    #
    # Used when OPENAI_API_KEY does not exist.
    # --------------------------------------------------------

    print("BharatAssist AI: Using local Ollama")

    return generate_ollama_answer(
        prompt,
        language,
        context
    )