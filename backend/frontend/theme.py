"""
Jarvis UI theme.

A single source of truth for colors, typography, radii, and QSS
fragments so widgets never hand-roll their own one-off rgba()
strings. Change a value here and it propagates everywhere.
"""

# ==========================================================
# PALETTE
# ==========================================================

# Base panel (frameless window background)
PANEL_BG = (14, 16, 22, 232)          # near-black, slightly blue
PANEL_BORDER = (255, 255, 255, 22)    # hairline edge

# Header strip
HEADER_BG = (255, 255, 255, 10)

# Accent (Jarvis blue)
ACCENT = (110, 168, 255)
ACCENT_SOFT = (110, 168, 255, 40)
ACCENT_STRONG = (110, 168, 255, 235)

# Text
TEXT_PRIMARY = (240, 244, 252, 245)
TEXT_SECONDARY = (200, 208, 224, 150)
TEXT_MUTED = (170, 178, 196, 110)

# Bubbles
USER_BUBBLE_BG = (110, 168, 255, 200)
USER_BUBBLE_TEXT = (12, 14, 20, 255)

ASSISTANT_BUBBLE_BG = (255, 255, 255, 18)
ASSISTANT_BUBBLE_BORDER = (255, 255, 255, 24)
ASSISTANT_BUBBLE_TEXT = (235, 240, 250, 240)

ERROR_BUBBLE_BG = (255, 99, 99, 34)
ERROR_BUBBLE_BORDER = (255, 99, 99, 90)
ERROR_BUBBLE_TEXT = (255, 210, 210, 245)

# Status dot
STATUS_IDLE = (110, 168, 255, 230)
STATUS_BUSY = (255, 196, 110, 235)
STATUS_OFFLINE = (140, 148, 165, 160)

# Scrollbar
SCROLLBAR_HANDLE = (255, 255, 255, 55)
SCROLLBAR_HANDLE_HOVER = (255, 255, 255, 90)

# ==========================================================
# TYPOGRAPHY
# ==========================================================

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_LIGHT = "Segoe UI Light"

SIZE_TITLE = 12
SIZE_BODY = 13
SIZE_INPUT = 14
SIZE_TIMESTAMP = 10

# ==========================================================
# GEOMETRY
# ==========================================================

RADIUS_PANEL = 18
RADIUS_BUBBLE = 14
RADIUS_PILL = 22


def rgba(color) -> str:
    """(r, g, b[, a]) -> 'rgba(r, g, b, a)' for QSS."""
    if len(color) == 4:
        r, g, b, a = color
    else:
        r, g, b = color
        a = 255
    return f"rgba({r}, {g}, {b}, {a})"


# ==========================================================
# REUSABLE QSS FRAGMENTS
# ==========================================================

def scrollbar_qss(selector: str = "QScrollArea") -> str:
    """Slim, unobtrusive scrollbar matching the panel's dark glass look."""
    return f"""
    {selector} {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px 0px 2px 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {rgba(SCROLLBAR_HANDLE)};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {rgba(SCROLLBAR_HANDLE_HOVER)};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """
