"""한글 TTF 를 reportlab 에 등록한다. 없으면 Helvetica 로 떨어진다."""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

log = logging.getLogger(__name__)

REGULAR = "MorningKR"
BOLD = "MorningKR-Bold"

# (경로, TTC 서브폰트 인덱스)
CANDIDATES: list[tuple[tuple[str, int], tuple[str, int]]] = [
    (
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
        ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
    ),
    (
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
    ),
    (
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 2),
    ),
    (
        ("/Library/Fonts/AppleGothic.ttf", 0),
        ("/Library/Fonts/AppleGothic.ttf", 0),
    ),
]

_registered = False


def register() -> tuple[str, str]:
    """(regular, bold) 폰트 이름을 돌려준다."""
    global _registered
    if _registered:
        return REGULAR, BOLD

    for (reg_path, reg_idx), (bold_path, bold_idx) in CANDIDATES:
        if not Path(reg_path).exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(REGULAR, reg_path, subfontIndex=reg_idx))
            if Path(bold_path).exists():
                pdfmetrics.registerFont(TTFont(BOLD, bold_path, subfontIndex=bold_idx))
            else:
                pdfmetrics.registerFont(TTFont(BOLD, reg_path, subfontIndex=reg_idx))
        except Exception as exc:  # noqa: BLE001
            log.warning("폰트 등록 실패 %s: %s", reg_path, exc)
            continue
        _registered = True
        log.info("한글 폰트: %s", reg_path)
        return REGULAR, BOLD

    log.warning(
        "한글 폰트를 찾지 못했습니다. 컨테이너 밖에서 실행 중이라면 "
        "fonts-nanum 을 설치하세요. 지금은 Helvetica 로 만듭니다(한글 깨짐)."
    )
    return "Helvetica", "Helvetica-Bold"
