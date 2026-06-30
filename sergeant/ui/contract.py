import tkinter as tk
import threading

BG     = "#0a0a0a"
RED    = "#ff2222"
GREEN  = "#00ff41"
DIM    = "#444444"
WHITE  = "#e0e0e0"
ORANGE = "#ff8800"
FONT   = ("Courier New", 10)
FONT_B = ("Courier New", 10, "bold")
FONT_T = ("Courier New", 13, "bold")

def _build_contract_text():
    try:
        from config import GRACE_PERIOD_SECONDS, TWEET_THRESHOLD_SECONDS, DEMO_MODE
        grace = GRACE_PERIOD_SECONDS
        tweet_mins = TWEET_THRESHOLD_SECONDS // 60
        demo_note = "  [MODO DEMO ACTIVO — timers acelerados]\n" if DEMO_MODE else ""
    except Exception:
        grace = 30; tweet_mins = 5; demo_note = ""

    return f"""\
ACUERDO DE USO — SERGEANT v1.0
{demo_note}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Al aceptar este acuerdo, el Usuario declara entender y consentir
que el software denominado SERGEANT:

  § 1.  MONITOREA en tiempo real todas las ventanas y procesos
        activos en este equipo, sin excepción.

  § 2.  CLASIFICA la actividad del Usuario como productiva o
        distractiva según el objetivo declarado.

  § 3.  CIERRA sin previo aviso adicional cualquier aplicación
        que interfiera con el objetivo, tras un período de gracia
        de {grace} segundos.

  § 4.  MUESTRA una cuenta regresiva amenazando la integridad
        del sistema operativo si la distracción persiste.

  § 5.  PUBLICA en redes sociales, en nombre del Usuario, el
        detalle de sus infracciones tras {tweet_mins} minuto(s) de distracción
        (si la integración está activa).

  § 6.  NO PUEDE SER CERRADO desde la interfaz gráfica.
        Para detener el servicio, debe forzarse el cierre del proceso.

  § 7.  El desarrollador NO se responsabiliza por pérdida de datos,
        cierre involuntario de aplicaciones, o daño emocional derivado
        del uso de este software.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"La tecnología no te hizo esto. Vos la instalaste."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def show_contract(on_accept=None, on_reject=None):
    """Muestra el contrato. Bloquea hasta que el usuario acepta o cierra."""

    root = tk.Tk()
    root.title("SERGEANT — CONTRATO DE USO")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    W, H = 720, 580
    # Forzar monitor primario: usar win32api si disponible, si no fallback
    try:
        import ctypes
        user32 = ctypes.windll.user32
        SW = user32.GetSystemMetrics(0)   # SM_CXSCREEN — monitor primario
        SH = user32.GetSystemMetrics(1)   # SM_CYSCREEN
    except Exception:
        SW = root.winfo_screenwidth()
        SH = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(SW-W)//2}+{(SH-H)//2}")
    root.lift()
    root.focus_force()

    tk.Label(root, text="SERGEANT  //  ACUERDO DE RESPONSABILIDAD",
             font=FONT_T, fg=RED, bg=BG).pack(pady=(20, 4))
    tk.Label(root, text="Lea y acepte los términos para continuar.",
             font=FONT, fg=DIM, bg=BG).pack(pady=(0, 10))

    text = tk.Text(root, bg="#0f0f0f", fg=WHITE, font=FONT,
                   relief=tk.FLAT, bd=0, wrap=tk.WORD,
                   height=20, state=tk.NORMAL, cursor="arrow",
                   padx=16, pady=8)
    text.insert(tk.END, _build_contract_text())
    text.config(state=tk.DISABLED)
    text.pack(fill=tk.X, padx=20)

    input_frame = tk.Frame(root, bg=BG)
    input_frame.pack(fill=tk.X, padx=20, pady=(12, 0))

    tk.Label(input_frame,
             text='escribí  "ACEPTO"  para activar el enforcer:',
             font=FONT, fg=ORANGE, bg=BG, anchor="w").pack(anchor="w")

    entry_var = tk.StringVar()
    status_var = tk.StringVar(value="")

    entry = tk.Entry(input_frame, textvariable=entry_var,
                     bg="#1a0000", fg=RED, font=("Courier New", 14, "bold"),
                     relief=tk.FLAT, bd=4, insertbackground=RED,
                     width=20)
    entry.pack(anchor="w", pady=(4, 0))
    entry.focus_set()

    status_lbl = tk.Label(root, textvariable=status_var,
                          font=FONT, fg=DIM, bg=BG)
    status_lbl.pack(pady=(4, 8))

    def check_input(event=None):
        val = entry_var.get().strip().upper()
        if val == "ACEPTO":
            status_var.set("✓ contrato aceptado. SERGEANT armado.")
            status_lbl.configure(fg=GREEN)
            root.after(800, lambda: (root.destroy(), on_accept() if on_accept else None))
        elif len(val) >= 6:
            status_var.set("✗ entrada incorrecta.")
            status_lbl.configure(fg=RED)
            entry_var.set("")

    entry.bind("<Return>", check_input)
    entry_var.trace_add("write", lambda *_: check_input())

    def on_close():
        root.destroy()
        if on_reject:
            on_reject()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
