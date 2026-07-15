package com.terry.nebocompanion

import java.time.Clock
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.Month
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

data class ParsedEvent(
    val title: String,
    val description: String,
    val start: LocalDateTime,
    val end: LocalDateTime,
    val reminderMinutes: Int
)

class EventParser(private val clock: Clock = Clock.systemDefaultZone()) {
    private val koreanDate = Regex("(?:(\\d{4})년\\s*)?(\\d{1,2})월\\s*(\\d{1,2})일")
    private val isoDate = Regex("(\\d{4})[-./](\\d{1,2})[-./](\\d{1,2})")
    private val usDate = Regex("(?<!\\d)(\\d{1,2})/(\\d{1,2})/(\\d{2}|\\d{4})(?!\\d)")
    private val shortDate = Regex("(?<!\\d)(\\d{1,2})[./](\\d{1,2})(?!\\d)")
    private val koreanTime = Regex("(?:(오전|오후)\\s*)?(\\d{1,2})시(?:\\s*(\\d{1,2})분)?")
    private val clockTime = Regex("(?<!\\d)(\\d{1,2}):(\\d{2})(?:\\s*(AM|PM))?", RegexOption.IGNORE_CASE)
    private val englishTime = Regex("(?<!\\d)(\\d{1,2})(?:\\s*(AM|PM))", RegexOption.IGNORE_CASE)

    fun parse(text: String, zoneId: ZoneId = ZoneId.systemDefault()): ParsedEvent? {
        val source = text.trim()
        if (source.isEmpty()) return null
        val today = LocalDate.now(clock.withZone(zoneId))
        val dateResult = parseDate(source, today) ?: return null
        val timeResult = parseTime(source) ?: return null
        val start = LocalDateTime.of(dateResult.value, timeResult.value)
        val reminderResult = parseReminder(source)
        val consumed = dateResult.ranges + timeResult.ranges + reminderResult.ranges
        val title = cleanTitle(source, consumed)
        return ParsedEvent(
            title = title.ifBlank { "Nebo 일정" },
            description = source,
            start = start,
            end = start.plusHours(1),
            reminderMinutes = reminderResult.value
        )
    }

    private fun parseDate(text: String, today: LocalDate): ParsePart<LocalDate>? {
        val relative = listOf(
            "모레" to 2L, "내일" to 1L, "오늘" to 0L,
            "day after tomorrow" to 2L, "tomorrow" to 1L, "today" to 0L
        ).firstOrNull { text.contains(it.first, ignoreCase = true) }
        if (relative != null) {
            val range = Regex(Regex.escape(relative.first), RegexOption.IGNORE_CASE).find(text)!!.range
            return ParsePart(today.plusDays(relative.second), listOf(range))
        }

        isoDate.find(text)?.let {
            return validDate(it.groupValues[1].toInt(), it.groupValues[2].toInt(), it.groupValues[3].toInt())
                ?.let { date -> ParsePart(date, listOf(it.range)) }
        }
        usDate.find(text)?.let {
            val rawYear = it.groupValues[3].toInt()
            val year = if (rawYear < 100) 2000 + rawYear else rawYear
            return validDate(year, it.groupValues[1].toInt(), it.groupValues[2].toInt())
                ?.let { date -> ParsePart(date, listOf(it.range)) }
        }
        koreanDate.find(text)?.let {
            val year = it.groupValues[1].toIntOrNull() ?: inferredYear(today, it.groupValues[2].toInt(), it.groupValues[3].toInt())
            return validDate(year, it.groupValues[2].toInt(), it.groupValues[3].toInt())
                ?.let { date -> ParsePart(date, listOf(it.range)) }
        }
        shortDate.find(text)?.let {
            val month = it.groupValues[1].toInt()
            val day = it.groupValues[2].toInt()
            return validDate(inferredYear(today, month, day), month, day)
                ?.let { date -> ParsePart(date, listOf(it.range)) }
        }

        parseEnglishMonthDate(text, today)?.let { return it }
        parseWeekday(text, today)?.let { return it }
        return null
    }

    private fun parseTime(text: String): ParsePart<LocalTime>? {
        koreanTime.find(text)?.let {
            var hour = it.groupValues[2].toInt()
            val minute = it.groupValues[3].toIntOrNull() ?: 0
            hour = applyMeridiem(hour, it.groupValues[1])
            return validTime(hour, minute)?.let { time -> ParsePart(time, listOf(it.range)) }
        }
        clockTime.find(text)?.let {
            var hour = it.groupValues[1].toInt()
            val minute = it.groupValues[2].toInt()
            hour = applyMeridiem(hour, it.groupValues[3])
            return validTime(hour, minute)?.let { time -> ParsePart(time, listOf(it.range)) }
        }
        englishTime.find(text)?.let {
            val hour = applyMeridiem(it.groupValues[1].toInt(), it.groupValues[2])
            return validTime(hour, 0)?.let { time -> ParsePart(time, listOf(it.range)) }
        }
        return null
    }

