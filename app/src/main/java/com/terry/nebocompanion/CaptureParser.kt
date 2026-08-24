package com.terry.nebocompanion

import java.time.Clock
import java.time.LocalDateTime
import java.time.ZoneId

enum class CaptureType { EVENT, TASK, REMINDER }

data class CaptureItem(
    val type: CaptureType,
    val title: String,
    val source: String,
    val dateTime: LocalDateTime?,
    val reminderMinutes: Int = 30
)

class CaptureParser(private val clock: Clock = Clock.systemDefaultZone()) {
    private val eventParser = EventParser(clock)

    // 모닝 브리핑을 Nebo 페이지에 붙여넣고 그 아래에 손으로 계획을 쓰면,
    // 페이지 전체를 공유해도 구분선 위(이미 캘린더에 있는 참고용 내용)는 저장되지 않습니다.
    private val dividerLine = Regex("^[-—–_=]{3,}$")

    // 시간 눈금("06", "07")은 쓰라고 넣은 안내선이지 할 일이 아닙니다.
    private val guideLine = Regex("^\\d{1,2}$")

    fun parse(text: String, zoneId: ZoneId = ZoneId.systemDefault()): List<CaptureItem> {
        val lines = text.lines().map { it.trim() }
        val afterDivider = lines.indexOfLast { dividerLine.matches(it) } + 1
        return lines.drop(afterDivider)
            .filter { it.isNotBlank() && !guideLine.matches(it) }
            .mapNotNull { parseLine(it, zoneId) }
    }

    private fun parseLine(line: String, zoneId: ZoneId): CaptureItem? {
        val cleaned = line.replace(Regex("^[□☐✅✓✔•*\\-]+\\s*"), "").trim()
        if (cleaned.isBlank()) return null
        val parsed = eventParser.parse(cleaned, zoneId)
        val reminderWords = Regex("알려줘|알림|리마인드|remind", RegexOption.IGNORE_CASE).containsMatchIn(cleaned)
        val taskWords = Regex("할[ ]?일|해야|까지|제출|전화|확인|구매|task", RegexOption.IGNORE_CASE).containsMatchIn(cleaned)
        val checkbox = Regex("^[□☐✅✓✔]").containsMatchIn(line)

        return when {
            reminderWords && parsed != null -> CaptureItem(CaptureType.REMINDER, parsed.title, cleaned, parsed.start, parsed.reminderMinutes)
            checkbox || taskWords -> {
                val due = parsed ?: eventParser.parse("$cleaned 오전 9시", zoneId)
                CaptureItem(CaptureType.TASK, cleanTaskTitle(due?.title ?: cleaned), cleaned, due?.start)
            }
            parsed != null -> CaptureItem(CaptureType.EVENT, parsed.title, cleaned, parsed.start, parsed.reminderMinutes)
            else -> CaptureItem(CaptureType.TASK, cleanTaskTitle(cleaned), cleaned, null)
        }
    }

    private fun cleanTaskTitle(value: String) = value
        .replace(Regex("(?i)\\b(task|todo)\\b"), "")
        .replace(Regex("할[ ]?일|해야|까지"), "")
        .replace(Regex("\\s+"), " ").trim().ifBlank { "Nebo 할 일" }
}
