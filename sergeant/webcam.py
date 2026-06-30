"""
webcam.py — deteccion de presencia mediante camara web.
Usa opencv-python + mediapipe para detectar si hay una cara frente al monitor.
Si no se detectan librerias, todo falla silenciosamente (is_available() = False).
"""
import threading
import time

try:
    import cv2 as _cv2
    import mediapipe as _mp
    _LIBS_OK = True
except ImportError:
    _LIBS_OK = False

_lock     = threading.Lock()
_running  = False
_thread   = None
_cap      = None
_detector = None
_state    = {"present": None, "reason": "inactivo"}

POLL_INTERVAL = 3.0  # segundos entre capturas de frame


def is_available():
    """True si opencv-python y mediapipe están instalados."""
    return _LIBS_OK


def is_running():
    return _running


def _init_cam():
    global _cap, _detector
    try:
        mp_face   = _mp.solutions.face_detection
        _detector = mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.5)
        _cap      = _cv2.VideoCapture(0)
        if not _cap.isOpened():
            _cap.release()
            _cap = None
            return False
        return True
    except Exception as exc:
        print(f"[WEBCAM] init error: {exc}")
        return False


def _release_cam():
    global _cap, _detector
    if _cap is not None:
        try:
            _cap.release()
        except Exception:
            pass
        _cap = None
    _detector = None


def _poll():
    global _running
    while _running:
        try:
            if _cap is None or _detector is None:
                with _lock:
                    _state["present"] = None
                    _state["reason"]  = "camara no disponible"
            else:
                ret, frame = _cap.read()
                if not ret:
                    with _lock:
                        _state["present"] = None
                        _state["reason"]  = "error de lectura"
                else:
                    frame_rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
                    results   = _detector.process(frame_rgb)
                    if results.detections:
                        with _lock:
                            _state["present"] = True
                            _state["reason"]  = "presencia detectada"
                    else:
                        with _lock:
                            _state["present"] = False
                            _state["reason"]  = "sin presencia"
        except Exception as exc:
            print(f"[WEBCAM] error en poll: {exc}")
            with _lock:
                _state["present"] = None
                _state["reason"]  = "error"
        time.sleep(POLL_INTERVAL)


def start():
    """Inicia la deteccion de presencia. Retorna True si pudo abrir la camara."""
    global _running, _thread
    if not _LIBS_OK:
        print("[WEBCAM] opencv-python o mediapipe no instalados — pip install opencv-python mediapipe")
        return False
    if _running:
        return True
    if not _init_cam():
        with _lock:
            _state["present"] = None
            _state["reason"]  = "camara no disponible"
        return False
    _running = True
    _thread  = threading.Thread(target=_poll, daemon=True, name="webcam-poll")
    _thread.start()
    print("[WEBCAM] iniciado — detectando presencia cada 3s")
    return True


def stop():
    """Detiene la deteccion y libera la camara."""
    global _running
    _running = False
    _release_cam()
    with _lock:
        _state["present"] = None
        _state["reason"]  = "inactivo"
    print("[WEBCAM] detenido")


def get_presence():
    """
    Retorna (present: bool|None, reason: str).
    present=True  → cara detectada
    present=False → sin presencia (AFK)
    present=None  → camara no disponible o inactivo
    """
    with _lock:
        return _state["present"], _state["reason"]
