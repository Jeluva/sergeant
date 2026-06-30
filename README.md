# SERGEANT

> *"You said you'd work. We're watching."*

App de productividad estilo **Black Mirror** construida para un ANTIhackaton. Corre en background, vigila lo que hacés en la computadora, y si detecta distracciones — actúa.

---

## Qué hace

- Detecta la ventana activa y la clasifica como **PRODUCTIVA** o **DISTRACCIÓN** usando un LLM (Groq) con contexto de tu objetivo actual
- Si te distraés: te avisa, cierra la pestaña de Chrome, y después de 3 infracciones dispara una cuenta regresiva con **fake sys32 deletion**
- Opcionalmente tweetea tus infracciones en tiempo real
- Opcionalmente detecta si estás frente al monitor usando la webcam (face detection offline con MediaPipe)
- Dashboard terminal negro/verde con métricas del día, historial de sesiones y DEFCON en tiempo real

---

## Stack

- Python 3.12 + tkinter
- pywin32 — detección de ventanas, envío de teclas
- psutil — info de procesos
- SQLite — time tracking local
- Groq API (`llama-3.1-8b-instant`) — clasificador semántico, ~100ms, gratuito
- tweepy — Twitter/X (mock por default)
- opencv-python + mediapipe — detección de presencia por webcam (opcional)
- Windows 10+

---

## Instalación

```bash
pip install pywin32 psutil tweepy groq opencv-python mediapipe
```

Crear un archivo `.env` en la raíz del proyecto:

```
GROQ_API_KEY=gsk_...

# Opcional — Twitter
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_ENABLED=true

# Opcional — persistir objetivo entre reinicios
CURRENT_GOAL=estudiar para una entrevista que tengo mañana

# Opcional — activar webcam al iniciar
WEBCAM_ENABLED=false
```

Si no tenés `GROQ_API_KEY`, la app igual funciona con fallback a keywords.

---

## Uso

```bat
# Desde la raíz del proyecto:
DEMO.bat                              # launcher con menú
python sergeant\main.py               # arranque normal (pide contrato)
python sergeant\main.py --skip-contract  # saltea el contrato (testing)
```

**DEMO_MODE = True** — todos los timers están acelerados para presentaciones (grace period 8s, countdown 20s).

---

## Cómo funciona

### Clasificación

Cada 2 segundos se detecta la ventana activa. El clasificador usa este orden de prioridad:

1. Proceso en lista negra (`discord.exe`, `steam.exe`, etc.) → **DISTRACTION** inmediata
2. Proceso en lista blanca (`code.exe`, `pycharm64.exe`, etc.) → **PRODUCTIVE** inmediata
3. Nueva pestaña / Google SERP → **UNKNOWN** (sin enforcement, es tránsito)
4. **LLM Groq** — clasifica semánticamente con tu objetivo como contexto
5. Fallback a keywords si el LLM falla o da timeout

### Enforcement — Modo CLOSE (infracciones 1-3)

```
Distracción detectada
    └─ A los ~Ns → toast de aviso ("cerrando en Xs")
         └─ Al expirar → Ctrl+W en Chrome / terminate() en otros procesos
              └─ infracción +1
```

### Enforcement — Modo COUNTDOWN (infracción 4 en adelante)

```
Distracción detectada → cuenta regresiva con fake sys32 deletion
Volvés a trabajar     → PAUSA (el timer persiste, no se resetea)
Te distraés de nuevo  → REANUDA desde donde estaba
```

### Detección de presencia (webcam)

Si activás la webcam desde la tab CONFIG, MediaPipe analiza un frame cada 3 segundos. Si no detecta una cara → infracción **AFK**, independientemente de qué ventana tengas abierta.

---

## Dashboard

Cuatro tabs:

| Tab | Contenido |
|-----|-----------|
| **MONITOR** | DEFCON 1-5, estado WORKING/DISTRACCION, ventana activa, métricas del día, últimas sesiones |
| **HISTORIAL** | Timeline visual del día con bloques coloreados por hora y hover tooltip |
| **MISION** | Objetivo actual, campo para cambiarlo en caliente con APPLY |
| **CONFIG** | Credenciales de Twitter/X, toggle de detección por webcam |

`Ctrl+D` fuerza un countdown demo (útil para presentaciones).

---

## Estructura

```
sergeant/
├── main.py          # loop principal, máquina de estados
├── config.py        # parámetros y API keys
├── monitor.py       # get_active_window()
├── classifier.py    # LLM + keyword fallback
├── enforcer.py      # warn, close, countdown, dismiss
├── tracker.py       # time tracking por sesión
├── db.py            # SQLite
├── social.py        # tweet_distraction()
├── webcam.py        # detección de presencia por cámara
└── ui/
    ├── contract.py  # pantalla de contrato inicial
    ├── boot.py      # animación de boot terminal
    ├── dashboard.py # dashboard principal (4 tabs)
    ├── toast.py     # notificación de aviso en esquina
    └── countdown.py # cuenta regresiva fake-sys32
```

---

## Cambiar el objetivo en caliente

Sin reiniciar la app: ir a tab **MISION** → escribir el nuevo objetivo → **APPLY**.

El LLM recibe el nuevo objetivo como contexto y el cache se limpia automáticamente.

---

## Activar Twitter

1. Crear una app en [developer.twitter.com](https://developer.twitter.com) con permisos **Read + Write**
2. Ingresar las keys en la tab **CONFIG** del dashboard → **GUARDAR Y ACTIVAR**
3. O agregar las keys directamente al `.env` y reiniciar

---

## Licencia

Sin licencia — proyecto de hackaton. Usalo como quieras.
