package com.ozbel.teacher

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

private val BG = Color(0xFF080B12)
private val CARD = Color(0xFF161B22)
private val BLUE = Color(0xFF3B82F6)
private val GREEN = Color(0xFF22C55E)
private val RED = Color(0xFFEF4444)
private val ORANGE = Color(0xFFF59E0B)
private val MUTED = Color(0xFF94A3B8)
private val TEXT = Color(0xFFF0F4F9)
private val BORDER = Color(0xFF30363D)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme(colorScheme = darkColorScheme(background = BG, surface = CARD)) { App() } }
    }
}

@Composable
fun App() {
    val ctx = LocalContextSafe()
    val screen by AppState.screen.collectAsStateWithLifecycle()
    val db by AppState.db.collectAsStateWithLifecycle()
    val err by AppState.errorMsg.collectAsStateWithLifecycle()

    val scanLauncher = rememberLauncherForActivityResult(ScanContract()) { result ->
        val content = result.contents ?: return@rememberLauncherForActivityResult
        val s = extractSession(content)
        if (s != null) {
            AppState.sessionId = s
            AppState.screen.value = AppState.Screen.MIC
        } else {
            AppState.errorMsg.value = "Geçersiz karekod. Tahtadaki QR'ı okutun."
            AppState.screen.value = AppState.Screen.ERROR
        }
    }

    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        val micOk = result[Manifest.permission.RECORD_AUDIO] == true ||
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        if (micOk) {
            startMonitor(ctx)
            AppState.screen.value = AppState.Screen.ACTIVE
        } else {
            AppState.errorMsg.value = "Mikrofon izni olmadan ölçüm yapılamaz."
            AppState.screen.value = AppState.Screen.ERROR
        }
    }

    Box(Modifier.fillMaxSize().background(BG), contentAlignment = Alignment.Center) {
        when (screen) {
            AppState.Screen.INTRO -> IntroScreen(onScan = {
                val opts = ScanOptions().apply {
                    setPrompt("Tahtadaki karekodu okutun")
                    setBeepEnabled(false)
                    setOrientationLocked(true)
                }
                scanLauncher.launch(opts)
            })
            AppState.Screen.MIC -> MicScreen {
                val perms = mutableListOf(Manifest.permission.RECORD_AUDIO)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                    perms.add(Manifest.permission.POST_NOTIFICATIONS)
                permLauncher.launch(perms.toTypedArray())
            }
            AppState.Screen.ACTIVE -> ActiveScreen(db = db, onEnd = {
                endLesson(ctx); AppState.screen.value = AppState.Screen.DONE
            })
            AppState.Screen.DONE -> DoneScreen()
            AppState.Screen.ERROR -> ErrorScreen(err) { AppState.reset() }
        }
    }
}

// ───────────────── Ekranlar ─────────────────

@Composable
fun IntroScreen(onScan: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("ÖzBel", color = TEXT, fontSize = 40.sp, fontWeight = FontWeight.Black)
        Text("Kulak Sağlığı Koruma Sistemi", color = MUTED, fontSize = 12.sp)
        Spacer(Modifier.height(6.dp))
        Text("Sınıfın gürültüsü 90 dB'i geçtiğinde tahtada öğrencilere uyarı gösterilir.",
            color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))
        BigButton("📷  Karekod Okut", BLUE, Color.White, onScan)
        Text("Mikrofon yalnızca ses seviyesi ölçümü için kullanılır. Ses kaydedilmez.",
            color = MUTED, fontSize = 11.sp, textAlign = TextAlign.Center)
    }
}

@Composable
fun MicScreen(onAllow: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("🎤", fontSize = 56.sp)
        Text("Mikrofon İzni", color = TEXT, fontSize = 21.sp, fontWeight = FontWeight.Bold)
        Text("Ses seviyesini ölçmek için mikrofon izni gerekli.\nAçılan pencerede \"İzin Ver\" seçin.",
            color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
        BigButton("Mikrofon İzni Ver & Başla", BLUE, Color.White, onAllow)
    }
}

