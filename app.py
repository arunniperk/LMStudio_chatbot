"""
Local Chatbot
Backend : LM Studio (http://localhost:1234)
UI      : Themeable — Windows 7 Aero (Light) / Win7 Dark Mode
"""

import customtkinter as ctk
import threading
import json
import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from openai import OpenAI, APIConnectionError

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import pypdf;   PDF_READ_OK = True
except ImportError: PDF_READ_OK = False

try:
    from fpdf import FPDF;  PDF_WRITE_OK = True
except ImportError:         PDF_WRITE_OK = False

try:
    import pynvml;  pynvml.nvmlInit();  NVML_OK = True
except Exception:                       NVML_OK = False

try:
    import psutil;  PSUTIL_OK = True
except ImportError: PSUTIL_OK = False

import platform, subprocess, re

# ── HARDWARE DETECTION ────────────────────────────────────────────────────────
def _detect_cpu() -> str:
    name = ""
    try:
        if platform.system() == "Windows":
            out  = subprocess.check_output("wmic cpu get Name /format:list",
                       shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore")
            m    = re.search(r"Name=(.+)", out)
            if m: name = m.group(1).strip()
        elif platform.system() == "Darwin":
            out  = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"],
                       stderr=subprocess.DEVNULL).decode(errors="ignore")
            name = out.strip()
        else:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        name = line.split(":")[1].strip(); break
    except Exception:
        name = platform.processor() or "Unknown CPU"

    name = re.sub(r"\s*\d+-Core Processor.*", "", name, flags=re.I)
    name = re.sub(r"^(Intel\(R\)|AMD)\s*", "", name, flags=re.I).strip()[:32]
    cores = ""
    if PSUTIL_OK:
        try:
            p = psutil.cpu_count(logical=False) or 1
            l = psutil.cpu_count(logical=True)  or 1
            cores = f"{p}C / {l}T"
        except Exception: pass
    return f"{name}  ·  {cores}" if cores else name


def _detect_gpu() -> tuple[str, str]:
    if NVML_OK:
        try:
            h    = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes): name = name.decode()
            name = re.sub(r"^NVIDIA\s*(GeForce\s*)?", "", name, flags=re.I).strip()
            info = pynvml.nvmlDeviceGetMemoryInfo(h)
            return name, f"{info.total/1e9:.0f} GB VRAM"
        except Exception: pass
    return "No NVIDIA GPU", "—"


HW_CPU            = _detect_cpu()
HW_GPU, HW_VRAM   = _detect_gpu()

# ── CONFIG ────────────────────────────────────────────────────────────────────
LM_URL    = "http://localhost:1234/v1"
API_KEY   = "lm-studio"
CTX       = 8192
SAVE_DIR  = Path("saved_chats")
CFG_FILE  = Path("chatbot_config.json")

# ── THEMES (Windows 7 Aero) ───────────────────────────────────────────────────
THEMES = {
    "dark": {
        "CTK_MODE":  "dark",
        "BG":        "#0F1419",
        "SURFACE":   "#1A2128",
        "SURFACE2":  "#242D35",
        "BORDER":    "#3E4C59",
        "ACCENT":    "#3DA5FF",
        "USER_BG":   "#132A3F",
        "USER_BORD": "#1D3B54",
        "TEXT_PRI":  "#F1F3F5",
        "TEXT_SEC":  "#A1B0BD",
        "TEXT_DIM":  "#708291",
        "SUCCESS":   "#40C057",
        "WARN":      "#FAB005",
        "ERROR":     "#FA5252",
        "BAR_CPU":   "#3DA5FF",
        "BAR_RAM":   "#40C057",
        "THINK_BG":  "#141A20",
        "ASST_LABEL":"#3DA5FF",
    },
    "light": {
        "CTK_MODE":  "light",
        "BG":        "#EBF1F8",
        "SURFACE":   "#FFFFFF",
        "SURFACE2":  "#F2F6FA",
        "BORDER":    "#A9C4E0",
        "ACCENT":    "#0066CC",
        "USER_BG":   "#E1EFFF",
        "USER_BORD": "#B8D4F0",
        "TEXT_PRI":  "#000000",
        "TEXT_SEC":  "#444444",
        "TEXT_DIM":  "#777777",
        "SUCCESS":   "#107C10",
        "WARN":      "#D83B01",
        "ERROR":     "#E81123",
        "BAR_CPU":   "#0066CC",
        "BAR_RAM":   "#107C10",
        "THINK_BG":  "#F8FAFC",
        "ASST_LABEL":"#0066CC",
    },
}

def _load_cfg() -> dict:
    try:
        return json.loads(CFG_FILE.read_text())
    except Exception:
        return {"theme": "light"}

def _save_cfg(data: dict):
    try:
        CFG_FILE.write_text(json.dumps(data))
    except Exception:
        pass

_cfg      = _load_cfg()
_theme_id = _cfg.get("theme", "light")
T         = THEMES[_theme_id]   

FALLBACK = [
    {"id": "gemma-3-12b-instruct",         "label": "Gemma 3 · 12B",     "desc": "Reports & admin drafting"},
    {"id": "qwen2.5-coder-14b-instruct",   "label": "Qwen Coder · 14B",  "desc": "Code & structured logic"},
    {"id": "deepseek-r1-distill-qwen-14b", "label": "DeepSeek R1 · 14B", "desc": "Deep reasoning & analysis"},
]

DEFAULT_SYSTEM = (
    "You are Local Chatbot, an AI assistant for administrative and academic workflows. "
    "Help with drafting documents, coding, data analysis, and presentations. "
    "Be precise and professional."
)

client = OpenAI(base_url=LM_URL, api_key=API_KEY)


def _model_meta(mid: str) -> dict:
    ml = mid.lower()
    if "r1" in ml or "deepseek" in ml:
        return {"id": mid, "label": "DeepSeek R1",  "desc": "Deep reasoning & analysis"}
    if "coder" in ml:
        return {"id": mid, "label": "Qwen Coder",   "desc": "Code & structured logic"}
    if "gemma" in ml:
        return {"id": mid, "label": "Gemma",        "desc": "Reports & admin drafting"}
    if "qwen" in ml:
        return {"id": mid, "label": "Qwen",         "desc": "General purpose, fast"}
    return {"id": mid, "label": mid.split("-")[0].capitalize(), "desc": "General purpose"}


