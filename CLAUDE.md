# SERGEANT — Contexto del proyecto para Claude

## Qué es esto

App de productividad estilo **Black Mirror** construida para un **ANTIhackaton**. Corre en background y vigila al usuario: si detecta distracciones, muestra avisos, cierra pestañas de Chrome, dispara una cuenta regresiva con fake-sys32-deletion, y opcionalmente tweetea la infracción en tiempo real.

Estética: terminal militar negro/verde, fuente Courier New, sin adornos.

## Cómo correrlo

```bat
# Desde E:\Proyects\sergeant\
DEMO.bat          # launcher con menú
python sergeant\main.py                   # arranque normal (pide contrato)
python sergeant\main.py --skip-contract   # saltea el contrato (testing)
```

**DEMO_MODE = True** en `config.py` — todos los timers están acelerados para el hackathon.

## Stack

- **Python 3.12** + **tkinter** (UI)
- **pywin32** (`win32gui`, `win32process`, `win32api`, `win32con`) — detección de ventanas y envío de teclas
- **psutil** — info de procesos
- **SQLite** (`sergeant/sergeant.db`) — time tracking
- **tweepy** — Twitter (mock por defecto, `TWITTER_ENABLED = False`)
- **winsound** — alertas de audio
- **Groq API** (llama-3.1-8b-instant) — clasificador semántico LLM, gratuito, ~100ms. Usa el **SDK oficial `groq`** (`pip install groq`). IMPORTANTE: no usar urllib directo — Cloudflare de Groq lo bloquea con error 1010.
- Windows 10, multi-monitor (se usa `ctypes.windll.user32.GetSystemMetrics(0)` para obtener el ancho del monitor primario, NO `winfo_screenwidth()` que retorna el ancho virtual total)

## Arquitectura de módulos

```
sergeant/
├── main.py          # loop principal, orquesta todo, state global
├── config.py        # todos los parámetros, timers, API keys (carga .env automáticamente)
├── monitor.py       # get_active_window() → WindowInfo(title, process_name, pid)
├── classifier.py    # classify(window, goal) → (Status, razón). LLM + keyword fallback.
├── enforcer.py      # warn_before_close(), close_window(), trigger_countdown(), dismiss()
├── tracker.py       # on_window_change(), get_today_calendar(), format_metrics_table()
├── db.py            # SQLite: sessions + events tables
├── social.py        # tweet_distraction() — mock si TWITTER_ENABLED=False
└── ui/
    ├── contract.py  # ventana de contrato (primer arranque)
    ├── boot.py      # animación de boot estilo terminal
    ├── dashboard.py # dashboard (4 tabs: MONITOR + HISTORIAL + MISION + TWITTER)
    ├── toast.py     # notificación toast en esquina (aviso antes de cerrar)
    └── countdown.py # cuenta regresiva con fake sys32 deletion (pause/resume)
```

## Flujo de ejecución

```
main() → init_db() → close_open_sessions() → show_contract() → show_boot() → _start_monitoring()
                                                                                    │
                                                                       launch_dashboard(get_state_fn, apply_goal_fn) [thread]
                                                                       _refresh_metrics() [thread]
                                                                       while True: get_active_window()
                                                                                   classify(window, state["goal"])
                                                                                   _update_state()
```

`_update_state()` en `main.py` maneja la máquina de estados con **dos modos de enforcement**:

**Modo CLOSE (infracciones 1-3, `_infraction_count < CLOSE_LIMIT=3`):**
1. **DISTRACTION detectada** → iniciar timer
2. **A los max(0, GRACE-WARN)s** → `warn_before_close()` (toast + sonido)
3. **Al expirar el toast** → `close_window()` + `_infraction_count += 1`
4. **A los TWEET_THRESHOLD_SECONDS** → `tweet_distraction()`
5. **Usuario retoma trabajo** → `cancel_warning()` o `dismiss()` según estado

**Modo COUNTDOWN (a partir de infracción 4, `_infraction_count >= CLOSE_LIMIT`):**
1. Primera vez en modo countdown → `trigger_countdown()` + `_countdown_persistent = True`
2. Distracción continua → `resume_countdown()` (reanuda si estaba pausado)
3. **Usuario retoma trabajo** → `pause_countdown()` (NO dismiss — el timer persiste)
4. Vuelve a distraerse → `resume_countdown()` (continúa desde donde quedó)
5. `_countdown_persistent` nunca se resetea en la sesión (solo reinicar la app)
6. No se cierran más ventanas en este modo

## Config (config.py)

```python
CURRENT_GOAL = "estudiar para una entrevista que tengo mañana"  # goal inicial
DEMO_MODE = True

# Timers con DEMO_MODE=True:
GRACE_PERIOD_SECONDS    = 8   # (30 en prod) — tiempo antes de cerrar app
COUNTDOWN_DURATION_SECS = 20  # (60 en prod) — duración del countdown
TWEET_THRESHOLD_SECONDS = 30  # (300 en prod) — cuándo tweetea

POLL_INTERVAL_SECONDS = 2     # frecuencia del loop de monitoreo (demo)
CLOSE_LIMIT = 3               # en main.py — infracciones antes de modo countdown

# Groq LLM (API key se carga desde .env automáticamente)
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL    = "llama-3.1-8b-instant"
GROQ_TIMEOUT  = 3
LLM_ENABLED   = bool(GROQ_API_KEY)
```

