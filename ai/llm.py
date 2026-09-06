import os
import requests

from ai.rag import build_context


# =========================================================
# CONFIGURATION
# =========================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat"
)

MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b"
)


# =========================================================
# GENERATE ANSWER
# =========================================================

def generate_answer(prompt, language="English"):

    try:

        # -------------------------------------------------
        # 1. Search BharatAssist knowledge base
        # -------------------------------------------------

        context, sources = build_context(
            prompt,
            top_k=2
        )

        # -------------------------------------------------
        # 2. Build lightweight knowledge instruction
        # -------------------------------------------------

        if context:

            knowledge_instruction = f"""
Use the following BharatAssist knowledge when relevant.

KNOWLEDGE:
{context}

Rules:
- Prefer the supplied knowledge for factual information.
- Do not invent facts.
- Do not contradict the supplied knowledge.
- If the knowledge is insufficient, say so.
"""

        else:

            knowledge_instruction = """
No relevant BharatAssist knowledge was found.

Answer using general knowledge carefully.

Do not invent facts, government schemes, eligibility rules,
medical diagnoses, medicines, deadlines, or official procedures.
"""

        # -------------------------------------------------
        # 3. Lightweight system prompt
        # -------------------------------------------------

        system_prompt = f"""
You are BharatAssist AI, a helpful assistant for users in India.

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
- Do not invent schemes, eligibility, benefits or deadlines.
- Recommend checking official government sources for important details.

Health:
- Give general educational information only.
- Do not diagnose or prescribe medicines.
- Encourage professional medical help when appropriate.

Agriculture:
- Explain general farming concepts.
- Mention that local conditions can affect recommendations.

Career:
- Give practical guidance.
- Do not guarantee jobs or salaries.

{knowledge_instruction}
"""

        # -------------------------------------------------
        # 4. User prompt
        # -------------------------------------------------

        user_prompt = f"""
User question:

{prompt}

Answer the question directly and keep the response reasonably short.
"""

        # -------------------------------------------------
        # 5. Send request to Ollama
        # -------------------------------------------------

        response = requests.post(
            OLLAMA_URL,

            json={
                "model": MODEL,

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
                    # Smaller context = less RAM usage
                    "num_ctx": 1024,

                    # Lower value = more focused answers
                    "temperature": 0.2,

                    # Limit response length
                    "num_predict": 200
                }
            },

            # Allow enough time for a low-RAM computer
            timeout=180
        )

        # -------------------------------------------------
        # 6. Check Ollama response
        # -------------------------------------------------

        response.raise_for_status()

        data = response.json()

        # -------------------------------------------------
        # 7. Extract generated answer
        # -------------------------------------------------

        answer = data.get("message", {}).get("content", "")

        if not answer:

            return (
                "## No Response\n\n"
                "BharatAssist AI did not receive a response "
                "from the local AI model."
            )

        return answer.strip()

    # =====================================================
    # TIMEOUT ERROR
    # =====================================================

    except requests.exceptions.Timeout:

        return (
            "## Response Timeout\n\n"
            "The local AI model is taking too long to respond.\n\n"
            "- Try asking a shorter question.\n"
            "- Make sure Ollama is running.\n"
            "- Close unnecessary applications to free RAM."
        )

    # =====================================================
    # CONNECTION ERROR
    # =====================================================

    except requests.exceptions.ConnectionError:

        return (
            "## AI Connection Error\n\n"
            "BharatAssist could not connect to Ollama.\n\n"
            "Please make sure:\n\n"
            "- Ollama is running.\n"
            "- `qwen2.5:1.5b` is installed.\n"
            "- Ollama is available at `127.0.0.1:11434`."
        )

    # =====================================================
    # HTTP ERROR
    # =====================================================

    except requests.exceptions.HTTPError as e:

        print("OLLAMA HTTP ERROR:", e)

        return (
            "## AI Server Error\n\n"
            "Ollama returned an error while processing "
            "the request.\n\n"
            "Please check that the Qwen model is available."
        )

    # =====================================================
    # OTHER ERROR
    # =====================================================

    except Exception as e:

        print("OLLAMA ERROR:", e)

        return (
            "## BharatAssist AI Error\n\n"
            "Sorry, BharatAssist AI could not generate "
            "a response.\n\n"
            "Please check that Ollama is running correctly."
        )