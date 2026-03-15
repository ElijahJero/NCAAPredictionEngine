import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import csv
import json
import os
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from constants import (
    APP_TITLE, DARK_BG, CARD_BG, ACCENT, ACCENT2, FG, MUTED,
    SUCCESS, WARNING, DANGER, DEFAULT_WEIGHTS, STYLE,
)
from api import get_teams, get_team_stats
from simulation import compute_strength, simulate_game, monte_carlo


class NCAAApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x820")
        self.minsize(1000, 700)
        self.configure(bg=DARK_BG)

        self._apply_styles()

        # ── State ──────────────────────────────────────────────────────────
        self.teams: list[dict] = []
        self.results: dict[str, int] = {}
        self.sim_runs = tk.IntVar(value=2000)
        self.noise_var = tk.DoubleVar(value=1.0)
        self.team_limit = tk.IntVar(value=500)
        self.loading = False

        # Per-weight controls: {label: (weight_var, enabled_var)}
        self.weight_vars: dict[str, tuple[tk.DoubleVar, tk.BooleanVar]] = {}
        for label, (key, w, pos) in DEFAULT_WEIGHTS.items():
            self.weight_vars[label] = (tk.DoubleVar(value=w), tk.BooleanVar(value=w > 0))

        self._build_ui()

    # ── Styling ─────────────────────────────────────────────────────────────

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        for widget, opts in STYLE.items():
            if "configure" in opts:
                style.configure(widget, **opts["configure"])
            if "map" in opts:
                style.map(widget, **opts["map"])

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self, bg=ACCENT, height=56)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="🏀  NCAA Tournament Prediction Engine",
                 bg=ACCENT, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(top, text=f"v2.0  •  {datetime.now().strftime('%B %d, %Y')}",
                 bg=ACCENT, fg="#d8b4fe",
                 font=("Segoe UI", 9)).pack(side="right", padx=20)

        # Main paned window
        pane = tk.PanedWindow(self, orient="horizontal", bg=DARK_BG,
                              sashwidth=6, sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        left_panel = ttk.Frame(pane, style="TFrame", width=320)
        pane.add(left_panel, minsize=280)

        right_panel = ttk.Frame(pane, style="TFrame")
        pane.add(right_panel, minsize=600)

        self._build_left_panel(left_panel)
        self._build_right_panel(right_panel)

        # Status bar
        self.status_var = tk.StringVar(value="Ready — load teams to begin.")
        status_bar = tk.Frame(self, bg=CARD_BG, height=28)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        tk.Label(status_bar, textvariable=self.status_var,
                 bg=CARD_BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=12)
        self.progress = ttk.Progressbar(status_bar, mode="determinate",
                                        length=180, style="TProgressbar")
        self.progress.pack(side="right", padx=12, pady=4)

    # ── Left Panel (Controls) ────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        canvas = tk.Canvas(parent, bg=DARK_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas, style="TFrame")
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _resize)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._section(inner, "⚙  Simulation Settings")
        self._setting_row(inner, "Teams to Load:", self.team_limit, 16, 500, 1)
        self._setting_row(inner, "Monte Carlo Runs:", self.sim_runs, 100, 10000, 100)
        self._noise_row(inner)

        self._section(inner, "⚖  Stat Weights & Toggles")
        self._build_weight_panel(inner)

        self._section(inner, "🔧  Actions")
        self._action_btn(inner, "📥  Load Teams & Stats",
                         self._load_teams, ACCENT)
        self._action_btn(inner, "▶  Run Simulation",
                         self._run_simulation, SUCCESS.replace("#", ""),
                         bg="#16a34a")
        self._action_btn(inner, "🔄  Reset Weights",
                         self._reset_weights, WARNING.replace("#", ""),
                         bg="#b45309")
        self._action_btn(inner, "💾  Export Results (CSV)",
                         self._export_csv, "#334155")
        self._action_btn(inner, "📊  Export Chart (PNG)",
                         self._export_chart, "#334155")
        self._action_btn(inner, "📁  Save Config (JSON)",
                         self._save_config, "#334155")
        self._action_btn(inner, "📂  Load Config (JSON)",
                         self._load_config, "#334155")

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=ACCENT, height=2)
        f.pack(fill="x", padx=8, pady=(14, 2))
        tk.Label(parent, text=text, bg=DARK_BG, fg=ACCENT2,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)

    def _setting_row(self, parent, label, var, from_, to, resolution):
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text=label, bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 9), width=20, anchor="w").pack(side="left")
        val_lbl = tk.Label(row, textvariable=var, bg=DARK_BG, fg=ACCENT2,
                           font=("Segoe UI", 9, "bold"), width=6)
        val_lbl.pack(side="right")
        ttk.Scale(row, from_=from_, to=to, variable=var,
                  orient="horizontal",
                  command=lambda v, va=var, r=resolution:
                      va.set(round(float(v) / r) * r)).pack(
                          side="left", fill="x", expand=True, padx=4)

    def _noise_row(self, parent):
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Randomness (noise):", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 9), width=20, anchor="w").pack(side="left")
        val_lbl = tk.Label(row, textvariable=self.noise_var, bg=DARK_BG,
                           fg=ACCENT2, font=("Segoe UI", 9, "bold"), width=6)
        val_lbl.pack(side="right")
        ttk.Scale(row, from_=0.1, to=5.0, variable=self.noise_var,
                  orient="horizontal",
                  command=lambda v: self.noise_var.set(
                      round(float(v), 1))).pack(side="left", fill="x",
                                                expand=True, padx=4)

    def _build_weight_panel(self, parent):
        for label, (key, default_w, positive) in DEFAULT_WEIGHTS.items():
            wvar, evar = self.weight_vars[label]
            card = ttk.Frame(parent, style="Card.TFrame")
            card.pack(fill="x", padx=10, pady=3, ipady=4, ipadx=4)

            # Row 1: toggle + label + direction badge
            top_row = ttk.Frame(card, style="Card.TFrame")
            top_row.pack(fill="x", padx=4)
            chk = tk.Checkbutton(top_row, variable=evar, bg=CARD_BG,
                                  activebackground=CARD_BG,
                                  selectcolor=ACCENT,
                                  command=lambda lbl=label:
                                      self._toggle_weight(lbl))
            chk.pack(side="left")
            direction = "▲ pos" if positive else "▼ neg"
            dir_color = SUCCESS if positive else DANGER
            tk.Label(top_row, text=label, bg=CARD_BG, fg=FG,
                     font=("Segoe UI", 9)).pack(side="left", padx=2)
            tk.Label(top_row, text=direction, bg=CARD_BG, fg=dir_color,
                     font=("Segoe UI", 8)).pack(side="right", padx=4)

            # Row 2: slider + value
            bot_row = ttk.Frame(card, style="Card.TFrame")
            bot_row.pack(fill="x", padx=4)
            val_lbl = tk.Label(bot_row, textvariable=wvar, bg=CARD_BG,
                               fg=ACCENT2, font=("Segoe UI", 9, "bold"), width=5)
            val_lbl.pack(side="right")
            ttk.Scale(bot_row, from_=0.0, to=1.0, variable=wvar,
                      orient="horizontal",
                      command=lambda v, va=wvar:
                          va.set(round(float(v), 2))).pack(
                              side="left", fill="x", expand=True)

    def _toggle_weight(self, label):
        wvar, evar = self.weight_vars[label]
        if not evar.get():
            wvar.set(0.0)

    def _action_btn(self, parent, text, cmd, color_hex="7c3aed",
                    bg: str = ACCENT):
        tk.Button(parent, text=text, command=cmd,
                  bg=bg, fg="white", activebackground=ACCENT2,
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", pady=7).pack(
                      fill="x", padx=10, pady=3)

    # ── Right Panel (Tabs) ───────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        self.tab_dashboard = ttk.Frame(self.notebook, style="TFrame")
        self.tab_chart     = ttk.Frame(self.notebook, style="TFrame")
        self.tab_table     = ttk.Frame(self.notebook, style="TFrame")
        self.tab_matchup   = ttk.Frame(self.notebook, style="TFrame")
        self.tab_advanced  = ttk.Frame(self.notebook, style="TFrame")
        self.tab_teams     = ttk.Frame(self.notebook, style="TFrame")

        self.notebook.add(self.tab_dashboard, text="🏠  Dashboard")
        self.notebook.add(self.tab_chart,     text="📊  Probability Chart")
        self.notebook.add(self.tab_table,     text="📋  Full Rankings")
        self.notebook.add(self.tab_matchup,   text="⚔  Head-to-Head")
        self.notebook.add(self.tab_advanced,  text="🔬  Advanced Stats")
        self.notebook.add(self.tab_teams,     text="🏀  Team Browser")

        self._build_dashboard_tab()
        self._build_chart_tab()
        self._build_table_tab()
        self._build_matchup_tab()
        self._build_advanced_tab()
        self._build_teams_tab()

    # ── Dashboard Tab ────────────────────────────────────────────────────────

    def _build_dashboard_tab(self):
        tab = self.tab_dashboard
        # Stat cards row
        self.dash_cards_frame = tk.Frame(tab, bg=DARK_BG)
        self.dash_cards_frame.pack(fill="x", padx=16, pady=12)

        self._dash_card(self.dash_cards_frame, "Teams Loaded", "0",
                        "teams_loaded_lbl", ACCENT)
        self._dash_card(self.dash_cards_frame, "Simulations Run", "0",
                        "sims_run_lbl", ACCENT2)
        self._dash_card(self.dash_cards_frame, "Projected Champion", "—",
                        "proj_champ_lbl", SUCCESS)
        self._dash_card(self.dash_cards_frame, "Champion Win %", "—",
                        "champ_pct_lbl", WARNING)

        # Mini chart
        self.dash_fig, self.dash_ax = plt.subplots(figsize=(7, 3.5),
                                                   facecolor=DARK_BG)
        self.dash_canvas = FigureCanvasTkAgg(self.dash_fig, master=tab)
        self.dash_canvas.get_tk_widget().pack(fill="both", expand=True,
                                              padx=16, pady=(0, 12))
        self._draw_placeholder(self.dash_ax, "Run simulation to see results")
        self.dash_canvas.draw()

    def _dash_card(self, parent, title, value, attr, color):
        card = tk.Frame(parent, bg=CARD_BG, bd=0, relief="flat")
        card.pack(side="left", fill="both", expand=True, padx=6, pady=4,
                  ipady=10, ipadx=10)
        tk.Label(card, text=title, bg=CARD_BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack()
        lbl = tk.Label(card, text=value, bg=CARD_BG, fg=color,
                       font=("Segoe UI", 18, "bold"))
        lbl.pack()
        setattr(self, attr, lbl)

    def _draw_placeholder(self, ax, msg):
        ax.set_facecolor(CARD_BG)
        ax.text(0.5, 0.5, msg, color=MUTED, ha="center", va="center",
                transform=ax.transAxes, fontsize=13)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    # ── Chart Tab ────────────────────────────────────────────────────────────

    def _build_chart_tab(self):
        ctrl = ttk.Frame(self.tab_chart, style="TFrame")
        ctrl.pack(fill="x", padx=16, pady=8)

        tk.Label(ctrl, text="Show top:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.chart_top_n = tk.IntVar(value=20)
        ttk.Spinbox(ctrl, from_=5, to=64, textvariable=self.chart_top_n,
                    width=5, command=self._refresh_chart).pack(side="left", padx=6)

        self.chart_type = tk.StringVar(value="Horizontal Bar")
        ttk.Combobox(ctrl, textvariable=self.chart_type, width=16,
                     values=["Horizontal Bar", "Vertical Bar",
                             "Pie Chart", "Treemap"],
                     state="readonly").pack(side="left", padx=6)
        self.chart_type.trace_add("write", lambda *_: self._refresh_chart())

        tk.Button(ctrl, text="🔄 Refresh", command=self._refresh_chart,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)

        self.chart_fig, self.chart_ax = plt.subplots(figsize=(8, 5),
                                                      facecolor=DARK_BG)
        self.chart_canvas = FigureCanvasTkAgg(self.chart_fig,
                                              master=self.tab_chart)
        toolbar = NavigationToolbar2Tk(self.chart_canvas, self.tab_chart)
        toolbar.configure(background=DARK_BG)
        toolbar.update()
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True,
                                               padx=8, pady=(0, 8))
        self._draw_placeholder(self.chart_ax, "Run simulation to see chart")
        self.chart_canvas.draw()

    # ── Table Tab ────────────────────────────────────────────────────────────

    def _build_table_tab(self):
        ctrl = ttk.Frame(self.tab_table, style="TFrame")
        ctrl.pack(fill="x", padx=12, pady=6)
        tk.Label(ctrl, text="Search:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.table_search = tk.StringVar()
        self.table_search.trace_add("write", lambda *_: self._filter_table())
        ttk.Entry(ctrl, textvariable=self.table_search, width=24).pack(
            side="left", padx=6)
        tk.Label(ctrl, text="Sort:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self.table_sort = tk.StringVar(value="Win %")
        ttk.Combobox(ctrl, textvariable=self.table_sort, width=16,
                     values=["Win %", "Team Name", "Wins",
                             "Strength Score"],
                     state="readonly").pack(side="left", padx=6)
        self.table_sort.trace_add("write", lambda *_: self._refresh_table())

        cols = ("Rank", "Team", "Wins", "Win %", "Strength")
        self.tree = ttk.Treeview(self.tab_table, columns=cols,
                                 show="headings", selectmode="browse")
        widths = {"Rank": 55, "Team": 220, "Wins": 70,
                  "Win %": 90, "Strength": 100}
        for c in cols:
            self.tree.heading(c, text=c,
                              command=lambda col=c: self._sort_tree(col))
            self.tree.column(c, width=widths[c], anchor="center")

        ysb = ttk.Scrollbar(self.tab_table, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree.tag_configure("top3", background="#3b1f6e", foreground="white")
        self.tree.tag_configure("top10", background="#1e3a5f", foreground=FG)
        self.tree.bind("<<TreeviewSelect>>", self._on_team_select)

    def _sort_tree(self, col):
        """Allow clicking column headers to sort."""
        if not self.results:
            return
        reverse = getattr(self, "_sort_reverse", False)
        self._sort_reverse = not reverse
        self._refresh_table(sort_col=col, reverse=not reverse)

    # ── Matchup Tab ──────────────────────────────────────────────────────────

    def _build_matchup_tab(self):
        tab = self.tab_matchup
        top = ttk.Frame(tab, style="TFrame")
        top.pack(fill="x", padx=20, pady=14)

        tk.Label(top, text="Team A:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", padx=6)
        self.matchup_a = ttk.Combobox(top, width=30, state="readonly")
        self.matchup_a.grid(row=0, column=1, padx=8)

        tk.Label(top, text="VS", bg=DARK_BG, fg=ACCENT2,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=2, padx=12)

        tk.Label(top, text="Team B:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 11)).grid(row=0, column=3, sticky="w", padx=6)
        self.matchup_b = ttk.Combobox(top, width=30, state="readonly")
        self.matchup_b.grid(row=0, column=4, padx=8)

        tk.Label(top, text="Simulations:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w",
                                             padx=6, pady=8)
        self.matchup_runs = tk.IntVar(value=5000)
        ttk.Spinbox(top, from_=100, to=50000, textvariable=self.matchup_runs,
                    width=8).grid(row=1, column=1, padx=8)

        tk.Button(top, text="⚔  Simulate Matchup",
                  command=self._run_matchup,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 11, "bold"),
                  pady=6, padx=12).grid(row=1, column=2, columnspan=3,
                                        padx=12)

        # Results area
        res_frame = tk.Frame(tab, bg=CARD_BG, bd=0)
        res_frame.pack(fill="both", expand=True, padx=20, pady=8)
        self.matchup_result_var = tk.StringVar(
            value="Select two teams and simulate a head-to-head matchup.")
        tk.Label(res_frame, textvariable=self.matchup_result_var,
                 bg=CARD_BG, fg=FG, font=("Segoe UI", 12),
                 wraplength=700, justify="center").pack(pady=20)

        self.matchup_fig, self.matchup_ax = plt.subplots(
            figsize=(6, 2.5), facecolor=CARD_BG)
        self.matchup_canvas = FigureCanvasTkAgg(self.matchup_fig,
                                                master=res_frame)
        self.matchup_canvas.get_tk_widget().pack(fill="both", expand=True,
                                                 pady=8)
        self._draw_placeholder(self.matchup_ax, "")
        self.matchup_canvas.draw()

    # ── Advanced Stats Tab ───────────────────────────────────────────────────

    def _build_advanced_tab(self):
        tab = self.tab_advanced
        lbl = tk.Label(tab, text="Advanced Statistical Analysis",
                       bg=DARK_BG, fg=FG, font=("Segoe UI", 13, "bold"))
        lbl.pack(anchor="w", padx=16, pady=(12, 4))

        self.adv_fig = plt.figure(figsize=(10, 6), facecolor=DARK_BG)
        self.adv_canvas = FigureCanvasTkAgg(self.adv_fig, master=tab)
        self.adv_canvas.get_tk_widget().pack(fill="both", expand=True,
                                             padx=8, pady=8)
        self._draw_adv_placeholder()

    def _draw_adv_placeholder(self):
        self.adv_fig.clear()
        ax = self.adv_fig.add_subplot(111, facecolor=CARD_BG)
        self._draw_placeholder(ax, "Run simulation to unlock advanced charts")
        self.adv_canvas.draw()

    # ── Team Browser Tab ─────────────────────────────────────────────────────

    def _build_teams_tab(self):
        tab = self.tab_teams
        ctrl = ttk.Frame(tab, style="TFrame")
        ctrl.pack(fill="x", padx=12, pady=6)
        tk.Label(ctrl, text="Search:", bg=DARK_BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.team_search = tk.StringVar()
        self.team_search.trace_add("write", lambda *_: self._filter_teams())
        ttk.Entry(ctrl, textvariable=self.team_search, width=28).pack(
            side="left", padx=6)

        cols = ("Team", "PPG", "RPG", "ORPG", "DRPG",
                "APG", "TOPG", "AST/TO",
                "FG%", "2P%", "3PT%", "FT%",
                "SPG", "BPG", "SC-EFF", "SH-EFF", "Strength")
        self.teams_tree = ttk.Treeview(tab, columns=cols,
                                       show="headings", selectmode="browse")
        col_w = {"Team": 190, "PPG": 60, "RPG": 60, "ORPG": 60, "DRPG": 65,
                 "APG": 60, "TOPG": 65, "AST/TO": 65, "FG%": 60, "2P%": 60,
                 "3PT%": 60, "FT%": 60, "SPG": 60, "BPG": 60,
                 "SC-EFF": 65, "SH-EFF": 65, "Strength": 85}
        for c in cols:
            self.teams_tree.heading(c, text=c)
            self.teams_tree.column(c, width=col_w.get(c, 70), anchor="center")

        ysb = ttk.Scrollbar(tab, orient="vertical",
                            command=self.teams_tree.yview)
        xsb = ttk.Scrollbar(tab, orient="horizontal",
                            command=self.teams_tree.xview)
        self.teams_tree.configure(yscrollcommand=ysb.set,
                                  xscrollcommand=xsb.set)
        ysb.pack(side="right", fill="y")
        xsb.pack(side="bottom", fill="x")
        self.teams_tree.pack(fill="both", expand=True, padx=8)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.update_idletasks()

    def _set_progress(self, val: float):
        self.progress["value"] = val * 100
        self.update_idletasks()

    def _load_teams(self):
        if self.loading:
            return
        self.loading = True
        self._set_status("Fetching team list from ESPN API…")

        def worker():
            try:
                limit = self.team_limit.get()
                teams = get_teams(limit)
                total = len(teams)
                for i, team in enumerate(teams):
                    self._set_status(
                        f"Loading stats: {team['name']}  ({i+1}/{total})")
                    self._set_progress((i + 1) / total * 0.9)
                    try:
                        team["stats"] = get_team_stats(team["id"])
                    except Exception:
                        team["stats"] = {}
                self.teams = teams
                self.after(0, self._on_teams_loaded)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(
                    "Load Error", str(exc)))
            finally:
                self.loading = False
                self._set_progress(0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_teams_loaded(self):
        self._set_status(f"✅  Loaded {len(self.teams)} teams.")
        self.teams_loaded_lbl.config(text=str(len(self.teams)))

        names = [t["name"] for t in self.teams]
        self.matchup_a["values"] = names
        self.matchup_b["values"] = names
        if len(names) >= 2:
            self.matchup_a.set(names[0])
            self.matchup_b.set(names[1])

        self._populate_teams_tree()
        messagebox.showinfo("Teams Loaded",
                            f"Successfully loaded {len(self.teams)} teams "
                            f"with stats!")

    def _run_simulation(self):
        if not self.teams:
            messagebox.showwarning("No Teams",
                                   "Please load teams first.")
            return
        if self.loading:
            return
        self.loading = True
        runs = self.sim_runs.get()
        noise = self.noise_var.get()
        weights = self._get_active_weights()

        self._set_status(f"Running {runs:,} Monte Carlo simulations…")

        def worker():
            def prog_cb(p):
                self._set_progress(p)
                self._set_status(
                    f"Simulating… {int(p*100)}%  ({int(p*runs):,}/{runs:,} runs)")

            results = monte_carlo(self.teams, weights, runs, noise, prog_cb)
            self.results = results
            self.after(0, lambda: self._on_sim_done(runs))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sim_done(self, runs: int):
        self.loading = False
        self._set_progress(0)
        if not self.results:
            self._set_status("Simulation complete — no results.")
            return

        sorted_res = sorted(self.results.items(), key=lambda x: x[1],
                            reverse=True)
        champ, champ_wins = sorted_res[0]
        pct = champ_wins / runs

        self.sims_run_lbl.config(text=f"{runs:,}")
        self.proj_champ_lbl.config(text=champ.split()[-1])  # short name
        self.champ_pct_lbl.config(text=f"{pct:.1%}")

        self._set_status(
            f"✅  Simulation complete — projected champion: {champ} "
            f"({pct:.1%})")
        self._refresh_all_tabs()

    def _refresh_all_tabs(self):
        self._refresh_dashboard()
        self._refresh_chart()
        self._refresh_table()
        self._refresh_advanced()
        self._populate_teams_tree()

    # ── Dashboard Refresh ────────────────────────────────────────────────────

    def _refresh_dashboard(self):
        if not self.results:
            return
        runs = self.sim_runs.get()
        sorted_r = sorted(self.results.items(), key=lambda x: x[1],
                          reverse=True)[:10]

        # Build parallel lists in display order (highest win% at top = last in
        # a horizontal bar chart, so we keep ascending order for barh).
        names = [r[0].split(" ")[-1] for r in sorted_r]   # short names
        vals  = [r[1] / runs * 100 for r in sorted_r]     # win % values

        # Reverse so the best team appears at the top of the horizontal bars.
        names_plot = names[::-1]
        vals_plot  = vals[::-1]
        colors = [ACCENT if i == (len(names_plot) - 1) else ACCENT2
                  for i in range(len(names_plot))]

        self.dash_ax.clear()
        self.dash_ax.set_facecolor(CARD_BG)
        self.dash_fig.patch.set_facecolor(DARK_BG)

        bars = self.dash_ax.barh(names_plot, vals_plot, color=colors, height=0.6)

        # Annotate each bar with its value — iterate bars and vals_plot together.
        for bar, val in zip(bars, vals_plot):
            self.dash_ax.text(
                bar.get_width() + 0.2,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%",
                va="center", color=FG, fontsize=8,
            )

        self.dash_ax.set_xlabel("Win Probability (%)", color=MUTED)
        self.dash_ax.set_title("Top 10 Championship Probabilities",
                               color=FG, fontsize=11, pad=10)
        self.dash_ax.tick_params(colors=MUTED)
        for spine in self.dash_ax.spines.values():
            spine.set_edgecolor(CARD_BG)
        self.dash_fig.tight_layout()
        self.dash_canvas.draw()

    # ── Chart Refresh ────────────────────────────────────────────────────────

    def _refresh_chart(self, *_):
        if not self.results:
            return
        runs = self.sim_runs.get()
        n    = self.chart_top_n.get()
        ctype = self.chart_type.get()
        sorted_r = sorted(self.results.items(), key=lambda x: x[1],
                          reverse=True)[:n]
        names = [r[0] for r in sorted_r]
        vals  = [r[1] / runs * 100 for r in sorted_r]

        self.chart_fig.clear()
        ax = self.chart_fig.add_subplot(111)
        ax.set_facecolor(CARD_BG)
        self.chart_fig.patch.set_facecolor(DARK_BG)

        palette = plt.cm.plasma([i / max(len(vals) - 1, 1)
                                  for i in range(len(vals))])

        if ctype == "Horizontal Bar":
            names_plot = names[::-1]
            vals_plot  = vals[::-1]
            palette_plot = palette[::-1]
            ax.barh(names_plot, vals_plot, color=palette_plot, height=0.65)
            ax.set_xlabel("Win Probability (%)", color=MUTED)
            for i, v in enumerate(vals_plot):
                ax.text(v + 0.1, i, f"{v:.2f}%", va="center",
                        color=FG, fontsize=8)

        elif ctype == "Vertical Bar":
            ax.bar(range(len(names)), vals, color=palette)
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels([n.split(" ")[-1] for n in names],
                               rotation=40, ha="right", fontsize=8, color=MUTED)
            ax.set_ylabel("Win Probability (%)", color=MUTED)

        elif ctype == "Pie Chart":
            wedges, texts, autotexts = ax.pie(
                vals, labels=[n.split(" ")[-1] for n in names],
                autopct="%1.1f%%", colors=palette,
                textprops={"color": FG, "fontsize": 7})
            for at in autotexts:
                at.set_color(DARK_BG)

        elif ctype == "Treemap":
            self._draw_treemap(ax, names, vals, palette)

        ax.set_title(f"Championship Probability — Top {n} Teams",
                     color=FG, fontsize=12, pad=12)
        ax.tick_params(colors=MUTED)
        for spine in ax.spines.values():
            spine.set_edgecolor(CARD_BG)
        self.chart_fig.tight_layout()
        self.chart_canvas.draw()

    def _draw_treemap(self, ax, names, vals, colors):
        """Simple manual treemap (row-based layout, no extra dependency)."""
        total = sum(vals)
        if total == 0:
            return
        fracs = [v / total for v in vals]
        x = 0.0
        for i, frac in enumerate(fracs):
            bw = frac
            ax.add_patch(mpatches.FancyBboxPatch(
                (x, 0), bw, 1, boxstyle="round,pad=0.01",
                facecolor=colors[i], edgecolor=DARK_BG, lw=1.5))
            if bw > 0.04:
                ax.text(x + bw / 2, 0.5,
                        f"{names[i].split()[-1]}\n{vals[i]:.1f}%",
                        ha="center", va="center",
                        color="white", fontsize=max(6, int(bw * 80)),
                        fontweight="bold")
            x += bw
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])

    # ── Table Refresh ────────────────────────────────────────────────────────

    def _refresh_table(self, sort_col: str = "Win %",
                       reverse: bool = True):
        if not self.results:
            return
        runs = self.sim_runs.get()
        weights = self._get_active_weights()
        data = []
        for team in self.teams:
            wins = self.results.get(team["name"], 0)
            pct  = wins / runs
            strength = compute_strength(team.get("stats", {}), weights)
            data.append((team["name"], wins, pct, round(strength, 2)))

        sort_key = {"Win %": 2, "Team Name": 0, "Wins": 1,
                    "Strength Score": 3}.get(sort_col, 2)
        data.sort(key=lambda x: x[sort_key], reverse=reverse)

        self.tree.delete(*self.tree.get_children())
        for rank, (name, wins, pct, strength) in enumerate(data, 1):
            tag = "top3" if rank <= 3 else ("top10" if rank <= 10 else "")
            self.tree.insert("", "end",
                             values=(rank, name, wins, f"{pct:.2%}",
                                     strength),
                             tags=(tag,))

    def _filter_table(self):
        if not self.results:
            return
        query = self.table_search.get().lower()
        for row in self.tree.get_children():
            vals = self.tree.item(row, "values")
            if query in vals[1].lower():
                self.tree.reattach(row, "", "end")
            else:
                self.tree.detach(row)

    def _on_team_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "values")[1]
        if name in [t["name"] for t in self.teams]:
            self.matchup_a.set(name)
            self.notebook.select(self.tab_matchup)

    # ── Advanced Stats Refresh ───────────────────────────────────────────────

    def _refresh_advanced(self):
        if not self.results or not self.teams:
            return
        runs = self.sim_runs.get()
        weights = self._get_active_weights()

        top_n = 16
        sorted_r = sorted(self.results.items(), key=lambda x: x[1],
                          reverse=True)[:top_n]
        top_names = [r[0] for r in sorted_r]
        top_teams = [t for t in self.teams if t["name"] in top_names]

        self.adv_fig.clear()
        self.adv_fig.patch.set_facecolor(DARK_BG)

        # 2x2 subplot grid
        axes = self.adv_fig.subplots(2, 2)

        # Four meaningful stats all present in the ESPN API response.
        stat_keys = [
            ("avgPoints",          "PPG"),
            ("avgDefensiveRebounds", "Def. Reb / Game"),
            ("assistTurnoverRatio", "AST/TO Ratio"),
            ("scoringEfficiency",  "Scoring Efficiency"),
        ]

        palette = plt.cm.cool([i / max(top_n - 1, 1)
                               for i in range(top_n)])

        for ax_idx, (key, label) in enumerate(stat_keys):
            ax = axes[ax_idx // 2][ax_idx % 2]
            ax.set_facecolor(CARD_BG)
            vals  = [t.get("stats", {}).get(key, 0) for t in top_teams]
            names = [t["name"].split(" ")[-1] for t in top_teams]
            sorted_pairs = sorted(zip(vals, names, palette[:len(vals)]),
                                  reverse=True)
            if sorted_pairs:
                s_vals, s_names, s_colors = zip(*sorted_pairs)
            else:
                s_vals, s_names, s_colors = [], [], []
            ax.barh(list(s_names)[::-1], list(s_vals)[::-1],
                    color=list(s_colors)[::-1], height=0.6)
            ax.set_title(label, color=FG, fontsize=9, pad=6)
            ax.tick_params(colors=MUTED, labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor(CARD_BG)

        self.adv_fig.suptitle("Top 16 Teams — Key Stat Breakdown",
                              color=FG, fontsize=12, y=1.01)
        self.adv_fig.tight_layout()
        self.adv_canvas.draw()

    # ── Team Browser ─────────────────────────────────────────────────────────

    def _populate_teams_tree(self):
        """
        Populate the team browser Treeview.

        Percentage stats from the ESPN API (fieldGoalPct, threePointFieldGoalPct,
        freeThrowPct) are stored as 0–100 values (e.g. 45.4).  We display them
        with a plain `%` suffix rather than Python's `:.1%` formatter (which
        would multiply by 100 again, producing values like 4540%).
        """
        self.teams_tree.delete(*self.teams_tree.get_children())
        weights = self._get_active_weights()
        for t in self.teams:
            s = t.get("stats", {})
            strength = round(compute_strength(s, weights), 2)

            # Percentage fields come from the API as 0–100 (e.g. 45.4 for 45.4%).
            # Format them as "45.4%" — do NOT use :.1% which would give "4540.0%".
            fg_pct   = f"{s.get('fieldGoalPct', 0):.1f}%"
            twoP_pct = f"{s.get('twoPointFieldGoalPct', 0):.1f}%"
            tpt_pct  = f"{s.get('threePointFieldGoalPct', 0):.1f}%"
            ft_pct   = f"{s.get('freeThrowPct', 0):.1f}%"

            self.teams_tree.insert("", "end", values=(
                t["name"],
                round(s.get("avgPoints",             0), 1),
                round(s.get("avgRebounds",           0), 1),
                round(s.get("avgOffensiveRebounds",  0), 1),
                round(s.get("avgDefensiveRebounds",  0), 1),
                round(s.get("avgAssists",            0), 1),
                round(s.get("avgTurnovers",          0), 1),
                round(s.get("assistTurnoverRatio",   0), 2),
                fg_pct,
                twoP_pct,
                tpt_pct,
                ft_pct,
                round(s.get("avgSteals",          0), 1),
                round(s.get("avgBlocks",           0), 1),
                round(s.get("scoringEfficiency",   0), 3),
                round(s.get("shootingEfficiency",  0), 3),
                strength,
            ))

    def _filter_teams(self):
        query = self.team_search.get().lower()
        for row in self.teams_tree.get_children():
            name = self.teams_tree.item(row, "values")[0].lower()
            if query in name:
                self.teams_tree.reattach(row, "", "end")
            else:
                self.teams_tree.detach(row)

    # ── Matchup Simulation ───────────────────────────────────────────────────

    def _run_matchup(self):
        if not self.teams:
            messagebox.showwarning("No Teams", "Load teams first.")
            return
        a_name = self.matchup_a.get()
        b_name = self.matchup_b.get()
        if not a_name or not b_name or a_name == b_name:
            messagebox.showwarning("Invalid Selection",
                                   "Please select two different teams.")
            return
        teamA = next((t for t in self.teams if t["name"] == a_name), None)
        teamB = next((t for t in self.teams if t["name"] == b_name), None)
        if not teamA or not teamB:
            return
        runs    = self.matchup_runs.get()
        weights = self._get_active_weights()
        noise   = self.noise_var.get()

        a_wins = 0
        for _ in range(runs):
            winner = simulate_game(teamA, teamB, weights, noise)
            if winner["name"] == a_name:
                a_wins += 1
        b_wins = runs - a_wins
        a_pct  = a_wins / runs
        b_pct  = b_wins / runs

        sA = compute_strength(teamA.get("stats", {}), weights)
        sB = compute_strength(teamB.get("stats", {}), weights)

        msg = (f"{a_name}  {a_pct:.1%}  vs  {b_pct:.1%}  {b_name}\n\n"
               f"Strength scores:  {a_name}: {sA:.2f}  •  "
               f"{b_name}: {sB:.2f}\n\n"
               f"Simulated {runs:,} games")
        self.matchup_result_var.set(msg)

        # Bar chart
        self.matchup_ax.clear()
        self.matchup_ax.set_facecolor(CARD_BG)
        self.matchup_fig.patch.set_facecolor(CARD_BG)
        bars = self.matchup_ax.bar(
            [a_name.split(" ")[-1], b_name.split(" ")[-1]],
            [a_pct * 100, b_pct * 100],
            color=[ACCENT, ACCENT2], width=0.45)
        for bar, val in zip(bars, [a_pct, b_pct]):
            self.matchup_ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.1%}", ha="center", color=FG,
                fontsize=11, fontweight="bold")
        self.matchup_ax.set_ylim(0, 115)
        self.matchup_ax.set_ylabel("Win Probability (%)", color=MUTED)
        self.matchup_ax.set_title("Head-to-Head Simulation", color=FG,
                                  pad=10)
        self.matchup_ax.tick_params(colors=MUTED)
        for spine in self.matchup_ax.spines.values():
            spine.set_edgecolor(CARD_BG)
        self.matchup_fig.tight_layout()
        self.matchup_canvas.draw()

    # ── Weight Utilities ─────────────────────────────────────────────────────

    def _get_active_weights(self) -> dict:
        active = {}
        for label, (key, default_w, positive) in DEFAULT_WEIGHTS.items():
            wvar, evar = self.weight_vars[label]
            if evar.get():
                active[label] = (key, wvar.get(), positive)
        return active

    def _reset_weights(self):
        for label, (key, w, pos) in DEFAULT_WEIGHTS.items():
            wvar, evar = self.weight_vars[label]
            wvar.set(w)
            evar.set(w > 0)
        self._set_status("Weights reset to defaults.")

    # ── Export / Import ──────────────────────────────────────────────────────

    def _export_csv(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save results as CSV")
        if not path:
            return
        runs = self.sim_runs.get()
        weights = self._get_active_weights()
        sorted_r = sorted(self.results.items(), key=lambda x: x[1],
                          reverse=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Rank", "Team", "Wins", "Win%", "Strength"])
            for rank, (name, wins) in enumerate(sorted_r, 1):
                team = next((t for t in self.teams if t["name"] == name),
                            None)
                strength = (compute_strength(team["stats"], weights)
                            if team else "N/A")
                writer.writerow([rank, name, wins,
                                 f"{wins/runs:.4f}", strength])
        messagebox.showinfo("Exported", f"Results saved to:\n{path}")

    def _export_chart(self):
        if not self.results:
            messagebox.showwarning("No Results", "Run simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
            title="Save chart as PNG")
        if not path:
            return
        self.chart_fig.savefig(path, dpi=150, bbox_inches="tight",
                               facecolor=DARK_BG)
        messagebox.showinfo("Exported", f"Chart saved to:\n{path}")

    def _save_config(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save configuration")
        if not path:
            return
        config = {
            "sim_runs": self.sim_runs.get(),
            "noise": self.noise_var.get(),
            "team_limit": self.team_limit.get(),
            "weights": {
                label: {"value": wvar.get(), "enabled": evar.get()}
                for label, (wvar, evar) in self.weight_vars.items()
            }
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        messagebox.showinfo("Saved", f"Configuration saved to:\n{path}")

    def _load_config(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load configuration")
        if not path or not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.sim_runs.set(config.get("sim_runs", 2000))
        self.noise_var.set(config.get("noise", 1.0))
        self.team_limit.set(config.get("team_limit", 64))
        for label, vals in config.get("weights", {}).items():
            if label in self.weight_vars:
                wvar, evar = self.weight_vars[label]
                wvar.set(vals.get("value", 0))
                evar.set(vals.get("enabled", False))
        self._set_status(f"Configuration loaded from {os.path.basename(path)}")
        messagebox.showinfo("Loaded", "Configuration applied successfully!")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
