from enum import Enum
from monitor import WindowInfo
from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT, LLM_ENABLED,
    GOAL_KEYWORDS,
    NEUTRAL_TITLE_PATTERNS,
    NEUTRAL_PLATFORM_HOMEPAGES,
    DISTRACTION_PROCESSES,
    DISTRACTION_WINDOW_KEYWORDS,
    PRODUCTIVE_WINDOW_KEYWORDS,
    PRODUCTIVE_PROCESSES,
    BROWSER_PROCESSES,
    NEUTRAL_PROCESSES,
)

_llm_cache: dict = {}
_CACHE_MAX = 500
_groq_client = None

# Keywords dinámicas extraídas del goal por LLM al inicio/cambio de objetivo.
# PRODUCTIVE tiene prioridad: si un título matchea ambas listas, gana PRODUCTIVE.
_dynamic_keywords: dict = {"productive": [], "distraction": []}


def clear_cache():
    _llm_cache.clear()


def set_dynamic_keywords(productive: list, distraction: list):
    """Actualiza las keywords dinámicas del goal. Llamar desde main al cambiar objetivo."""
    _dynamic_keywords["productive"] = [k.lower().strip() for k in productive if k.strip()]
    _dynamic_keywords["distraction"] = [k.lower().strip() for k in distraction if k.strip()]
    print(f"[CLASSIFIER] keywords dinámicas: "
          f"{len(_dynamic_keywords['productive'])} productivas, "
          f"{len(_dynamic_keywords['distraction'])} distractoras")


def _get_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        from config import GROQ_API_KEY
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


class Status(Enum):
    PRODUCTIVE = "PRODUCTIVE"
    DISTRACTION = "DISTRACTION"
    UNKNOWN = "UNKNOWN"


def analyze_goal(goal: str) -> dict | None:
    """
    Analiza el goal: detecta si es ambiguo y extrae keywords productivas/distractoras.
    Retorna dict con: is_ambiguous, reason, suggested, productive_keywords, distraction_keywords.
    Retorna None si LLM no está disponible o falla.
    """
    if not LLM_ENABLED or not GROQ_API_KEY:
        return None

    prompt = (
        f'You are a focus enforcement assistant. Analyze this user goal for a productivity app '
        f'that classifies browser windows as PRODUCTIVE or DISTRACTION.\n\n'
        f'Goal: "{goal}"\n\n'
        f'Respond in EXACTLY this format. Use the SAME LANGUAGE as the goal. No extra text:\n'
        f'AMBIGUOUS: yes|no\n'
        f'REASON: <one line — why ambiguous, or why specific enough>\n'
        f'SUGGESTED: <more specific version if ambiguous; same goal if specific>\n'
        f'PRODUCTIVE: <15-20 comma-separated lowercase keywords: specific tools, platforms, '
        f'technologies, topics, and domains directly related to the goal>\n'
        f'DISTRACTION: <10-12 comma-separated lowercase keywords: entertainment platforms and '
        f'services clearly unrelated to the goal (exclude youtube — it is context-dependent)>'
    )

    try:
        resp = _get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0,
            timeout=GROQ_TIMEOUT * 2,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM] error analizando goal: {e}")
        return None

    result = {
        "is_ambiguous": False,
        "reason": "",
        "suggested": goal,
        "productive_keywords": [],
        "distraction_keywords": [],
    }

    for line in text.splitlines():
        if line.startswith("AMBIGUOUS:"):
            result["is_ambiguous"] = "yes" in line.lower()
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
        elif line.startswith("SUGGESTED:"):
            result["suggested"] = line.split(":", 1)[1].strip()
        elif line.startswith("PRODUCTIVE:"):
            kws = line.split(":", 1)[1].strip()
            result["productive_keywords"] = [k.strip().lower() for k in kws.split(",") if k.strip()]
        elif line.startswith("DISTRACTION:"):
            kws = line.split(":", 1)[1].strip()
            result["distraction_keywords"] = [k.strip().lower() for k in kws.split(",") if k.strip()]

    status = "AMBIGUO" if result["is_ambiguous"] else "especifico"
    print(f"[LLM] goal {status} | "
          f"+{len(result['productive_keywords'])} prod kw | "
          f"+{len(result['distraction_keywords'])} dist kw")
    return result


