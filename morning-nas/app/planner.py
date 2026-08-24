"""Hyperlinked planner PDF for handwriting on a tablet.

The layout follows the conventions shared by the digital planners people
actually buy (GoodNotes/Notability marketplace planners, Full Focus, Panda,
Passion Planner):

    cover -> year overview -> month -> week -> day, plus a notes/meeting
    section, with persistent tab navigation on every page

Every page is reachable in one tap: section tabs top-right, month tabs down
the right edge, and every date in every grid links to its own day page.
Sized for a TCL NXTPAPER-class tablet (5:3 landscape) so a page fills the
screen with no pinch-zooming before you write on it.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from pathlib import Path

from reportlab.pdfgen import canvas as pdfcanvas

from .config import Config
from .pdfbase import FAINT, GRAY, INK, LINE, Sheet

log = logging.getLogger(__name__)

WEEKDAYS_MON = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS_SUN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

COVER = "cover"
YEAR = "year"
NOTES = "notes"


def day_key(d: date) -> str:
    return f"day-{d.isoformat()}"


def month_key(d: date) -> str:
    return f"month-{d.year}-{d.month:02d}"


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"week-{y}-{w:02d}"


def note_key(index: int) -> str:
    return f"note-{index:02d}"


def next_month(today: date) -> date:
    return (today.replace(day=28) + timedelta(days=7)).replace(day=1)


class Planner(Sheet):
    def __init__(self, cfg: Config, events: dict[date, list[str]] | None = None):
        super().__init__(cfg.planner_page)
        self.cfg = cfg
        self.events = events or {}
        self.first_weekday = 0 if cfg.planner_week_start != "sun" else 6
        self.weekday_names = WEEKDAYS_MON if self.first_weekday == 0 else WEEKDAYS_SUN
        self.cal = calendar.Calendar(firstweekday=self.first_weekday)

        # Filled in by build(); linking to a page that was never drawn makes
        # reportlab refuse to save the file, so every link is checked first.
        self.months: list[tuple[date, list[list[date]]]] = []
        self.days: set[date] = set()
        self.weeks: set[str] = set()
        self.note_count = 0

    # -- navigation ---------------------------------------------------
    @property
    def tab_width(self) -> float:
        return 30.0 if len(self.months) > 1 else 0.0

    @property
    def right(self) -> float:
        """Right edge of the writable content area."""
        return self.w - self.margin - (self.tab_width + 10 if self.tab_width else 0)

    def month_tabs(self, c: pdfcanvas.Canvas, current: date | None) -> None:
        """Vertical JAN..DEC tabs down the right edge, like a tabbed binder."""
        if not self.tab_width:
            return
        available = {(m.year, m.month): m for m, _ in self.months}
        top = self.h - self.margin
        height = (top - self.margin) / 12
        x = self.w - self.margin - self.tab_width
        year = self.months[0][0].year
        for i in range(12):
            y = top - height * (i + 1)
            target = available.get((year, i + 1))
            active = bool(current and current.month == i + 1 and current.year == year)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.8)
            if active:
                c.setFillColor(FAINT)
                c.rect(x, y, self.tab_width, height, stroke=1, fill=1)
            else:
                c.rect(x, y, self.tab_width, height, stroke=1, fill=0)
            self.text(
                c, x + self.tab_width / 2, y + height / 2 - 3,
                MONTH_SHORT[i], size=7.5, bold=active,
                color=INK if target else GRAY, align="center",
            )
            if target is not None:
                self.link(c, month_key(target), (x, y, x + self.tab_width, y + height))

    def section_tabs(
        self,
        c: pdfcanvas.Canvas,
        current: str,
        month: date | None = None,
        day: date | None = None,
    ) -> None:
        """Year / Month / Week / Day / Notes, always in the same place."""
        week_target = week_key(day) if day and week_key(day) in self.weeks else None
        day_target = day_key(day) if day and day in self.days else None
        items = [
            ("Year", YEAR),
            ("Month", month_key(month) if month else None),
            ("Week", week_target),
            ("Day", day_target),
            ("Notes", NOTES if self.note_count else None),
        ]
        width, gap, height = 54.0, 6.0, 22.0
        y = self.h - self.margin - height
        x = self.right - (width + gap) * len(items) + gap
        for label, key in items:
            self.button(
                c, x, y, label, key, width=width, height=height,
                active=label.lower() == current,
            )
            x += width + gap

    def page_frame(
        self,
        c: pdfcanvas.Canvas,
        title: str,
        sub: str,
        current: str,
        month: date | None = None,
        day: date | None = None,
    ) -> float:
        c.setPageSize((self.w, self.h))
        top = self.h - self.margin
        self.text(c, self.margin, top - 22, title, size=22, bold=True)
        if sub:
            self.text(c, self.margin, top - 39, sub, size=9.5, color=GRAY)
        self.section_tabs(c, current, month, day)
        self.month_tabs(c, month)
        c.setStrokeColor(LINE)
        c.setLineWidth(1)
        y = top - 50
        c.line(self.margin, y, self.right, y)
        return y - 10

    def link_day(self, c: pdfcanvas.Canvas, d: date, rect) -> None:
        if d in self.days:
            self.link(c, day_key(d), rect)

    # -- pages --------------------------------------------------------
    def cover_page(self, c: pdfcanvas.Canvas) -> None:
        c.setPageSize((self.w, self.h))
        c.bookmarkPage(COVER)
        first = self.months[0][0]
        last = self.months[-1][0]
        span = (
            MONTH_NAMES[first.month - 1]
            if first == last
            else f"{MONTH_NAMES[first.month - 1]} – {MONTH_NAMES[last.month - 1]}"
        )

        c.setStrokeColor(LINE)
        c.setLineWidth(1.2)
        c.rect(self.margin, self.margin, self.w - self.margin * 2, self.h - self.margin * 2)

        cx = self.w / 2
        self.text(c, cx, self.h * 0.66, str(first.year), size=64, bold=True, align="center")
        self.text(c, cx, self.h * 0.60, "PLANNER", size=16, color=GRAY, align="center")
        self.text(c, cx, self.h * 0.56, span, size=11, color=GRAY, align="center")

        c.setStrokeColor(LINE)
        c.line(cx - 90, self.h * 0.53, cx + 90, self.h * 0.53)

        available = {(m.year, m.month) for m, _ in self.months}
        cols, width, gap, height = 6, 86.0, 10.0, 30.0
        grid_w = cols * width + (cols - 1) * gap
        x0 = cx - grid_w / 2
        y = self.h * 0.44
        for i in range(12):
            col, row = i % cols, i // cols
            target = next(
                (m for m, _ in self.months if m.month == i + 1 and m.year == first.year), None
            )
            self.button(
                c, x0 + col * (width + gap), y - row * (height + gap),
                MONTH_NAMES[i], month_key(target) if target else None,
                width=width, height=height,
                active=(first.year, i + 1) in available,
            )
        y -= (height + gap) * 2 + 18
        self.button(c, cx - 150, y, "Year overview", YEAR, width=140, height=30)
        self.button(c, cx + 10, y, "Notes & meetings", NOTES if self.note_count else None,
                    width=140, height=30)
        c.showPage()

    def year_page(self, c: pdfcanvas.Canvas) -> None:
        c.setPageSize((self.w, self.h))
        c.bookmarkPage(YEAR)
        year = self.months[0][0].year
        top = self.page_frame(c, str(year), "Tap a month to open it", "year")

        cols, rows = 4, 3
        gap = 20.0
        cell_w = (self.right - self.margin - gap * (cols - 1)) / cols
        cell_h = (top - self.margin - gap * (rows - 1)) / rows
        available = {(m.year, m.month): m for m, _ in self.months}

        for i in range(12):
            col, row = i % cols, i // cols
            x = self.margin + col * (cell_w + gap)
            y = top - cell_h - row * (cell_h + gap)
            target = available.get((year, i + 1))
            self.text(
                c, x, y + cell_h - 12, MONTH_NAMES[i], size=11, bold=True,
                color=INK if target else GRAY,
            )
            if target is not None:
                self.link(c, month_key(target), (x, y, x + cell_w, y + cell_h))
            self._mini_month(c, x, y + cell_h - 26, cell_w, cell_h - 30, date(year, i + 1, 1))
        c.showPage()

    def _mini_month(
        self, c: pdfcanvas.Canvas, x: float, top: float, width: float, height: float, month: date
    ) -> None:
        weeks = self.cal.monthdatescalendar(month.year, month.month)
        col_w = width / 7
        row_h = min(height / (len(weeks) + 1), 18.0)
        for i, name in enumerate(self.weekday_names):
            self.text(
                c, x + col_w * i + col_w / 2, top - 8, name[0],
                size=6.5, color=GRAY, align="center",
            )
        for r, week in enumerate(weeks):
            for col, d in enumerate(week):
                if d.month != month.month:
                    continue
                cx = x + col_w * col + col_w / 2
                cy = top - 8 - row_h * (r + 1)
                self.text(c, cx, cy, str(d.day), size=7.5, color=INK, align="center")
                self.link_day(c, d, (cx - col_w / 2, cy - 3, cx + col_w / 2, cy + 9))

    def month_page(self, c: pdfcanvas.Canvas, month: date, weeks: list[list[date]]) -> None:
        c.bookmarkPage(month_key(month))
        top = self.page_frame(
            c, f"{MONTH_NAMES[month.month - 1]} {month.year}",
            "Tap a date to open its day page", "month", month=month,
        )

        side = round(self.w * 0.20)
        grid_w = self.right - self.margin - side - 20
        grid_x = self.margin
        bottom = self.margin

        head_h = 16.0
        cell_h = (top - head_h - bottom) / max(len(weeks), 1)
        cell_w = grid_w / 7

        for i, name in enumerate(self.weekday_names):
            weekend = name in ("Sat", "Sun")
            self.text(
                c, grid_x + cell_w * i + cell_w / 2, top - 11, name.upper(),
                size=8, bold=True, color=GRAY if weekend else INK, align="center",
            )

        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        for r in range(len(weeks) + 1):
            y = top - head_h - cell_h * r
            c.line(grid_x, y, grid_x + grid_w, y)
        for col in range(8):
            x = grid_x + cell_w * col
            c.line(x, top - head_h, x, top - head_h - cell_h * len(weeks))

        today = date.today()
        for r, week in enumerate(weeks):
            for col, d in enumerate(week):
                x = grid_x + cell_w * col
                y = top - head_h - cell_h * (r + 1)
                in_month = d.month == month.month
                self.text(
                    c, x + 6, y + cell_h - 14, str(d.day),
                    size=11, bold=in_month, color=INK if in_month else FAINT,
                )
                if d == today:
                    c.setStrokeColor(INK)
                    c.setLineWidth(1.4)
                    c.rect(x + 1.5, y + 1.5, cell_w - 3, cell_h - 3, stroke=1, fill=0)
                    c.setStrokeColor(LINE)
                    c.setLineWidth(0.8)
                if not in_month:
                    continue
                self.link_day(c, d, (x, y, x + cell_w, y + cell_h))
                for n, title in enumerate(self.events.get(d, [])[:3]):
                    self.text(
                        c, x + 6, y + cell_h - 27 - n * 10,
                        title[:22], size=7, color=GRAY,
                    )

        sx = self.right - side
        y = self.section(c, sx, top - 11, "Goals this month")
        y = self.checkboxes(c, sx, y, side, 5, 24) - 28
        y = self.section(c, sx, y, "Notes")
        self.rules(c, sx, y, side, max(int((y - bottom) / 22), 1), 22)
        c.showPage()

    def week_page(self, c: pdfcanvas.Canvas, month: date, week: list[date]) -> None:
        c.bookmarkPage(week_key(week[0]))
        span = f"{week[0].strftime('%b %d')} – {week[-1].strftime('%b %d, %Y')}"
        top = self.page_frame(c, "Week", span, "week", month=month, day=week[0])

        bottom = self.margin
        band = 128.0
        col_top = top
        col_bottom = bottom + band + 18
        usable = self.right - self.margin
        col_w = usable / 7
        head = 20.0

        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        for i in range(8):
            x = self.margin + col_w * i
            c.line(x, col_top, x, col_bottom)
        c.line(self.margin, col_top, self.right, col_top)
        c.line(self.margin, col_top - head, self.right, col_top - head)
        c.line(self.margin, col_bottom, self.right, col_bottom)

        for i, d in enumerate(week):
            x = self.margin + col_w * i
            in_month = d.month == month.month
            self.text(
                c, x + 8, col_top - 14, f"{self.weekday_names[i].upper()}  {d.day}",
                size=9.5, bold=True, color=INK if in_month else GRAY,
            )
            self.link_day(c, d, (x, col_top - head, x + col_w, col_top))
            rows = int((col_top - head - col_bottom) / 20)
            self.rules(c, x + 6, col_top - head, col_w - 12, rows, 20)

        # Bottom band: weekly focus + habit tracker, the two blocks every
        # popular weekly spread has.
        focus_w = usable * 0.36
        y = self.section(c, self.margin, bottom + band, "This week's focus")
        self.checkboxes(c, self.margin, y, focus_w - 20, 3, 26)

        hx = self.margin + focus_w
        y = self.section(c, hx, bottom + band, "Habits")
        habits = list(self.cfg.planner_habits)[:5]
        grid_w = self.right - hx
        label_w = min(96.0, grid_w * 0.3)
        cell_w = (grid_w - label_w) / 7
        row_h = min(18.0, (y - bottom) / max(len(habits) + 1, 1))
        for i, name in enumerate(self.weekday_names):
            self.text(
                c, hx + label_w + cell_w * i + cell_w / 2, y - 9, name[0],
                size=7, color=GRAY, align="center",
            )
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        for r, habit in enumerate(habits):
            ry = y - 14 - row_h * (r + 1)
            self.text(c, hx, ry + 5, habit[:16], size=8.5)
            for col in range(7):
                cx = hx + label_w + cell_w * col
                c.rect(cx + cell_w / 2 - 5, ry + 2, 10, 10, stroke=1, fill=0)
        c.showPage()

    def day_page(self, c: pdfcanvas.Canvas, month: date, d: date) -> None:
        c.bookmarkPage(day_key(d))
        weekday = WEEKDAYS_MON[d.weekday()]
        title = f"{weekday}, {MONTH_NAMES[d.month - 1]} {d.day}"
        top = self.page_frame(
            c, title, f"{d.year}  ·  week {d.isocalendar()[1]:02d}", "day",
            month=month, day=d,
        )

        bottom = self.margin
        usable = self.right - self.margin
        gap = 22.0
        sched_w = usable * 0.36
        mid_w = usable * 0.30
        notes_w = usable - sched_w - mid_w - gap * 2
        mid_x = self.margin + sched_w + gap
        notes_x = mid_x + mid_w + gap

        # Schedule column
        y = self.section(c, self.margin, top, "Schedule")
        hours = list(range(self.cfg.planner_start_hour, self.cfg.planner_end_hour + 1))
        slot_h = (y - bottom) / max(len(hours), 1)
        gutter = 26.0
        for i, hour in enumerate(hours):
            ly = y - slot_h * (i + 1)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.7)
            c.line(self.margin, ly, self.margin + sched_w, ly)
            self.text(
                c, self.margin + 2, ly + slot_h - 11,
                f"{hour:02d}", size=8.5, color=GRAY,
            )
            c.setStrokeColor(FAINT)
            c.setLineWidth(0.5)
            c.line(self.margin + gutter, ly + slot_h / 2, self.margin + sched_w, ly + slot_h / 2)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.7)
        c.line(self.margin + gutter - 4, y, self.margin + gutter - 4, bottom)

        # Middle column: today's big three, then the rest
        y = self.section(c, mid_x, top, "Top 3")
        y = self.checkboxes(c, mid_x, y, mid_w, 3, 28) - 28
        y = self.section(c, mid_x, y, "To do")
        space = y - bottom
        rows = max(min(int(space / 24), 12), 1)
        self.checkboxes(c, mid_x, y, mid_w, rows, space / rows)

        # Notes column, with a jump into the meeting log
        y = self.section(c, notes_x, top, "Notes")
        link_h = 26.0
        floor = bottom + (link_h + 10 if self.note_count else 0)
        self.rules(c, notes_x, y, notes_w, max(int((y - floor) / 20), 1), 20)
        if self.note_count:
            self.button(
                c, notes_x, bottom, "Meeting notes  →", NOTES,
                width=notes_w, height=link_h,
            )
        c.showPage()

    def notes_index_page(self, c: pdfcanvas.Canvas) -> None:
        c.bookmarkPage(NOTES)
        month = self.months[0][0]
        top = self.page_frame(
            c, "Notes & meetings",
            "Write the title on the line, tap it later to jump back",
            "notes", month=month,
        )
        bottom = self.margin
        cols = 2
        gap = 40.0
        col_w = (self.right - self.margin - gap) / cols
        per_col = -(-self.note_count // cols)
        row_h = min(44.0, (top - bottom) / max(per_col, 1))

        for i in range(self.note_count):
            col, row = i // per_col, i % per_col
            x = self.margin + col * (col_w + gap)
            y = top - row_h * (row + 1)
            self.text(c, x, y + 6, f"{i + 1:02d}", size=9, bold=True, color=GRAY)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.6)
            c.line(x + 24, y + 2, x + col_w, y + 2)
            self.link(c, note_key(i + 1), (x, y, x + col_w, y + row_h - 6))
        c.showPage()

    def note_page(self, c: pdfcanvas.Canvas, index: int) -> None:
        c.bookmarkPage(note_key(index))
        month = self.months[0][0]
        top = self.page_frame(
            c, f"Meeting note {index:02d}", "", "notes", month=month
        )
        bottom = self.margin
        usable = self.right - self.margin

        # Header fields
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        field_y = top - 6
        for label, x, width in (
            ("Date", self.margin, usable * 0.22),
            ("With", self.margin + usable * 0.26, usable * 0.36),
            ("Topic", self.margin + usable * 0.66, usable * 0.34),
        ):
            self.text(c, x, field_y, label, size=8.5, color=GRAY)
            c.line(x + 34, field_y - 2, x + width, field_y - 2)

        body_top = field_y - 22
        left_w = usable * 0.58
        right_x = self.margin + left_w + 24
        right_w = self.right - right_x

        y = self.section(c, self.margin, body_top, "Discussion")
        self.rules(c, self.margin, y, left_w, max(int((y - bottom) / 20), 1), 20)

        y = self.section(c, right_x, body_top, "Decisions")
        y = self.rules(c, right_x, y, right_w, 5, 20) - 20
        y = self.section(c, right_x, y, "Action items")
        space = y - bottom
        rows = max(min(int(space / 24), 8), 1)
        self.checkboxes(c, right_x, y, right_w, rows, space / rows)
        c.showPage()

    # -- assembly -----------------------------------------------------
    def build(self, first_month: date, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        month = first_month
        for _ in range(max(self.cfg.planner_months, 1)):
            weeks = self.cal.monthdatescalendar(month.year, month.month)
            self.months.append((month, weeks))
            self.days.update(d for w in weeks for d in w if d.month == month.month)
            self.weeks.update(week_key(w[0]) for w in weeks)
            month = next_month(month)
        self.note_count = max(self.cfg.planner_meeting_pages, 0)

        c = pdfcanvas.Canvas(str(out_path), pagesize=(self.w, self.h))
        c.setTitle(f"{first_month.year} planner — {MONTH_NAMES[first_month.month - 1]}")
        c.setAuthor("morning")

        self.cover_page(c)
        self.year_page(c)
        for month, weeks in self.months:
            self.month_page(c, month, weeks)
            for week in weeks:
                self.week_page(c, month, week)
            for d in [x for w in weeks for x in w if x.month == month.month]:
                self.day_page(c, month, d)
        if self.note_count:
            self.notes_index_page(c)
            for i in range(1, self.note_count + 1):
                self.note_page(c, i)

        c.save()
        log.info("planner written: %s", out_path)
        return out_path


def build_planner(
    cfg: Config,
    month: date | None = None,
    events: dict[date, list[str]] | None = None,
) -> Path:
    month = (month or next_month(date.today())).replace(day=1)
    out = cfg.planner_dir / f"planner-{month.year}-{month.month:02d}.pdf"
    return Planner(cfg, events).build(month, out)
