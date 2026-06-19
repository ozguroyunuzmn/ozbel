package com.ozbel.teacher

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** Mikrofonu dinleyip dB hesaplar ve Firebase'e yazar.
 *  Foreground service olduğu için ekran kapansa/kilitlense de çalışır. */
class MonitorService : Service() {

    @Volatile private var running = false
    private var worker: Thread? = null
    private var session: String = ""

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> { stopEverything(); return START_NOT_STICKY }
            else -> {
                session = intent?.getStringExtra(EXTRA_SESSION) ?: AppState.sessionId ?: ""
                AppState.calib = intent?.getDoubleExtra(EXTRA_CALIB, AppState.calib) ?: AppState.calib
                startForeground(NOTIF_ID, buildNotification())
                startMeasuring()
            }
        }
        return START_STICKY
    }

    private fun startMeasuring() {
        if (running) return
        running = true

        // Bağlandığını bildir
        Thread {
            FirebaseRest.putBool(session, "teacher", true)
            FirebaseRest.putBool(session, "mic", true)
        }.start()

        worker = Thread {
            val sampleRate = 44100
            val minBuf = AudioRecord.getMinBufferSize(
                sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val bufSize = max(minBuf, sampleRate / 15) // ~66ms → daha akıcı gösterim
            val rec = try {
                AudioRecord(
                    MediaRecorder.AudioSource.MIC, sampleRate,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufSize * 2)
            } catch (e: SecurityException) {
                fail("Mikrofon izni yok"); return@Thread
            }
            if (rec.state != AudioRecord.STATE_INITIALIZED) { fail("Mikrofon başlatılamadı"); return@Thread }

            val buf = ShortArray(bufSize)
            var dbSmooth = 0.0
            var lastSend = 0L
            var lastCtrl = 0L
            rec.startRecording()

            while (running) {
                val n = rec.read(buf, 0, buf.size)
                if (n > 0) {
                    var sum = 0.0
                    for (i in 0 until n) { val s = buf[i].toDouble(); sum += s * s }
                    val rms = sqrt(sum / n) / 32768.0
                    val raw = if (rms > 0.00001)
                        min(120.0, max(0.0, 20.0 * log10(rms) + AppState.calib)) else 0.0
                    dbSmooth = if (dbSmooth == 0.0) raw else dbSmooth * 0.8 + raw * 0.2
                    val db = dbSmooth.toInt()
                    AppState.db.value = db

                    val now = System.currentTimeMillis()
                    if (now - lastSend >= 200) { FirebaseRest.putNumber(session, "db", db); lastSend = now }
                    if (now - lastCtrl >= 1000) {
                        lastCtrl = now
                        if (FirebaseRest.readControl(session) == "disconnect") {
                            finishByBoard(); break
                        }
                    }
                }
            }
            try { rec.stop(); rec.release() } catch (_: Exception) {}
        }
        worker?.start()
    }

    private fun fail(msg: String) {
        AppState.errorMsg.value = msg
        AppState.screen.value = AppState.Screen.ERROR
        stopEverything()
    }

    private fun finishByBoard() {
        AppState.screen.value = AppState.Screen.DONE
        stopEverything()
    }

    private fun stopEverything() {
        running = false
        Thread { FirebaseRest.putBool(session, "teacher", false) }.start()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun buildNotification(): Notification {
        val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(CHANNEL, "ÖzBel Ölçüm", NotificationManager.IMPORTANCE_LOW)
            ch.setShowBadge(false)
            mgr.createNotificationChannel(ch)
        }
        return NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle("ÖzBel çalışıyor")
            .setContentText("Sınıf ses seviyesi ölçülüyor")
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_START = "com.ozbel.teacher.START"
        const val ACTION_STOP = "com.ozbel.teacher.STOP"
        const val EXTRA_SESSION = "session"
        const val EXTRA_CALIB = "calib"
        private const val CHANNEL = "ozbel_monitor"
        private const val NOTIF_ID = 1001
    }
}
