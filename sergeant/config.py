import os as _os

def _load_dotenv():
    env_file = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), ".env")
    if not _os.path.exists(env_file):
        return
    with open(env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

_load_dotenv()

CURRENT_GOAL = _os.environ.get("CURRENT_GOAL", "estudiar para una entrevista que tengo mañana")

# ── Groq LLM classification ──────────────────────────────────────────────────
GROQ_API_KEY = _os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"
GROQ_TIMEOUT = 3
LLM_ENABLED  = bool(GROQ_API_KEY)

GOAL_KEYWORDS = [
    "entrevista", "interview",
    "python",
    "python tutorial", "python docs", "python course", "learn python", "python interview",
    "algoritmo", "algorithm",
    "leetcode", "data structure", "estructura de datos", "sorting",
    "linked list", "binary tree", "binary search", "recursion",
    "sql tutorial", "system design",
    "big o", "complexity", "stack overflow", "queue", "tree traversal",
    "graph algorithm",
    "curso", "aprender", "study guide", "study notes", "cheat sheet",
    "notion", "obsidian", "anki", "flashcard",
    "docs.python", "developer.mozilla", "w3schools", "geeksforgeeks",
]

# Páginas de tránsito (substring): el usuario no llegó a ningún lado todavía → UNKNOWN, nunca se cierra.
NEUTRAL_TITLE_PATTERNS = [
    "nueva pestaña",        # Chrome new tab (es)
    "new tab",              # Chrome new tab (en)
    "buscar con google",    # Google SERP (es) — "python - Buscar con Google"
    "google search",        # Google SERP (en)
    # NO incluir "- google" suelto: matchea "- Google Chrome" (sufijo de TODOS los títulos de Chrome)
]

# Homepages de plataformas sin contenido (exact match).
# "YouTube - Google Chrome" → tránsito (el user aún no eligió qué ver).
# "Tutorial de Python - YouTube - Google Chrome" → NO es tránsito (tiene contenido).
# Diferencia con NEUTRAL_TITLE_PATTERNS: estos usan igualdad exacta, no substring,
# para no bloquear títulos que contienen el nombre de la plataforma pero sí tienen contenido.
NEUTRAL_PLATFORM_HOMEPAGES = frozenset({
    "youtube",
    "youtube - google chrome",
    "instagram",
    "instagram - google chrome",
    "reddit",
    "reddit - google chrome",
    "reddit: the front page of the internet",
    "reddit: the front page of the internet - google chrome",
    "twitch",
    "twitch - google chrome",
    "x",
    "x - google chrome",
    "twitter",
    "twitter - google chrome",
})

DISTRACTION_PROCESSES = [
    "discord.exe", "steam.exe", "epicgameslauncher.exe",
    "leagueclient.exe", "valorant.exe", "spotify.exe",
]

DISTRACTION_WINDOW_KEYWORDS = [
    "youtube", "twitch", "netflix", "twitter", "x.com",
    "instagram", "tiktok", "reddit", "facebook", "whatsapp",
    "telegram", "9gag", "meme", "juego", "game",
]

PRODUCTIVE_WINDOW_KEYWORDS = [
    "visual studio", "vscode", "pycharm", "intellij", "cursor",
    "jupyter", "terminal", "cmd", "powershell", "notepad",
    "word", "excel", "google docs", "notion", "obsidian",
    "stackoverflow", "github", "docs.python", "mdn",
    "sergeant",  # la propia app de monitoreo nunca es distracción
]

DEMO_MODE = True

GRACE_PERIOD_SECONDS    = 8   if DEMO_MODE else 30
COUNTDOWN_TRIGGER_SECS  = 16  if DEMO_MODE else 60
COUNTDOWN_DURATION_SECS = 20  if DEMO_MODE else 60
TWEET_THRESHOLD_SECONDS = 30  if DEMO_MODE else 300

TWITTER_API_KEY = ""
TWITTER_API_SECRET = ""
TWITTER_ACCESS_TOKEN = ""
TWITTER_ACCESS_SECRET = ""
TWITTER_ENABLED = False

PRODUCTIVE_PROCESSES = {
    "code.exe", "windowsterminal.exe", "python3.12.exe", "python.exe",
    "pycharm64.exe", "notepad++.exe", "obsidian.exe", "notion.exe",
}

BROWSER_PROCESSES = {"chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "brave.exe"}

DB_PATH = _os.path.join(_os.path.dirname(__file__), "sergeant.db")
POLL_INTERVAL_SECONDS = 2 if DEMO_MODE else 5
IDLE_THRESHOLD_SECONDS = 30 if DEMO_MODE else 120

WEBCAM_ENABLED = _os.environ.get("WEBCAM_ENABLED", "false").lower() == "true"
