"""The morning brief as a page you can write on.

Left column is printed — what the day already contains. The rest is empty and
ruled, so the first thing you do at 06:00 is plan the day by hand right next to
the brief instead of copying it somewhere else. Same page size as the planner,
so both live in the same notebook on the tablet.
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfgen import canvas as pdfcanvas

from .brief import Brief
from .config import Config
from .pdfbase import FAINT, GRAY, INK, LINE, Sheet

log = logging.getLogger(__name__)


class BriefSheet(Sheet):
    def __init__(self, cfg: Config):
        super().__init__(cfg.planner_page)
        self.cfg = cfg

    def _bullets(
        self,
        c: pdfcanvas.Canvas,
        x: float,
        top: float,
        width: float,
        items: list[str],
        size: float = 9,
        marker: str = "·",
        floor: float = 0.0,
    ) -> float:
        y = top
        for item in items:
            if y - size * 2 < floor:
                break
            self.text(c, x, y - size, marker, size=size, color=GRAY)
            y = self.paragraph(
                c, x + 12, y, item, width - 12, size=size, leading=size * 1.4
            )
            y -= 3
        return y

    def draw(self, c: pdfcanvas.Canvas, brief: Brief) -> None:
        c.setPageSize((self.w, self.h))
        top = self.h - self.margin
        bottom = self.margin

        self.text(c, self.margin, top - 22, brief.title(), size=22, bold=True)
        stamp = brief.generated_at.replace("T", " ")[:16]
        sub = f"Morning brief · {stamp}"
        if brief.source != "claude":
            sub += f" · {brief.source}"
        self.text(c, self.margin, top - 39, sub, size=9, color=GRAY)
        if brief.weather:
            self.text(c, self.w - self.margin, top - 39, brief.weather, size=9,
                      color=GRAY, align="right")

        c.setStrokeColor(LINE)
        c.setLineWidth(1)
        rule = top - 50
        c.line(self.margin, rule, self.w - self.margin, rule)

        usable = self.w - self.margin * 2
        gap = 26.0
        left_w = usable * 0.36
        mid_w = usable * 0.30
        right_w = usable - left_w - mid_w - gap * 2
        mid_x = self.margin + left_w + gap
        right_x = mid_x + mid_w + gap
        body = rule - 12

        # Divider lines make the printed half read as separate from the blank half
        c.setStrokeColor(FAINT)
        c.setLineWidth(0.8)
        c.line(mid_x - gap / 2, body + 6, mid_x - gap / 2, bottom)

        # -- printed: what today already contains -----------------------
        y = body
        if brief.headline:
            y = self.paragraph(
                c, self.margin, y, brief.headline, left_w, size=12.5, bold=True, leading=17
            )
            y -= 18

        if brief.priorities:
            y = self.section(c, self.margin, y, "Priorities", size=9.5)
            for item in brief.priorities:
                box = 9.0
                c.setStrokeColor(LINE)
                c.setLineWidth(0.8)
                c.rect(self.margin, y - 11, box, box, stroke=1, fill=0)
                y = self.paragraph(
                    c, self.margin + box + 8, y, item, left_w - box - 8, size=9.5, leading=13
                )
                y -= 4
            y -= 16

        if brief.timeline:
            y = self.section(c, self.margin, y, "Today", size=9.5)
            for row in brief.timeline:
                when = row.get("time") or "—"
                self.text(c, self.margin, y - 9, when, size=9, bold=True)
                y = self.paragraph(
                    c, self.margin + 44, y, row.get("what", ""), left_w - 44,
                    size=9, leading=12.5,
                )
                y -= 3
            y -= 16

        if brief.watch and y > bottom + 90:
            y = self.section(c, self.margin, y, "Watch", size=9.5)
            y = self._bullets(c, self.margin, y, left_w, brief.watch, floor=bottom + 60)
            y -= 14

        if brief.mail and y > bottom + 70:
            y = self.section(c, self.margin, y, "Unread", size=9.5)
            mails = [f"{m['from']} — {m['subject']}" for m in brief.mail[:5]]
            y = self._bullets(c, self.margin, y, left_w, mails, size=8.5, floor=bottom + 20)

        if brief.closing and y > bottom + 30:
            self.text(c, self.margin, bottom + 6, brief.closing[:110], size=8.5, color=GRAY)

        # -- blank: plan it by hand --------------------------------------
        y = self.section(c, mid_x, body, "Plan")
        hours = list(range(self.cfg.planner_start_hour, self.cfg.planner_end_hour + 1))
        slot_h = (y - bottom) / max(len(hours), 1)
        gutter = 24.0
        for i, hour in enumerate(hours):
            ly = y - slot_h * (i + 1)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.6)
            c.line(mid_x, ly, mid_x + mid_w, ly)
            self.text(c, mid_x + 2, ly + slot_h - 10, f"{hour:02d}", size=8, color=GRAY)
        c.setStrokeColor(LINE)
        c.line(mid_x + gutter - 4, y, mid_x + gutter - 4, bottom)

        y = self.section(c, right_x, body, "My top 3")
        y = self.checkboxes(c, right_x, y, right_w, 3, 28) - 26
        y = self.section(c, right_x, y, "Notes")
        self.rules(c, right_x, y, right_w, max(int((y - bottom) / 20), 1), 20)

        c.showPage()

    def blank_page(self, c: pdfcanvas.Canvas, title: str) -> None:
        """A second, entirely empty page — meeting notes, thinking, whatever."""
        c.setPageSize((self.w, self.h))
        top = self.h - self.margin
        self.text(c, self.margin, top - 18, title, size=13, bold=True, color=INK)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        c.line(self.margin, top - 28, self.w - self.margin, top - 28)
        self.rules(
            c, self.margin, top - 32, self.w - self.margin * 2,
            max(int((top - 32 - self.margin) / 24), 1), 24,
        )
        c.showPage()


def build_brief_pdf(cfg: Config, brief: Brief, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet = BriefSheet(cfg)
    c = pdfcanvas.Canvas(str(out_path), pagesize=(sheet.w, sheet.h))
    c.setTitle(f"Morning brief — {brief.day}")
    c.setAuthor("morning")
    sheet.draw(c, brief)
    sheet.blank_page(c, f"{brief.title()} — notes")
    c.save()
    log.info("brief PDF written: %s", out_path)
    return out_path