**Archivo .env** (raíz del proyecto, ignorado en git):
```
GROQ_API_KEY=gsk_...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_ENABLED=true
```

## Classifier — LLM + keyword fallback

El clasificador usa **Groq (llama-3.1-8b-instant)** como primera línea. El objetivo del usuario se pasa como contexto dinámico (`state["goal"]`, no CURRENT_GOAL hardcodeado).

**Orden de prioridad:**
1. Proceso en `DISTRACTION_PROCESSES` → DISTRACTION (sin LLM)
2. Proceso en `PRODUCTIVE_PROCESSES` → PRODUCTIVE (sin LLM)
3. `NEUTRAL_TITLE_PATTERNS` → UNKNOWN (nueva pestaña, SERP de Google — no enforcement)
4. **LLM (Groq)** → clasifica semánticamente usando el goal como contexto
5. Fallback a keywords si LLM falla/timeout/UNKNOWN:
   - `GOAL_KEYWORDS` en título → PRODUCTIVE (va ANTES que distraction keywords)
   - `PRODUCTIVE_WINDOW_KEYWORDS` → PRODUCTIVE
   - `DISTRACTION_WINDOW_KEYWORDS` → DISTRACTION
   - Browser sin match → DISTRACTION

`clear_cache()` en classifier.py vacía el cache LLM (se llama al cambiar el goal con APPLY).

**Si LLM no está disponible**: fallback automático a keywords, app sigue funcionando.

## Dashboard (ui/dashboard.py)

Cuatro tabs custom (tkinter buttons, no ttk.Notebook):

**Tab MONITOR:**
- THREAT bar + DEFCON 1-5
- Estado grande: `● WORKING` / `⚠ DISTRACCION` con fondo rojo
- Info grid: objetivo, ventana, proceso, razón, tiempo productivo, **infracciones (X/3)**
- Métricas del día, tweet banner, últimas 5 sesiones

**Tab HISTORIAL:**
- Timeline vertical (Canvas): bloques coloreados por hora
- Hover tooltip con info de la sesión
- Filtros: excluye sesiones < 10s, excluye SERGEANT

**Tab MISION:**
- Objetivo actual (display)
- Campo de texto + botón APPLY para cambiar goal en caliente
  - APPLY llama `apply_goal_fn(new_goal)` → actualiza `state["goal"]` + `clear_cache()`
- Estado de sesión: "infracciones X/3" o "MODO COUNTDOWN ACTIVO"

**Tab TWITTER:**
- Campos API Key / Secret / Access Token / Access Secret (enmascarados, botón "ver")
- GUARDAR Y ACTIVAR: escribe al .env + actualiza os.environ
- desactivar: limpia keys del .env

`launch_dashboard(get_state_fn, apply_goal_fn=None)` — pasa ambas funciones.

## Countdown (ui/countdown.py)

API:
- `show_countdown(seconds, distraction, on_close_cb)` — inicia (si no hay uno activo)
- `pause_countdown()` — pausa el timer, muestra "PAUSADO" en UI
- `resume_countdown()` — reanuda desde donde estaba
- `dismiss_countdown()` — cancela (muestra secuencia ABORTADO y destruye)

Estados del tick loop:
- `_countdown_running=True, _countdown_paused=False` → contando
- `_countdown_running=True, _countdown_paused=True` → pausado (UI visible, timer detenido)
- `_countdown_running=False` → triggerea _abort_sequence() → "ABORTADO" → destroy

## Enforcer (enforcer.py)

- **Browsers** (chrome, firefox, edge, opera, brave): `_find_hwnd_for_pid()` + Ctrl+W
- **Otros procesos**: `psutil.Process(pid).terminate()`
- `cancel_warning(pid)` → cancela toast sin cerrar
- `dismiss(warned_pid, countdown_was_active)` → cancela countdown+toast (NO usar en modo countdown persistente)

## Toast (ui/toast.py)

Flag-based dismiss: `dismiss_toast(key)` setea `dismissed[0]=True`, el `tick()` interno destruye desde el thread correcto. Evita `Tcl_AsyncDelete`.

**Arquitectura actual (post-fix multi-Tk):** toast y countdown usan `tk.Toplevel(_root)` en el thread del dashboard, NO `tk.Tk()` en threads separados. Requiere que `dashboard._build_ui` llame `toast.set_root(root)` y `countdown.set_root(root)` después de crear el `Tk()` raíz. Todo scheduling vía `_root.after()`.

## Problemas conocidos y sus fixes

