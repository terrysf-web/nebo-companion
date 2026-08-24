"""Drawing helpers shared by the planner and the daily brief PDF.

These pages exist to be written on with a stylus, so the rules are simple:
- almost no colour (pale colour disappears on a matte NXTPAPER-style screen)
- faint rules, dark text
- anything tappable is at least fingertip-sized
"""

from __future__ import annotations

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdfcanvas

from .fonts import register

INK = HexColor("#1a1a1a")
GRAY = HexColor("#8a8a8a")
LINE = HexColor("#c8c8c8")
FAINT = HexColor("#e4e4e4")
SUN = HexColor("#b23b3b")
SAT = HexColor("#3b62b2")

PAGE_SIZES = {
    # TCL NXTPAPER tablet aspect ratio, 5:3 landscape
    "tablet": (1200.0, 720.0),
    "a4": (841.89, 595.28),
    "a5": (595.28, 419.53),
}


def page_size(name: str) -> tuple[float, float]:
    return PAGE_SIZES.get(name, PAGE_SIZES["tablet"])


class Sheet:
    """Canvas wrapper for one kind of PDF."""

    def __init__(self, page: str = "tablet"):
        self.font, self.bold = register()
        self.w, self.h = page_size(page)
        self.margin = round(self.w * 0.035)

    # -- text ---------------------------------------------------
    def text(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        y: float,
        s: str,
        size: float = 10,
        bold: bool = False,
        color: Color = INK,
        align: str = "left",
    ) -> None:
        c.setFont(self.bold if bold else self.font, size)
        c.setFillColor(color)
        if align == "right":
            c.drawRightString(x, y, s)
        elif align == "center":
            c.drawCentredString(x, y, s)
        else:
            c.drawString(x, y, s)

    def wrap(self, s: str, width: float, size: float, bold: bool = False) -> list[str]:
        """Word-wrap, falling back to character wrap (CJK has no spaces)."""
        font = self.bold if bold else self.font
        lines: list[str] = []
        for para in s.split("\n"):
            line = ""
            for word in para.split(" "):
                probe = f"{line} {word}".strip()
                if pdfmetrics.stringWidth(probe, font, size) <= width:
                    line = probe
                    continue
                if line:
                    lines.append(line)
                line = ""
                for ch in word:
                    if pdfmetrics.stringWidth(line + ch, font, size) <= width:
                        line += ch
                    else:
                        lines.append(line)
                        line = ch
            lines.append(line)
        return lines

    def paragraph(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        top: float,
        s: str,
        width: float,
        size: float = 10,
        leading: float | None = None,
        bold: bool = False,
        color: Color = INK,
        max_lines: int | None = None,
    ) -> float:
        """Draw a paragraph from its top-left corner; return the next free y."""
        leading = leading or size * 1.45
        lines = self.wrap(s, width, size, bold)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1][: max(len(lines[-1]) - 1, 0)] + "…"
        y = top
        for line in lines:
            self.text(c, x, y - size, line, size=size, bold=bold, color=color)
            y -= leading
        return y

    # -- rules and boxes ----------------------------------------
    def rules(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        top: float,
        width: float,
        rows: int,
        gap: float,
        color: Color = FAINT,
    ) -> float:
        c.setStrokeColor(color)
        c.setLineWidth(0.6)
        y = top
        for _ in range(max(rows, 0)):
            y = y - gap
            c.line(x, y, x + width, y)
        return y

    def checkboxes(
        self, c: pdfcanvas.Canvas, x: float, top: float, width: float, rows: int, gap: float
    ) -> float:
        box = min(11.0, gap * 0.55)
        y = top
        for _ in range(max(rows, 0)):
            y = y - gap
            c.setStrokeColor(LINE)
            c.setLineWidth(0.8)
            c.rect(x, y + 2, box, box, stroke=1, fill=0)
            c.setStrokeColor(FAINT)
            c.setLineWidth(0.6)
            c.line(x + box + 8, y, x + width, y)
        return y

    def section(
        self, c: pdfcanvas.Canvas, x: float, y: float, title: str, size: float = 11
    ) -> float:
        """Draw a section label; return the y just below it."""
        self.text(c, x, y - size * 0.2, title, size=size, bold=True)
        return y - size - 4

    def header(self, c: pdfcanvas.Canvas, title: str, sub: str = "") -> float:
        top = self.h - self.margin
        self.text(c, self.margin, top - 22, title, size=24, bold=True)
        if sub:
            self.text(c, self.margin, top - 40, sub, size=10, color=GRAY)
        c.setStrokeColor(LINE)
        c.setLineWidth(1)
        y = top - 52
        c.line(self.margin, y, self.w - self.margin, y)
        return y

    # -- links --------------------------------------------------
    def link(
        self, c: pdfcanvas.Canvas, key: str, rect: tuple[float, float, float, float]
    ) -> None:
        c.linkRect("", key, rect, relative=0, thickness=0)

    def button(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        y: float,
        label: str,
        key: str | None,
        width: float = 58.0,
        height: float = 24.0,
        active: bool = False,
    ) -> float:
        """A tappable rounded button; returns its left x."""
        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        c.roundRect(x, y, width, height, 5, stroke=1, fill=0)
        self.text(
            c, x + width / 2, y + height / 2 - 3.5, label,
            size=10, bold=active, color=INK if active else GRAY, align="center",
        )
        if key:
            self.link(c, key, (x, y, x + width, y + height))
        return x
