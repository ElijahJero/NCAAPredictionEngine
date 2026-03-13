# Theme colours, URL constants, stat weights, and ttk style map.

TEAM_LIST_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/teams"
)
APP_TITLE = "NCAA Prediction Tool"
DARK_BG   = "#1e1e2e"
CARD_BG   = "#2a2a3e"
ACCENT    = "#7c3aed"
ACCENT2   = "#06b6d4"
FG        = "#e2e8f0"
MUTED     = "#94a3b8"
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
DANGER    = "#ef4444"

# ── Stat key mapping from ESPN API response ───────────────────────────────────
# ESPN's stats endpoint returns category arrays with these exact `name` fields.
# Keys below must match the `name` field values in the API response.
# Percentage stats (freeThrowPct, fieldGoalPct, threePointFieldGoalPct) are
# returned as 0–100 values (e.g. 72.4), NOT 0–1 fractions.

DEFAULT_WEIGHTS = {
    # ── Core scoring / production ─────────────────────────────────────────
    "Offense (PPG)":              ("avgPoints",              0.25, True),
    "Defense (Opp PPG)":          ("avgPointsAllowed",       0.15, False),
    "Rebounds (RPG)":             ("avgRebounds",            0.15, True),
    "Turnovers (TOPG)":           ("avgTurnovers",           0.10, False),
    # ── Per-game playmaking / shooting ───────────────────────────────────
    "Assists (APG)":              ("avgAssists",             0.05, True),
    "FG% (Field Goal %)":         ("fieldGoalPct",           0.05, True),
    "3PT% (Three Point %)":       ("threePointFieldGoalPct", 0.05, True),
    "FT% (Free Throw %)":         ("freeThrowPct",           0.05, True),
    "Steals (SPG)":               ("avgSteals",              0.05, True),
    "Blocks (BPG)":               ("avgBlocks",              0.05, True),
    # ── Additional ESPN fields (off by default, tune as desired) ─────────
    "Off. Rebounds (ORPG)":       ("avgOffensiveRebounds",   0.00, True),
    "Def. Rebounds (DRPG)":       ("avgDefensiveRebounds",   0.00, True),
    "Fouls (PFPG)":               ("avgFouls",               0.00, False),
    "AST/TO Ratio":               ("assistTurnoverRatio",    0.00, True),
    "2PT% (2-Point %)":           ("twoPointFieldGoalPct",   0.00, True),
    "Scoring Efficiency":         ("scoringEfficiency",      0.00, True),
    "Shooting Efficiency":        ("shootingEfficiency",     0.00, True),
}

STYLE = {
    "TFrame":       {"configure": {"background": DARK_BG}},
    "Card.TFrame":  {"configure": {"background": CARD_BG,  "relief": "flat"}},
    "TLabel":       {"configure": {"background": DARK_BG,  "foreground": FG,
                                   "font": ("Segoe UI", 10)}},
    "Header.TLabel":{"configure": {"background": DARK_BG,  "foreground": FG,
                                   "font": ("Segoe UI", 18, "bold")}},
    "Sub.TLabel":   {"configure": {"background": DARK_BG,  "foreground": MUTED,
                                   "font": ("Segoe UI", 9)}},
    "Card.TLabel":  {"configure": {"background": CARD_BG,  "foreground": FG,
                                   "font": ("Segoe UI", 10)}},
    "TButton":      {"configure": {"font": ("Segoe UI", 10, "bold"),
                                   "relief": "flat", "cursor": "hand2"}},
    "Accent.TButton": {"configure": {"background": ACCENT, "foreground": "white",
                                     "font": ("Segoe UI", 11, "bold"),
                                     "relief": "flat", "padding": (12, 6)}},
    "TNotebook":    {"configure": {"background": DARK_BG, "tabmargins": [2, 5, 2, 0]}},
    "TNotebook.Tab":{"configure": {"background": CARD_BG,  "foreground": MUTED,
                                   "font": ("Segoe UI", 10),
                                   "padding": [12, 6]},
                     "map":       {"background": [("selected", ACCENT)],
                                   "foreground": [("selected", "white")]}},
    "Treeview":     {"configure": {"background": CARD_BG,  "foreground": FG,
                                   "fieldbackground": CARD_BG,
                                   "rowheight": 26,
                                   "font": ("Segoe UI", 9)}},
    "Treeview.Heading": {"configure": {"background": ACCENT, "foreground": "white",
                                       "font": ("Segoe UI", 9, "bold"), "relief": "flat"}},
    "TScale":       {"configure": {"background": DARK_BG, "troughcolor": CARD_BG,
                                   "sliderlength": 18}},
    "TProgressbar": {"configure": {"background": ACCENT,  "troughcolor": CARD_BG}},
    "TEntry":       {"configure": {"fieldbackground": CARD_BG, "foreground": FG,
                                   "insertcolor": FG, "font": ("Segoe UI", 10)}},
    "TCombobox":    {"configure": {"fieldbackground": CARD_BG, "foreground": FG,
                                   "font": ("Segoe UI", 10)}},
    "TCheckbutton": {"configure": {"background": DARK_BG, "foreground": FG,
                                   "font": ("Segoe UI", 10), "activebackground": DARK_BG}},
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA / SIMULATION LAYER
# ─────────────────────────────────────────────────────────────────────────────
