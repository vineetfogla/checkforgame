#!/usr/bin/env python3
"""
MemoryGameV17ToastOnly.py

- True-rank-preserving live search
- All rating/feedback removed
- After Game Over: show only a centered toast (2s) sized ~230x230 px (approx 6cm x 6cm)
- Game window stays open (player can close manually)
- Theme and leaderboard UI preserved
"""

import tkinter as tk
from tkinter import ttk, simpledialog
import json
import os
import random
import re
import uuid
import shutil

LEADERBOARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard.json")
ADMIN_PASSWORD = "shriram999"

APP_TITLE = "Memory Grid Game-An Interactive Python Project"
FONT_NAME = "Segoe UI"
BG = "#0A1426"
CARD_BLUE = "#243B5C"
GOLD = "#FFD700"
SILVER = "#C0C0C0"
BRONZE = "#CD7F32"
ACCENT = "#5E9BFF"

DEFAULT_GRID_N = 4
POINTS_PER_LEVEL = 10

# --- Utilities ----------------------------------------------------------------
def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass



def _identity_text(value):
    """Normalize identity fields so capitalization and extra spaces do not create new profiles."""
    return " ".join(str(value or "").strip().casefold().split())


def merge_duplicate_profiles(entries):
    """Merge profiles sharing a stable identity; retain the best score and all recorded attempts."""
    merged = []
    index_by_key = {}

    for original in entries:
        entry = dict(original)
        role = entry.get("role", "")
        if role == "Student":
            # In a school, school + class + section + roll is the stable student identifier.
            key = ("Student", _identity_text(entry.get("school")),
                   _identity_text(entry.get("class")), _identity_text(entry.get("section")),
                   _identity_text(entry.get("roll")))
            if not key[-1] or key[-1] == "-":
                key = ("Student-name", _identity_text(entry.get("name")),
                       _identity_text(entry.get("class")), _identity_text(entry.get("school")))
        else:
            key = (role, _identity_text(entry.get("name")))

        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(entry)
            continue

        existing_index = index_by_key[key]
        existing = merged[existing_index]
        # Keep the profile with the highest score/name as the primary record.
        if int(entry.get("score", 0) or 0) > int(existing.get("score", 0) or 0):
            primary, secondary = entry, existing
        else:
            primary, secondary = existing, entry

        primary["score"] = max(int(existing.get("score", 0) or 0),
                               int(entry.get("score", 0) or 0))
        primary["times_played"] = (int(existing.get("times_played", 0) or 0) +
                                   int(entry.get("times_played", 0) or 0))
        for field in ("school", "class", "section", "roll", "uid"):
            if not primary.get(field) and secondary.get(field):
                primary[field] = secondary[field]
        merged[existing_index] = primary

    return merged

def normalize_name(s: str) -> str:
    return " ".join(w.capitalize() for w in s.strip().split())

def is_valid_name(s: str) -> bool:
    s2 = s.strip()
    if not s2:
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z\s'\-]*$", s2))

def validate_name_entry(new_value: str) -> bool:
    if new_value == "":
        return True
    return bool(re.match(r"^[A-Za-z\s'\-]*$", new_value))

# --- Modal helpers (replace messagebox) --------------------------------------
def center_modal(parent, title, body, width=420, height=160, auto_close=None, ok_only=True, buttons=None):
    dlg = tk.Toplevel(parent)
    dlg.transient(parent)
    dlg.title(title)
    dlg.configure(bg="#1B2E4B")
    dlg.resizable(False, False)
    try:
        pwx = parent.winfo_rootx(); pwy = parent.winfo_rooty(); pww = parent.winfo_width(); pwh = parent.winfo_height()
        x = pwx + (pww - width)//2; y = pwy + (pwh - height)//2
        dlg.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        dlg.geometry(f"{width}x{height}")
    dlg.grab_set()
    dlg.protocol("WM_DELETE_WINDOW", lambda: None)

    frm = tk.Frame(dlg, bg="#1B2E4B", padx=12, pady=12)
    frm.pack(expand=True, fill="both")
    tk.Label(frm, text=title, bg="#1B2E4B", fg=ACCENT, font=(FONT_NAME, 12, "bold")).pack(anchor="w")
    tk.Label(frm, text=body, bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME, 10), wraplength=width-24, justify="left").pack(anchor="w", pady=(8,8))

    result = {"clicked": None}
    btn_frame = tk.Frame(frm, bg="#1B2E4B")
    btn_frame.pack(anchor="e", pady=(6,0))
    def on_ok():
        result["clicked"] = "ok"
        dlg.grab_release(); dlg.destroy()

    if buttons:
        for (lbl, cb) in buttons:
            def make_cb(c=cb):
                def run():
                    result["clicked"] = lbl
                    try:
                        c()
                    except Exception:
                        pass
                    dlg.grab_release(); dlg.destroy()
                return run
            tk.Button(btn_frame, text=lbl, command=make_cb(), bg=ACCENT, fg="#F5F8FF").pack(side="right", padx=6)
    else:
        if ok_only:
            tk.Button(btn_frame, text="OK", command=on_ok, bg=ACCENT, fg="#F5F8FF").pack()

    if auto_close:
        dlg.after(int(auto_close*1000), lambda: (dlg.grab_release(), dlg.destroy()))
        parent.wait_window(dlg)
        return result.get("clicked")
    else:
        parent.wait_window(dlg)
        return result.get("clicked")

def confirm_modal(parent, title, body):
    res = {"ok": False}
    def set_ok():
        res["ok"] = True
    # Use a taller, clearly labelled confirmation dialog. The previous fixed
    # 160px dialog could push its buttons below the visible area when a bulk
    # delete listed many student names.
    center_modal(parent, title, body, width=440, height=220,
                 buttons=[("Delete", set_ok), ("Cancel", lambda: None)])
    return res["ok"]

# --- Main App ----------------------------------------------------------------


