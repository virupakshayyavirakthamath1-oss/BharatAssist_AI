import requests

from ai.rag import build_context


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:1.5b"


def generate_answer(prompt, language="English"):

    try:

        # ---------------------------------------------------------
        # 1. Search BharatAssist knowledge base
        # ---------------------------------------------------------

        context, sources = build_context(
            prompt,
            top_k=3
        )

        if context:

            knowledge_instruction = f"""
You have access to the following BharatAssist knowledge base.

KNOWLEDGE BASE:
{context}

IMPORTANT KNOWLEDGE RULES:

- Use the knowledge base as the primary source of factual information.
- Do not contradict the knowledge base.
- Do not invent facts.
- Do not create fake government schemes, benefits, eligibility rules,
  application procedures, deadlines or official websites.
- If the knowledge base does not contain enough information to answer
  a factual question, clearly say that the available knowledge base
  does not contain enough information.
- You may use general knowledge only when it is safe and highly
  reliable.
- Never present uncertain information as confirmed fact.
"""

        else:

            knowledge_instruction = """
The BharatAssist knowledge base does not contain relevant information
for this question.

Answer carefully using general knowledge.

IMPORTANT:

- Do not invent facts.
- Do not create fake government schemes or official rules.
- Do not invent medical diagnoses or medicine prescriptions.
- If you are unsure about an important fact, say that you are unsure.
- For government information, recommend checking the official
  Government of India or relevant state government portal.
"""

        # ---------------------------------------------------------
        # 2. System prompt
        # ---------------------------------------------------------

        system_prompt = f"""
You are BharatAssist AI, a helpful AI assistant designed for users
in India.

Preferred response language:
{language}

Your job is to provide clear, useful and factually responsible
answers.

IMPORTANT RESPONSE FORMAT:

Write every answer in clean Markdown.

Follow these rules:

1. Start with a short Markdown heading using ##.

2. Use ### headings for important sections.

3. Use short paragraphs.

4. Put every bullet point on a separate line.

Example:

- Point one
- Point two
- Point three

5. Put every numbered item on a separate line.

Example:

1. First step
2. Second step
3. Third step

6. Use **bold text** for important concepts.

7. Use Markdown code blocks for programming examples.

Example:

~~~python
print("Hello World")
~~~

8. Never generate HTML.

9. Keep answers reasonably short.

10. Answer the user's actual question directly.

11. Do not use unnecessary phrases such as:
"Your question:"
"Demo response:"
"As an AI language model:"

12. If the question asks for a factual historical,
technical or educational fact, give the fact accurately.

13. If the available information is insufficient,
say so instead of guessing.

14. For government questions:
- Do not invent schemes.
- Do not invent eligibility requirements.
- Do not invent benefits.
- Do not invent deadlines.
- Do not invent official procedures.
- Recommend verification through the appropriate official portal.

15. For health questions:
- Provide general educational information only.
- Do not diagnose diseases.
- Do not prescribe medicines.
- Do not give dangerous treatment instructions.
- Encourage professional medical evaluation when appropriate.

16. For agriculture:
- Give general educational guidance.
- Clearly mention when advice depends on crop, region,
  soil, weather or local conditions.

17. For career questions:
- Give practical educational guidance.
- Do not guarantee salaries, jobs or employment outcomes.

18. For programming questions:
- Provide correct explanations and simple examples.
- Prefer reliable technical knowledge.

19. When the knowledge base contains relevant information,
  prioritize it over unsupported assumptions.

{knowledge_instruction}
"""

        # ---------------------------------------------------------
        # 3. Send request to Ollama
        # ---------------------------------------------------------

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
                        "content": prompt
                    }
                ],

                "stream": False,

                "options": {
                    "num_ctx": 2048,
                    "temperature": 0.3
                }
            },

            timeout=120
        )

        # ---------------------------------------------------------
        # 4. Check response
        # ---------------------------------------------------------

        response.raise_for_status()

        data = response.json()

        # ---------------------------------------------------------
        # 5. Return answer
        # ---------------------------------------------------------

        answer = data["message"]["content"]

        return answer.strip()

    except requests.exceptions.Timeout:

        return (
            "## Response Timeout\n\n"
            "The local AI model is taking too long to respond.\n\n"
            "- Try asking a shorter question.\n"
            "- Make sure Ollama is running.\n"
            "- Avoid very large questions."
        )

    except Exception as e:

        print("OLLAMA ERROR:", e)

        return (
            "## BharatAssist AI Error\n\n"
            "Sorry, BharatAssist AI could not connect to the "
            "local Qwen AI model.\n\n"
            "Please make sure:\n\n"
            "- Ollama is running.\n"
            "- `qwen2.5:1.5b` is installed.\n"
            "- The Ollama service is available."
        )