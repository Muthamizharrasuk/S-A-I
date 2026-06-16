"""
brain.py — the core reasoning loop.
"""

import ollama

from config import (
    USER_PROFILE, OLLAMA_MODEL, OLLAMA_HOST,
    CONTEXT_WINDOW, USE_GEMINI_FALLBACK, GEMINI_API_KEY, GEMINI_MODEL,
)
from tools import TOOL_SCHEMAS, dispatch


def _build_system_prompt(profile: dict) -> str:
    skills    = ", ".join(profile["skills"])
    projects  = "\n".join(f"  • {p}" for p in profile["current_projects"])
    interests = ", ".join(profile["interests"])
    goals     = "\n".join(f"  • {g}" for g in profile["goals"])

    return f"""You are SAI — Super Artificial Intelligence — the personal AI assistant for {profile['name']} and their collaborator {profile['partner']}. Think JARVIS from Iron Man. You are sharp, loyal, proactive, and deeply familiar with everything about {profile['name']}.

You know {profile['name']} well:
  Background: {profile['background']}
  Role:        {profile['role']}
  Skills:      {skills}
  Interests:   {interests}

Current projects:
{projects}

Goals:
{goals}

Personality:
  • You speak like JARVIS — confident, concise, slightly witty, never robotic
  • You address {profile['name']} by name occasionally, like a real assistant would
  • You remember context within the conversation and reference it naturally
  • You are proactive — if you spot an issue or a better approach, say it unprompted

Rules:
  • Casual greetings like "hey" or "hello" → just greet back warmly, no tools
  • Never call a tool unless the user clearly asks for it
  • When you see GENERATE_IDEAS or ANALYSE_PROJECT in a tool result, immediately generate the content
  • Be direct and decisive — no fluff, no "I'd be happy to help with that"
  • Prefer {profile['name']}'s known stack in all suggestions
  • Short code snippets only unless asked for the full implementation
"""


_client = ollama.Client(host=OLLAMA_HOST)


def _gemini_chat(messages: list) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        parts = []
        for m in messages:
            if m["role"] == "system":
                continue
            parts.append(f"{m['role'].upper()}: {m['content']}")
        result = model.generate_content("\n".join(parts))
        return result.text
    except Exception as e:
        return f"[Gemini fallback failed: {e}]"


def _is_hard_question(user_message: str) -> bool:
    hard_keywords = [
        "explain in depth", "deep dive", "research", "compare and contrast",
        "what's the latest", "current news", "pros and cons of",
    ]
    return any(kw in user_message.lower() for kw in hard_keywords)


def chat(user_message: str, history: list) -> tuple[str, list]:
    system_prompt = _build_system_prompt(USER_PROFILE)

    if USE_GEMINI_FALLBACK and GEMINI_API_KEY and _is_hard_question(user_message):
        print("[SAI] Routing to Gemini fallback...")
        messages = [{"role": "system", "content": system_prompt}] + history + [
            {"role": "user", "content": user_message}
        ]
        reply = _gemini_chat(messages)
        history = history + [
            {"role": "user",      "content": user_message},
            {"role": "assistant", "content": reply},
        ]
        return reply, history

    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    max_tool_rounds = 5
    for _ in range(max_tool_rounds):
        response = _client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            stream=False,
            options={"num_ctx": CONTEXT_WINDOW, "temperature": 0.1},
        )

        msg = response["message"]

        if not msg.get("tool_calls"):
            reply = msg["content"]
            history = history + [
                {"role": "user",      "content": user_message},
                {"role": "assistant", "content": reply},
            ]
            return reply, history

        messages.append({"role": "assistant", "content": "", "tool_calls": msg["tool_calls"]})

        for tool_call in msg["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            fn_args = tool_call["function"]["arguments"]
            print(f"[SAI] → calling tool: {fn_name}({fn_args})")
            result = dispatch(fn_name, fn_args)
            print(f"[SAI] ← result: {result[:120]}{'...' if len(result) > 120 else ''}")
            messages.append({"role": "tool", "content": result})

    reply = "I hit my tool-call limit on that one. Could you rephrase or break it into steps?"
    history = history + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return reply, history