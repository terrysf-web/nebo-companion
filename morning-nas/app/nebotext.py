"""The brief as plain text, shaped for pasting into a Nebo page.

Nebo's own pages are where handwriting becomes text — an imported PDF is only
an annotation layer, so the brief reaches Nebo as text you paste, not as a page
you draw on. From there the loop closes with the Nebo Companion app: write the
day's plan by hand under PLAN, convert, share, and the events land in Calendar.

Rules this format follows, all of them Nebo's:
- no Markdown syntax; Nebo renders none of it and the characters just sit there
- short lines, because a Nebo page column is narrower than a PDF page
- section labels in caps so they survive as headings when you restyle them
- PLAN and NOTES left deliberately empty — that is where the handwriting goes
"""

from __future__ import annotations

from .brief import Brief
from .config import Config

WIDTH = 46

# CaptureParser in the Android app treats a line of 3+ dashes as "read back from
# here down". Keep the two in step.
DIVIDER = "-" * 30


def _wrap(text: str, width: int = WIDTH, indent: str = "") -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        probe = f"{line} {word}".strip()
        if len(probe) <= width:
            line = probe
        else:
            if line:
                lines.append(indent + line)
            line = word
    if line:
        lines.append(indent + line)
    return lines or [indent.rstrip()]


def _bullets(items: list[str]) -> list[str]:
    """"- first line" then hanging indent, never a mid-word cut."""
    out: list[str] = []
    for item in items:
        wrapped = _wrap(item, WIDTH - 2)
        out.append(f"- {wrapped[0].strip()}")
        out.extend("  " + line.strip() for line in wrapped[1:])
    return out


def to_text(cfg: Config, brief: Brief, plan_hours: bool = True) -> str:
    out: list[str] = [brief.title().upper()]
    if brief.weather:
        out.extend(_wrap(brief.weather))
    out.append("")

    if brief.headline:
        out.extend(_wrap(brief.headline))
        out.append("")

    if brief.priorities:
        out.append("PRIORITIES")
        for i, item in enumerate(brief.priorities, 1):
            wrapped = _wrap(item, WIDTH - 3)
            out.append(f"{i}. {wrapped[0].strip()}")
            out.extend("   " + line.strip() for line in wrapped[1:])
        out.append("")

    if brief.timeline:
        out.append("TODAY")
        for row in brief.timeline:
            when = (row.get("time") or "").strip()
            what = (row.get("what") or "").strip()
            head = f"{when:<6}" if when else " " * 6
            wrapped = _wrap(what, WIDTH - 6)
            out.append(head + wrapped[0].strip())
            out.extend(" " * 6 + line.strip() for line in wrapped[1:])
        out.append("")

    if brief.watch:
        out.append("WATCH")
        out.extend(_bullets(brief.watch))
        out.append("")

    if brief.tasks:
        out.append("OPEN")
        out.extend(_bullets(brief.tasks[:6]))
        out.append("")

    if brief.mail:
        out.append("UNREAD")
        out.extend(_bullets([f"{m['from']}: {m['subject']}" for m in brief.mail[:6]]))
        out.append("")

    if brief.closing:
        out.extend(_wrap(brief.closing))
        out.append("")
    if brief.problems:
        out.append("CHECK")
        for problem in brief.problems:
            out.extend(_wrap(problem, WIDTH - 2, indent="- ")[:2])
        out.append("")

    # Everything above the divider is reference — it is already in the calendar.
    # Nebo Companion reads back only what is written below it, so the whole page
    # can be shared without the brief itself turning into duplicate tasks.
    out.append("PLAN - write below the line")
    out.append(DIVIDER)
    if plan_hours:
        for hour in range(cfg.planner_start_hour, cfg.planner_end_hour + 1):
            out.append(f"{hour:02d}")

    return "\n".join(out).rstrip() + "\n"
