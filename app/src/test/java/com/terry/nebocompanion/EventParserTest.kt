package com.terry.nebocompanion

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneId

class EventParserTest {
    private val zone = ZoneId.of("America/Los_Angeles")
    private val parser = EventParser(Clock.fixed(Instant.parse("2026-07-15T16:00:00Z"), zone))

    @Test fun parsesKoreanRelativeDate() {
        val event = parser.parse("내일 오후 3시 팀 회의 1시간 전에 알려줘", zone)
        assertNotNull(event)
        assertEquals("팀 회의", event!!.title)
        assertEquals("2026-07-16T15:00", event.start.toString())
        assertEquals(60, event.reminderMinutes)
    }

    @Test fun parsesKoreanMonthAndDay() {
        val event = parser.parse("7월 20일 오전 10시 치과", zone)
        assertEquals("2026-07-20T10:00", event!!.start.toString())
    }

    @Test fun parsesIsoDateAndTime() {
        val event = parser.parse("2026-07-21 14:30 프로젝트 검토", zone)
        assertEquals("프로젝트 검토", event!!.title)
        assertEquals("2026-07-21T14:30", event.start.toString())
    }

    @Test fun parsesNeboEnglishUsDate() {
        val event = parser.parse("7/15/26 3PM Daily huddle", zone)
        assertEquals("Daily huddle", event!!.title)
        assertEquals("2026-07-15T15:00", event.start.toString())
    }

    @Test fun rejectsTextWithoutDateAndTime() {
        assertEquals(null, parser.parse("아이디어를 나중에 정리하기", zone))
    }

    @Test fun usesThirtyMinuteReminderByDefault() {
        val event = parser.parse("7월 20일 오전 10시 치과", zone)
        assertEquals(30, event!!.reminderMinutes)
    }
}
