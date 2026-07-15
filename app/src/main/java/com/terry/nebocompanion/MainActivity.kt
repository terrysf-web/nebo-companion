package com.terry.nebocompanion

import android.app.Activity
import android.Manifest
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.CalendarContract
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import java.time.ZoneId

class MainActivity : Activity() {
    private val calendarPermissionRequest = 701
    private lateinit var noteInput: EditText
    private lateinit var resultView: TextView
    private lateinit var calendarButton: Button
    private val parser = EventParser()
    private var parsedEvent: ParsedEvent? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        noteInput = findViewById(R.id.noteInput)
        resultView = findViewById(R.id.resultView)
        calendarButton = findViewById(R.id.calendarButton)

        findViewById<Button>(R.id.analyzeButton).setOnClickListener { analyze() }
        calendarButton.setOnClickListener { openCalendar() }
        consumeSharedText(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consumeSharedText(intent)
    }

    private fun consumeSharedText(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND || intent.type != "text/plain") return
        val shared = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty()
        if (shared.isNotBlank()) {
            noteInput.setText(shared)
            analyze()
        }
    }

    private fun analyze() {
        parsedEvent = parser.parse(noteInput.text.toString())
        val event = parsedEvent
        resultView.visibility = View.VISIBLE
        if (event == null) {
            resultView.text = getString(R.string.no_event)
            calendarButton.isEnabled = false
        } else {
            resultView.text = "${getString(R.string.event_ready)}\n\n${event.displayText()}"
            calendarButton.isEnabled = true
        }
    }

    private fun openCalendar() {
        val event = parsedEvent ?: return
        if (checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED ||
            checkSelfPermission(Manifest.permission.WRITE_CALENDAR) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(
                arrayOf(Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR),
                calendarPermissionRequest
            )
            return
        }
        saveToCalendar(event)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != calendarPermissionRequest) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            parsedEvent?.let { saveToCalendar(it) }
        } else {
            Toast.makeText(this, R.string.calendar_permission, Toast.LENGTH_LONG).show()
        }
    }

    private fun saveToCalendar(event: ParsedEvent) {
        val zone = ZoneId.systemDefault()
        val calendarId = findWritableCalendarId()
        if (calendarId == null) {
            Toast.makeText(this, R.string.calendar_save_failed, Toast.LENGTH_LONG).show()
            return
        }
        val values = ContentValues().apply {
            put(CalendarContract.Events.CALENDAR_ID, calendarId)
            put(CalendarContract.Events.TITLE, event.title)
            put(CalendarContract.Events.DESCRIPTION, event.description)
            put(CalendarContract.Events.DTSTART, event.start.atZone(zone).toInstant().toEpochMilli())
            put(CalendarContract.Events.DTEND, event.end.atZone(zone).toInstant().toEpochMilli())
            put(CalendarContract.Events.EVENT_TIMEZONE, zone.id)
            put(CalendarContract.Events.HAS_ALARM, 1)
        }
        val eventUri = contentResolver.insert(CalendarContract.Events.CONTENT_URI, values)
        val eventId = eventUri?.lastPathSegment?.toLongOrNull()
        if (eventId == null) {
            Toast.makeText(this, R.string.calendar_save_failed, Toast.LENGTH_LONG).show()
            return
        }
        val reminder = ContentValues().apply {
            put(CalendarContract.Reminders.EVENT_ID, eventId)
            put(CalendarContract.Reminders.MINUTES, event.reminderMinutes)
            put(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT)
        }
        contentResolver.insert(CalendarContract.Reminders.CONTENT_URI, reminder)
        Toast.makeText(this, R.string.calendar_saved, Toast.LENGTH_LONG).show()
    }

    private fun findWritableCalendarId(): Long? {
        val projection = arrayOf(
            CalendarContract.Calendars._ID,
            CalendarContract.Calendars.ACCOUNT_TYPE,
            CalendarContract.Calendars.IS_PRIMARY
        )
        val selection = "${CalendarContract.Calendars.VISIBLE}=1 AND " +
            "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL}>=?"
        val args = arrayOf(CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR.toString())
        contentResolver.query(CalendarContract.Calendars.CONTENT_URI, projection, selection, args, null)?.use { cursor ->
            var fallback: Long? = null
            while (cursor.moveToNext()) {
                val id = cursor.getLong(0)
                val accountType = cursor.getString(1).orEmpty()
                val primary = cursor.getInt(2) == 1
                if (fallback == null) fallback = id
                if (accountType == "com.google" && primary) return id
            }
            return fallback
        }
        return null
    }
}
