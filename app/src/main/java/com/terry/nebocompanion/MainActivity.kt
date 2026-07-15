package com.terry.nebocompanion

import android.app.Activity
import android.app.AlarmManager
import android.app.PendingIntent
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
    private val captureParser = CaptureParser()
    private var parsedEvent: ParsedEvent? = null
    private var captureItems: List<CaptureItem> = emptyList()
    private lateinit var taskStore: TaskStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        noteInput = findViewById(R.id.noteInput)
        resultView = findViewById(R.id.resultView)
        calendarButton = findViewById(R.id.calendarButton)
        taskStore = TaskStore(this)

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
        captureItems = captureParser.parse(noteInput.text.toString())
        parsedEvent = parser.parse(noteInput.text.toString())
        resultView.visibility = View.VISIBLE
        if (captureItems.isEmpty()) {
            resultView.text = getString(R.string.no_event)
            calendarButton.isEnabled = false
        } else {
            resultView.text = captureItems.joinToString("\n\n", "인식된 항목 ${captureItems.size}개\n\n") { item ->
                val label = when (item.type) { CaptureType.EVENT -> "일정"; CaptureType.TASK -> "할 일"; CaptureType.REMINDER -> "알림" }
                val time = item.dateTime?.let { "\n$it" }.orEmpty()
                "[$label] ${item.title}$time"
            }
            calendarButton.isEnabled = true
        }
    }

    private fun openCalendar() {
        if (captureItems.isEmpty()) return
        val permissions = mutableListOf<String>()
        if (captureItems.any { it.type == CaptureType.EVENT } &&
            (checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED ||
             checkSelfPermission(Manifest.permission.WRITE_CALENDAR) != PackageManager.PERMISSION_GRANTED)) {
            permissions += Manifest.permission.READ_CALENDAR
            permissions += Manifest.permission.WRITE_CALENDAR
        }
        if (android.os.Build.VERSION.SDK_INT >= 33 && captureItems.any { it.type == CaptureType.REMINDER } &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }
        if (permissions.isNotEmpty()) {
            requestPermissions(permissions.toTypedArray(), calendarPermissionRequest)
            return
        }
        saveAll()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != calendarPermissionRequest) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            saveAll()
        } else {
            Toast.makeText(this, R.string.calendar_permission, Toast.LENGTH_LONG).show()
        }
    }

    private fun saveAll() {
        var saved = 0
        captureItems.forEach { item ->
            when (item.type) {
                CaptureType.TASK -> { taskStore.add(item); item.dateTime?.let { scheduleReminder(item, it) }; saved++ }
                CaptureType.REMINDER -> { item.dateTime?.let { scheduleReminder(item, it.minusMinutes(item.reminderMinutes.toLong())) }; saved++ }
                CaptureType.EVENT -> if (item.dateTime != null) {
                    saveToCalendar(ParsedEvent(item.title, item.source, item.dateTime, item.dateTime.plusHours(1), item.reminderMinutes)); saved++
                }
            }
        }
        if (saved > 0) Toast.makeText(this, "$saved개 항목을 저장했습니다.", Toast.LENGTH_LONG).show()
    }

    private fun scheduleReminder(item: CaptureItem, whenAt: java.time.LocalDateTime) {
        val trigger = whenAt.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        if (trigger <= System.currentTimeMillis()) return
        val id = (System.currentTimeMillis() xor item.title.hashCode().toLong()).toInt()
        val intent = Intent(this, ReminderReceiver::class.java).putExtra("title", item.title).putExtra("id", id)
        val pending = PendingIntent.getBroadcast(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        getSystemService(AlarmManager::class.java).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
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