def _llm_verify(title: str, process: str, goal: str) -> tuple:
    """
    Verificación con LLM: dado el objetivo del usuario, ¿esta ventana es
    productiva, una distracción, o no hay contenido real que juzgar? Solo se
    llama cuando el fast-path de keywords no pudo confirmar que es productivo.

    Siempre retorna (Status, razón) — si el LLM falla, asume DISTRACTION.
    Cache por (título, objetivo): cada título único se llama una sola vez.
    """
    cache_key = (title.lower()[:120], goal.lower()[:80])
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    prompt = (
        f'You are a strict focus enforcement assistant. Answer with ONE word only.\n\n'
        f'User mission: "{goal}"\n'
        f'Active window: "{title}" (process: {process})\n\n'
        f'Classify this window as PRODUCTIVE, DISTRACTION, or UNKNOWN for the user\'s mission.\n\n'
        f'Rules:\n'
        f'- UNKNOWN: the title is NOT real content the user chose to engage with — it is a '
        f'transient system/browser notification, toast, confirmation message, save/print/permission '
        f'dialog, loading state, or an empty/near-empty title. Examples: "Se agregó a Favoritos", '
        f'"Guardando...", "Descarga completa", "Abrir con...", "". Check UNKNOWN FIRST, before '
        f'judging relevance — these have nothing to evaluate, so never call them a DISTRACTION.\n'
        f'- PRODUCTIVE: tutorials, documentation, tools, code editors, or platforms where the '
        f'specific content visible in the title is CLEARLY and DIRECTLY related to the mission. '
        f'YouTube/Reddit count as PRODUCTIVE ONLY if the specific video/post title shows a '
        f'direct, obvious connection to the mission topic — not a vague or indirect one.\n'
        f'- DISTRACTION: entertainment, gaming, social media, shopping, piracy, social events, '
        f'unrelated news, finance apps, or any page with REAL content where the title does not '
        f'clearly connect to the mission. Generic content titles ("Home", "Dashboard", "Inicio") '
        f'= DISTRACTION.\n'
        f'- Among PRODUCTIVE vs DISTRACTION, default to DISTRACTION when the connection is '
        f'ambiguous, weak, or unclear. This rule does NOT apply to UNKNOWN — that is decided '
        f'first, based on whether there is content at all, not on relevance.\n\n'
        f'Reply with exactly one word: PRODUCTIVE, DISTRACTION, or UNKNOWN.'
    )

    try:
        resp = _get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=6,
            temperature=0,
            timeout=GROQ_TIMEOUT,
        )
        word = resp.choices[0].message.content.strip().upper()
    except Exception as e:
        print(f"[LLM] error verificando '{title[:35]}': {e}")
        return Status.DISTRACTION, "[LLM] error — asumiendo distracción"

    if "UNKNOWN" in word:
        result = (Status.UNKNOWN, "[LLM] sin contenido real que evaluar")
        print(f"[LLM] UNKNOWN (no es contenido): '{title[:50]}'")
    elif "PRODUCTIVE" in word:
        result = (Status.PRODUCTIVE, "[LLM] productivo según la misión")
        print(f"[LLM] PRODUCTIVO: '{title[:50]}'")
    else:
        result = (Status.DISTRACTION, "[LLM] no productivo para la misión")

    if len(_llm_cache) < _CACHE_MAX:
        _llm_cache[cache_key] = result
    return result


_BROWSER_SUFFIXES = (
    " - google chrome",
    " - microsoft edge",
    " - mozilla firefox",
    " - firefox",
    " - opera",
    " - brave",
)


def _strip_browser_suffix(title_lower: str) -> str:
    """Elimina el sufijo del browser ('- Google Chrome') para evitar falsos positivos en keywords."""
    for suffix in _BROWSER_SUFFIXES:
        if title_lower.endswith(suffix):
            return title_lower[: -len(suffix)].rstrip(" -–")
    return title_lower


