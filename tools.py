"""
tools.py — every action SAI can take.
"""

import json
import datetime
import subprocess
from pathlib import Path

import dateparser

DATA_DIR       = Path.home() / ".sai"
DATA_DIR.mkdir(exist_ok=True)
REMINDERS_FILE = DATA_DIR / "reminders.json"
NOTES_FILE     = DATA_DIR / "notes.json"
IDEAS_FILE     = DATA_DIR / "project_ideas.json"


# ── helpers ──────────────────────────────────
def _load(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text())
    return []

def _save(path: Path, data: list):
    path.write_text(json.dumps(data, indent=2))


# ── tools ─────────────────────────────────────

def get_current_datetime() -> str:
    return datetime.datetime.now().strftime("Today is %A, %B %d %Y. Current time: %I:%M %p.")


def set_reminder(task: str, when: str) -> str:
    parsed = dateparser.parse(when)
    script = f'tell application "Reminders" to make new reminder with properties {{name:"{task}"}}'
    subprocess.run(["osascript", "-e", script])
    due = parsed.strftime("%b %d at %I:%M %p") if parsed else when
    # also log locally
    reminders = _load(REMINDERS_FILE)
    reminders.append({
        "id":      len(reminders) + 1,
        "task":    task,
        "when":    when,
        "created": datetime.datetime.now().isoformat(),
        "done":    False,
    })
    _save(REMINDERS_FILE, reminders)
    return f"✅ Added '{task}' to Reminders app (due: {due})"


def list_reminders() -> str:
    reminders = [r for r in _load(REMINDERS_FILE) if not r["done"]]
    if not reminders:
        return "No pending reminders."
    lines = [f"  [{r['id']}] {r['task']} — {r['when']}" for r in reminders]
    return "Pending reminders:\n" + "\n".join(lines)


def complete_reminder(reminder_id: int) -> str:
    reminders = _load(REMINDERS_FILE)
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
            _save(REMINDERS_FILE, reminders)
            return f"✅ Reminder {reminder_id} marked done."
    return f"No reminder with ID {reminder_id}."


def add_calendar_event(title: str, when: str) -> str:
    parsed = dateparser.parse(when)
    if not parsed:
        return f"Couldn't parse '{when}' — try something like 'June 20 at 3pm'"
    apple_date = parsed.strftime("%B %d, %Y at %I:%M:%S %p")
    script = f'''
tell application "Calendar"
    tell calendar "Home"
        make new event with properties {{summary:"{title}", start date:date "{apple_date}"}}
    end tell
end tell
'''
    subprocess.run(["osascript", "-e", script])
    return f"✅ Added '{title}' to Calendar on {parsed.strftime('%b %d at %I:%M %p')}"


def save_note(title: str, content: str) -> str:
    notes = _load(NOTES_FILE)
    entry = {
        "id":      len(notes) + 1,
        "title":   title,
        "content": content,
        "saved":   datetime.datetime.now().isoformat(),
    }
    notes.append(entry)
    _save(NOTES_FILE, notes)
    return f"📝 Note saved: '{title}' (ID {entry['id']})"


def list_notes() -> str:
    notes = _load(NOTES_FILE)
    if not notes:
        return "No notes saved yet."
    lines = [f"  [{n['id']}] {n['title']} — {n['saved'][:10]}" for n in notes]
    return "Saved notes:\n" + "\n".join(lines)


def read_note(note_id: int) -> str:
    notes = _load(NOTES_FILE)
    for n in notes:
        if n["id"] == note_id:
            return f"📄 [{n['title']}]\n{n['content']}"
    return f"No note with ID {note_id}."


def generate_project_ideas(domain: str, difficulty: str = "medium", count: int = 3) -> str:
    ideas_log = _load(IDEAS_FILE)
    ideas_log.append({
        "domain":     domain,
        "difficulty": difficulty,
        "count":      count,
        "requested":  datetime.datetime.now().isoformat(),
    })
    _save(IDEAS_FILE, ideas_log)
    return f"GENERATE_IDEAS|domain={domain}|difficulty={difficulty}|count={count}"


def analyse_project(project_name: str, description: str) -> str:
    return f"ANALYSE_PROJECT|name={project_name}|description={description}"


def web_search(query: str) -> str:
    return (
        f"[Web search not connected yet. Query: '{query}']\n"
        "Tip: connect SearXNG or Tavily to enable real search."
    )


# ── dispatcher ───────────────────────────────
TOOL_FUNCTIONS = {
    "get_current_datetime":   lambda args: get_current_datetime(),
    "set_reminder":           lambda args: set_reminder(**args),
    "list_reminders":         lambda args: list_reminders(),
    "complete_reminder":      lambda args: complete_reminder(**args),
    "add_calendar_event":     lambda args: add_calendar_event(**args),
    "save_note":              lambda args: save_note(**args),
    "list_notes":             lambda args: list_notes(),
    "read_note":              lambda args: read_note(**args),
    "generate_project_ideas": lambda args: generate_project_ideas(**args),
    "analyse_project":        lambda args: analyse_project(**args),
    "web_search":             lambda args: web_search(**args),
}

def dispatch(tool_name: str, args: dict) -> str:
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn:
        try:
            return fn(args)
        except Exception as e:
            return f"Tool error in '{tool_name}': {e}"
    return f"Unknown tool: '{tool_name}'"


# ── schemas ──────────────────────────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Add a reminder to the Apple Reminders app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What to remember."},
                    "when": {"type": "string", "description": "When — e.g. 'tomorrow at 9am'."},
                },
                "required": ["task", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all pending reminders.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_reminder",
            "description": "Mark a reminder as done by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "integer"},
                },
                "required": ["reminder_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_calendar_event",
            "description": "Add an event to the Apple Calendar app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title."},
                    "when":  {"type": "string", "description": "When — e.g. 'June 20 at 3pm'."},
                },
                "required": ["title", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a note or idea for later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":   {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List all saved notes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read a saved note by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "integer"},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_project_ideas",
            "description": "Generate project ideas for a given domain or tech stack. Use when the user asks for ideas or what to build next.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain":     {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["beginner", "medium", "advanced"]},
                    "count":      {"type": "integer"},
                },
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyse_project",
            "description": "Analyse a project and give feedback, issues, and next steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "description":  {"type": "string"},
                },
                "required": ["project_name", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]