"""
brain.py — the core reasoning loop.

Flow (every turn):
  1. Build messages: system prompt (with your profile) + conversation history
  2. Send to Ollama with tool schemas (stream=False for tool calls)
  3. If the model returns tool_calls → dispatch each tool, append results, call again
  4. Return the final text response
  5. (Optional) if USE_GEMINI_FALLBACK and the query is flagged as hard, route there instead
"""

import json
import ollama

from config import (
    USER_PROFILE, OLLAMA_MODEL, OLLAMA_HOST,
    CONTEXT_WINDOW, USE_GEMINI_FALLBACK, GEMINI_API_KEY, GEMINI_MODEL,
)
from tools import TOOL_SCHEMAS, dispatch

# ─────────────────────────────────────────────
#  Build the system prompt from the user's profile
# ─────────────────────────────────────────────
def _build_system_prompt(profile: dict) -> str:
    skills    = ", ".join(profile["skills"])
    projects  = "\n".join(f"  • {p}" for p in profile["current_projects"])
    interests = ", ".join(profile["interests"])
    goals     = "\n".join(f"  • {g}" for g in profile["goals"])

    return f"""You are SAI — Super Artificial Intelligence — a personal dev assistant for {profile['name']} and their collaborator {profile['partner']}.

You know {profile['name']} well:
  Role:      {profile['role']}
  Skills:    {skills}
  Interests: {interests}

Current projects:
{projects}

Goals:
{goals}

Your job:
  • Help with active projects — bugs, architecture, code reviews, ideas
  • Generate creative, realistic project ideas tuned to their stack and interests
  • Set reminders and save notes when asked
  • Answer technical questions clearly and concisely
  • When you see a GENERATE_IDEAS or ANALYSE_PROJECT signal from a tool result,
    immediately generate the content — don't ask for more info.

Rules:
  • Be direct and practical. No fluff.
  • Keep code snippets short unless the user asks for full implementations.
  • Prefer their known stack (Python, FastAPI, React, Supabase) in suggestions.
  • Use tools when appropriate — don't describe what you *would* do, just do it.
  • Temperature is low — be decisive, not wishy-washy.
"""


# ─────────────────────────────────────────────
#  Ollama client
# ─────────────────────────────────────────────
_client = ollama.Client(host=OLLAMA_HOST)


# ─────────────────────────────────────────────
#  Gemini fallback (optional)
# ─────────────────────────────────────────────
def _gemini_chat(messages: list) -> str:
    """Route to Gemini when the local SLM isn't enough."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        # Convert messages to Gemini format (skip system — already in history)
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
    """
    Simple heuristic to decide whether to escalate to Gemini.
    You can make this smarter over time.
    """
    hard_keywords = [
        "explain in depth", "deep dive", "research", "compare and contrast",
        "what's the latest", "current news", "pros and cons of",
    ]
    lower = user_message.lower()
    return any(kw in lower for kw in hard_keywords)


# ─────────────────────────────────────────────
#  Core chat function — call this from main.py
# ─────────────────────────────────────────────
def chat(user_message: str, history: list) -> tuple[str, list]:
    """
    Args:
        user_message:  the latest thing the user typed
        history:       list of previous {"role": ..., "content": ...} dicts

    Returns:
        (assistant_reply_text, updated_history)
    """
    system_prompt = _build_system_prompt(USER_PROFILE)

    # Optionally escalate to Gemini for hard questions
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

    # ── Build message list for Ollama ──
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    max_tool_rounds = 5  # prevent infinite loops
    for _ in range(max_tool_rounds):
        response = _client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            stream=False,
            options={"num_ctx": CONTEXT_WINDOW, "temperature": 0.1},
        )

        msg = response["message"]

        # ── No tool call → final text response ──
        if not msg.get("tool_calls"):
            reply = msg["content"]
            # Update history (exclude system prompt — it's rebuilt each turn)
            history = history + [
                {"role": "user",      "content": user_message},
                {"role": "assistant", "content": reply},
            ]
            return reply, history

        # ── Model wants to call one or more tools ──
        messages.append({"role": "assistant", "content": "", "tool_calls": msg["tool_calls"]})

        for tool_call in msg["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            fn_args = tool_call["function"]["arguments"]

            print(f"[SAI] → calling tool: {fn_name}({fn_args})")
            result = dispatch(fn_name, fn_args)
            print(f"[SAI] ← result: {result[:120]}{'...' if len(result) > 120 else ''}")

            messages.append({
                "role":    "tool",
                "content": result,
            })

    # Fallback if max rounds hit
    reply = "I hit my tool-call limit on that one. Could you rephrase or break it into steps?"
    history = history + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return reply, history