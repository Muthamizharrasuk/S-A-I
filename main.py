import sys
from config import USER_PROFILE, OLLAMA_MODEL
from brain import chat

BANNER = f"""
╔══════════════════════════════════════════════╗
║   SAI — Super Artificial Intelligence        ║
║   Local assistant for {USER_PROFILE['name']:<22} ║
║   Model: {OLLAMA_MODEL:<36}║
╚══════════════════════════════════════════════╝
Type your message and press Enter.
Commands:  /clear  reset conversation
           /exit   quit
           /help   show example prompts
"""

HELP_TEXT = """
Try saying:
  "Give me 3 project ideas using FastAPI and AI"
  "Remind me to push my Collegable fix tomorrow at 10am"
  "Add a calendar event — SAI demo on June 20 at 2pm"
  "What are my pending reminders?"
  "Save a note: add rate limiting to the API"
  "Analyse my Collegable project"
  "What should I work on next?"
"""

def main():
    print(BANNER)
    history = []

    while True:
        try:
            user_input = input(f"{USER_PROFILE['name']}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSAI: See you later.")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            print("SAI: Shutting down. Bye!")
            break

        if user_input.lower() == "/clear":
            history = []
            print("SAI: Conversation cleared.\n")
            continue

        if user_input.lower() == "/help":
            print(HELP_TEXT)
            continue

        print("\nSAI: ", end="", flush=True)
        try:
            reply, history = chat(user_input, history)
            print(reply + "\n")
        except Exception as e:
            print(f"\n[Error] {e}")
            print("→ Is Ollama running? Try: ollama serve")
            print(f"→ Is the model pulled? Try: ollama pull {OLLAMA_MODEL}\n")

if __name__ == "__main__":
    main()