class GlassPanel(tk.Frame):
    """Rounded, tinted glass-style panel for the homepage (Tkinter approximation)."""
    def __init__(self, parent, tint="#1B2D49", radius=26, padding=16, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), bd=0, **kwargs)
        self.tint = tint
        self.radius = radius
        self.padding = padding
        self.canvas = tk.Canvas(self, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(self.canvas, bg=tint, bd=0)
        self.window = self.canvas.create_window((padding, padding), anchor="nw", window=self.content)
        self.canvas.bind("<Configure>", self._redraw)
        self.content.bind("<Configure>", self._content_changed)
        self.after_idle(self._content_changed)

    def _rounded(self, x1, y1, x2, y2, r, **kw):
        r = min(r, max(4, (x2-x1)//2), max(4, (y2-y1)//2))
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.canvas.create_polygon(pts, smooth=True, splinesteps=24, **kw)

    def _redraw(self, _event=None):
        w=max(40,self.canvas.winfo_width()); h=max(40,self.canvas.winfo_height())
        self.canvas.delete("glass-bg")
        # Soft offset edge + tinted surface + top sheen: layered glass-like depth.
        self._rounded(3,5,w-3,h-2,self.radius,fill="#0A1425",outline="",tags="glass-bg")
        self._rounded(2,2,w-5,h-5,self.radius,fill=self.tint,outline="#6F8EBA",width=1.4,tags="glass-bg")
        self._rounded(9,7,w-12,max(18,min(34,h//4)),max(8,self.radius-10),
                      fill="#294567",outline="",tags="glass-bg")
        self.canvas.tag_lower("glass-bg")
        self.canvas.coords(self.window,self.padding,self.padding)
        self.canvas.itemconfigure(self.window,width=max(20,w-2*self.padding))

    def _content_changed(self, _event=None):
        self.after_idle(self._fit_height)

    def _fit_height(self):
        try:
            req=max(40,self.content.winfo_reqheight()+2*self.padding)
            self.canvas.configure(height=req)
            self._redraw()
        except tk.TclError:
            pass


class MemoryGameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=BG)
        # Dark, glass-inspired ttk controls for the main application (game board is separate).
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox", fieldbackground="#203750", background="#29435E",
                        foreground="#F5F8FF", arrowcolor="#DCEBFA", bordercolor="#58799A",
                        lightcolor="#58799A", darkcolor="#17283D", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#203750")],
                  foreground=[("readonly", "#F5F8FF")],
                  selectbackground=[("readonly", "#176BC1")],
                  selectforeground=[("readonly", "#FFFFFF")])
        style.configure("Vertical.TScrollbar", background="#29435E", troughcolor="#142338",
                        bordercolor="#142338", arrowcolor="#DCEBFA")
        self.geometry("1240x800")
        self.minsize(1000, 680)

        loaded_leaderboard = load_json(LEADERBOARD_FILE) or []
        self.leaderboard = merge_duplicate_profiles(loaded_leaderboard)
        if len(self.leaderboard) < len(loaded_leaderboard):
            backup_path = LEADERBOARD_FILE + ".before_deduplication.bak"
            if not os.path.exists(backup_path):
                shutil.copy2(LEADERBOARD_FILE, backup_path)
            save_json(LEADERBOARD_FILE, self.leaderboard)
        # ensure uid and times_played exist
        changed = False
        for e in self.leaderboard:
            if e.get("role") == "Student" and not e.get("player_id"):
                e["player_id"] = str(uuid.uuid4()); changed = True
            if "uid" not in e:
                e["uid"] = str(uuid.uuid4()); changed = True
            if "times_played" not in e:
                e["times_played"] = 0; changed = True
        if changed:
            save_json(LEADERBOARD_FILE, self.leaderboard)

        self.player = None
        self.admin = False
        self.grid_n = DEFAULT_GRID_N
        self.delete_mode = False
        self.delete_map = {}

        # validation
        self.vcmd_name = (self.register(validate_name_entry), "%P")
        self.vcmd_roll = (self.register(lambda P: P.isdigit() or P == ""), "%P")

        # layout columns
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # frames
        self.left_frame = tk.Frame(self, bg=BG)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.right_frame = tk.Frame(self, bg=BG)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=12)

        self._build_left()
        self._build_right()

        self.after(150, self.refresh_leaderboard)

    # ----------------- Left side (form + info) -----------------
    def _build_left(self):
        tk.Label(self.left_frame, text="Memory Grid Game", bg=BG, fg="#F5F8FF",
                 font=(FONT_NAME, 25, "bold")).pack(anchor="nw")
        tk.Label(self.left_frame, text="     by Vineet Fogla", bg=BG, fg="#FFD54A",
                 font=(FONT_NAME, 15, "bold italic")).pack(anchor="nw", pady=(0, 2))
        tk.Label(self.left_frame, text="A brighter way to challenge your memory",
                 bg=BG, fg="#B5C7DC", font=(FONT_NAME, 11)).pack(anchor="nw", pady=(1, 4))
        form_glass = GlassPanel(self.left_frame, tint="#1B2E4B", radius=30, padding=17)
        form_glass.pack(fill="x", pady=(10, 14))
        form_card = form_glass.content
        form_card.configure(bg="#1B2E4B")
        tk.Label(form_card, text="PLAYER DETAILS", bg="#1B2E4B", fg=ACCENT,
                 font=(FONT_NAME, 10, "bold")).grid(row=0, column=0, sticky="w")
        already_btn = tk.Button(form_card, text="Already a player?  Find your name  →",
                                command=self._choose_existing_player,
                                bg="#294B70", fg="#F5F8FF", activebackground="#37638F",
                                activeforeground="#FFFFFF", relief="flat", bd=0,
                                padx=13, pady=7, font=(FONT_NAME, 9, "bold"), cursor="hand2")
        already_btn.grid(row=0, column=1, columnspan=3, sticky="e", padx=(8, 0))
        form_card.grid_columnconfigure(1, weight=1)
        self.role_var = tk.StringVar(value="Student")
        roles_frame = tk.Frame(form_card, bg="#1B2E4B")
        roles_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 2))
        for i, role in enumerate(["Student", "Parent/Guardian", "Teacher"]):
            tk.Radiobutton(roles_frame, text=role, variable=self.role_var, value=role,
                           bg="#1B2E4B", fg="#F5F8FF", selectcolor="#29435E",
                           activebackground="#17283D", activeforeground="#087AFF",
                           font=(FONT_NAME, 11), command=self._on_role_change).pack(
                               side="left", padx=(0 if i == 0 else 14, 0))
        self.form_area = tk.Frame(form_card, bg="#1B2E4B")
        self.form_area.grid(row=2, column=0, columnspan=4, pady=(10, 0), sticky="ew")
        self._build_student_form()
        self._build_parent_form()
        self._build_teacher_form()
        self._on_role_change()
        self.proceed_row = tk.Frame(form_card, bg="#1B2E4B")
        self.proceed_row.grid(row=4, column=0, columnspan=4, pady=(14, 0), sticky="w")
        tk.Label(self.proceed_row, text="🎮", bg="#1B2E4B", fg="#087AFF",
                 font=(FONT_NAME, 16), width=2, height=1).pack(side="left", padx=(0, 8))
        tk.Button(self.proceed_row, text="Proceed to Game", bg=ACCENT, fg="#102033",
                  activebackground="#168CFF", activeforeground="#FFFFFF",
                  relief="flat", padx=16, pady=8, font=(FONT_NAME, 12, "bold"),
                  cursor="hand2", command=self._on_proceed).pack(side="left")
        grid_glass = GlassPanel(self.proceed_row, tint="#294567", radius=18, padding=8)
        grid_glass.configure(width=178, height=48)
        grid_glass.pack_propagate(False)
        grid_glass.canvas.configure(width=178)
        grid_glass.pack(side="left", padx=(10, 0))
        self.grid_settings_frame = grid_glass.content
        self.grid_settings_frame.configure(bg="#294567")
        tk.Button(self.proceed_row, text="Edit Existing Profile", bg="#29435E", fg="#F5F8FF",
                  activebackground="#536F8D", activeforeground="#FFFFFF", relief="flat",
                  padx=10, pady=8, font=(FONT_NAME, 9, "bold"), cursor="hand2",
                  command=self._edit_current_student_profile).pack(side="left", padx=(10, 0))
        self.grid_size_lbl = tk.Label(self.grid_settings_frame, text="Grid size:",
                                      bg="#1B2E4B", fg="#E1EAF5", font=(FONT_NAME, 10, "bold"))
        self.grid_size_lbl.pack(side="left", padx=(0, 8))
        self.grid_size_cb = ttk.Combobox(self.grid_settings_frame,
                                         values=[str(i) for i in range(3, 16)],
                                         width=5, state="readonly")
        self.grid_size_cb.set(str(self.grid_n))
        self.grid_size_cb.bind("<<ComboboxSelected>>", lambda e: self._on_grid_size_change())
        self.grid_size_cb.pack(side="left")
        # Grid size is a player setting, so it remains available outside admin mode.
        info_glass = GlassPanel(self.left_frame, tint="#203653", radius=30, padding=16)
        info_glass.pack(fill="both", expand=True, pady=(0, 4))
        info_card = info_glass.content
        info_card.configure(bg="#203653")
        self.grid_info_lbl = tk.Label(
            info_card, text=f"Grid: {self.grid_n} × {self.grid_n}. Each completed level = {POINTS_PER_LEVEL} points.",
            bg="#203653", fg="#E1EAF5", font=(FONT_NAME, 11))
        self.grid_info_lbl.pack(anchor="nw")
        self.last_score_lbl = tk.Label(info_card, text="Last Score: -",
                                       bg="#203653", fg="#E1EAF5", font=(FONT_NAME, 11))
        self.last_score_lbl.pack(anchor="nw", pady=(8, 0))

    def _build_student_form(self):
        f = tk.Frame(self.form_area, bg="#1B2E4B")
        tk.Label(f, text="Student Name:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=0, column=0, sticky="w")
        self.student_name_var = tk.StringVar()
        tk.Entry(f, textvariable=self.student_name_var, width=32, font=(FONT_NAME,14), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                  highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF",
                  validate="key", validatecommand=self.vcmd_name).grid(row=0, column=1, padx=6, pady=6)

        tk.Label(f, text="Class:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=1, column=0, sticky="w")
        classes = ["LKG","UKG"] + [str(i) for i in range(1,13)]
        self.class_var = tk.StringVar(value=classes[0])
        ttk.Combobox(f, values=classes, textvariable=self.class_var, state="readonly", width=10, font=(FONT_NAME,11)).grid(row=1, column=1, padx=6, pady=6, sticky="w")

        tk.Label(f, text="Section:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=2, column=0, sticky="w")
        self.section_var = tk.StringVar(value="A")
        ttk.Combobox(f, values=["A","B","C"], textvariable=self.section_var, state="readonly", width=6, font=(FONT_NAME,11)).grid(row=2, column=1, padx=6, pady=6, sticky="w")

        tk.Label(f, text="Roll No.:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=3, column=0, sticky="w")
        self.roll_var = tk.StringVar()
        tk.Entry(f, textvariable=self.roll_var, validate="key", validatecommand=self.vcmd_roll, width=12, font=(FONT_NAME,13), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                      highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF").grid(row=3, column=1, padx=6, pady=6, sticky="w")

        tk.Label(f, text="School Name:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=4, column=0, sticky="w")
        self.school_var = tk.StringVar(value="DAV SDPS Public School")
        sf = tk.Frame(f, bg="#1B2E4B")
        sf.grid(row=4, column=1, columnspan=3, sticky="w")
        tk.Radiobutton(sf, text="DAV SDPS Public School", variable=self.school_var, value="DAV SDPS Public School", command=self._on_school_change, bg="#1B2E4B", fg="#F5F8FF", selectcolor="#29435E", font=(FONT_NAME,11)).pack(side="left")
        tk.Radiobutton(sf, text="Other", variable=self.school_var, value="Other",
                       bg="#1B2E4B", fg="#F5F8FF", selectcolor="#29435E", font=(FONT_NAME,11), command=self._on_school_change).pack(side="left", padx=8)
        self.other_school_var = tk.StringVar()
        self.other_school_entry = tk.Entry(f, textvariable=self.other_school_var, width=28, font=(FONT_NAME,13), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                      highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF")

        self.student_frame = f

    def _build_parent_form(self):
        f = tk.Frame(self.form_area, bg="#1B2E4B")
        tk.Label(f, text="Parent/Guardian Name:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=0, column=0, sticky="w")
        self.parent_name_var = tk.StringVar()
        tk.Entry(f, textvariable=self.parent_name_var, width=32, font=(FONT_NAME,13), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                  highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF",
                  validate="key", validatecommand=self.vcmd_name).grid(row=0, column=1, padx=6, pady=6)
        self.parent_frame = f

    def _build_teacher_form(self):
        f = tk.Frame(self.form_area, bg="#1B2E4B")
        tk.Label(f, text="Teacher Name:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,12)).grid(row=0, column=0, sticky="w")
        self.teacher_name_var = tk.StringVar()
        tk.Entry(f, textvariable=self.teacher_name_var, width=32, font=(FONT_NAME,13), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                  highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF",
                  validate="key", validatecommand=self.vcmd_name).grid(row=0, column=1, padx=6, pady=6)
        tk.Label(f, text="School Name:", bg="#1B2E4B", fg="#F5F8FF", font=(FONT_NAME,11)).grid(row=1, column=0, sticky="w")
        self.teacher_school_var = tk.StringVar(value="DAV SDPS Public School")
        tsf = tk.Frame(f, bg="#1B2E4B"); tsf.grid(row=1, column=1, sticky="w")
        tk.Radiobutton(tsf, text="DAV SDPS Public School", variable=self.teacher_school_var, value="DAV SDPS Public School", bg="#1B2E4B", fg="#F5F8FF", selectcolor="#29435E", font=(FONT_NAME,11), command=self._on_teacher_school_change).pack(side="left")
        tk.Radiobutton(tsf, text="Other", variable=self.teacher_school_var, value="Other", bg="#1B2E4B", fg="#F5F8FF", selectcolor="#29435E", font=(FONT_NAME,11), command=self._on_teacher_school_change).pack(side="left", padx=8)
        self.teacher_other_var = tk.StringVar()
        self.teacher_other_entry = tk.Entry(f, textvariable=self.teacher_other_var, width=28, font=(FONT_NAME,13), bd=0, relief="flat", bg="#263D5C", fg="#FFFFFF", insertbackground="#FFFFFF",
                      highlightthickness=1, highlightbackground="#58799A", highlightcolor="#0A84FF")
        self.teacher_frame = f

    def _reset_all_input_fields(self):
        try:
            self.student_name_var.set("")
            self.parent_name_var.set("")
            self.teacher_name_var.set("")
        except Exception:
            pass
        try:
            self.class_var.set("LKG")
            self.section_var.set("A")
            self.roll_var.set("")
            self.school_var.set("DAV SDPS Public School")
            self.other_school_var.set("")
            self.teacher_school_var.set("DAV SDPS Public School")
            self.teacher_other_var.set("")
        except Exception:
            pass

    def _on_role_change(self):
        self._reset_all_input_fields()
        for w in self.form_area.winfo_children():
            w.pack_forget()
            w.grid_forget()
        r = self.role_var.get()
        if r == "Student":
            self.student_frame.pack(fill="x", pady=4)
            self._on_school_change()
        elif r == "Parent/Guardian":
            self.parent_frame.pack(fill="x", pady=4)
        else:
            self.teacher_frame.pack(fill="x", pady=4)

    def _on_school_change(self):
        try:
            self.other_school_entry.grid_forget()
        except Exception:
            pass
        if getattr(self, "school_var", None) and self.school_var.get() == "Other":
            try:
                self.other_school_entry.grid(row=5, column=1, padx=6, pady=6, sticky="w")
            except Exception:
                pass

    def _on_teacher_school_change(self):
        try:
            self.teacher_other_entry.grid_forget()
        except Exception:
            pass
        if getattr(self, "teacher_school_var", None) and self.teacher_school_var.get() == "Other":
            try:
                self.teacher_other_entry.grid(row=2, column=1, padx=6, pady=6, sticky="w")
            except Exception:
                pass

    # ----------------- Right side (leaderboard + admin) -----------------
    def _build_right(self):
        header_glass = GlassPanel(self.right_frame, tint="#243D60", radius=24, padding=5)
        header_glass.pack(fill="x", pady=(0, 7))
        header = header_glass.content
        tk.Label(header, text="🏆  LEADERBOARD  🏆", bg="#243D60", fg="#F5F8FF",
                 font=(FONT_NAME,16,"bold")).pack(padx=8, pady=10)

        ctrl = tk.Frame(self.right_frame, bg=BG)
        ctrl.pack(fill="x", pady=(8, 3))

        # Keep the search row separate from admin actions so controls never get squeezed.
        self.admin_btn = tk.Button(ctrl, text="Admin Login", bg=ACCENT, fg="#FFFFFF",
                                   activebackground="#347FD8", relief="flat", padx=12, pady=7,
                                   font=(FONT_NAME, 9, "bold"), cursor="hand2", command=self._admin_login)
        self.admin_btn.pack(side="left", padx=(5, 8))
        self.lock_admin_btn = tk.Button(ctrl, text="Lock Admin", bg="#29435E", fg="#F5F8FF",
                                        activebackground="#3B5B7D", relief="flat", padx=12, pady=7,
                                        font=(FONT_NAME, 9, "bold"), cursor="hand2", command=self._lock_admin)
        self.admin_tools = tk.Frame(self.right_frame, bg=BG)

        # Build a search frame (icon + entry + inline clear) placed to the right of admin button
        self.search_frame = tk.Frame(ctrl, bg=BG)
        self.search_frame.pack(side="left", padx=(6,6))
        self.search_icon = tk.Label(self.search_frame, text="🔍", bg="#263D5C", fg="#F5F8FF", font=(FONT_NAME,10))
        self.search_icon.pack(side="left", padx=(4,4))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, font=(FONT_NAME,11), width=22,
                                     relief="flat", bd=0, bg="#263D5C", fg="#FFFFFF",
                                     insertbackground="#FFFFFF", highlightthickness=1,
                                     highlightbackground="#58799A", highlightcolor="#0A84FF")
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self._live_search())
        # clear button inside search (initially hidden)
        self.search_clear_btn = tk.Button(self.search_frame, text="✖", command=self._clear_search_small, bg="#ff4b4b", fg="#17283D", bd=0)
        # do not pack clear yet; will show only when user types
        self.search_var.trace_add("write", lambda *a: self._update_search_clear_visibility())

        # Admin-only buttons (created but not packed)
        admin_btn_style = {"relief":"flat", "bd":0, "padx":14, "pady":8,
                           "font":(FONT_NAME, 9, "bold"), "cursor":"hand2"}
        self.remove_student_btn = tk.Button(self.admin_tools, text="Remove Student", bg="#344F70", fg="#FFFFFF",
                                            activebackground="#46688F", command=self._toggle_delete_mode,
                                            **admin_btn_style)
        self.delete_selected_btn = tk.Button(self.admin_tools, text="Delete Selected", bg="#B83F50", fg="#FFFFFF",
                                             activebackground="#D45464", command=self._delete_selected,
                                             **admin_btn_style)
        self.clear_btn = tk.Button(self.admin_tools, text="Clear Leaderboard", bg="#873B48", fg="#FFFFFF",
                                   activebackground="#A64B59", command=self._clear_leaderboard,
                                   **admin_btn_style)

        # leaderboard canvas
        self.lb_canvas = tk.Canvas(self.right_frame, bg="#101E33", highlightthickness=0)
        self.lb_scroll = ttk.Scrollbar(self.right_frame, orient="vertical", command=self.lb_canvas.yview)
        self.lb_canvas.configure(yscrollcommand=self.lb_scroll.set)
        self.lb_scroll.pack(side="right", fill="y")
        self.lb_canvas.pack(fill="both", expand=True)
        self.lb_frame = tk.Frame(self.lb_canvas, bg="#101E33")
        self.lb_window = self.lb_canvas.create_window((0,0), window=self.lb_frame, anchor="nw")
        self.lb_frame.bind("<Configure>", lambda e: self.lb_canvas.configure(scrollregion=self.lb_canvas.bbox("all")))
        self.lb_canvas.bind("<Configure>", lambda e: self.lb_canvas.itemconfig(self.lb_window, width=e.width))
        self.lb_canvas.bind("<Enter>", lambda e: self.lb_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.lb_canvas.bind("<Leave>", lambda e: self.lb_canvas.unbind_all("<MouseWheel>"))

    # -------------- Search helpers --------------
    def _update_search_clear_visibility(self):
        txt = self.search_var.get()
        if txt and not getattr(self.search_clear_btn, "_visible", False):
            try:
                self.search_clear_btn.pack(side="left", padx=(4,2))
            except Exception:
                pass
            self.search_clear_btn._visible = True
        if not txt and getattr(self.search_clear_btn, "_visible", False):
            try:
                self.search_clear_btn.pack_forget()
            except Exception:
                pass
            try:
                delattr(self.search_clear_btn, "_visible")
            except Exception:
                try:
                    self.search_clear_btn._visible = False
                except Exception:
                    pass

    def _clear_search_small(self):
        self.search_var.set("")
        self._live_search()

    def _live_search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            self.refresh_leaderboard()
            return

        # sort full leaderboard by score first (main order)
        sorted_full = sorted(self.leaderboard, key=lambda e: (-e.get("score", 0), e.get("name", "")))

        # find matching entries but preserve their actual rank index from sorted_full
        matches = []
        for idx, e in enumerate(sorted_full, start=1):
            if q in e.get("name", "").lower():
                e_copy = e.copy()
                e_copy["_true_rank"] = idx  # store actual rank
                matches.append(e_copy)

        # render leaderboard using true ranks (sorted by actual rank so gaps remain)
        matches = sorted(matches, key=lambda x: x.get("_true_rank", 99999))
        self._render_leaderboard(entries=matches, show_true_rank=True)

    def _on_mousewheel(self, event):
        try:
            delta = int(-1 * (event.delta / 120))
        except Exception:
            delta = -1 if event.delta < 0 else 1
        self.lb_canvas.yview_scroll(delta, "units")

    # ----------------- Leaderboard rendering -----------------
    def refresh_leaderboard(self):
        for e in self.leaderboard:
            uid = e.get("uid")
            if uid not in self.delete_map:
                self.delete_map[uid] = False
        self.leaderboard.sort(key=lambda e: (-e.get("score", 0), e.get("name", "")))
        self._render_leaderboard()
        self.lb_canvas.update_idletasks()

    def _render_leaderboard(self, entries=None, show_true_rank=False):
        if entries is None:
            entries = self.leaderboard
        for child in self.lb_frame.winfo_children():
            child.destroy()

        cw = max(300, self.lb_canvas.winfo_width())
        for idx, entry in enumerate(entries, start=1):
            rank_num = entry.get("_true_rank", idx) if show_true_rank else idx
            uid = entry.get("uid")
            row = tk.Frame(self.lb_frame, bg="#101E33")
            row.pack(fill="x", pady=(0, 11), padx=8)

            toggle_w = 42
            if self.admin and self.delete_mode:
                tcv = tk.Canvas(row, width=toggle_w, height=48, bg="#101E33", highlightthickness=0)
                tcv.pack(side="left", padx=(3, 7), pady=3)
                def draw_toggle(canvas, state=False):
                    canvas.delete("all")
                    canvas.create_oval(4,4,toggle_w-4,toggle_w-4,fill="#263D5C",outline="#A9C4E8",width=2)
                    if state:
                        canvas.create_oval(9,9,toggle_w-9,toggle_w-9,fill="#0A84FF",outline="")
                draw_toggle(tcv, self.delete_map.get(uid, False))
                def on_toggle(ev, canv=tcv, uid_local=uid):
                    self.delete_map[uid_local] = not self.delete_map.get(uid_local, False)
                    draw_toggle(canv, self.delete_map[uid_local])
                    self.delete_selected_btn.config(state="normal" if any(self.delete_map.values()) else "disabled")
                tcv.bind("<Button-1>", on_toggle)
            else:
                tk.Frame(row, width=toggle_w, bg="#101E33").pack(side="left")

            height = 116 if self.admin and entry.get("role") == "Student" else 98
            c = tk.Canvas(row, height=height, bg="#101E33", highlightthickness=0, bd=0)
            c.pack(fill="x", expand=True)
            c.update_idletasks()
            card_w = max(250, c.winfo_width()-8)
            x1,y1,x2,y2 = 4,4,card_w,height-4

            # Top three use dark tinted medal colours, not bright flat blocks.
            tint = {1:"#493B27", 2:"#34445A", 3:"#49352E"}.get(rank_num, "#203653")
            edge = {1:"#E7C56A", 2:"#AFC6E2", 3:"#D49A72"}.get(rank_num, "#49698F")
            self._draw_rounded_rect(c,x1+2,y1+3,x2,y2,22,fill="#091426",outline="")
            self._draw_rounded_rect(c,x1,y1,x2-2,y2-3,22,fill=tint,outline=edge,width=1.5)
            # faint glass sheen across the top edge
            sheen = {1:"#6A5734", 2:"#536780", 3:"#68483C"}.get(rank_num, "#344D6B")
            self._draw_rounded_rect(c,x1+7,y1+5,x2-10,y1+20,12,fill=sheen,outline="")

            cy=(y1+y2)//2-1
            badge_cx=x1+38
            medal = {1:"🥇",2:"🥈",3:"🥉"}.get(rank_num)
            c.create_oval(badge_cx-23,cy-23,badge_cx+23,cy+23,fill="#14243B",outline=edge,width=2)
            if medal:
                c.create_text(badge_cx,cy,text=medal,font=(FONT_NAME,17),fill="#FFFFFF")
            else:
                c.create_text(badge_cx,cy,text=str(rank_num),font=(FONT_NAME,13,"bold"),fill="#F4F7FF")

            name_x=x1+76
            score_x=x2-18
            name_y=cy-17 if height>90 else cy-11
            c.create_text(name_x,name_y,anchor="w",text=entry.get("name",""),
                          font=(FONT_NAME,12,"bold"),fill="#FFFFFF",width=max(100,card_w-190))
            plays = int(entry.get("times_played", 0) or 0)
            c.create_text(name_x,cy+5,anchor="w",
                          text=f"{entry.get('role','')}  ·  Played {plays} time{'s' if plays != 1 else ''}",
                          font=(FONT_NAME,9),fill="#D6E4F6")
            if self.admin and entry.get("role")=="Student":
                detail=f"{entry.get('school','-')}  ·  Class {entry.get('class','-')}  ·  Section {entry.get('section','-')}  ·  Roll {entry.get('roll','-')}"
                c.create_text(name_x,cy+27,anchor="w",text=detail,font=(FONT_NAME,8),
                              fill="#C8D9EE",width=max(100,card_w-190))
            elif self.admin and entry.get("role")=="Teacher":
                c.create_text(name_x,cy+25,anchor="w",text=f"School: {entry.get('school','-')}",
                              font=(FONT_NAME,8),fill="#C8D9EE")
            # Show the circular play-count badge only after the first play.
            play_count = max(0, int(entry.get("times_played", 0) or 0))
            if play_count > 1:
                play_cx = x2 - 25
                play_cy = y1 + 22
                c.create_oval(play_cx-15, play_cy-15, play_cx+15, play_cy+15,
                              fill="#000000", outline="#A9C9EA", width=1.5)
                c.create_text(play_cx, play_cy, text=str(play_count),
                              font=(FONT_NAME,9,"bold"), fill="#FFFFFF")
            c.create_text(score_x,cy+10,anchor="e",text=f"{entry.get('score',0)} pts",
                          font=(FONT_NAME,11,"bold"),fill="#FFFFFF")

        self.lb_frame.update_idletasks()
        self.lb_canvas.configure(scrollregion=self.lb_canvas.bbox("all"))

    def _draw_rounded_rect(self, canvas, x1,y1,x2,y2, r, **kwargs):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return canvas.create_polygon(pts, smooth=True, **kwargs)

    # ----------------- Admin & controls -----------------
    def _admin_login(self):
        pwd = simpledialog.askstring("Admin Login", "Enter admin password:", show="*")
        if pwd is None:
            return
        if pwd == ADMIN_PASSWORD:
            self.admin = True
            self.admin_btn.pack_forget()
            self.lock_admin_btn.pack(side="left", padx=(0, 8))
            self.admin_tools.pack(fill="x", pady=(2, 8))
            for btn in (self.remove_student_btn, self.delete_selected_btn, self.clear_btn):
                btn.pack(side="left", padx=(5, 7), pady=2)
            self.delete_selected_btn.config(state="disabled")
            self.refresh_leaderboard()
            center_modal(self, "Admin", "Access granted.", width=360, height=120, auto_close=1.2)
        else:
            center_modal(self, "Admin", "Incorrect password.", width=360, height=120, auto_close=1.4)

    def _lock_admin(self):
        if not self.admin:
            return
        self.admin = False
        self.delete_mode = False
        for k in list(self.delete_map.keys()):
            self.delete_map[k] = False
        self.lock_admin_btn.pack_forget()
        self.admin_tools.pack_forget()
        for widget in (self.remove_student_btn, self.delete_selected_btn, self.clear_btn):
            widget.pack_forget()
        self.admin_btn.pack(side="left", padx=(5, 8))
        self.refresh_leaderboard()
        center_modal(self, "Admin", "Admin locked.", width=360, height=120, auto_close=1.2)

    def _toggle_delete_mode(self):
        if not self.admin:
            center_modal(self, "Admin", "Login first.", width=360, height=120, auto_close=1.2)
            return
        self.delete_mode = not self.delete_mode
        if self.delete_mode:
            self.delete_selected_btn.config(state="disabled")
            self.remove_student_btn.config(relief="sunken")
        else:
            self.delete_selected_btn.config(state="disabled")
            self.remove_student_btn.config(relief="raised")
            for k in list(self.delete_map.keys()):
                self.delete_map[k] = False
        self.refresh_leaderboard()

    def _delete_selected(self):
        if not self.admin:
            center_modal(self, "Admin", "Login first.", width=360, height=120, auto_close=1.2)
            return
        to_delete = [uid for uid,val in self.delete_map.items() if val]
        if not to_delete:
            center_modal(self, "Delete", "No students selected.", width=360, height=120, auto_close=1.2)
            return
        names = [e.get("name") for e in self.leaderboard if e.get("uid") in to_delete]
        # Keep the confirmation compact so its Delete/Cancel buttons always
        # remain visible, even when 8-9 (or more) students are selected.
        preview = names[:4]
        details = "\n".join(f"• {name}" for name in preview if name)
        remaining = len(names) - len(preview)
        if remaining > 0:
            details += f"\n…and {remaining} more"
        message = f"Delete {len(to_delete)} selected student(s)?\n\n{details}\n\nThis cannot be undone."
        ok = confirm_modal(self, "Confirm Bulk Delete", message)
        if not ok:
            return
        self.leaderboard = [e for e in self.leaderboard if e.get("uid") not in to_delete]
        for uid in to_delete:
            if uid in self.delete_map:
                del self.delete_map[uid]
        save_json(LEADERBOARD_FILE, self.leaderboard)
        self.delete_mode = False
        self.delete_selected_btn.config(state="disabled")
        self.remove_student_btn.config(relief="raised")
        self.refresh_leaderboard()
        center_modal(self, "Deleted", "Selected students removed.", width=360, height=120, auto_close=1.2)

    def _clear_leaderboard(self):
        if not self.admin:
            center_modal(self, "Admin", "Login first.", width=360, height=120, auto_close=1.2)
            return
        ok = confirm_modal(self, "Confirm", "Clear leaderboard? This cannot be undone.")
        if not ok:
            return
        self.leaderboard = []
        save_json(LEADERBOARD_FILE, self.leaderboard)
        self.refresh_leaderboard()
        center_modal(self, "Cleared", "Leaderboard cleared.", width=360, height=120, auto_close=1.2)

    def _on_grid_size_change(self):
        try:
            val = int(self.grid_size_cb.get())
            if 3 <= val <= 15:
                self.grid_n = val
                self.grid_info_lbl.config(text=f"Grid: {self.grid_n}x{self.grid_n} (squares). Each completed level = {POINTS_PER_LEVEL} points.")
                center_modal(self, "Grid updated", f"Grid size set to {val}x{val} (used for next games).", width=380, height=120, auto_close=1.4)
        except Exception:
            pass

    def _choose_existing_player(self):
        """Find a previously registered player and launch directly with that saved profile."""
        candidates = list(self.leaderboard)
        if not candidates:
            center_modal(self, "No saved players", "No registered players were found yet.", width=380, height=120)
            return
        dlg = tk.Toplevel(self)
        dlg.title("Already a player? Find your profile")
        dlg.transient(self); dlg.grab_set(); dlg.geometry("820x600"); dlg.minsize(700, 500)
        dlg.configure(bg="#0A1426")
        shell = GlassPanel(dlg, tint="#1B2E4B", radius=28, padding=20)
        shell.pack(fill="both", expand=True, padx=14, pady=14)
        body = shell.content
        tk.Label(body, text="WELCOME BACK", bg="#1B2E4B", fg="#73B8FF",
                 font=(FONT_NAME, 16, "bold")).pack(anchor="w")
        tk.Label(body, text="Search your name, verify your details, then select Play.",
                 bg="#1B2E4B", fg="#C5D6EA", font=(FONT_NAME, 10)).pack(anchor="w", pady=(5, 12))
        query = tk.StringVar()
        search = tk.Entry(body, textvariable=query, font=(FONT_NAME, 12), bg="#263D5C", fg="#FFFFFF",
                          insertbackground="#FFFFFF", relief="flat", highlightthickness=1,
                          highlightbackground="#6484AE", highlightcolor="#0A84FF")
        search.pack(fill="x", ipady=9, pady=(0, 12))
        wrap = tk.Frame(body, bg="#172943", highlightthickness=1, highlightbackground="#526F94")
        wrap.pack(fill="both", expand=True)
        cols = ("name", "role", "class", "section", "roll", "plays", "score")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse", height=12)
        labels = {"name":"Player name", "role":"Role", "class":"Class", "section":"Section",
                  "roll":"Roll", "plays":"Times played", "score":"Best score"}
        widths = {"name":190, "role":125, "class":65, "section":70, "roll":65, "plays":90, "score":85}
        for col in cols:
            tree.heading(col, text=labels[col])
            tree.column(col, width=widths[col], minwidth=50, stretch=(col == "name"),
                        anchor="w" if col == "name" else "center")
        style = ttk.Style(dlg)
        style.configure("Treeview", background="#172943", fieldbackground="#172943", foreground="#F3F7FF",
                        rowheight=32, borderwidth=0, font=(FONT_NAME, 10))
        style.configure("Treeview.Heading", background="#294565", foreground="#FFFFFF",
                        font=(FONT_NAME, 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#176BC1")], foreground=[("selected", "#FFFFFF")])
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scroll.pack(side="right", fill="y", padx=(0, 5), pady=6)
        shown = {}
        def refresh(*_):
            q = _identity_text(query.get())
            for iid in tree.get_children(): tree.delete(iid)
            shown.clear()
            matches = [p for p in candidates if not q or q in _identity_text(p.get("name"))]
            matches.sort(key=lambda p: (_identity_text(p.get("name")), str(p.get("class", "")), str(p.get("section", ""))))
            for i, pf in enumerate(matches):
                iid = str(i); shown[iid] = pf
                tree.insert("", "end", iid=iid, values=(pf.get("name", ""), pf.get("role", ""),
                    pf.get("class", "-"), pf.get("section", "-"), pf.get("roll", "-"),
                    int(pf.get("times_played", 0) or 0), int(pf.get("score", 0) or 0)))
            if matches:
                first = tree.get_children()[0]; tree.selection_set(first); tree.focus(first)
        def play_selected():
            selected = tree.selection()
            if not selected:
                center_modal(dlg, "Select a player", "Choose your saved player profile first.", width=340, height=115)
                return
            player = shown.get(selected[0])
            if not player: return
            self.player = player
            # Reflect the chosen record in the registration form for easy verification.
            role = player.get("role", "Student")
            self.role_var.set(role); self._on_role_change()
            if role == "Student":
                self.student_name_var.set(player.get("name", ""))
                self.class_var.set(str(player.get("class", "LKG")))
                self.section_var.set(str(player.get("section", "A")))
                self.roll_var.set(str(player.get("roll", "")))
                school = player.get("school", "DAV SDPS Public School")
                if school == "DAV SDPS Public School": self.school_var.set(school)
                else:
                    self.school_var.set("Other"); self.other_school_var.set(school); self._on_school_change()
            elif role == "Teacher":
                self.teacher_name_var.set(player.get("name", ""))
            else:
                self.parent_name_var.set(player.get("name", ""))
            dlg.grab_release(); dlg.destroy()
            save_json(LEADERBOARD_FILE, self.leaderboard)
            self.refresh_leaderboard()
            self._open_game_window()
        query.trace_add("write", refresh)
        tree.bind("<Double-1>", lambda _e: play_selected())
        actions = tk.Frame(body, bg="#1B2E4B"); actions.pack(fill="x", pady=(12, 0))
        tk.Button(actions, text="Cancel", command=dlg.destroy, bg="#344B69", fg="#FFFFFF",
                  relief="flat", padx=18, pady=9, cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(actions, text="Play  →", command=play_selected, bg="#0A84FF", fg="#FFFFFF",
                  activebackground="#409BFF", relief="flat", padx=22, pady=9,
                  font=(FONT_NAME, 10, "bold"), cursor="hand2").pack(side="right")
        refresh(); search.focus_set()
        dlg.bind("<Return>", lambda _e: play_selected())
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width()-dlg.winfo_width())//2
        y = self.winfo_rooty() + (self.winfo_height()-dlg.winfo_height())//2
        dlg.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _edit_current_student_profile(self):
        """Search saved students in a clean aligned table, then open the existing edit step."""
        candidates = [e for e in self.leaderboard if e.get("role") == "Student"]
        if not candidates:
            center_modal(self, "No saved profiles", "There are no student profiles to edit yet.", width=390, height=125)
            return

        dlg = tk.Toplevel(self)
        dlg.title("Find a student profile")
        dlg.transient(self); dlg.grab_set(); dlg.geometry("800x650")
        dlg.minsize(720, 590); dlg.configure(bg="#0A1426")
        shell = GlassPanel(dlg, tint="#1B2E4B", radius=28, padding=20)
        shell.pack(fill="both", expand=True, padx=14, pady=14)
        body = shell.content
        tk.Label(body,text="EDIT EXISTING PROFILE",bg="#1B2E4B",fg="#F5F8FF",
                 font=(FONT_NAME,15,"bold")).pack(anchor="w")
        tk.Label(body,text="Search by student name. Check the school, class, section and roll number before continuing.",
                 bg="#1B2E4B",fg="#BFD0E5",font=(FONT_NAME,10)).pack(anchor="w",pady=(5,13))

        search_var=tk.StringVar()
        search_entry=tk.Entry(body,textvariable=search_var,font=(FONT_NAME,12),bg="#263D5C",fg="#FFFFFF",
                              insertbackground="#FFFFFF",relief="flat",highlightthickness=1,
                              highlightbackground="#6484AE",highlightcolor="#0A84FF")
        search_entry.pack(fill="x",ipady=9,pady=(0,12))
        search_entry.insert(0,self.student_name_var.get().strip())

        table_wrap=tk.Frame(body,bg="#172943",highlightthickness=1,highlightbackground="#526F94")
        table_wrap.pack(fill="both",expand=True)
        cols=("name","school","class","section","roll","score")
        tree=ttk.Treeview(table_wrap,columns=cols,show="headings",selectmode="browse",height=11)
        headings={"name":"Student name","school":"School","class":"Class","section":"Section","roll":"Roll no.","score":"Best score"}
        widths={"name":190,"school":190,"class":65,"section":75,"roll":75,"score":85}
        for col in cols:
            tree.heading(col,text=headings[col])
            tree.column(col,width=widths[col],minwidth=55,anchor="w" if col in ("name","school") else "center",stretch=(col in ("name","school")))
        style=ttk.Style(dlg)
        style.configure("Treeview",background="#172943",fieldbackground="#172943",foreground="#F3F7FF",
                        rowheight=31,borderwidth=0,font=(FONT_NAME,10))
        style.configure("Treeview.Heading",background="#294565",foreground="#FFFFFF",
                        font=(FONT_NAME,9,"bold"),relief="flat")
        style.map("Treeview",background=[("selected","#176BC1")],foreground=[("selected","#FFFFFF")])
        scroll=ttk.Scrollbar(table_wrap,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left",fill="both",expand=True,padx=(6,0),pady=6)
        scroll.pack(side="right",fill="y",padx=(0,5),pady=6)
        shown={}

        def refresh_matches(*_):
            query=_identity_text(search_var.get())
            for iid in tree.get_children(): tree.delete(iid)
            shown.clear()
            matches=[p for p in candidates if not query or query in _identity_text(p.get("name"))]
            matches.sort(key=lambda p:(_identity_text(p.get("name")),str(p.get("class","")),str(p.get("section",""))))
            for i,pf in enumerate(matches):
                iid=str(i); shown[iid]=pf
                tree.insert("","end",iid=iid,values=(pf.get("name",""),pf.get("school","-"),
                    pf.get("class","-"),pf.get("section","-"),pf.get("roll","-"),pf.get("score",0)))
            if matches:
                first=tree.get_children()[0]; tree.selection_set(first); tree.focus(first)

        def continue_to_edit():
            selected=tree.selection()
            if not selected:
                center_modal(dlg,"Select a profile","Select a student row to continue.",width=350,height=115); return
            chosen=shown.get(selected[0])
            if chosen is None: return
            dlg.grab_release(); dlg.destroy()
            self._open_profile_editor([chosen])

        search_var.trace_add("write",refresh_matches)
        tree.bind("<Double-1>",lambda _e:continue_to_edit())
        actions=tk.Frame(body,bg="#1B2E4B"); actions.pack(fill="x",pady=(13,0))
        tk.Button(actions,text="Cancel",command=dlg.destroy,bg="#344B69",fg="#FFFFFF",relief="flat",
                  padx=18,pady=9,cursor="hand2").pack(side="right",padx=(8,0))
        tk.Button(actions,text="Continue  →",command=continue_to_edit,bg="#0A84FF",fg="#FFFFFF",
                  activebackground="#409BFF",relief="flat",padx=20,pady=9,
                  font=(FONT_NAME,10,"bold"),cursor="hand2").pack(side="right")
        refresh_matches(); search_entry.focus_set()
        dlg.bind("<Return>",lambda _e:continue_to_edit())
        dlg.update_idletasks()
        x=self.winfo_rootx()+(self.winfo_width()-dlg.winfo_width())//2
        y=self.winfo_rooty()+(self.winfo_height()-dlg.winfo_height())//2
        dlg.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _open_profile_editor(self, candidates):
        """Second step: edit the selected saved record without losing score/history."""
        selected_profile = [candidates[-1]]
        dlg = tk.Toplevel(self)
        dlg.title("Edit Student Profile")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.configure(bg="#0A1426")
        panel_glass = GlassPanel(dlg, tint="#1B2E4B", radius=28, padding=22)
        panel_glass.pack(fill="both", expand=True, padx=14, pady=14)
        panel = panel_glass.content
        panel.configure(bg="#1B2E4B")
        tk.Label(panel, text="EDIT SAVED PROFILE", bg="#1B2E4B", fg="#73B8FF",
                 font=(FONT_NAME, 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        name_var = tk.StringVar()
        class_var = tk.StringVar()
        section_var = tk.StringVar()
        roll_var = tk.StringVar()
        profile_var = tk.StringVar()
        profile_labels = [f"Class {e.get('class', '-')} · Section {e.get('section', '-')} · Score {e.get('score', 0)}"
                          for e in candidates]

        def load_selected_profile(*_):
            idx = profile_labels.index(profile_var.get()) if profile_var.get() in profile_labels else 0
            selected_profile[0] = candidates[idx]
            chosen = selected_profile[0]
            name_var.set(chosen.get("name", ""))
            class_var.set(str(chosen.get("class", "LKG")))
            section_var.set(str(chosen.get("section", "A")))
            roll_var.set(str(chosen.get("roll", "")))

        if len(candidates) > 1:
            tk.Label(panel, text="Saved school-year profile", bg="#1B2E4B", fg="#EAF2FC",
                     font=(FONT_NAME, 10)).grid(row=1, column=0, sticky="w", pady=5)
            picker = ttk.Combobox(panel, textvariable=profile_var, values=profile_labels,
                                  state="readonly", width=29)
            picker.grid(row=1, column=1, padx=(12, 0), pady=5)
            picker.bind("<<ComboboxSelected>>", load_selected_profile)
        else:
            tk.Label(panel, text="Selected profile", bg="#1B2E4B", fg="#C3D2E4",
                     font=(FONT_NAME, 9)).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        profile_var.set(profile_labels[-1])
        load_selected_profile()

        panel.grid_columnconfigure(0, minsize=145, weight=0)
        panel.grid_columnconfigure(1, minsize=270, weight=1)
        def field_label(text, row):
            tk.Label(panel, text=text, bg="#1B2E4B", fg="#EAF2FC",
                     font=(FONT_NAME, 10, "bold"), anchor="w", width=17).grid(row=row, column=0, sticky="ew", pady=7)
        for row, (label, var) in enumerate([("Student name", name_var), ("Roll number", roll_var)], start=2):
            field_label(label, row)
            tk.Entry(panel, textvariable=var, width=25, font=(FONT_NAME, 11), bg="#263B56", fg="#FFFFFF",
                     insertbackground="#FFFFFF", relief="flat", highlightthickness=1,
                     highlightbackground="#405A78", highlightcolor="#0A84FF").grid(row=row, column=1, padx=(12, 0), pady=6)
        field_label("Class", 4)
        ttk.Combobox(panel, textvariable=class_var, values=["LKG", "UKG"] + [str(i) for i in range(1, 13)],
                     state="readonly", width=22).grid(row=4, column=1, padx=(12, 0), pady=6)
        field_label("Section", 5)
        ttk.Combobox(panel, textvariable=section_var, values=["A", "B", "C"],
                     state="readonly", width=22).grid(row=5, column=1, padx=(12, 0), pady=6)
        tk.Label(panel, text="Your saved score and play history will be preserved.",
                 bg="#1B2E4B", fg="#B6C8DD", font=(FONT_NAME, 9),
                 wraplength=350).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 9))

        def save_edits():
            profile = selected_profile[0]
            new_name = name_var.get().strip()
            new_roll = roll_var.get().strip()
            if not is_valid_name(new_name) or not new_roll.isdigit():
                center_modal(dlg, "Invalid details", "Enter a valid name and numeric roll number.", width=360, height=120)
                return
            new_key = (_identity_text(profile.get("school")), _identity_text(class_var.get()),
                       _identity_text(section_var.get()), _identity_text(new_roll))
            collision = next((e for e in self.leaderboard if e is not profile and e.get("role") == "Student"
                              and (_identity_text(e.get("school")), _identity_text(e.get("class")),
                                   _identity_text(e.get("section")), _identity_text(e.get("roll"))) == new_key), None)
            if collision:
                center_modal(dlg, "Profile already exists", "Another profile already uses this school, class, section and roll number. No changes were saved.", width=430, height=140)
                return
            profile["name"] = normalize_name(new_name)
            profile["class"] = class_var.get()
            profile["section"] = section_var.get()
            profile["roll"] = int(new_roll)
            save_json(LEADERBOARD_FILE, self.leaderboard)
            self.student_name_var.set(profile["name"])
            self.class_var.set(profile["class"])
            self.section_var.set(profile["section"])
            self.roll_var.set(str(profile["roll"]))
            self.player = profile
            self.refresh_leaderboard()
            dlg.grab_release()
            dlg.destroy()
            center_modal(self, "Profile updated", "Saved profile details updated. Your score and play history were kept.", width=430, height=130)

        buttons = tk.Frame(panel, bg="#1B2E4B")
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(8, 0))
        tk.Button(buttons, text="Cancel", command=dlg.destroy, bg="#2B405A", fg="#FFFFFF",
                  relief="flat", padx=14, pady=8, cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(buttons, text="Save Changes", command=save_edits, bg="#0A84FF", fg="#FFFFFF",
                  activebackground="#2795FF", relief="flat", padx=15, pady=8,
                  font=(FONT_NAME, 10, "bold"), cursor="hand2").pack(side="right")
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ----------------- Registration & start -----------------
    def _on_proceed(self):
        role = self.role_var.get()
        if role == "Student":
            raw = self.student_name_var.get()
            if not is_valid_name(raw):
                center_modal(self, "Invalid", "Enter a valid student name (letters and spaces only).", width=420, height=120)
                return
            name = normalize_name(raw)
            school = self.school_var.get()
            if school == "Other":
                school_raw = self.other_school_var.get()
                if not is_valid_name(school_raw):
                    center_modal(self, "Invalid", "Enter valid school name.", width=420, height=120)
                    return
                school = normalize_name(school_raw)
            cls = self.class_var.get(); sec = self.section_var.get(); roll = self.roll_var.get().strip()
            if not roll.isdigit():
                center_modal(self, "Invalid", "Roll number must contain only digits.", width=420, height=120)
                return
            rollnum = int(roll)
            student_key = (_identity_text(school), _identity_text(cls),
                           _identity_text(sec), _identity_text(rollnum))
            existing = next((e for e in self.leaderboard
                             if e.get("role") == "Student"
                             and (_identity_text(e.get("school")), _identity_text(e.get("class")),
                                  _identity_text(e.get("section")), _identity_text(e.get("roll"))) == student_key), None)
            if existing:
                # Same student + same academic profile: reopen it, never create a repeat record.
                self.player = existing
                existing["name"] = name
            else:
                # A changed class/section is a new academic-year profile, linked to the same player.
                previous = next((e for e in self.leaderboard if e.get("role") == "Student"
                                 and _identity_text(e.get("name")) == _identity_text(name)
                                 and _identity_text(e.get("school")) == _identity_text(school)
                                 and _identity_text(e.get("roll")) == _identity_text(rollnum)), None)
                player_id = previous.get("player_id") if previous else str(uuid.uuid4())
                entry = {"uid": str(uuid.uuid4()), "player_id": player_id, "name": name,
                         "role": "Student", "school": school, "class": cls, "section": sec,
                         "roll": rollnum, "score": 0, "times_played": 0}
                self.leaderboard.append(entry); save_json(LEADERBOARD_FILE, self.leaderboard)
                self.delete_map[entry["uid"]] = False; self.player = entry
        elif role == "Parent/Guardian":
            raw = self.parent_name_var.get()
            if not is_valid_name(raw):
                center_modal(self, "Invalid", "Enter a valid parent/guardian name (letters and spaces only).", width=420, height=120)
                return
            name = normalize_name(raw)
            existing = next((e for e in self.leaderboard if e.get("role")=="Parent/Guardian" and _identity_text(e.get("name"))==_identity_text(name)), None)
            if not existing:
                entry = {"uid": str(uuid.uuid4()), "name": name, "role": "Parent/Guardian", "school": "-", "class": "-", "section": "-", "roll": "-", "score":0, "times_played":0}
                self.leaderboard.append(entry); save_json(LEADERBOARD_FILE, self.leaderboard); self.delete_map[entry["uid"]] = False; self.player = entry
            else:
                self.player = existing
        else:
            raw = self.teacher_name_var.get()
            if not is_valid_name(raw):
                center_modal(self, "Invalid", "Enter a valid teacher name (letters and spaces only).", width=420, height=120)
                return
            name = normalize_name(raw)
            school = self.teacher_school_var.get()
            if school == "Other":
                school_raw = self.teacher_other_var.get()
                if not is_valid_name(school_raw):
                    center_modal(self, "Invalid", "Enter valid school name for Teacher.", width=420, height=120)
                    return
                school = normalize_name(school_raw)
            existing = next((e for e in self.leaderboard if e.get("role")=="Teacher" and _identity_text(e.get("name"))==_identity_text(name)), None)
            if not existing:
                entry = {"uid": str(uuid.uuid4()), "name": name, "role": "Teacher", "school": school, "class":"-", "section":"-", "roll":"-", "score":0, "times_played":0}
                self.leaderboard.append(entry); save_json(LEADERBOARD_FILE, self.leaderboard); self.delete_map[entry["uid"]] = False; self.player = entry
            else:
                self.player = existing

        save_json(LEADERBOARD_FILE, self.leaderboard)
        self.refresh_leaderboard()
        # start directly
        self._open_game_window()

    # ----------------- Game window & logic -----------------
    def _open_game_window(self):
        if not self.player:
            center_modal(self, "No player", "Please register first.", width=380, height=120)
            return
        gw = tk.Toplevel(self)
        gw.title(f"Game — {self.player.get('name')}")
        gw.geometry("760x760")
        gw.minsize(560,560)
        gw.configure(bg="#142235")

        tk.Label(gw, text=f"{self.player.get('name')}  —  {self.player.get('role')}", bg="#142235", fg=ACCENT, font=(FONT_NAME,14,"bold")).pack(anchor="nw", padx=8, pady=(8,6))
        status = tk.Label(gw, text="Press Start to play", bg="#263A52", fg="#E7F1FC",
                          padx=12, pady=7, highlightthickness=1, highlightbackground="#6D89A8")
        status.pack(anchor="w", padx=8)

        ctrl_top = tk.Frame(gw, bg="#142235"); ctrl_top.pack(fill="x", padx=8, pady=8)
        start_btn = tk.Button(ctrl_top, text="Start", bg=ACCENT, fg="#102033", activebackground="#168CFF",
                              activeforeground="#FFFFFF", relief="flat", padx=20,
                              font=(FONT_NAME,13,"bold"), width=16, height=1)
        start_btn.pack(side="top", pady=4)

        board_holder = tk.Frame(gw, bg="#000000", padx=7, pady=7, highlightthickness=1, highlightbackground="#D8D2B8"); board_holder.pack(fill="both", expand=True, padx=8, pady=8)
        board_canvas = tk.Canvas(board_holder, bg="#8fa8be", highlightthickness=0); board_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        score_label = tk.Label(gw, text="Score: 0", bg="#263A52", fg="#FFFFF0", font=(FONT_NAME,12,"bold"),
                               padx=12, pady=7, highlightthickness=1, highlightbackground="#6D89A8"); score_label.pack(anchor="w", padx=8, pady=(0,6))

        state = {"level":0, "sequence":[], "user_seq":[], "is_input":False, "score":0}

        def persist_best_score(points):
            points = max(0, int(points))
            if points > int(self.player.get("score", 0) or 0):
                self.player["score"] = points
            save_json(LEADERBOARD_FILE, self.leaderboard)
            self.last_score_lbl.config(text=f"Best Score: {self.player.get('score', 0)}")
            self.refresh_leaderboard()

        rects = {}; cell_padding = 8

        def draw_grid():
            board_canvas.delete("all"); rects.clear()
            w = board_canvas.winfo_width(); h = board_canvas.winfo_height()
            total_pad = (self.grid_n + 1) * cell_padding
            max_cell_w = (w - total_pad) // self.grid_n
            max_cell_h = (h - total_pad) // self.grid_n
            if max_cell_w <= 0 or max_cell_h <= 0:
                return
            cell_size = min(max_cell_w, max_cell_h)
            grid_w = cell_size * self.grid_n + cell_padding * (self.grid_n + 1)
            ox = max((w - grid_w)//2, 6); oy = max((h - (cell_size * self.grid_n + cell_padding*(self.grid_n +1)))//2, 6)
            idx = 0
            for r in range(self.grid_n):
                for c in range(self.grid_n):
                    x1 = ox + cell_padding + c*(cell_size + cell_padding); y1 = oy + cell_padding + r*(cell_size + cell_padding)
                    x2 = x1 + cell_size; y2 = y1 + cell_size
                    rect = board_canvas.create_rectangle(x1,y1,x2,y2, fill="#28282B", outline="#829BB5", width=2)
                    rects[idx] = (rect, (x1,y1,x2,y2))
                    board_canvas.tag_bind(rect, '<Button-1>', lambda e, i=idx: on_cell_click(i))
                    idx += 1

        def on_cell_click(i):
            if not state['is_input']: return
            rect_id, _ = rects[i]
            state['user_seq'].append(i); pos = len(state['user_seq']) - 1
            if state['user_seq'][pos] != state['sequence'][pos]:
                board_canvas.itemconfigure(rect_id, fill="#F4C7CC", outline="#E5484D", width=4)
                end_game(); return
            board_canvas.itemconfigure(rect_id, fill="#C7E8D2", outline="#28A66A", width=4)
            if len(state['user_seq']) == len(state['sequence']):
                state['score'] = len(state['sequence']) * POINTS_PER_LEVEL
                score_label.config(text=f"Score: {state['score']}  |  Best: {max(state['score'], int(self.player.get('score', 0) or 0))}")
                state['is_input'] = False
                # Save immediately after every completed level. Closing the game cannot erase it.
                persist_best_score(state["score"])
                self._show_center_toast(gw, f"🎉 Level {state['level']} cleared! 🎉", 2)
                gw.after(2200, lambda: next_level())

        def highlight_cell(idx, flash_time=300):
            rect_id, _ = rects[idx]; orig = board_canvas.itemcget(rect_id, 'fill'); board_canvas.itemconfigure(rect_id, fill="#168CFF"); board_canvas.after(flash_time, lambda: board_canvas.itemconfigure(rect_id, fill=orig))

        def play_sequence(i=0):
            if i < len(state['sequence']):
                idx = state['sequence'][i]; highlight_cell(idx); gw.after(500, lambda: play_sequence(i+1))
            else:
                state['is_input']=True; status.config(text='Your turn — repeat the sequence')

        def next_level():
            # Each new level starts with neutral cells; correct picks turn green,
            # while an incorrect pick is marked red and ends the current run.
            for rect_id, _ in rects.values():
                board_canvas.itemconfigure(rect_id, fill="#28282B", outline="#829BB5", width=2)
            state['level'] += 1; state['user_seq'] = []; state['sequence'].append(random.randrange(0, self.grid_n*self.grid_n)); status.config(text=f"Level {state['level']} — Watch"); state['is_input']=False; gw.after(500, lambda: play_sequence(0))

        def start_game():
            state['level'] = 0
            state['sequence'] = []
            state['user_seq'] = []
            state['is_input'] = False
            state['score'] = 0
            self.player['times_played'] = int(self.player.get('times_played', 0) or 0) + 1
            save_json(LEADERBOARD_FILE, self.leaderboard)
            self.refresh_leaderboard()
            score_label.config(text=f"Score: 0  |  Best: {self.player.get('score', 0)}")
            status.config(text="Watch the sequence")
            next_level()

        def end_game():
            completed = len(state['sequence']) - 1
            final_points = max(0, completed * POINTS_PER_LEVEL)
            persist_best_score(final_points)
            # show score toast (2 seconds) sized ~230x230 px (approx 6cm x 6cm)
            self._show_center_toast(gw, f"Wrong box!\nLevels cleared: {completed}  ·  Score: {final_points}", 2)
            status.config(text=f"Game over — incorrect box. {completed} levels cleared. Press Start to play again.")

        board_canvas.bind('<Configure>', lambda e: draw_grid())
        start_btn.config(command=start_game)
        self.after(150, lambda: draw_grid())

    # ----------------- toasts/modal used inside game -----------------
    def _show_center_toast(self, parent_window, text, seconds=2):
        """Compact dark glass announcement for level clear / game over."""
        tw=tk.Toplevel(parent_window)
        tw.overrideredirect(True)
        tw.attributes("-topmost",True)
        tw.configure(bg="#0A1426")
        cv=tk.Canvas(tw,width=360,height=142,bg="#0A1426",highlightthickness=0)
        cv.pack(fill="both",expand=True)
        self._draw_rounded_rect(cv,5,7,355,136,27,fill="#1D3554",outline="#79AFFF",width=2)
        self._draw_rounded_rect(cv,13,12,347,34,16,fill="#536A88",outline="")
        title="LEVEL COMPLETE" if "Level" in text and "cleared" in text else "GAME FINISHED"
        body=text.replace("🎉", "").strip()
        cv.create_text(180,48,text=title,font=(FONT_NAME,10,"bold"),fill="#8DBBFF")
        cv.create_text(180,83,text=body,font=(FONT_NAME,16,"bold"),fill="#FFFFFF",justify="center",width=310)
        cv.create_text(180,116,text="MEMORY GRID  ·  KEEP GOING",font=(FONT_NAME,8,"bold"),fill="#B9CDE8")
        parent_window.update_idletasks()
        pwx=parent_window.winfo_rootx(); pwy=parent_window.winfo_rooty()
        pww=parent_window.winfo_width(); pwh=parent_window.winfo_height()
        x=pwx+(pww-360)//2; y=pwy+(pwh-142)//2
        tw.geometry(f"360x142+{x}+{y}")
        tw.after(int(seconds*1000),lambda:tw.destroy())

if __name__ == "__main__":
    app = MemoryGameApp()
    app.mainloop()
