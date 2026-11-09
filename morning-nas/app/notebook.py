"""A work daybook: tasks first, with a schedule beside them.

The thing carried into work every day is not a planner and not a notebook —
it is a list of what has to get done, and the meetings that keep adding to it.
So this file is built around three pages that point at each other:

    Open items   one running list, the only place a task is tracked to done
    Day          what is being done today, with the hours beside it
    Meeting      notes, and the actions a meeting just created

A task is written once on Open items and ticked there. A day page is a
working surface, not a record: copy across what today is for, and anything
not finished is simply still open on the list.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from pathlib import Path

from reportlab.pdfbase.pdfdoc import PDFName
from reportlab.pdfgen import canvas as pdfcanvas

from .config import Config
from .pdfbase import FAINT, GRAY, HAIR, INK, LINE, Sheet

log = logging.getLogger(__name__)

INDEX = "index"
MEETINGS = "meetings"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def open_key(i: int) -> str:
    return f"open-{i:02d}"


def day_key(d: date) -> str:
    return f"day-{d.isoformat()}"


def meet_key(i: int) -> str:
    return f"meet-{i:03d}"


class Daybook(Sheet):
    def __init__(
        self,
        cfg: Config,
        first: date,
        weeks: int = 12,
        meetings: int = 30,
        open_pages: int = 4,
        saturdays: bool = False,
    ):
        super().__init__(cfg.planner_page, cfg.planner_style)
        self.cfg = cfg
        # A4-sized point values, scaled to whatever page this is drawn on.
        self.k = self.h / 595.28
        self.meetings = max(meetings, 0)
        self.open_pages = max(open_pages, 1)

        start = first - timedelta(days=first.weekday())  # that week's Monday
        span = 6 if saturdays else 5
        self.days = [
            start + timedelta(days=w * 7 + i)
            for w in range(max(weeks, 1))
            for i in range(span)
        ]
        self.day_set = set(self.days)

    @property
    def right(self) -> float:
        return self.w - self.margin

    # -- shared furniture ----------------------------------------------
    def frame(self, c: pdfcanvas.Canvas, title: str, sub: str, current: str) -> float:
        c.setPageSize((self.w, self.h))
        k = self.k
        top = self.h - self.margin
        self.text(
            c, self.margin, top - 20 * k, title,
            size=17 * k if self.minimal else 19 * k, bold=not self.minimal,
        )
        if sub:
            self.text(c, self.margin, top - 34 * k, sub, size=8 * k, color=GRAY)

        items = [("Index", INDEX), ("Open", open_key(1))]
        if self.meetings:
            items.append(("Meetings", MEETINGS))
        width, gap, height = 56 * k, 6 * k, 20 * k
        x = self.right - (width + gap) * len(items) + gap
        y = top - 24 * k
        for label, key in items:
            self.button(
                c, x, y, label, key, width=width, height=height,
                active=label.lower() == current, size=10 * k,
            )
            x += width + gap

        c.setStrokeColor(HAIR if self.minimal else LINE)
        c.setLineWidth(0.5 if self.minimal else 1)
        rule = top - 44 * k
        c.line(self.margin, rule, self.right, rule)
        return rule - 14 * k

    # -- index -----------------------------------------------------------
    def index_page(self, c: pdfcanvas.Canvas) -> None:
        c.bookmarkPage(INDEX, fit="Fit")
        k = self.k
        first, last = self.days[0], self.days[-1]
        top = self.frame(
            c, "Daybook",
            f"{first.strftime('%b %d, %Y')} - {last.strftime('%b %d, %Y')}"
            "   ·   tap a date to open that day",
            "index",
        )
        bottom = self.margin

        months: list[date] = []
        for d in self.days:
            m = d.replace(day=1)
            if m not in months:
                months.append(m)

        cols = 2 if self.h > self.w else 4
        rows = -(-len(months) // cols)
        gap = 24 * k
        cell_w = (self.right - self.margin - gap * (cols - 1)) / cols
        cell_h = min((top - bottom - gap * (rows - 1)) / max(rows, 1), 260 * k)

        cal = calendar.Calendar(firstweekday=0)
        for i, month in enumerate(months):
            col, row = i % cols, i // cols
            x = self.margin + col * (cell_w + gap)
            y = top - cell_h - row * (cell_h + gap)
            self.text(
                c, x, y + cell_h - 12 * k,
                f"{MONTHS[month.month - 1]} {month.year}", size=11 * k, bold=True,
            )
            weeks = cal.monthdatescalendar(month.year, month.month)
            col_w = cell_w / 7
            row_h = min((cell_h - 28 * k) / (len(weeks) + 1), 26 * k)
            head = y + cell_h - 28 * k
            for n, name in enumerate(WEEKDAYS):
                self.text(
                    c, x + col_w * n + col_w / 2, head, name[0],
                    size=7 * k, color=GRAY, align="center",
                )
            for r, week in enumerate(weeks):
                for n, d in enumerate(week):
                    if d.month != month.month:
                        continue
                    cx = x + col_w * n + col_w / 2
                    cy = head - row_h * (r + 1)
                    live = d in self.day_set
                    self.text(
                        c, cx, cy, str(d.day), size=9 * k,
                        color=INK if live else FAINT, align="center",
                    )
                    if not live:
                        continue
                    if d == date.today():
                        c.setStrokeColor(INK)
                        c.setLineWidth(0.6)
                        c.rect(cx - col_w / 2 + 2, cy - 5 * k,
                               col_w - 4, row_h * 0.85, stroke=1, fill=0)
                    self.link(
                        c, day_key(d),
                        (cx - col_w / 2, cy - 6 * k, cx + col_w / 2, cy + 12 * k),
                    )
        c.showPage()

    # -- the running list --------------------------------------------------
    def open_page(self, c: pdfcanvas.Canvas, index: int) -> None:
        c.bookmarkPage(open_key(index), fit="Fit")
        k = self.k
        top = self.frame(
            c, f"Open items  {index}/{self.open_pages}",
            "Every task lives here until it is ticked. Day pages only borrow from it.",
            "open",
        )
        bottom = self.margin
        usable = self.right - self.margin

        box = 11 * k
        from_x = self.margin + usable * 0.62
        due_x = self.margin + usable * 0.78
        done_x = self.margin + usable * 0.89

        for label, x in (("TASK", self.margin + box + 10 * k),
                         ("FROM", from_x), ("DUE", due_x), ("DONE", done_x)):
            self.text(c, x, top, label, size=7.5 * k, color=GRAY)

        gap = 26 * k
        y = top - 10 * k
        rows = max(int((y - bottom) / gap), 1)
        for _ in range(rows):
            y -= gap
            c.setStrokeColor(HAIR)
            c.setLineWidth(0.5)
            c.rect(self.margin, y + 2, box, box, stroke=1, fill=0)
            c.line(self.margin + box + 10 * k, y, self.right, y)
            # faint uprights, so the columns stay readable once written in
            c.setStrokeColor(FAINT)
            for x in (from_x - 6 * k, due_x - 6 * k, done_x - 6 * k):
                c.line(x, y, x, y + gap - 4)
        c.showPage()

    # -- a working day -----------------------------------------------------
    def day_page(self, c: pdfcanvas.Canvas, d: date) -> None:
        c.bookmarkPage(day_key(d), fit="Fit")
        k = self.k
        title = f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}"
        top = self.frame(c, title, f"{d.year}  ·  week {d.isocalendar()[1]:02d}", "")
        bottom = self.margin
        usable = self.right - self.margin

        sched_w = usable * 0.30
        task_x = self.margin + sched_w + 26 * k
        task_w = self.right - task_x

        # Schedule: a quiet column, not the point of the page
        y = self.section(c, self.margin, top, "Schedule", size=12 * k)
        hours = list(range(self.cfg.planner_start_hour, self.cfg.planner_end_hour + 1))
        slot = (y - bottom) / max(len(hours), 1)
        gutter = 24 * k
        for i, hour in enumerate(hours):
            ly = y - slot * (i + 1)
            c.setStrokeColor(HAIR)
            c.setLineWidth(0.5)
            c.line(self.margin, ly, self.margin + sched_w, ly)
            self.text(
                c, self.margin + 2, ly + slot - 11 * k, f"{hour:02d}",
                size=8.5 * k, color=GRAY,
            )
        c.setStrokeColor(HAIR)
        c.line(self.margin + gutter, y, self.margin + gutter, bottom)

        # Today: the main event
        space = top - bottom
        y = self.section(c, task_x, top, "Today", size=12 * k)
        gap = 28 * k
        rows = max(min(int(space * 0.50 / gap), 12), 1)
        y = self.checkboxes(c, task_x, y, task_w, rows, gap) - 24 * k

        y = self.section(c, task_x, y, "Came up today", size=12 * k)
        self.text(
            c, self.right, y + 11 * k, "copy to Open items",
            size=7.5 * k, color=GRAY, align="right",
        )
        gap2 = 26 * k
        rows2 = max(min(int((y - bottom) * 0.55 / gap2), 6), 1)
        y = self.checkboxes(c, task_x, y, task_w, rows2, gap2) - 22 * k

        if y - bottom > 50 * k:
            y = self.section(c, task_x, y, "Notes", size=12 * k)
            self.dots(c, task_x, y - 6, task_w, y - bottom - 6, pitch=22 * k)
        c.showPage()

    # -- meetings ----------------------------------------------------------
    def meetings_index_page(self, c: pdfcanvas.Canvas) -> None:
        c.bookmarkPage(MEETINGS, fit="Fit")
        k = self.k
        top = self.frame(
            c, "Meetings", "Write the date and who it was with", "meetings"
        )
        bottom = self.margin
        cols = 2
        gap = 30 * k
        col_w = (self.right - self.margin - gap) / cols
        per_col = -(-self.meetings // cols)
        row_h = (top - bottom) / max(per_col, 1)
        for i in range(self.meetings):
            col, row = i // per_col, i % per_col
            x = self.margin + col * (col_w + gap)
            y = top - row_h * (row + 1)
            self.text(c, x, y + 5 * k, f"{i + 1:02d}", size=8 * k, color=GRAY)
            c.setStrokeColor(HAIR)
            c.setLineWidth(0.5)
            c.line(x + 20 * k, y + 2, x + col_w, y + 2)
            self.link(c, meet_key(i + 1), (x, y, x + col_w, y + row_h - 4))
        c.showPage()

    def meeting_page(self, c: pdfcanvas.Canvas, index: int) -> None:
        c.bookmarkPage(meet_key(index), fit="Fit")
        k = self.k
        top = self.frame(c, f"Meeting {index:02d}", "", "meetings")
        bottom = self.margin
        usable = self.right - self.margin

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
        if self.h > self.w:
            split = bottom + (body - bottom) * 0.36
            y = self.section(c, self.margin, body, "Notes", size=12 * k)
            self.dots(c, self.margin, y - 6, usable, y - split - 16 * k, pitch=22 * k)
            half = (usable - 24 * k) / 2
            y = self.section(c, self.margin, split, "Decided", size=12 * k)
            self.rules(
                c, self.margin, y, half, max(int((y - bottom) / (22 * k)), 1), 22 * k
            )
            x2 = self.margin + half + 24 * k
            y = self.section(c, x2, split, "Actions", size=12 * k)
            self.text(
                c, self.right, y + 11 * k, "copy to Open items",
                size=7.5 * k, color=GRAY, align="right",
            )
            self.checkboxes(
                c, x2, y, half, max(int((y - bottom) / (24 * k)), 1), 24 * k
            )
        else:
            left_w = usable * 0.58
            right_x = self.margin + left_w + 24 * k
            right_w = self.right - right_x
            y = self.section(c, self.margin, body, "Notes", size=12 * k)
            self.dots(c, self.margin, y - 6, left_w, y - bottom - 6, pitch=22 * k)
            y = self.section(c, right_x, body, "Decided", size=12 * k)
            y = self.rules(c, right_x, y, right_w, 5, 22 * k) - 20 * k
            y = self.section(c, right_x, y, "Actions", size=12 * k)
            self.text(
                c, self.right, y + 11 * k, "to Open items",
                size=7.5 * k, color=GRAY, align="right",
            )
            self.checkboxes(
                c, right_x, y, right_w, max(int((y - bottom) / (24 * k)), 1), 24 * k
            )
        c.showPage()

    # -- assembly ------------------------------------------------------------
    def build(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        c = pdfcanvas.Canvas(str(out_path), pagesize=(self.w, self.h))
        c.setTitle("Daybook")
        c.setAuthor("morning")
        c.setCatalogEntry("PageLayout", PDFName("SinglePage"))
        c.setCatalogEntry("PageMode", PDFName("UseNone"))
        c.setViewerPreference("FitWindow", "true")

        self.index_page(c)
        for i in range(1, self.open_pages + 1):
            self.open_page(c, i)
        for d in self.days:
            self.day_page(c, d)
        if self.meetings:
            self.meetings_index_page(c)
            for i in range(1, self.meetings + 1):
                self.meeting_page(c, i)

        c.save()
        log.info("daybook written: %s", out_path)
        return out_path


def build_notebook(
    cfg: Config,
    weeks: int = 12,
    first: date | None = None,
    meetings: int = 30,
    open_pages: int = 4,
    out: Path | None = None,
) -> Path:
    return Daybook(
        cfg, first or date.today(), weeks, meetings, open_pages
    ).build(out or (cfg.planner_dir / "daybook.pdf"))