def _keyword_fast_path(title_lower: str, process_lower: str) -> tuple | None:
    """
    Retorna (Status, razón) si alguna keyword/proceso confirma PRODUCTIVE con certeza,
    o None si no hay match — indicando que hay que ir al LLM.
    Usa título sin sufijo de browser para evitar que 'google' matchee '- Google Chrome'.
    """
    if process_lower in PRODUCTIVE_PROCESSES:
        return Status.PRODUCTIVE, f"app productiva: {process_lower}"

    title_clean = _strip_browser_suffix(title_lower)

    for kw in _dynamic_keywords["productive"]:
        if kw in title_clean:
            return Status.PRODUCTIVE, f"[kw] productivo: '{kw}'"

    for kw in GOAL_KEYWORDS:
        if kw.lower() in title_clean:
            return Status.PRODUCTIVE, f"[kw] objetivo: '{kw}'"

    for kw in PRODUCTIVE_WINDOW_KEYWORDS:
        if kw.lower() in title_clean or kw.lower() in process_lower:
            return Status.PRODUCTIVE, f"[kw] app productiva: '{kw}'"

    return None


def _keyword_distraction_fallback(title_lower: str, process_lower: str) -> tuple:
    """Fallback sin LLM: keywords distractoras + browser genérico."""
    for kw in _dynamic_keywords["distraction"]:
        if kw in title_lower:
            return Status.DISTRACTION, f"[kw] distracción: '{kw}'"

    for kw in DISTRACTION_WINDOW_KEYWORDS:
        if kw.lower() in title_lower or kw.lower() in process_lower:
            return Status.DISTRACTION, f"[fallback] distracción: '{kw}'"

    if process_lower in BROWSER_PROCESSES:
        return Status.DISTRACTION, "[fallback] browser sin contenido productivo"

    return Status.UNKNOWN, "sin clasificar"


def classify(window: WindowInfo, goal: str) -> tuple:
    """
    Arquitectura de dos pasos:

    FAST PATH — retorna PRODUCTIVE/UNKNOWN directamente sin LLM:
      0. NEUTRAL_PROCESSES      → UNKNOWN (proceso de sistema/shell, nunca se evalúa)
      1. DISTRACTION_PROCESSES  → DISTRACTION inmediato (sin verificar)
      2. NEUTRAL_TITLE_PATTERNS → UNKNOWN (tránsito, no enforcement)
      3. Keywords productivas (dinámicas + estáticas) → PRODUCTIVE

    VERIFY PATH — todo lo que no es claramente productivo pasa por LLM:
      4. LLM binario (PRODUCTIVE / DISTRACTION) cruzado con la misión del usuario
         Cache por (título, objetivo): cada título único se llama una sola vez.

    FALLBACK (sin LLM disponible):
      5. Keywords distractoras + browser genérico
    """
    title_lower   = window.title.lower()
    process_lower = window.process_name.lower()

    # 0. Procesos de sistema/shell (explorer.exe, etc.) — nunca se evalúan, nunca se cierran.
    if process_lower in NEUTRAL_PROCESSES:
        return Status.UNKNOWN, "proceso de sistema — no se evalúa"

    # 1. Procesos bloqueados: Discord, Steam, Spotify — siempre DISTRACTION, sin LLM
    for proc in DISTRACTION_PROCESSES:
        if proc in process_lower:
            return Status.DISTRACTION, f"proceso bloqueado: {proc}"

    # 2. Páginas de tránsito (substring): nueva pestaña, Google SERP → UNKNOWN
    for pat in NEUTRAL_TITLE_PATTERNS:
        if pat in title_lower:
            return Status.UNKNOWN, "página de tránsito — esperando destino"

    # 2b. Homepages de plataformas sin contenido (exact match).
    #     "YouTube - Google Chrome" → tránsito (aún no eligió qué ver).
    #     "Tutorial - YouTube - Google Chrome" → NO entra acá, sigue al fast-path.
    if title_lower in NEUTRAL_PLATFORM_HOMEPAGES:
        return Status.UNKNOWN, "plataforma sin contenido — esperando destino"

    # 3. Fast path productivo: keywords confirman con certeza → no necesita LLM
    productive = _keyword_fast_path(title_lower, process_lower)
    if productive:
        return productive

    # 4. Verify path: no es claramente productivo → LLM decide con la misión como contexto
    if LLM_ENABLED and GROQ_API_KEY:
        return _llm_verify(window.title, window.process_name, goal)

    # 5. Sin LLM: fallback a keywords distractoras
    return _keyword_distraction_fallback(title_lower, process_lower)