def fetch_models() -> list[dict]:
    try:
        data = client.models.list().data
        return [_model_meta(m.id) for m in data] or FALLBACK
    except Exception:
        return FALLBACK


# ── THINK PARSER ──────────────────────────────────────────────────────────────
class ThinkParser:
    def __init__(self):
        self._buf = ""; self._in = False
        self.display = ""; self.thinking = ""

    def feed(self, tok):
        self._buf += tok
        dd = tt = ""
        while True:
            if not self._in:
                i = self._buf.find("<think>")
                if i == -1:
                    s = max(0, len(self._buf) - len("<think>"))
                    if s:
                        c = self._buf[:s]; dd += c; self.display += c; self._buf = self._buf[s:]
                    break
                c = self._buf[:i]; dd += c; self.display += c
                self._buf = self._buf[i + 7:]; self._in = True
            else:
                i = self._buf.find("</think>")
                if i == -1:
                    s = max(0, len(self._buf) - len("</think>"))
                    if s:
                        c = self._buf[:s]; tt += c; self.thinking += c; self._buf = self._buf[s:]
                    break
                c = self._buf[:i]; tt += c; self.thinking += c
                self._buf = self._buf[i + 8:]; self._in = False
        return dd, tt

    def flush(self):
        r = self._buf; self._buf = ""
        if self._in:
            self.thinking += r; return "", r
        self.display += r; return r, ""


# ── MODEL PICKER ──────────────────────────────────────────────────────────────
class ModelPicker(ctk.CTkToplevel):
    def __init__(self, anchor, models, current_id, on_select, think_var):
        super().__init__()
        self.overrideredirect(True)
        self.configure(fg_color=T["SURFACE"])
        self.attributes("-topmost", True)

        self.update_idletasks()
        ax = anchor.winfo_rootx()
        h  = 72 * len(models) + 96
        ay = anchor.winfo_rooty() - h - 8
        self.geometry(f"320x{h}+{ax}+{ay}")

        card = ctk.CTkFrame(self, fg_color=T["SURFACE"], corner_radius=4,
                            border_width=1, border_color=T["BORDER"])
        card.pack(fill="both", expand=True, padx=1, pady=1)

        for m in models:
            self._row(card, m, m["id"] == current_id, on_select)

        ctk.CTkFrame(card, height=1, fg_color=T["BORDER"]).pack(fill="x", padx=12, pady=(4, 0))

        tr = ctk.CTkFrame(card, fg_color="transparent")
        tr.pack(fill="x", padx=16, pady=10)
        lc = ctk.CTkFrame(tr, fg_color="transparent")
        lc.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(lc, text="Deep Reasoning",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=T["TEXT_PRI"], anchor="w").pack(anchor="w")
        ctk.CTkLabel(lc, text="<think> trace for R1 models",
                     font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_SEC"], anchor="w").pack(anchor="w")
        ctk.CTkSwitch(tr, text="", variable=think_var, width=44,
                      button_color=T["ACCENT"]).pack(side="right")

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.focus_set()

    def _row(self, parent, m, active, on_select):
        hover_bg = T["SURFACE2"]
        row = ctk.CTkFrame(parent, fg_color="transparent", cursor="hand2")
        row.pack(fill="x", padx=8, pady=1)
        row.bind("<Enter>", lambda e: row.configure(fg_color=hover_bg))
        row.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))
        row.bind("<Button-1>", lambda e: (on_select(m), self.destroy()))

        if active:
            ctk.CTkFrame(row, width=3, fg_color=T["ACCENT"],
                         corner_radius=0).pack(side="left", fill="y", pady=6, padx=(6, 0))

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        inner.bind("<Button-1>", lambda e: (on_select(m), self.destroy()))

        ctk.CTkLabel(inner, text=m["label"],
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold" if active else "normal"),
                     text_color=T["ACCENT"] if active else T["TEXT_PRI"],
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text=m["desc"],
                     font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_SEC"],
                     anchor="w").pack(anchor="w")


