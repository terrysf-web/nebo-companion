package com.terry.nebocompanion

import android.app.Activity
import android.app.AlarmManager
import android.app.AlertDialog
import android.app.PendingIntent
import android.Manifest
import android.content.ContentValues
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.CalendarContract
import android.provider.DocumentsContract
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions
import java.time.LocalDate
import java.time.ZoneId

class MainActivity : Activity() {
    private val savePermissionRequest = 701
    private val pickCalendarPermissionRequest = 702
    private val pickBriefFolderRequest = 703
    private lateinit var noteInput: EditText
    private lateinit var resultView: TextView
    private lateinit var calendarButton: Button
    private lateinit var briefButton: Button
    private lateinit var calendarTargetView: TextView
    private lateinit var prefs: SharedPreferences
    private val parser = EventParser()
    private val captureParser = CaptureParser()
    private var parsedEvent: ParsedEvent? = null
    private var captureItems: List<CaptureItem> = emptyList()
    private var lastClipboard: String? = null
    private lateinit var taskStore: TaskStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        noteInput = findViewById(R.id.noteInput)
        resultView = findViewById(R.id.resultView)
        calendarButton = findViewById(R.id.calendarButton)
        briefButton = findViewById(R.id.briefButton)
        calendarTargetView = findViewById(R.id.calendarTargetView)
        taskStore = TaskStore(this)
        prefs = getSharedPreferences("settings", MODE_PRIVATE)

