package com.ozbel.teacher

import kotlinx.coroutines.flow.MutableStateFlow

/** Uygulama genelinde paylaşılan canlı durum (servis günceller, UI dinler). */
object AppState {
    enum class Screen { INTRO, MIC, ACTIVE, DONE, ERROR }

    val screen = MutableStateFlow(Screen.INTRO)
    val db = MutableStateFlow(0)
    val errorMsg = MutableStateFlow("")

    // Oturum
    @Volatile var sessionId: String? = null

    // Canlı hassasiyet (kalibrasyon offset'i) — slider değiştirince servis anında okur
    @Volatile var calib: Double = 90.0

    fun reset() {
        sessionId = null
        db.value = 0
        screen.value = Screen.INTRO
    }
}
