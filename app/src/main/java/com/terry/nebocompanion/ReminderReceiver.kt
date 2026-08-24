package com.terry.nebocompanion

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(
            NotificationChannel(
                "nebo_reminders",
                context.getString(R.string.reminder_channel),
                NotificationManager.IMPORTANCE_HIGH
            )
        )
        val open = PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val notification = android.app.Notification.Builder(context, "nebo_reminders")
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle(intent.getStringExtra("title") ?: context.getString(R.string.reminder_title))
            .setContentText(context.getString(R.string.reminder_body))
            .setContentIntent(open).setAutoCancel(true).build()
        manager.notify(intent.getIntExtra("id", 1), notification)
    }
}