        findViewById<Button>(R.id.analyzeButton).setOnClickListener { analyze() }
        calendarButton.setOnClickListener { requestPermissionsThenSave() }
        briefButton.setOnClickListener { openTodaysBrief() }
        briefButton.setOnLongClickListener { pickBriefFolder(); true }
        calendarTargetView.setOnClickListener { changeCalendarTarget() }
        updateCalendarTargetLabel()
        consumeShared(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consumeShared(intent)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus || noteInput.text.isNotBlank()) return
        val clipboard = getSystemService(android.content.ClipboardManager::class.java) ?: return
        val text = clipboard.primaryClip?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)?.coerceToText(this)?.toString().orEmpty().trim()
        if (text.isBlank() || text == lastClipboard) return
        lastClipboard = text
        noteInput.setText(text)
        analyze()
        Toast.makeText(this, R.string.clipboard_imported, Toast.LENGTH_SHORT).show()
    }

    private fun consumeShared(intent: Intent?) {
        when (intent?.action) {
            Intent.ACTION_PROCESS_TEXT -> {
                val text = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString().orEmpty()
                if (text.isNotBlank()) {
                    noteInput.setText(text)
                    analyze()
                }
            }
            Intent.ACTION_SEND -> {
                val text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString().orEmpty()
                if (text.isNotBlank()) {
                    noteInput.setText(text)
                    analyze()
                    return
                }
                val stream = streamExtra(intent) ?: return
                // A shared .txt (a morning brief out of the synced folder, say)
                // is text, not something to run OCR over.
                if (looksLikeText(stream)) loadSharedText(stream) else recognizeImages(listOf(stream))
            }
            Intent.ACTION_SEND_MULTIPLE -> {
                val streams = streamListExtra(intent)
                if (streams.isNotEmpty()) recognizeImages(streams)
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun streamExtra(intent: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else intent.getParcelableExtra(Intent.EXTRA_STREAM)

    @Suppress("DEPRECATION")
    private fun streamListExtra(intent: Intent): List<Uri> =
        (if (Build.VERSION.SDK_INT >= 33) intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
         else intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM))?.filterNotNull().orEmpty()

    // ── Morning brief ───────────────────────────────────────────
    // Opens today's <date>.txt straight out of the synced folder. The folder is
    // one the user picked, so this needs no new permission and the app still
    // asks for no internet access.

    private fun briefFileName(): String = "${LocalDate.now()}.txt"

    private fun pickBriefFolder() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        try {
            startActivityForResult(intent, pickBriefFolderRequest)
        } catch (e: android.content.ActivityNotFoundException) {
            Toast.makeText(this, R.string.brief_no_picker, Toast.LENGTH_LONG).show()
        }
    }

    private fun openTodaysBrief() {
        val saved = prefs.getString("brief_folder", null)
        if (saved == null) {
            pickBriefFolder()
            return
        }
        val file = findInFolder(Uri.parse(saved), briefFileName())
        if (file == null) {
            Toast.makeText(this, getString(R.string.brief_not_found, briefFileName()), Toast.LENGTH_LONG).show()
            return
        }
        loadSharedText(file)
    }

    private fun findInFolder(treeUri: Uri, name: String): Uri? = try {
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(
            treeUri, DocumentsContract.getTreeDocumentId(treeUri)
        )
        contentResolver.query(
            children,
            arrayOf(
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME
            ),
            null, null, null
        )?.use { cursor ->
            var found: Uri? = null
            while (found == null && cursor.moveToNext()) {
                if (cursor.getString(1) == name) {
                    found = DocumentsContract.buildDocumentUriUsingTree(treeUri, cursor.getString(0))
                }
            }
            found
        }
    } catch (e: Exception) {
        null
    }

    private fun looksLikeText(uri: Uri): Boolean {
        val type = contentResolver.getType(uri).orEmpty()
        if (type.startsWith("text/")) return true
        if (type.startsWith("image/")) return false
        return uri.toString().substringAfterLast('.', "").lowercase() in setOf("txt", "md", "text")
    }

    private fun loadSharedText(uri: Uri) {
        val text = try {
            contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) }
        } catch (e: Exception) {
            resultView.visibility = View.VISIBLE
            resultView.text = getString(R.string.brief_read_failed, e.localizedMessage ?: e.javaClass.simpleName)
            return
        }
        if (text.isNullOrBlank()) {
            Toast.makeText(this, R.string.brief_empty, Toast.LENGTH_LONG).show()
            return
        }
        noteInput.setText(text)
        // A brief with nothing written under the divider yields no items yet —
        // that is normal at 06:00, so say so instead of "couldn't find a date".
        if (captureParser.parse(text).isEmpty()) {
            resultView.visibility = View.GONE
            calendarButton.isEnabled = false
            Toast.makeText(this, R.string.brief_loaded, Toast.LENGTH_LONG).show()
        } else {
            analyze()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != pickBriefFolderRequest || resultCode != RESULT_OK) return
        val tree = data?.data ?: return
        try {
            contentResolver.takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (e: SecurityException) {
            Toast.makeText(this, R.string.brief_folder_failed, Toast.LENGTH_LONG).show()
            return
        }
        prefs.edit().putString("brief_folder", tree.toString()).apply()
        openTodaysBrief()
    }

    private fun recognizeImages(uris: List<Uri>) {
        resultView.visibility = View.VISIBLE
        resultView.text = getString(R.string.ocr_running)
        calendarButton.isEnabled = false
        val recognizer = TextRecognition.getClient(KoreanTextRecognizerOptions.Builder().build())
        val collected = StringBuilder()
        fun processAt(index: Int) {
            if (index >= uris.size) {
                recognizer.close()
                val text = collected.toString().trim()
                if (text.isBlank()) {
                    resultView.text = getString(R.string.ocr_empty)
                } else {
                    noteInput.setText(text)
                    analyze()
                }
                return
            }
            val image = try {
                InputImage.fromFilePath(this, uris[index])
            } catch (e: Exception) {
                recognizer.close()
                resultView.text = getString(R.string.ocr_open_failed, e.localizedMessage ?: e.javaClass.simpleName)
                return
            }
            recognizer.process(image)
                .addOnSuccessListener { result ->
                    if (result.text.isNotBlank()) collected.appendLine(result.text)
                    processAt(index + 1)
                }
                .addOnFailureListener { e ->
                    recognizer.close()
                    resultView.text = getString(R.string.ocr_failed, e.localizedMessage ?: e.javaClass.simpleName)
                }
        }
        processAt(0)
    }

    private fun analyze() {
        captureItems = captureParser.parse(noteInput.text.toString())
        parsedEvent = parser.parse(noteInput.text.toString())
        resultView.visibility = View.VISIBLE
        if (captureItems.isEmpty()) {
            resultView.text = getString(R.string.no_event)
            calendarButton.isEnabled = false
        } else {
            val header = getString(R.string.items_found, captureItems.size) + "\n\n"
            resultView.text = captureItems.joinToString("\n\n", header) { item ->
                val label = getString(
                    when (item.type) {
                        CaptureType.EVENT -> R.string.type_event
                        CaptureType.TASK -> R.string.type_task
                        CaptureType.REMINDER -> R.string.type_reminder
                    }
                )
                val time = item.dateTime?.let { "\n$it" }.orEmpty()
                "[$label] ${item.title}$time"
            }
            calendarButton.isEnabled = true
        }
    }

    private fun neededPermissions(forSave: Boolean): List<String> {
        val permissions = mutableListOf<String>()
        val needsCalendar = !forSave || captureItems.any { it.type == CaptureType.EVENT }
        if (needsCalendar &&
            (checkSelfPermission(Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED ||
             checkSelfPermission(Manifest.permission.WRITE_CALENDAR) != PackageManager.PERMISSION_GRANTED)) {
            permissions += Manifest.permission.READ_CALENDAR
            permissions += Manifest.permission.WRITE_CALENDAR
        }
        if (forSave && Build.VERSION.SDK_INT >= 33 &&
            captureItems.any { (it.type == CaptureType.REMINDER || it.type == CaptureType.TASK) && it.dateTime != null } &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }
        return permissions
    }

    private fun requestPermissionsThenSave() {
        if (captureItems.isEmpty()) return
        val permissions = neededPermissions(forSave = true)
        if (permissions.isNotEmpty()) {
            requestPermissions(permissions.toTypedArray(), savePermissionRequest)
            return
        }
        chooseCalendarThenSave()
    }

    private fun changeCalendarTarget() {
        val permissions = neededPermissions(forSave = false)
        if (permissions.isNotEmpty()) {
            requestPermissions(permissions.toTypedArray(), pickCalendarPermissionRequest)
            return
        }
        val calendars = loadWritableCalendars()
        if (calendars.isEmpty()) {
            Toast.makeText(this, R.string.calendar_save_failed, Toast.LENGTH_LONG).show()
            return
        }
        showCalendarPicker(calendars) { }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val granted = grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }
        when (requestCode) {
            savePermissionRequest ->
                if (granted) chooseCalendarThenSave()
                else Toast.makeText(this, R.string.calendar_permission, Toast.LENGTH_LONG).show()
            pickCalendarPermissionRequest ->
                if (granted) changeCalendarTarget()
                else Toast.makeText(this, R.string.calendar_permission, Toast.LENGTH_LONG).show()
        }
    }

    private fun chooseCalendarThenSave() {
        val needsCalendar = captureItems.any { it.type == CaptureType.EVENT && it.dateTime != null }
        if (!needsCalendar) {
            saveAll(null)
            return
        }
        val calendars = loadWritableCalendars()
        if (calendars.isEmpty()) {
            saveAll(null)
            return
        }
        val savedId = prefs.getLong("calendar_id", -1L)
        val remembered = calendars.firstOrNull { it.id == savedId }
        if (remembered != null) {
            saveAll(remembered)
            return
        }
        showCalendarPicker(calendars) { choice -> saveAll(choice) }
    }

    private fun showCalendarPicker(calendars: List<CalendarChoice>, onChosen: (CalendarChoice) -> Unit) {
        AlertDialog.Builder(this)
            .setTitle(R.string.choose_calendar)
            .setItems(calendars.map { it.label }.toTypedArray()) { _, which ->
                val choice = calendars[which]
                prefs.edit().putLong("calendar_id", choice.id).apply()
                updateCalendarTargetLabel()
                onChosen(choice)
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun updateCalendarTargetLabel() {
        val hasPermission = checkSelfPermission(Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED
        val savedId = prefs.getLong("calendar_id", -1L)
        val label = if (hasPermission && savedId >= 0) {
            loadWritableCalendars().firstOrNull { it.id == savedId }?.label
        } else null
        calendarTargetView.text =
            if (label != null) getString(R.string.calendar_target, label)
            else getString(R.string.calendar_target_unset)
    }

    private fun saveAll(calendar: CalendarChoice?) {
        var saved = 0
        var eventsSaved = 0
        var fallbackLaunched = false
        captureItems.forEach { item ->
            when (item.type) {
                CaptureType.TASK -> { taskStore.add(item); item.dateTime?.let { scheduleReminder(item, it) }; saved++ }
                CaptureType.REMINDER -> { item.dateTime?.let { scheduleReminder(item, it.minusMinutes(item.reminderMinutes.toLong())) }; saved++ }
                CaptureType.EVENT -> if (item.dateTime != null) {
                    val event = ParsedEvent(item.title, item.source, item.dateTime, item.dateTime.plusHours(1), item.reminderMinutes)
                    if (calendar != null) {
                        if (saveToCalendar(event, calendar.id)) { saved++; eventsSaved++ }
                    } else if (!fallbackLaunched) {
                        fallbackLaunched = launchCalendarInsert(event)
                        if (fallbackLaunched) saved++
                    }
                }
            }
        }
        val message = when {
            eventsSaved > 0 && calendar != null -> getString(R.string.saved_with_calendar, saved, calendar.label)
            fallbackLaunched -> getString(R.string.calendar_fallback)
            saved > 0 -> getString(R.string.saved_count, saved)
            else -> getString(R.string.calendar_save_failed)
        }
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun launchCalendarInsert(event: ParsedEvent): Boolean {
        val zone = ZoneId.systemDefault()
        val intent = Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, event.title)
            .putExtra(CalendarContract.Events.DESCRIPTION, event.description)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, event.start.atZone(zone).toInstant().toEpochMilli())
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, event.end.atZone(zone).toInstant().toEpochMilli())
        return try {
            startActivity(intent)
            true
        } catch (e: android.content.ActivityNotFoundException) {
            Toast.makeText(this, R.string.calendar_missing, Toast.LENGTH_LONG).show()
            false
        }
    }

    private fun scheduleReminder(item: CaptureItem, whenAt: java.time.LocalDateTime) {
        val trigger = whenAt.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        if (trigger <= System.currentTimeMillis()) return
        val id = (System.currentTimeMillis() xor item.title.hashCode().toLong()).toInt()
        val intent = Intent(this, ReminderReceiver::class.java).putExtra("title", item.title).putExtra("id", id)
        val pending = PendingIntent.getBroadcast(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        getSystemService(AlarmManager::class.java).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pending)
    }

    private fun saveToCalendar(event: ParsedEvent, calendarId: Long): Boolean {
        val zone = ZoneId.systemDefault()
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
        val eventId = eventUri?.lastPathSegment?.toLongOrNull() ?: return false
        val reminder = ContentValues().apply {
            put(CalendarContract.Reminders.EVENT_ID, eventId)
            put(CalendarContract.Reminders.MINUTES, event.reminderMinutes)
            put(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT)
        }
        contentResolver.insert(CalendarContract.Reminders.CONTENT_URI, reminder)
        return true
    }

    private fun loadWritableCalendars(): List<CalendarChoice> {
        val projection = arrayOf(
            CalendarContract.Calendars._ID,
            CalendarContract.Calendars.CALENDAR_DISPLAY_NAME,
            CalendarContract.Calendars.ACCOUNT_NAME,
            CalendarContract.Calendars.ACCOUNT_TYPE
        )
        val selection = "${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL}>=?"
        val args = arrayOf(CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR.toString())
        val calendars = mutableListOf<CalendarChoice>()
        contentResolver.query(CalendarContract.Calendars.CONTENT_URI, projection, selection, args, null)?.use { cursor ->
            while (cursor.moveToNext()) {
                val id = cursor.getLong(0)
                val account = cursor.getString(2).orEmpty()
                val accountType = cursor.getString(3).orEmpty()
                val name = cursor.getString(1).orEmpty()
                    .ifBlank { account.ifBlank { getString(R.string.calendar_unnamed, id.toString()) } }
                val origin = when {
                    accountType == "com.google" -> "Google · $account"
                    accountType == CalendarContract.ACCOUNT_TYPE_LOCAL ||
                        accountType.contains("local", ignoreCase = true) -> getString(R.string.calendar_local)
                    else -> account
                }
                calendars += CalendarChoice(id, if (origin.isBlank() || origin == name) name else "$name ($origin)")
            }
        }
        return calendars
    }
}

data class CalendarChoice(val id: Long, val label: String)