    private fun parseReminder(text: String): ParsePart<Int> {
        val natural = listOf("하루" to 1440, "한\\s*시간" to 60, "반\\s*시간" to 30)
            .mapNotNull { (word, minutes) ->
                Regex("$word\\s*전(?:에)?(?:\\s*(?:알려줘|알림|리마인드))?").find(text)?.let { it to minutes }
            }.firstOrNull()
        if (natural != null) {
            return ParsePart(natural.second, listOf(natural.first.range))
        }
        val pattern = Regex("(\\d+)\\s*(분|시간|일)\\s*전(?:에)?(?:\\s*(?:알려줘|알림|리마인드))?")
        val match = pattern.find(text)
        if (match != null) {
            val amount = match.groupValues[1].toInt().coerceAtMost(30)
            val minutes = when (match.groupValues[2]) {
                "시간" -> amount * 60
                "일" -> amount * 24 * 60
                else -> amount
            }
            return ParsePart(minutes, listOf(match.range))
        }
        val english = Regex("(\\d+)\\s*(minutes?|hours?|days?)\\s+before", RegexOption.IGNORE_CASE).find(text)
        if (english != null) {
            val amount = english.groupValues[1].toInt().coerceAtMost(30)
            val unit = english.groupValues[2].lowercase()
            val minutes = when {
                unit.startsWith("hour") -> amount * 60
                unit.startsWith("day") -> amount * 24 * 60
                else -> amount
            }
            return ParsePart(minutes, listOf(english.range))
        }
        return ParsePart(30, emptyList())
    }

    private fun parseEnglishMonthDate(text: String, today: LocalDate): ParsePart<LocalDate>? {
        val months = Month.entries.associateBy { it.getDisplayName(java.time.format.TextStyle.FULL, Locale.ENGLISH).lowercase() } +
            Month.entries.associateBy { it.getDisplayName(java.time.format.TextStyle.SHORT, Locale.ENGLISH).lowercase() }
        val match = Regex("([A-Za-z]+)\\s+(\\d{1,2})(?:,?\\s+(\\d{4}))?", RegexOption.IGNORE_CASE).find(text) ?: return null
        val month = months[match.groupValues[1].lowercase()] ?: return null
        val day = match.groupValues[2].toInt()
        val year = match.groupValues[3].toIntOrNull() ?: inferredYear(today, month.value, day)
        return validDate(year, month.value, day)?.let { ParsePart(it, listOf(match.range)) }
    }

    private fun parseWeekday(text: String, today: LocalDate): ParsePart<LocalDate>? {
        val names = mapOf(
            "월요일" to DayOfWeek.MONDAY, "화요일" to DayOfWeek.TUESDAY, "수요일" to DayOfWeek.WEDNESDAY,
            "목요일" to DayOfWeek.THURSDAY, "금요일" to DayOfWeek.FRIDAY, "토요일" to DayOfWeek.SATURDAY,
            "일요일" to DayOfWeek.SUNDAY, "monday" to DayOfWeek.MONDAY, "tuesday" to DayOfWeek.TUESDAY,
            "wednesday" to DayOfWeek.WEDNESDAY, "thursday" to DayOfWeek.THURSDAY, "friday" to DayOfWeek.FRIDAY,
            "saturday" to DayOfWeek.SATURDAY, "sunday" to DayOfWeek.SUNDAY
        )
        val entry = names.entries.firstOrNull { text.contains(it.key, ignoreCase = true) } ?: return null
        var days = (entry.value.value - today.dayOfWeek.value + 7) % 7
        if (days == 0) days = 7
        val range = Regex(Regex.escape(entry.key), RegexOption.IGNORE_CASE).find(text)!!.range
        return ParsePart(today.plusDays(days.toLong()), listOf(range))
    }

    private fun cleanTitle(text: String, ranges: List<IntRange>): String {
        val chars = text.toCharArray()
        ranges.forEach { range -> range.forEach { index -> if (index in chars.indices) chars[index] = ' ' } }
        return String(chars)
            .replace(Regex("(?i)\\b(at|on)\\b"), " ")
            .replace(Regex("[,:@]"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
            .lineSequence().firstOrNull().orEmpty()
            .take(80)
    }

    private fun inferredYear(today: LocalDate, month: Int, day: Int): Int {
        val candidate = validDate(today.year, month, day) ?: return today.year
        return if (candidate.isBefore(today.minusDays(1))) today.year + 1 else today.year
    }

    private fun applyMeridiem(hour: Int, marker: String): Int = when (marker.lowercase()) {
        "오후", "pm" -> if (hour in 1..11) hour + 12 else hour
        "오전", "am" -> if (hour == 12) 0 else hour
        else -> hour
    }

    private fun validDate(year: Int, month: Int, day: Int) = runCatching { LocalDate.of(year, month, day) }.getOrNull()
    private fun validTime(hour: Int, minute: Int) = runCatching { LocalTime.of(hour, minute) }.getOrNull()

    private data class ParsePart<T>(val value: T, val ranges: List<IntRange>)
}

fun ParsedEvent.displayText(): String {
    val formatter = DateTimeFormatter.ofPattern("yyyy년 M월 d일 (E) a h:mm", Locale.KOREAN)
    val reminder = when {
        reminderMinutes % 1440 == 0 -> "${reminderMinutes / 1440}일 전 알림"
        reminderMinutes % 60 == 0 -> "${reminderMinutes / 60}시간 전 알림"
        else -> "${reminderMinutes}분 전 알림"
    }
    return "${title}\n${start.format(formatter)} · 1시간\n${reminder}"
}
