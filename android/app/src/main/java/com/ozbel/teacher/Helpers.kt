package com.ozbel.teacher

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat

@Composable
fun LocalContextSafe(): Context = LocalContext.current

/** Ripple'sız tıklama (basit metin butonları için). */
fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier = composed {
    val src = remember { MutableInteractionSource() }
    this.clickable(interactionSource = src, indication = null, onClick = onClick)
}

/** QR içeriğinden oturum kodunu çıkar.
 *  Board QR'ı: https://...netlify.app/?s=KOD  → KOD döner. */
fun extractSession(content: String): String? {
    return try {
        when {
            content.contains("?s=") ->
                content.substringAfter("?s=").substringBefore("&").trim().ifEmpty { null }
            content.contains("&s=") ->
                content.substringAfter("&s=").substringBefore("&").trim().ifEmpty { null }
            content.trim().length in 4..16 && !content.contains("/") ->
                content.trim()
            else -> null
        }
    } catch (_: Exception) {
        null
    }
}

/** Ölçüm servisini başlat. */
fun startMonitor(ctx: Context) {
    val calib = Prefs.getCalib(ctx).toDouble()
    AppState.calib = calib
    val i = Intent(ctx, MonitorService::class.java).apply {
        action = MonitorService.ACTION_START
        putExtra(MonitorService.EXTRA_SESSION, AppState.sessionId)
        putExtra(MonitorService.EXTRA_CALIB, calib)
    }
    ContextCompat.startForegroundService(ctx, i)
}

/** Hassasiyeti canlı değiştir (slider/buton) — servis anında okur + kaydet. */
fun setCalibLive(ctx: Context, calib: Int) {
    AppState.calib = calib.toDouble()
    Prefs.setCalib(ctx, calib)
}

/** Ders bitti — board'a haber ver + servisi durdur. */
fun endLesson(ctx: Context) {
    AppState.sessionId?.let { sid ->
        Thread { FirebaseRest.putString(sid, "lesson", "end") }.start()
    }
    val i = Intent(ctx, MonitorService::class.java).apply { action = MonitorService.ACTION_STOP }
    ctx.startService(i)
}
