package com.terry.nebocompanion

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Bundle
import android.provider.CalendarContract
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import java.time.ZoneId

class MainActivity : Activity() {
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
        val zone = ZoneId.systemDefault()
        val intent = Intent(Intent.ACTION_INSERT).apply {
            data = CalendarContract.Events.CONTENT_URI
            putExtra(CalendarContract.Events.TITLE, event.title)
            putExtra(CalendarContract.Events.DESCRIPTION, event.description)
            putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, event.start.atZone(zone).toInstant().toEpochMilli())
            putExtra(CalendarContract.EXTRA_EVENT_END_TIME, event.end.atZone(zone).toInstant().toEpochMilli())
        }
        try {
            startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.calendar_missing, Toast.LENGTH_LONG).show()
        }
    }
}
