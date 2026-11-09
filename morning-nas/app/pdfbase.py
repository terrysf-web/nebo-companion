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
# The minimal style is drawn in grey, not black: on a matte screen a hairline
# at full black still reads as a hard rule and fights the handwriting.
HAIR = HexColor("#b4b4b4")
DOT = HexColor("#bdbdbd")
SUN = HexColor("#b23b3b")
SAT = HexColor("#3b62b2")

PAGE_SIZES = {
    # TCL NXTPAPER tablet aspect ratio, 5:3 landscape
    "tablet": (1200.0, 720.0),
    "a4": (841.89, 595.28),
    "a5": (595.28, 419.53),
}


def page_size(name: str) -> tuple[float, float]:
    """A named size, or "WxH" in points to match a screen exactly.

    Tablet screens differ more than the marketing suggests — 4:3, 16:10 and
    3:2 all ship as "NXTPAPER" — and a page whose shape does not match the
    screen can never fill it, however the reader is set up.
    """
    if name not in PAGE_SIZES and "x" in name:
        w, _, h = name.partition("x")
        try:
            width, height = float(w), float(h)
        except ValueError:
            return PAGE_SIZES["tablet"]
        if width > 0 and height > 0:
            return width, height
    return PAGE_SIZES.get(name, PAGE_SIZES["tablet"])


class Sheet:
    """Canvas wrapper for one kind of PDF."""

    def __init__(self, page: str = "tablet", style: str = "minimal"):
        self.font, self.bold = register()
        self.w, self.h = page_size(page)
        # The minimal style keeps a wider margin: white space is the point.
        self.minimal = style != "classic"
        self.margin = round(self.w * (0.052 if self.minimal else 0.035))

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
        color: Color | None = None,
    ) -> float:
        c.setStrokeColor(color or (HAIR if self.minimal else FAINT))
        c.setLineWidth(0.4 if self.minimal else 0.6)
        y = top
        for _ in range(max(rows, 0)):
            y = y - gap
            c.line(x, y, x + width, y)
        return y

    def dots(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        top: float,
        width: float,
        height: float,
        pitch: float = 24.0,
    ) -> None:
        """A dot grid: guides the hand without drawing a box around it.

        Each dot is a zero-length round-capped segment in one path, not a
        circle: a full page of circles added megabytes to the file.
        """
        if height <= 0 or width <= 0:
            return
        c.saveState()
        c.setStrokeColor(DOT)
        c.setLineWidth(1.0)
        c.setLineCap(1)  # round
        path = c.beginPath()
        cols = max(int(width / pitch), 1)
        rows = max(int(height / pitch), 1)
        for r in range(rows + 1):
            yy = top - r * pitch
            for col in range(cols + 1):
                xx = x + col * pitch
                path.moveTo(xx, yy)
                path.lineTo(xx, yy)
        c.drawPath(path, stroke=1, fill=0)
        c.restoreState()

    def checkboxes(
        self, c: pdfcanvas.Canvas, x: float, top: float, width: float, rows: int, gap: float
    ) -> float:
        box = min(10.0, gap * 0.5)
        y = top
        for _ in range(max(rows, 0)):
            y = y - gap
            c.setStrokeColor(HAIR if self.minimal else LINE)
            c.setLineWidth(0.4 if self.minimal else 0.8)
            c.rect(x, y + 2, box, box, stroke=1, fill=0)
            c.setStrokeColor(HAIR if self.minimal else FAINT)
            c.setLineWidth(0.4 if self.minimal else 0.6)
            c.line(x + box + 10, y, x + width, y)
        return y

    def section(
        self, c: pdfcanvas.Canvas, x: float, y: float, title: str, size: float = 11
    ) -> float:
        """Draw a section label; return the y just below it."""
        if not self.minimal:
            self.text(c, x, y - size * 0.2, title, size=size, bold=True)
            return y - size - 4
        small = size * 0.72
        # Letter-spaced small capitals: the label recedes, the space stays.
        text = c.beginText(x, y - small * 0.2)
        text.setFont(self.font, small)
        text.setFillColor(GRAY)
        text.setCharSpace(small * 0.14)
        text.textOut(title.upper())
        c.drawText(text)
        return y - small - 10

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
        size: float | None = None,
    ) -> float:
        """A tap target; returns its left x.

        Minimal style draws no pill — just the word, with a short rule under
        the active one. The link rectangle stays finger-sized either way.
        """
        if self.minimal:
            pt = size or 9
            self.text(
                c, x + width / 2, y + height / 2 - pt * 0.36, label,
                size=pt, color=INK if active else GRAY, align="center",
            )
            if active:
                c.setStrokeColor(INK)
                c.setLineWidth(0.7)
                mid = x + width / 2
                c.line(mid - width * 0.3, y + height / 2 - 7, mid + width * 0.3,
                       y + height / 2 - 7)
        else:
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