| Problema | Fix aplicado |
|----------|-------------|
| Chrome cierra aunque user retomó trabajo | `_do_close()` verifica `state["status"] == "DISTRACTION"` antes de ejecutar |
| `Tcl_AsyncDelete` crash al cancelar toast | `dismiss_toast` setea flag; `tick()` destruye desde el thread correcto |
| App aparece en monitor 2 | `ctypes.windll.user32.GetSystemMetrics(0)` en dashboard, toast, countdown, boot y contract |
| DEMO.bat caracteres garbled | `chcp 65001` al inicio del bat, em-dash reemplazado por `--` |
| Dashboard oculto detrás de otras ventanas | `root.attributes("-topmost", True)` |
| Toast timing incorrecto en DEMO (grace=8 < warn=10) | `warn_at = max(0, GRACE-WARN)` + `actual_warn = min(WARN, GRACE-elapsed)` |
| Countdown "ABORTADO" aparecía al expirar el timer | Flujos separados: `_expire_sequence()` y `_abort_sequence()` |
| `winfo_exists()` lanza TclError en countdown | `_window_alive()` con try/except |
| Toast dict `_active` sin lock en multi-thread | `threading.Lock()` en show/dismiss |
| Ctrl+W iba al dashboard en lugar de Chrome | `_find_hwnd_for_pid()` busca HWND por PID antes de enviar Ctrl+W |
| Nueva pestaña de distracción no se avisa | `_warned_title` resetea ciclo warn+close cuando cambia el título dentro de una distracción continua |
| Tiempo se acumula con app cerrada | `close_open_sessions()` al arrancar cierra sesiones huérfanas (end_time = start_time) |
| Hover HISTORIAL muestra proceso incorrecto | `reversed(_blocks)` para match del bloque visualmente encima |
| Browser legítimo clasificado como distracción | LLM semántico + NEUTRAL_TITLE_PATTERNS para páginas de tránsito |
| Loop principal muere silenciosamente | try/except con circuit-breaker + reset tras pausa de 5s |
| `elapsed` con `.seconds` incorrecto para >24h | `.total_seconds()` |
| SQLite `database is locked` | `timeout=5` + `PRAGMA journal_mode=WAL` |
| Groq HTTP 403 (Cloudflare bloquea urllib) | SDK oficial `groq` usa httpx con headers correctos |
| Countdown no se pausa al volver productivo (modo 4ta infracción) | `pause_countdown()` en vez de `dismiss()` cuando `_countdown_persistent=True` |
| Goal hardcodeado no se podía cambiar en runtime | `state["goal"]` dinámico + APPLY en tab MISIÓN + `clear_cache()` |
| Toast detectada como PRODUCTIVE → cancela su propio aviso (loop infinito) | `is_sergeant_self` excluye `python3.12.exe` con title `"tk"` o `""` (Tkinter default) |
| **`tcl86t.dll` assertion crash (0x80000003) tras 2-3 infracciones** | Múltiples `tk.Tk()` en múltiples threads viola invariantes de Tcl 8.6. Fix: toast y countdown usan `Toplevel(_root)` en el thread del dashboard. `dashboard._build_ui` registra el root con `toast.set_root(root)` + `countdown.set_root(root)` |
| `_do_close()` no resetea ciclo de aviso post-cierre | Después de cerrar pestaña, `_warned=True` bloqueaba nuevas advertencias. Fix: `_do_close` resetea `_warned`, `_warned_pid`, `_warned_title`, `_distracted_start=None` |
| `_Tee` stdout pipe break mata el loop principal | Si la consola se cierra, `write()` propagaba BrokenPipeError y mataba el proceso. Fix: try/except en `_Tee.write()` y `_Tee.flush()` |
| Ctrl+W enviado a ventana incorrecta (crash o cierre equivocado) | `_close_browser_tab` verifica `GetForegroundWindow() == hwnd` antes de enviar keys; si falla, termina el proceso directamente |
| Crash al cerrar pestaña manualmente antes de que SERGEANT actúe | `_do_close` corría en el thread de Tkinter (via `on_expire` del toast): `close_window` → `time.sleep(0.3+0.2)` bloqueaba el mainloop + enviaba keystrokes desde el thread incorrecto. Fix: `on_close=lambda w=window: threading.Thread(target=lambda: _do_close(w), daemon=True).start()` — `_do_close` siempre corre en background thread |
| Race condition en `dismiss_toast`: `on_expire` podía ejecutarse aunque `dismiss` fue llamado | `dismissed[0] = True` se seteaba FUERA del lock → si el tick del toast corría en el gap, veía `dismissed=False` y disparaba `on_expire`. Fix: mover `dismissed[0] = True` dentro del `with _lock:` en `dismiss_toast()` |
| LLM clasifica "Home", "Meetup", "Awesome Piracy" como PRODUCTIVO | Prompt demasiado permisivo ("prefer PRODUCTIVE when ambiguous"). Fix: cambió a "Default to DISTRACTION when connection is ambiguous" + "Generic titles = DISTRACTION" |

## Para activar Twitter

1. Crear app en developer.twitter.com con permisos Read+Write
2. Usar la tab **TWITTER** en el dashboard para ingresar las keys (se guardan en .env)
3. O editar `.env` directamente y reiniciar

## Shortcuts del dashboard

- `Ctrl+D` — fuerza un countdown demo (para presentaciones)

## Instalar dependencias

```bash
pip install pywin32 psutil tweepy groq
```
