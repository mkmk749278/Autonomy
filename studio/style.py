"""Shared palette and typography so every video looks like one series."""
from manim import ManimColor

FONT = "Inter"

BG = ManimColor("#0f1720")          # deep slate
PANEL = ManimColor("#1b2632")
INK = ManimColor("#e8eef4")         # main text
MUTED = ManimColor("#8a9bab")       # secondary text
ACCENT = ManimColor("#ffd166")      # highlights / electrical signal

# Blood is always red; textbooks draw oxygen-poor blood blue by convention.
O2_RICH = ManimColor("#e63946")
O2_POOR = ManimColor("#3a7bd5")

MUSCLE = ManimColor("#b5524f")
MUSCLE_DARK = ManimColor("#7d2f33")
VALVE = ManimColor("#f5e6c8")
LUNG = ManimColor("#f2a7b0")
AIR = ManimColor("#9fd8ff")
