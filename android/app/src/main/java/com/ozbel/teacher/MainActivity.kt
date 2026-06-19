package com.ozbel.teacher

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
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
private val BLUE2 = Color(0xFF1D4ED8)
private val BLUE_LT = Color(0xFF60A5FA)
private val GREEN = Color(0xFF22C55E)
private val RED = Color(0xFFEF4444)
private val ORANGE = Color(0xFFF59E0B)
private val MUTED = Color(0xFF94A3B8)
private val TEXT = Color(0xFFF0F4F9)
private val BORDER = Color(0xFF24304A)

private val bgBrush = Brush.linearGradient(
    colors = listOf(Color(0xFF0A0E18), BG, Color(0xFF0A1410)),
    start = Offset(0f, 0f), end = Offset(900f, 1600f)
)
private val blueBtn = Brush.linearGradient(listOf(BLUE_LT, BLUE2))

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
            startMonitor(ctx); AppState.screen.value = AppState.Screen.ACTIVE
        } else {
            AppState.errorMsg.value = "Mikrofon izni olmadan ölçüm yapılamaz."
            AppState.screen.value = AppState.Screen.ERROR
        }
    }

    Box(Modifier.fillMaxSize().background(bgBrush), contentAlignment = Alignment.Center) {
        when (screen) {
            AppState.Screen.INTRO -> IntroScreen(onScan = {
                scanLauncher.launch(ScanOptions().apply {
                    setPrompt("Tahtadaki karekodu okutun"); setBeepEnabled(false); setOrientationLocked(true)
                })
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

// ───────────────── Ortak parçalar ─────────────────

@Composable
fun Logo(big: Boolean = true) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
        Box(
            Modifier.size(if (big) 46.dp else 36.dp).clip(RoundedCornerShape(13.dp)).background(blueBtn),
            contentAlignment = Alignment.Center
        ) { Text("🔊", fontSize = if (big) 22.sp else 18.sp) }
        Row {
            Text("Öz", color = TEXT, fontSize = if (big) 30.sp else 24.sp, fontWeight = FontWeight.Black)
            Text("Bel", color = BLUE_LT, fontSize = if (big) 30.sp else 24.sp, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
fun GradientButton(text: String, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(blueBtn)
            .clickableNoRipple(onClick).padding(vertical = 18.dp),
        contentAlignment = Alignment.Center
    ) { Text(text, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp) }
}

@Composable
fun GlassCard(content: @Composable ColumnScope.() -> Unit) {
    Surface(
        color = CARD, shape = RoundedCornerShape(20.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, BORDER),
        modifier = Modifier.fillMaxWidth()
    ) { Column(Modifier.padding(20.dp), content = content) }
}

// ───────────────── Ekranlar ─────────────────

@Composable
fun IntroScreen(onScan: () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(26.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Spacer(Modifier.height(40.dp))
        Logo(big = true)
        Spacer(Modifier.height(6.dp))
        Text("Kulak Sağlığı Koruma Sistemi", color = MUTED, fontSize = 12.sp)
        Spacer(Modifier.height(26.dp))

        GlassCard {
            Text("Nasıl Çalışır?", color = TEXT, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            StepRow("1", "Tahtadaki büyük QR'ı okutun", "Kamera uygulamasıyla veya aşağıdaki butona basın")
            StepDivider()
            StepRow("2", "Mikrofon izni verin", "Ses seviyesi ölçümü için gerekli")
            StepDivider()
            StepRow("3", "Sistem aktif", "90 dB'i aşınca tahtada uyarı çıkar", last = true)
        }

        Spacer(Modifier.height(24.dp))
        GradientButton("📷  Karekod Okut", onScan)
        Spacer(Modifier.height(14.dp))
        Text("Mikrofon yalnızca ses seviyesi ölçümü için kullanılır. Ses kaydedilmez.",
            color = MUTED, fontSize = 11.sp, textAlign = TextAlign.Center)
        Spacer(Modifier.height(40.dp))
    }
}

@Composable
fun StepRow(num: String, title: String, sub: String, last: Boolean = false) {
    Row(Modifier.fillMaxWidth().padding(vertical = 11.dp), verticalAlignment = Alignment.Top) {
        Box(
            Modifier.size(28.dp).clip(CircleShape)
                .background(Brush.linearGradient(listOf(BLUE.copy(alpha = .35f), BLUE.copy(alpha = .12f)))),
            contentAlignment = Alignment.Center
        ) { Text(num, color = BLUE_LT, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.width(13.dp))
        Column {
            Text(title, color = TEXT, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Text(sub, color = MUTED, fontSize = 12.sp)
        }
    }
}

@Composable
fun StepDivider() { Box(Modifier.fillMaxWidth().height(1.dp).background(BORDER)) }

@Composable
fun MicScreen(onAllow: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("🎤", fontSize = 64.sp)
        Text("Mikrofon İzni", color = TEXT, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text("Ses seviyesini ölçmek için mikrofon izni gerekli.\nAçılan pencerede \"İzin Ver\" seçin.",
            color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        GradientButton("Mikrofon İzni Ver & Başla", onAllow)
    }
}

@Composable
fun ActiveScreen(db: Int, onEnd: () -> Unit) {
    val ctx = LocalContextSafe()
    val rec = remember { DeviceRec.detect() }
    var calib by remember { mutableStateOf(Prefs.getCalib(ctx)) }

    // 60fps akıcı geçiş — değerler arası yumuşak interpolasyon
    val animDb by animateFloatAsState(
        targetValue = db.toFloat(),
        animationSpec = tween(durationMillis = 220, easing = LinearEasing),
        label = "db"
    )
    val targetColor = when { db >= 90 -> RED; db >= 70 -> ORANGE; else -> GREEN }
    val ringColor by animateColorAsState(targetColor, tween(300), label = "col")
    val status = when { db >= 90 -> "⚠️ Çok Gürültülü!"; db >= 70 -> "Dikkat — Yüksek Ses"; else -> "Normal Seviye" }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Spacer(Modifier.height(10.dp))
        Logo(big = false)

        Box(contentAlignment = Alignment.Center, modifier = Modifier.size(240.dp).padding(top = 6.dp)) {
            Canvas(Modifier.fillMaxSize()) {
                val stroke = 30f
                val d = size.minDimension - stroke
                val tl = Offset((size.width - d) / 2, (size.height - d) / 2)
                drawArc(Color(0x18FFFFFF), -90f, 360f, false, topLeft = tl, size = Size(d, d),
                    style = Stroke(stroke, cap = StrokeCap.Round))
                val sweep = (animDb.coerceIn(0f, 120f) / 120f) * 360f
                drawArc(ringColor, -90f, sweep, false, topLeft = tl, size = Size(d, d),
                    style = Stroke(stroke, cap = StrokeCap.Round))
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("$db", color = TEXT, fontSize = 64.sp, fontWeight = FontWeight.Black)
                Text("DESİBEL", color = MUTED, fontSize = 11.sp)
            }
        }
        Surface(color = ringColor.copy(alpha = .14f), shape = RoundedCornerShape(999.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, ringColor.copy(alpha = .4f))) {
            Text(status, color = ringColor, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 9.dp))
        }

        Spacer(Modifier.height(2.dp))
        Box(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp))
                .background(Brush.linearGradient(listOf(Color(0xFFF87171), RED)))
                .clickableNoRipple(onEnd).padding(vertical = 16.dp),
            contentAlignment = Alignment.Center
        ) { Text("🏁  Ders Bitti", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp) }

        // Cihaz kutusu
        GlassCard {
            Text("📱  ${rec.name} tespit edildi", color = TEXT, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text("Bu cihaz için önerilen ayar: ${rec.label}", color = MUTED, fontSize = 12.sp)
            Spacer(Modifier.height(10.dp))
            Box(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(blueBtn)
                    .clickableNoRipple { calib = rec.calib; setCalibLive(ctx, rec.calib) }
                    .padding(vertical = 11.dp),
                contentAlignment = Alignment.Center
            ) { Text("Öneriyi Uygula", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
        }

        // Hassasiyet seçici
        GlassCard {
            Text("Mikrofon Hassasiyeti", color = TEXT, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            SENS_LEVELS.forEach { lvl ->
                val sel = lvl.calib == calib
                Surface(
                    color = if (sel) BLUE.copy(alpha = .20f) else Color.Transparent,
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, if (sel) BLUE else BORDER),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                ) {
                    Row(
                        Modifier.fillMaxWidth().padding(13.dp)
                            .clickableNoRipple { calib = lvl.calib; setCalibLive(ctx, lvl.calib) },
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("${lvl.emoji}  ${lvl.label}", color = if (sel) TEXT else MUTED,
                            fontSize = 14.sp, fontWeight = if (sel) FontWeight.Bold else FontWeight.Normal)
                        Spacer(Modifier.weight(1f))
                        if (lvl.calib == rec.calib)
                            Text("Önerilen", color = BLUE_LT, fontSize = 10.sp, fontWeight = FontWeight.Black)
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
fun DoneScreen() {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("🏁", fontSize = 72.sp)
        Text("Ders Tamamlandı", color = TEXT, fontSize = 22.sp, fontWeight = FontWeight.Bold)
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
        Text("⚠️", fontSize = 60.sp)
        Text("Hata", color = TEXT, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text(msg, color = MUTED, fontSize = 13.sp, textAlign = TextAlign.Center)
        Surface(color = CARD, shape = RoundedCornerShape(14.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, BORDER)) {
            Text("Yeniden Dene", color = TEXT, fontWeight = FontWeight.Bold, fontSize = 14.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().clickableNoRipple(onRetry).padding(vertical = 14.dp))
        }
    }
}
