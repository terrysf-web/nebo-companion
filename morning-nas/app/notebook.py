"""A standalone meeting notebook.

The planner has meeting pages, but they sit two hundred pages in — nobody
flips there while walking into a room. This is the same page on its own: one
small file that opens on an index, one tap to the next blank sheet.

Kept deliberately plain. A meeting note is mostly listening, so the page gives
a few fields, a wide dotted area to write in, and two columns that are the
only reason to re-read it later: what was decided, and who owes what.
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase.pdfdoc import PDFName
from reportlab.pdfgen import canvas as pdfcanvas

from .config import Config
from .pdfbase import GRAY, HAIR, INK, LINE, Sheet

log = logging.getLogger(__name__)

INDEX = "index"


def note_key(i: int) -> str:
    return f"note-{i:03d}"


class Notebook(Sheet):
    def __init__(self, cfg: Config, pages: int = 60):
        super().__init__(cfg.planner_page, cfg.planner_style)
        self.cfg = cfg
        self.pages = max(pages, 1)
        # Point sizes that look right on A4 come out half-size on a 1200pt
        # tablet page, because the page is twice as tall for the same physical
        # screen. Everything here is an A4-equivalent size times this.
        self.k = self.h / 595.28

    @property
    def right(self) -> float:
        """No month tabs here, so the content runs to the margin."""
        return self.w - self.margin

    def _frame(self, c: pdfcanvas.Canvas, title: str, sub: str, back: bool) -> float:
        c.setPageSize((self.w, self.h))
        top = self.h - self.margin
        k = self.k
        self.text(
            c, self.margin, top - 20 * k, title,
            size=17 * k if self.minimal else 19 * k, bold=not self.minimal,
        )
        if sub:
            self.text(c, self.margin, top - 34 * k, sub, size=8 * k, color=GRAY)
        if back:
            self.button(
                c, self.right - 70 * k, top - 24 * k, "Index", INDEX,
                width=70 * k, height=20 * k, size=10 * k,
            )
        c.setStrokeColor(HAIR if self.minimal else LINE)
        c.setLineWidth(0.5 if self.minimal else 1)
        y = top - 44 * k
        c.line(self.margin, y, self.right, y)
        return y - 14 * k

    def index_page(self, c: pdfcanvas.Canvas) -> None:
        c.bookmarkPage(INDEX, fit="Fit")
        top = self._frame(
            c, "Meeting notes",
            "Write the date and who it was with; tap the line to open that page",
            back=False,
        )
        bottom = self.margin
        k = self.k
        cols = 2
        gap = 30.0 * k
        col_w = (self.right - self.margin - gap) / cols
        per_col = -(-self.pages // cols)
        row_h = (top - bottom) / max(per_col, 1)

        for i in range(self.pages):
            col, row = i // per_col, i % per_col
            x = self.margin + col * (col_w + gap)
            y = top - row_h * (row + 1)
            self.text(c, x, y + 5 * k, f"{i + 1:02d}", size=8 * k, color=GRAY)
            c.setStrokeColor(HAIR)
            c.setLineWidth(0.5)
            c.line(x + 20 * k, y + 2, x + col_w, y + 2)
            self.link(c, note_key(i + 1), (x, y, x + col_w, y + row_h - 4))
        c.showPage()

    def note_page(self, c: pdfcanvas.Canvas, index: int) -> None:
        c.bookmarkPage(note_key(index), fit="Fit")
        top = self._frame(c, f"{index:02d}", "", back=True)
        bottom = self.margin
        usable = self.right - self.margin

        k = self.k
        c.setStrokeColor(HAIR)
        c.setLineWidth(0.5)
        field_y = top - 2 * k
        for label, x, width in (
            ("DATE", self.margin, usable * 0.26),
            ("WITH", self.margin + usable * 0.30, usable * 0.40),
            ("ABOUT", self.margin + usable * 0.74, usable * 0.26),
        ):
            self.text(c, x, field_y, label, size=7.5 * k, color=GRAY)
            c.line(x + 32 * k, field_y - 3 * k, x + width, field_y - 3 * k)

        body = field_y - 24 * k
        tall = self.h > self.w
        if tall:
            # Portrait: notes on top, the two columns that matter underneath.
            split = bottom + (body - bottom) * 0.36
            y = self.section(c, self.margin, body, "Notes", size=12 * k)
            self.dots(c, self.margin, y - 6, usable, y - split - 16 * k, pitch=22 * k)

            half = (usable - 24 * k) / 2
            gap_r = 22 * k
            y = self.section(c, self.margin, split, "Decided", size=12 * k)
            self.rules(c, self.margin, y, half, max(int((y - bottom) / gap_r), 1), gap_r)
            x2 = self.margin + half + 24 * k
            gap_c = 24 * k
            y = self.section(c, x2, split, "Who does what, by when", size=12 * k)
            self.checkboxes(c, x2, y, half, max(int((y - bottom) / gap_c), 1), gap_c)
        else:
            left_w = usable * 0.58
            right_x = self.margin + left_w + 24 * k
            right_w = self.right - right_x
            y = self.section(c, self.margin, body, "Notes", size=12 * k)
            self.dots(c, self.margin, y - 6, left_w, y - bottom - 6, pitch=22 * k)

            gap_r = 22 * k
            y = self.section(c, right_x, body, "Decided", size=12 * k)
            y = self.rules(c, right_x, y, right_w, 5, gap_r) - 20 * k
            gap_c = 24 * k
            y = self.section(c, right_x, y, "Who does what, by when", size=12 * k)
            self.checkboxes(c, right_x, y, right_w, max(int((y - bottom) / gap_c), 1), gap_c)
        c.showPage()

    def build(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        c = pdfcanvas.Canvas(str(out_path), pagesize=(self.w, self.h))
        c.setTitle("Meeting notes")
        c.setAuthor("morning")
        c.setCatalogEntry("PageLayout", PDFName("SinglePage"))
        c.setCatalogEntry("PageMode", PDFName("UseNone"))
        c.setViewerPreference("FitWindow", "true")

        self.index_page(c)
        for i in range(1, self.pages + 1):
            self.note_page(c, i)

        c.save()
        log.info("notebook written: %s (%d pages)", out_path, self.pages + 1)
        return out_path


def build_notebook(cfg: Config, pages: int = 60, out: Path | None = None) -> Path:
    out = out or (cfg.planner_dir / "meeting-notes.pdf")
    return Notebook(cfg, pages).build(out)