# ── MAIN APP ──────────────────────────────────────────────────────────────────
ctk.set_appearance_mode(T["CTK_MODE"])
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Local Chatbot")
        self.geometry("1300x800")
        self.minsize(960, 620)
        self.configure(fg_color=T["BG"])

        self._messages    : list[dict] = []
        self._generating              = False
        self._stop_flag               = False
        self._parser                  = None
        self._models                  = FALLBACK
        self._cur                     = FALLBACK[0]
        self.think_var                = ctk.BooleanVar(value=False)
        self._attachments : list[dict] = []
        self._stream_var  : ctk.StringVar | None = None
        self._stream_label            = None
        self._msg_count               = 0
        self._last_response           = ""
        self._theme_id                = _theme_id

        # Widget registries for theme updates
        self._tw_frames  : list[tuple] = []
        self._tw_labels  : list[tuple] = []
        self._tw_buttons : list[tuple] = []
        self._tw_boxes   : list[tuple] = []
        self._tw_bars    : list[tuple] = []

        SAVE_DIR.mkdir(exist_ok=True)
        self._build_ui()
        threading.Thread(target=self._probe, daemon=True).start()
        self._poll_resources()

    # ──────────────────────────────────────────────────────────────────────────
    # THEME SYSTEM
    # ──────────────────────────────────────────────────────────────────────────
    def _toggle_theme(self):
        global T, _theme_id
        _theme_id    = "light" if self._theme_id == "dark" else "dark"
        self._theme_id = _theme_id
        T            = THEMES[_theme_id]
        _save_cfg({"theme": _theme_id})

        ctk.set_appearance_mode(T["CTK_MODE"])
        self._apply_theme()

        icon = "☀" if _theme_id == "dark" else "🌙"
        self.theme_btn.configure(text=icon)

    def _apply_theme(self):
        self.configure(fg_color=T["BG"])

        for widget, prop, key in self._tw_frames:
            try: widget.configure(**{prop: T[key]})
            except Exception: pass

        for widget, prop, key in self._tw_labels:
            try: widget.configure(**{prop: T[key]})
            except Exception: pass

        for widget, props in self._tw_buttons:
            try: widget.configure(**{k: T[v] for k, v in props.items()})
            except Exception: pass

        for widget, props in self._tw_boxes:
            try: widget.configure(**{k: T[v] for k, v in props.items()})
            except Exception: pass

        for widget, key in self._tw_bars:
            try: widget.configure(progress_color=T[key])
            except Exception: pass

        try: self.greet_frame.configure(fg_color=T["BG"])
        except Exception: pass

        try: self.inp_card.configure(fg_color=T["SURFACE"], border_color=T["BORDER"])
        except Exception: pass

    def _reg_frame(self, w, prop, key):
        self._tw_frames.append((w, prop, key)); return w

    def _reg_lbl(self, w, prop, key):
        self._tw_labels.append((w, prop, key)); return w

    def _reg_btn(self, w, **props):
        self._tw_buttons.append((w, props)); return w

    def _reg_box(self, w, **props):
        self._tw_boxes.append((w, props)); return w

    def _reg_bar(self, w, key):
        self._tw_bars.append((w, key)); return w

    # ──────────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── LEFT SIDEBAR ─────────────────────────────────────────────────────
        sb = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=T["SURFACE"])
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self.sidebar = sb
        self._reg_frame(sb, "fg_color", "SURFACE")

        # Logo row
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=20, pady=(22, 2))
        self._reg_lbl(
            ctk.CTkLabel(logo, text="●", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=T["ACCENT"]),
            "text_color", "ACCENT").pack(side="left")
        self._reg_lbl(
            ctk.CTkLabel(logo, text="  Local Chatbot",
                         font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=T["TEXT_PRI"]),
            "text_color", "TEXT_PRI").pack(side="left")

        # Theme toggle button
        icon = "☀" if self._theme_id == "dark" else "🌙"
        self.theme_btn = ctk.CTkButton(
            logo, text=icon, width=30, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="transparent", hover_color=T["SURFACE2"],
            text_color=T["TEXT_SEC"],
            corner_radius=4, command=self._toggle_theme,
        )
        self.theme_btn.pack(side="right")
        self._reg_btn(self.theme_btn,
                      hover_color="SURFACE2", text_color="TEXT_SEC")

        # Status Label (Moved to top left)
        self.status_lbl = self._reg_lbl(
            ctk.CTkLabel(sb, text="● Connecting to LM Studio...",
                         font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["WARN"]),
            "text_color", "WARN")
        self.status_lbl.pack(anchor="w", padx=20, pady=(0, 2))
            
        # Creator Signature
        self._reg_lbl(
            ctk.CTkLabel(sb, text="Created by Arun Verma",
                         font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"), text_color=T["TEXT_SEC"]),
            "text_color", "TEXT_SEC").pack(anchor="w", padx=20, pady=(0, 14))

        div1 = ctk.CTkFrame(sb, height=1, fg_color=T["BORDER"])
        div1.pack(fill="x", padx=16, pady=(0, 14))
        self._reg_frame(div1, "fg_color", "BORDER")

        # Model
        self._sb_lbl(sb, "MODEL")
        self.model_btn = ctk.CTkButton(
            sb, text=f"{self._cur['label']}  ▾",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=T["SURFACE2"], hover_color=T["BORDER"],
            text_color=T["TEXT_PRI"], border_width=1, border_color=T["BORDER"],
            corner_radius=4, height=36, anchor="w", command=self._open_picker,
        )
        self.model_btn.pack(fill="x", padx=16, pady=(6, 14))
        self._reg_btn(self.model_btn,
                      fg_color="SURFACE2", hover_color="BORDER",
                      text_color="TEXT_PRI", border_color="BORDER")

        div2 = ctk.CTkFrame(sb, height=1, fg_color=T["BORDER"])
        div2.pack(fill="x", padx=16, pady=(0, 12))
        self._reg_frame(div2, "fg_color", "BORDER")

        # Hardware info (Percentage Utilizations)
        self._sb_lbl(sb, "HARDWARE UTILIZATION")
        
        # ── CPU Card ──
        cpu_info = ctk.CTkFrame(sb, fg_color=T["SURFACE2"], corner_radius=4,
                                border_width=1, border_color=T["BORDER"])
        cpu_info.pack(fill="x", padx=16, pady=(6, 2))
        self._reg_frame(cpu_info, "fg_color", "SURFACE2")
        
        cpu_icon_row = ctk.CTkFrame(cpu_info, fg_color="transparent")
        cpu_icon_row.pack(fill="x", padx=10, pady=8)
        self._reg_lbl(ctk.CTkLabel(cpu_icon_row, text="CPU",
                         font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                         text_color=T["BAR_CPU"]), "text_color", "BAR_CPU").pack(side="left")
        
        self.cpu_util_lbl = self._reg_lbl(ctk.CTkLabel(cpu_icon_row, text="--%",
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=T["TEXT_PRI"]),
                      "text_color", "TEXT_PRI")
        self.cpu_util_lbl.pack(side="right")

        # ── RAM Card ──
        ram_info = ctk.CTkFrame(sb, fg_color=T["SURFACE2"], corner_radius=4,
                                border_width=1, border_color=T["BORDER"])
        ram_info.pack(fill="x", padx=16, pady=(2, 2))
        self._reg_frame(ram_info, "fg_color", "SURFACE2")
        
        ram_icon_row = ctk.CTkFrame(ram_info, fg_color="transparent")
        ram_icon_row.pack(fill="x", padx=10, pady=8)
        self._reg_lbl(ctk.CTkLabel(ram_icon_row, text="RAM",
                         font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                         text_color=T["BAR_RAM"]), "text_color", "BAR_RAM").pack(side="left")
        
        self.ram_util_lbl = self._reg_lbl(ctk.CTkLabel(ram_icon_row, text="--%",
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=T["TEXT_PRI"]),
                      "text_color", "TEXT_PRI")
        self.ram_util_lbl.pack(side="right")

        # ── GPU Card ──
        gpu_info = ctk.CTkFrame(sb, fg_color=T["SURFACE2"], corner_radius=4,
                                border_width=1, border_color=T["BORDER"])
        gpu_info.pack(fill="x", padx=16, pady=(2, 4))
        self._reg_frame(gpu_info, "fg_color", "SURFACE2")
        
        gpu_icon_row = ctk.CTkFrame(gpu_info, fg_color="transparent")
        gpu_icon_row.pack(fill="x", padx=10, pady=8)
        self._reg_lbl(ctk.CTkLabel(gpu_icon_row, text="GPU VRAM",
                         font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                         text_color=T["ACCENT"]), "text_color", "ACCENT").pack(side="left")
        
        self.vram_util_lbl = self._reg_lbl(ctk.CTkLabel(gpu_icon_row, text="--%",
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=T["TEXT_PRI"]),
                      "text_color", "TEXT_PRI")
        self.vram_util_lbl.pack(side="right")

        div4 = ctk.CTkFrame(sb, height=1, fg_color=T["BORDER"])
        div4.pack(fill="x", padx=16, pady=(12, 10))
        self._reg_frame(div4, "fg_color", "BORDER")

        # System prompt
        self._sb_lbl(sb, "SYSTEM PROMPT")
        self.sys_box = ctk.CTkTextbox(
            sb, height=110, font=ctk.CTkFont(family="Segoe UI", size=11), wrap="word",
            fg_color=T["SURFACE2"], border_color=T["BORDER"],
            border_width=1, corner_radius=4, text_color=T["TEXT_PRI"],
        )
        self.sys_box.pack(fill="x", padx=16, pady=(6, 14))
        self.sys_box.insert("1.0", DEFAULT_SYSTEM)
        self._reg_box(self.sys_box,
                      fg_color="SURFACE2", border_color="BORDER", text_color="TEXT_PRI")

        div5 = ctk.CTkFrame(sb, height=1, fg_color=T["BORDER"])
        div5.pack(fill="x", padx=16, pady=(0, 10))
        self._reg_frame(div5, "fg_color", "BORDER")

        self.turns_lbl = self._reg_lbl(
            ctk.CTkLabel(sb, text="0 messages",
                         font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_DIM"]),
            "text_color", "TEXT_DIM")
        self.turns_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        _btn = dict(font=ctk.CTkFont(family="Segoe UI", size=12), border_width=1, corner_radius=4, height=32)
        nc = self._reg_btn(
            ctk.CTkButton(sb, text="⊕  New Chat",
                          fg_color="transparent", hover_color=T["SURFACE2"],
                          text_color=T["TEXT_SEC"], border_color=T["BORDER"],
                          command=self._clear, **_btn),
            fg_color="transparent", hover_color="SURFACE2",
            text_color="TEXT_SEC", border_color="BORDER")
        nc.pack(fill="x", padx=16, pady=(0, 6))
        sc = self._reg_btn(
            ctk.CTkButton(sb, text="↓  Save Chat",
                          fg_color="transparent", hover_color=T["SURFACE2"],
                          text_color=T["TEXT_SEC"], border_color=T["BORDER"],
                          command=self._save, **_btn),
            fg_color="transparent", hover_color="SURFACE2",
            text_color="TEXT_SEC", border_color="BORDER")
        sc.pack(fill="x", padx=16)

        # ── RIGHT OUTPUT PANE ─────────────────────────────────────────────────
        rp = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=T["SURFACE"])
        rp.pack(side="right", fill="y")
        rp.pack_propagate(False)
        self.right_pane = rp
        self._reg_frame(rp, "fg_color", "SURFACE")

        rp_hdr = ctk.CTkFrame(rp, fg_color="transparent")
        rp_hdr.pack(fill="x", padx=16, pady=(20, 0))
        self._reg_lbl(
            ctk.CTkLabel(rp_hdr, text="Output",
                         font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                         text_color=T["TEXT_PRI"]),
            "text_color", "TEXT_PRI").pack(side="left")
        self._reg_btn(
            ctk.CTkButton(rp_hdr, text="Clear", width=50, height=24,
                          fg_color="transparent", hover_color=T["SURFACE2"],
                          text_color=T["TEXT_DIM"], border_width=1,
                          border_color=T["BORDER"], corner_radius=4,
                          font=ctk.CTkFont(family="Segoe UI", size=11), command=self._clear_output),
            fg_color="transparent", hover_color="SURFACE2",
            text_color="TEXT_DIM", border_color="BORDER").pack(side="right")

        div_rp = ctk.CTkFrame(rp, height=1, fg_color=T["BORDER"])
        div_rp.pack(fill="x", padx=16, pady=(10, 10))
        self._reg_frame(div_rp, "fg_color", "BORDER")

        self.output_box = ctk.CTkTextbox(
            rp, font=ctk.CTkFont(family="Segoe UI", size=12), wrap="word",
            fg_color=T["SURFACE2"], border_color=T["BORDER"],
            border_width=1, corner_radius=4,
            text_color=T["TEXT_PRI"], state="disabled",
        )
        self.output_box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self._reg_box(self.output_box,
                      fg_color="SURFACE2", border_color="BORDER", text_color="TEXT_PRI")

        div_rp2 = ctk.CTkFrame(rp, height=1, fg_color=T["BORDER"])
        div_rp2.pack(fill="x", padx=16, pady=(0, 8))
        self._reg_frame(div_rp2, "fg_color", "BORDER")

        self._sb_lbl(rp, "EXPORT")
        dl_row = ctk.CTkFrame(rp, fg_color="transparent")
        dl_row.pack(fill="x", padx=16, pady=(6, 4))
        _dl = dict(font=ctk.CTkFont(family="Segoe UI", size=11), corner_radius=4,
                   height=30, border_width=1)

        for text, cmd, is_accent in [
            ("Copy",     self._copy_output, False),
            ("Save TXT", self._save_txt,    False),
            ("Save PDF", self._save_pdf,    True),
        ]:
            b = ctk.CTkButton(
                dl_row, text=text,
                fg_color=T["ACCENT"] if is_accent else "transparent",
                hover_color=T["BORDER"] if not is_accent else "#1D4ED8",
                text_color=T["TEXT_PRI"] if is_accent else T["TEXT_SEC"],
                border_color=T["BORDER"],
                command=cmd, **_dl)
            b.pack(side="left", padx=(0, 4))
            if is_accent:
                self._reg_btn(b, fg_color="ACCENT", hover_color="BORDER",
                              text_color="TEXT_PRI", border_color="BORDER")
            else:
                self._reg_btn(b, fg_color="transparent", hover_color="BORDER",
                              text_color="TEXT_SEC", border_color="BORDER")

        if not PDF_WRITE_OK:
            self._reg_lbl(
                ctk.CTkLabel(rp, text="pip install fpdf2 for PDF",
                             font=ctk.CTkFont(family="Segoe UI", size=10),
                             text_color=T["TEXT_DIM"], wraplength=220),
                "text_color", "TEXT_DIM").pack(padx=16, pady=(0, 4))

        div_rp3 = ctk.CTkFrame(rp, height=1, fg_color=T["BORDER"])
        div_rp3.pack(fill="x", padx=16, pady=(4, 8))
        self._reg_frame(div_rp3, "fg_color", "BORDER")

        self._sb_lbl(rp, "SAVED FILES")
        
        self.files_frame = ctk.CTkScrollableFrame(
            rp, fg_color=T["SURFACE2"], height=110, corner_radius=4,
            border_width=1, border_color=T["BORDER"],
            scrollbar_button_color=T["BORDER"],
        )
        self.files_frame.pack(fill="x", padx=16, pady=(6, 14))
        self._reg_frame(self.files_frame, "fg_color", "SURFACE2")
        
        self._refresh_files_list()

        # ── MAIN CHAT PANEL ───────────────────────────────────────────────────
        self._main_frame = ctk.CTkFrame(self, fg_color=T["BG"], corner_radius=0)
        self._main_frame.pack(side="left", fill="both", expand=True)
        self._reg_frame(self._main_frame, "fg_color", "BG")

        # Greeting
        self.greet_frame = ctk.CTkFrame(self._main_frame, fg_color=T["BG"])
        self.greet_frame.pack(fill="both", expand=True)
        self._reg_frame(self.greet_frame, "fg_color", "BG")

        self._greet_title = self._reg_lbl(
            ctk.CTkLabel(self.greet_frame, text="Hi there",
                         font=ctk.CTkFont(family="Segoe UI", size=38, weight="bold"),
                         text_color=T["TEXT_PRI"]),
            "text_color", "TEXT_PRI")
        self._greet_title.pack(pady=(100, 6))

        self._greet_sub = self._reg_lbl(
            ctk.CTkLabel(self.greet_frame,
                         text="What can I help you with today?",
                         font=ctk.CTkFont(family="Segoe UI", size=16), text_color=T["TEXT_SEC"]),
            "text_color", "TEXT_SEC")
        self._greet_sub.pack()

        chips_row = ctk.CTkFrame(self.greet_frame, fg_color="transparent")
        chips_row.pack(pady=(28, 0))
        for label in ["Draft a document", "Explain code", "Summarise text", "Analyse data"]:
            b = ctk.CTkButton(
                chips_row, text=label,
                fg_color=T["SURFACE"], hover_color=T["SURFACE2"],
                text_color=T["TEXT_SEC"], border_width=1, border_color=T["BORDER"],
                font=ctk.CTkFont(family="Segoe UI", size=12), corner_radius=6, height=34,
                command=lambda l=label: self._chip(l))
            b.pack(side="left", padx=4)
            self._reg_btn(b, fg_color="SURFACE", hover_color="SURFACE2",
                          text_color="TEXT_SEC", border_color="BORDER")

        # Chat scroll
        self.chat_outer = ctk.CTkFrame(self._main_frame, fg_color="transparent")
        self.chat_scroll = ctk.CTkScrollableFrame(
            self.chat_outer, fg_color="transparent",
            scrollbar_button_color=T["BORDER"],
            scrollbar_button_hover_color=T["SURFACE2"],
        )
        self.chat_scroll.pack(fill="both", expand=True, padx=4)

        # Input
        inp_outer = ctk.CTkFrame(self._main_frame, fg_color="transparent")
        inp_outer.pack(fill="x", padx=20, pady=(6, 14))
        self.inp_outer = inp_outer

        self.attach_strip = ctk.CTkFrame(inp_outer, fg_color="transparent")

        self.inp_card = ctk.CTkFrame(inp_outer, fg_color=T["SURFACE"],
                                     corner_radius=6, border_width=1,
                                     border_color=T["BORDER"])
        self.inp_card.pack(fill="x")
        self._reg_frame(self.inp_card, "fg_color", "SURFACE")

        self.inp = ctk.CTkTextbox(
            self.inp_card, height=52, font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="transparent", border_width=0,
            text_color=T["TEXT_PRI"], wrap="word",
        )
        self.inp.pack(fill="x", padx=16, pady=(12, 4))
        self._reg_box(self.inp, text_color="TEXT_PRI")
        
        self.inp.bind("<Return>", self._on_enter)

        bot = ctk.CTkFrame(self.inp_card, fg_color="transparent")
        bot.pack(fill="x", padx=12, pady=(2, 10))

        self.attach_btn = self._reg_btn(
            ctk.CTkButton(bot, text="+", width=32, height=30,
                          font=ctk.CTkFont(family="Segoe UI", size=16),
                          fg_color=T["SURFACE2"], hover_color=T["BORDER"],
                          text_color=T["TEXT_SEC"], border_width=1,
                          border_color=T["BORDER"], corner_radius=4,
                          command=self._attach_file),
            fg_color="SURFACE2", hover_color="BORDER",
            text_color="TEXT_SEC", border_color="BORDER")
        self.attach_btn.pack(side="left", padx=(0, 8))

        self.model_badge = self._reg_lbl(
            ctk.CTkLabel(bot, text=f"  {self._cur['label']}",
                         font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_DIM"]),
            "text_color", "TEXT_DIM")
        self.model_badge.pack(side="left")

        self.send_btn = ctk.CTkButton(
            bot, text="↑", width=34, height=30,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            fg_color=T["ACCENT"], hover_color="#1D4ED8",
            corner_radius=4, command=self._send)
        self.send_btn.pack(side="right")
        self._reg_btn(self.send_btn, fg_color="ACCENT")

        self.stop_btn = ctk.CTkButton(
            bot, text="■", width=34, height=30,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color=T["ERROR"], hover_color="#B91C1C",
            corner_radius=4, command=self._stop)
        self._reg_btn(self.stop_btn, fg_color="ERROR")

    def _sb_lbl(self, parent, text):
        w = self._reg_lbl(
            ctk.CTkLabel(parent, text=text,
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=T["TEXT_DIM"]),
            "text_color", "TEXT_DIM")
        w.pack(anchor="w", padx=(20 if parent == self.sidebar else 16))

    # ──────────────────────────────────────────────────────────────────────────
    # OUTPUT PANE
    # ──────────────────────────────────────────────────────────────────────────
    def _set_output(self, text: str):
        self._last_response = text
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", text)
        self.output_box.configure(state="disabled")

    def _clear_output(self):
        self._last_response = ""
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.configure(state="disabled")

    def _copy_output(self):
        if not self._last_response: return
        self.clipboard_clear(); self.clipboard_append(self._last_response)
        self._set_status("Copied ✓", T["SUCCESS"])
        self.after(2000, lambda: self._set_status("● LM Studio Ready", T["SUCCESS"]))

    def _save_txt(self):
        if not self._last_response: return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All", "*.*")],
            initialfile=f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if path:
            Path(path).write_text(self._last_response, encoding="utf-8")
            self._set_status("Saved TXT ✓", T["SUCCESS"])
            self.after(2000, lambda: self._set_status("● LM Studio Ready", T["SUCCESS"]))
            self._refresh_files_list()

    def _save_pdf(self):
        if not self._last_response: return
        if not PDF_WRITE_OK:
            messagebox.showinfo("Install required", "Run:  pip install fpdf2"); return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf"), ("All", "*.*")],
            initialfile=f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
        if path:
            try:
                pdf = FPDF(); pdf.add_page(); pdf.set_margins(20, 20, 20)
                pdf.set_font("Helvetica", style="B", size=13)
                pdf.set_text_color(30, 30, 30)
                pdf.cell(0, 8, "Local Chatbot — Response", ln=True)
                pdf.set_font("Helvetica", size=9); pdf.set_text_color(120, 120, 120)
                pdf.cell(0, 6, datetime.now().strftime("%d %b %Y  %H:%M"), ln=True)
                pdf.ln(4); pdf.set_draw_color(180, 180, 180)
                pdf.line(20, pdf.get_y(), 190, pdf.get_y()); pdf.ln(6)
                pdf.set_font("Helvetica", size=11); pdf.set_text_color(30, 30, 30)
                for line in self._last_response.split("\n"):
                    pdf.multi_cell(0, 6, line if line else " ")
                pdf.output(path)
                self._set_status("Saved PDF ✓", T["SUCCESS"])
                self.after(2000, lambda: self._set_status("● LM Studio Ready", T["SUCCESS"]))
                self._refresh_files_list()
            except Exception as e:
                messagebox.showerror("PDF Error", str(e))

    def _refresh_files_list(self):
        for w in self.files_frame.winfo_children(): w.destroy()
        files = sorted(SAVE_DIR.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)[:8]
        if not files:
            self._reg_lbl(
                ctk.CTkLabel(self.files_frame, text="No files yet",
                             font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_DIM"]),
                "text_color", "TEXT_DIM").pack(anchor="w", padx=10, pady=10); return
        for f in files:
            row = ctk.CTkFrame(self.files_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            icon = "📄" if f.suffix == ".pdf" else "💬" if f.suffix == ".json" else "📝"
            self._reg_lbl(
                ctk.CTkLabel(row, text=f"{icon} {f.name[:26]}",
                             font=ctk.CTkFont(family="Segoe UI", size=11), text_color=T["TEXT_SEC"], anchor="w"),
                "text_color", "TEXT_SEC").pack(side="left", fill="x", expand=True, padx=(4, 0))
            self._reg_btn(
                ctk.CTkButton(row, text="↗", width=24, height=22,
                              fg_color="transparent", hover_color=T["BORDER"],
                              text_color=T["TEXT_DIM"], font=ctk.CTkFont(family="Segoe UI", size=11),
                              command=lambda p=f: self._open_file(p)),
                fg_color="transparent", hover_color="BORDER",
                text_color="TEXT_DIM").pack(side="right")

    def _open_file(self, path: Path):
        import os, subprocess, sys
        try:
            if sys.platform == "win32": os.startfile(str(path))
            elif sys.platform == "darwin": subprocess.run(["open", str(path)])
            else: subprocess.run(["xdg-open", str(path)])
        except Exception: pass

    # ──────────────────────────────────────────────────────────────────────────
    # MODEL / PROBE
    # ──────────────────────────────────────────────────────────────────────────
    def _chip(self, label):
        self.inp.delete("1.0", "end")
        self.inp.insert("1.0", label + " ")
        self.inp.focus()

    def _open_picker(self):
        ModelPicker(self.model_btn, self._models, self._cur["id"],
                    self._on_model_select, self.think_var)

    def _on_model_select(self, m):
        self._cur = m
        self.model_btn.configure(text=f"{m['label']}  ▾")
        self.model_badge.configure(text=f"  {m['label']}")
        self.think_var.set("r1" in m["id"].lower() or "deepseek" in m["id"].lower())

    def _probe(self):
        models = fetch_models()
        self._models = models
        if models != FALLBACK:
            self._cur = models[0]
            self.after(0, lambda: self.model_btn.configure(text=f"{self._cur['label']}  ▾"))
            self.after(0, lambda: self.model_badge.configure(text=f"  {self._cur['label']}"))
            self.after(0, lambda: self._set_status("● LM Studio Connected", T["SUCCESS"]))
        else:
            self.after(0, lambda: self._set_status("⚠ LM Studio Not Reachable", T["ERROR"]))

    def _set_status(self, t, c=None):
        if c is None: c = T["SUCCESS"]
        self.status_lbl.configure(text=t, text_color=c)

    # ──────────────────────────────────────────────────────────────────────────
    # RESOURCES
    # ──────────────────────────────────────────────────────────────────────────
    def _poll_resources(self):
        if PSUTIL_OK:
            try:
                cpu = psutil.cpu_percent(interval=None)
                if hasattr(self, 'cpu_util_lbl'): self.cpu_util_lbl.configure(text=f"{cpu:.0f}%")
            except Exception: pass
            try:
                vm = psutil.virtual_memory()
                if hasattr(self, 'ram_util_lbl'): self.ram_util_lbl.configure(text=f"{vm.percent:.0f}%")
            except Exception: pass
        if NVML_OK:
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                i = pynvml.nvmlDeviceGetMemoryInfo(h)
                r = i.used / i.total
                if hasattr(self, 'vram_util_lbl'): self.vram_util_lbl.configure(text=f"{r*100:.0f}%")
            except Exception: pass
        self.after(2000, self._poll_resources)

    # ──────────────────────────────────────────────────────────────────────────
    # CHAT BUBBLES
    # ──────────────────────────────────────────────────────────────────────────
    def _show_chat(self):
        if not self.chat_outer.winfo_ismapped():
            self.greet_frame.pack_forget()
            self.chat_outer.pack(fill="both", expand=True)

    def _scroll_bottom(self):
        self.after(80, lambda: self.chat_scroll._parent_canvas.yview_moveto(1.0))

    def _add_user_bubble(self, text, attach_note=""):
        wrapper = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=(14, 2))
        ctk.CTkFrame(wrapper, fg_color="transparent").pack(side="left", fill="x", expand=True)
        bubble = ctk.CTkFrame(wrapper, fg_color=T["USER_BG"], corner_radius=6,
                              border_width=1, border_color=T["USER_BORD"])
        bubble.pack(side="right")
        ctk.CTkLabel(bubble, text=(text + attach_note).strip(),
                     font=ctk.CTkFont(family="Segoe UI", size=13), text_color=T["TEXT_PRI"],
                     wraplength=480, justify="left", anchor="w").pack(padx=16, pady=12)

    def _add_asst_bubble(self) -> ctk.StringVar:
        wrapper = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=(2, 2))
        ctk.CTkFrame(wrapper, width=3, fg_color=T["ACCENT"],
                     corner_radius=0).pack(side="left", fill="y", padx=(0, 10), pady=4)
        bubble = ctk.CTkFrame(wrapper, fg_color=T["SURFACE"], corner_radius=6)
        bubble.pack(side="left", fill="x", expand=True)
        hdr = ctk.CTkFrame(bubble, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(hdr, text="Assistant", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=T["ASST_LABEL"]).pack(side="left")
        sv  = ctk.StringVar(value="▌")
        lbl = ctk.CTkLabel(bubble, textvariable=sv, font=ctk.CTkFont(family="Segoe UI", size=13),
                           text_color=T["TEXT_PRI"], wraplength=560,
                           justify="left", anchor="w")
        lbl.pack(fill="x", padx=14, pady=(2, 14))
        self._stream_label = lbl
        self._scroll_bottom()
        return sv

    def _add_thinking_bubble(self, thinking: str):
        wrapper = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        wrapper.pack(fill="x", padx=36, pady=(0, 10))
        frame = ctk.CTkFrame(wrapper, fg_color=T["THINK_BG"], corner_radius=6,
                             border_width=1, border_color=T["BORDER"])
        frame.pack(fill="x")
        ctk.CTkLabel(frame, text="⚙  Reasoning trace",
                     font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                     text_color=T["TEXT_DIM"]).pack(anchor="w", padx=14, pady=(8, 2))
        preview = thinking[:500] + ("…" if len(thinking) > 500 else "")
        ctk.CTkLabel(frame, text=preview, font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=T["TEXT_DIM"], wraplength=520,
                     justify="left", anchor="w").pack(fill="x", padx=14, pady=(0, 10))

    # ──────────────────────────────────────────────────────────────────────────
    # FILE ATTACHMENT
    # ──────────────────────────────────────────────────────────────────────────
    IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def _attach_file(self):
        paths = filedialog.askopenfilenames(
            title="Attach files",
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.gif *.webp *.bmp "
                 "*.txt *.py *.js *.ts *.html *.md *.csv *.json *.xml "
                 "*.yaml *.yml *.pdf *.c *.cpp *.java *.rs *.bat *.sh"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("Text / Code", "*.txt *.py *.js *.md *.csv *.json *.xml"),
                ("PDF", "*.pdf"), ("All", "*.*"),
            ],
        )
        for p in paths:
            path = Path(p); ext = path.suffix.lower()
            kind = "image" if ext in self.IMAGE_EXT else ("pdf" if ext == ".pdf" else "text")
            self._attachments.append({"name": path.name, "path": str(path), "kind": kind})
        self._refresh_attach_strip()

    def _refresh_attach_strip(self):
        for w in self.attach_strip.winfo_children(): w.destroy()
        if not self._attachments:
            self.attach_strip.pack_forget(); return
        if not self.attach_strip.winfo_ismapped():
            self.attach_strip.pack(fill="x", pady=(0, 6), before=self.inp_card)
        for i, att in enumerate(self._attachments):
            chip = ctk.CTkFrame(self.attach_strip, fg_color=T["SURFACE2"],
                                corner_radius=4, border_width=1, border_color=T["BORDER"])
            chip.pack(side="left", padx=(0, 6), pady=4)
            icon = "🖼" if att["kind"] == "image" else ("📄" if att["kind"] == "pdf" else "📎")
            ctk.CTkLabel(chip, text=f"{icon} {att['name'][:22]}",
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=T["TEXT_SEC"]).pack(side="left", padx=(8, 2), pady=5)
            ctk.CTkButton(chip, text="✕", width=20, height=20,
                          fg_color="transparent", hover_color=T["BORDER"],
                          text_color=T["TEXT_DIM"], font=ctk.CTkFont(family="Segoe UI", size=10),
                          command=lambda i=i: self._remove_att(i)).pack(side="left", padx=(0, 4))

    def _remove_att(self, idx):
        if 0 <= idx < len(self._attachments): self._attachments.pop(idx)
        self._refresh_attach_strip()

    def _read_attachment(self, att):
        path = Path(att["path"])
        if att["kind"] == "image":
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            b64  = base64.b64encode(path.read_bytes()).decode()
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        if att["kind"] == "pdf":
            if PDF_READ_OK:
                r = pypdf.PdfReader(str(path))
                text = "\n".join(p.extract_text() or "" for p in r.pages)
            else:
                text = "[PDF unavailable — pip install pypdf]"
            return f"\n--- {path.name} ---\n{text}\n---\n"
        try:
            return f"\n--- {path.name} ---\n{path.read_text(encoding='utf-8', errors='replace')}\n---\n"
        except Exception as e:
            return f"\n[Could not read {path.name}: {e}]\n"

    def _build_user_content(self, text):
        extra = ""; imgs = []
        for att in self._attachments:
            r = self._read_attachment(att)
            if isinstance(r, dict): imgs.append(r)
            else: extra += r
        full = (extra + "\n" + text).strip() if extra else text
        return [{"type": "text", "text": full}] + imgs if imgs else full

    # ──────────────────────────────────────────────────────────────────────────
    # SEND / STREAM
    # ──────────────────────────────────────────────────────────────────────────
    def _on_enter(self, event):
        if not (event.state & 0x1):
            self._send(); return "break"

    def _send(self):
        if self._generating: return
        text = self.inp.get("1.0", "end").strip()
        if not text and not self._attachments: return

        self.inp.delete("1.0", "end")
        self._show_chat()
        content = self._build_user_content(text or "(see attached)")
        attach_note = ""
        if self._attachments:
            attach_note = f"\n📎 {', '.join(a['name'] for a in self._attachments)}"

        self._messages.append({"role": "user", "content": content})
        self._msg_count += 1; self._update_turns()

        self._add_user_bubble(text, attach_note)
        self._stream_var = self._add_asst_bubble()

        self._attachments = []; self._refresh_attach_strip()

        sys_p = self.sys_box.get("1.0", "end").strip()
        msgs  = [{"role": "system", "content": sys_p}] + self._messages
        model = self._cur["id"]

        self._generating = True; self._stop_flag = False
        self._parser = ThinkParser()
        self.send_btn.pack_forget(); self.stop_btn.pack(side="right")
        self._set_status("● Generating…", T["WARN"])

        threading.Thread(target=self._stream, args=(model, msgs), daemon=True).start()

    def _stop(self):
        self._stop_flag = True

    def _stream(self, model, msgs):
        fd = ft = ""
        try:
            stream = client.chat.completions.create(
                model=model, messages=msgs, stream=True, max_tokens=CTX)
            for chunk in stream:
                if self._stop_flag: break
                delta = chunk.choices[0].delta.content or ""
                if not delta: continue
                d, t = self._parser.feed(delta)
                fd += d; ft += t
                self.after(0, self._update_stream, fd)
            d, t = self._parser.flush(); fd += d; ft += t
        except APIConnectionError:
            fd = "⚠  Cannot reach LM Studio — is the server running on port 1234?"
            self.after(0, lambda: self._set_status("⚠ LM Studio Not Reachable", T["ERROR"]))
        except Exception as e:
            fd = f"⚠  Error: {e}"

        self._messages.append({"role": "assistant", "content": fd})
        self._msg_count += 1; self._update_turns()
        self.after(0, self._done, fd, ft)

    def _update_stream(self, text):
        if self._stream_var:
            self._stream_var.set(text or "▌")
            if self._stream_label:
                w = self.chat_scroll.winfo_width()
                if w > 100: self._stream_label.configure(wraplength=max(300, w - 140))
            self._scroll_bottom()

    def _done(self, display, thinking):
        self._generating = False
        self.stop_btn.pack_forget(); self.send_btn.pack(side="right")
        self._set_status("● LM Studio Ready", T["SUCCESS"])
        if self._stream_var: self._stream_var.set(display or "")
        self.after(0, self._set_output, display)
        if thinking and self.think_var.get(): self._add_thinking_bubble(thinking)
        self._scroll_bottom()

    # ──────────────────────────────────────────────────────────────────────────
    # CLEAR / SAVE / TURNS
    # ──────────────────────────────────────────────────────────────────────────
    def _clear(self):
        if self._generating: return
        self._messages = []; self._msg_count = 0; self._update_turns()
        for w in self.chat_scroll.winfo_children(): w.destroy()
        self.chat_outer.pack_forget()
        self.greet_frame.pack(fill="both", expand=True)

    def _save(self):
        SAVE_DIR.mkdir(exist_ok=True)
        name = SAVE_DIR / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(name, "w", encoding="utf-8") as f:
            json.dump(self._messages, f, ensure_ascii=False, indent=2)
        self._set_status("Saved ✓", T["SUCCESS"])
        self.after(2000, lambda: self._set_status("● LM Studio Ready", T["SUCCESS"]))
        self._refresh_files_list()

    def _update_turns(self):
        self.turns_lbl.configure(text=f"{self._msg_count} messages")


if __name__ == "__main__":
    app = App()
    app.mainloop()