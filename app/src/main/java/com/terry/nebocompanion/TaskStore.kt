package com.terry.nebocompanion

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDateTime
import java.util.UUID

data class SavedTask(val id: String, val title: String, val due: LocalDateTime?, val done: Boolean)

class TaskStore(context: Context) {
    private val preferences = context.getSharedPreferences("nebo_tasks", Context.MODE_PRIVATE)

    fun add(item: CaptureItem) {
        val tasks = all().toMutableList()
        tasks += SavedTask(UUID.randomUUID().toString(), item.title, item.dateTime, false)
        save(tasks)
    }

    fun all(): List<SavedTask> {
        val data = preferences.getString("items", "[]") ?: "[]"
        return runCatching {
            val array = JSONArray(data)
            (0 until array.length()).map { index ->
                val value = array.getJSONObject(index)
                SavedTask(
                    value.getString("id"), value.getString("title"),
                    value.optString("due").takeIf { it.isNotBlank() }?.let(LocalDateTime::parse),
                    value.optBoolean("done")
                )
            }
        }.getOrDefault(emptyList())
    }

    private fun save(tasks: List<SavedTask>) {
        val array = JSONArray()
        tasks.forEach { task -> array.put(JSONObject().apply {
            put("id", task.id); put("title", task.title); put("due", task.due?.toString().orEmpty()); put("done", task.done)
        }) }
        preferences.edit().putString("items", array.toString()).apply()
    }
}
