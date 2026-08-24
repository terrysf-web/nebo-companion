package com.terry.nebocompanion

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneId

class CaptureParserTest {
    private val zone = ZoneId.of("America/Los_Angeles")
    private val parser = CaptureParser(Clock.fixed(Instant.parse("2026-07-15T16:00:00Z"), zone))

    @Test fun classifiesMultipleHandwrittenLines() {
        val items = parser.parse("""
            내일 오후 3시 팀 회의
            □ 금요일까지 보고서 제출
            오늘 오후 5시 약 먹기 알려줘
        """.trimIndent(), zone)
        assertEquals(listOf(CaptureType.EVENT, CaptureType.TASK, CaptureType.REMINDER), items.map { it.type })
    }

    @Test fun readsOnlyWhatIsWrittenBelowTheDivider() {
        val items = parser.parse("""
            MONDAY, JULY 20
            PRIORITIES
            1. Finish the Q3 deck
            UNREAD
            - Jisoo: vendor contract
            ------------------------------
            내일 오후 3시 팀 회의
        """.trimIndent(), zone)
        assertEquals(listOf(CaptureType.EVENT), items.map { it.type })
    }

    @Test fun ignoresHourGuidesUnderTheDivider() {
        val items = parser.parse("""
            ------------------------------
            06
            07
            □ 금요일까지 보고서 제출
            22
        """.trimIndent(), zone)
        assertEquals(listOf(CaptureType.TASK), items.map { it.type })
    }

    @Test fun keepsParsingEverythingWhenThereIsNoDivider() {
        val items = parser.parse("""
            내일 오후 3시 팀 회의
            우유 사기
        """.trimIndent(), zone)
        assertEquals(listOf(CaptureType.EVENT, CaptureType.TASK), items.map { it.type })
    }
}