@Composable
fun ActiveScreen(db: Int, onEnd: () -> Unit) {
    val ctx = LocalContextSafe()
    val rec = remember { DeviceRec.detect() }
    var calib by remember { mutableStateOf(Prefs.getCalib(ctx)) }

    val color = when { db >= 90 -> RED; db >= 70 -> ORANGE; else -> GREEN }
    val status = when { db >= 90 -> "⚠️ Çok Gürültülü!"; db >= 70 -> "Dikkat — Yüksek Ses"; else -> "Normal Seviye" }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        Spacer(Modifier.height(8.dp))
        Text("ÖzBel  ● Aktif", color = GREEN, fontSize = 16.sp, fontWeight = FontWeight.Bold)

        Box(contentAlignment = Alignment.Center, modifier = Modifier.size(220.dp)) {
            Canvas(Modifier.fillMaxSize()) {
                val stroke = 28f
                val d = size.minDimension - stroke
                val tl = Offset((size.width - d) / 2, (size.height - d) / 2)
                drawArc(Color(0x22FFFFFF), -90f, 360f, false, topLeft = tl, size = Size(d, d),
                    style = Stroke(stroke, cap = StrokeCap.Round))
                val sweep = (db.coerceIn(0, 120) / 120f) * 360f
                drawArc(color, -90f, sweep, false, topLeft = tl, size = Size(d, d),
                    style = Stroke(stroke, cap = StrokeCap.Round))
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("$db", color = TEXT, fontSize = 58.sp, fontWeight = FontWeight.Black)
                Text("DESİBEL", color = MUTED, fontSize = 11.sp)
            }
        }
        Text(status, color = color, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        BigButton("🏁 Ders Bitti", RED, Color.White, onEnd)

        // ── Akıllı cihaz kutusu ──
        Surface(color = CARD, shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("📱  ${rec.name} tespit edildi", color = TEXT, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Text("Bu cihaz için önerilen ayar: ${rec.label}", color = MUTED, fontSize = 12.sp)
                Spacer(Modifier.height(6.dp))
                Surface(color = BLUE, shape = RoundedCornerShape(10.dp)) {
                    Text("Öneriyi Uygula", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 11.dp)
                            .clickableNoRipple { calib = rec.calib; setCalibLive(ctx, rec.calib) })
                }
            }
        }

        // ── Hassasiyet seçici (5 seviye) ──
        Surface(color = CARD, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Mikrofon Hassasiyeti", color = TEXT, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                SENS_LEVELS.forEach { lvl ->
                    val sel = lvl.calib == calib
                    Surface(
                        color = if (sel) BLUE.copy(alpha = 0.20f) else Color.Transparent,
                        shape = RoundedCornerShape(12.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, if (sel) BLUE else BORDER),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            Modifier.fillMaxWidth().padding(13.dp)
                                .clickableNoRipple { calib = lvl.calib; setCalibLive(ctx, lvl.calib) },
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("${lvl.emoji}  ${lvl.label}", color = if (sel) TEXT else MUTED,
                                fontSize = 14.sp, fontWeight = if (sel) FontWeight.Bold else FontWeight.Normal)
                            Spacer(Modifier.weight(1f))
                            if (lvl.calib == rec.calib) {
                                Text("Önerilen", color = BLUE, fontSize = 10.sp, fontWeight = FontWeight.Black)
                            }
                        }
                    }
                }
                Text("Bağırınca ötüyor ama normal seste ötmüyorsa ideal ayardasınız.",
                    color = MUTED, fontSize = 11.sp)
            }
        }
        Spacer(Modifier.height(20.dp))
    }
}

@Composable
fun DoneScreen() {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("🏁", fontSize = 70.sp)
        Text("Ders Tamamlandı", color = TEXT, fontSize = 21.sp, fontWeight = FontWeight.Bold)
        Text("Mikrofon kapatıldı.\nUygulamayı kapatabilirsiniz.", color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
    }
}

@Composable
fun ErrorScreen(msg: String, onRetry: () -> Unit) {
    Column(
        Modifier.padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("⚠️", fontSize = 56.sp)
        Text("Hata", color = TEXT, fontSize = 21.sp, fontWeight = FontWeight.Bold)
        Text(msg, color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
        BigButton("Yeniden Dene", CARD, TEXT, onRetry)
    }
}

@Composable
fun BigButton(text: String, bg: Color, fg: Color, onClick: () -> Unit) {
    Surface(color = bg, shape = RoundedCornerShape(15.dp), modifier = Modifier.fillMaxWidth()) {
        Text(text, color = fg, fontWeight = FontWeight.Bold, fontSize = 15.sp, textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(vertical = 17.dp).clickableNoRipple(onClick))
    }
}
