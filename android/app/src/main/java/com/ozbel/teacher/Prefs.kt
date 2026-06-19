package com.ozbel.teacher

import android.content.Context

/** Hassasiyet seviyeleri — site (index.html) ile birebir aynı kalibrasyon değerleri.
 *  Yüksek calib = dB daha yüksek okunur = daha duyarlı. */
data class SensLevel(val calib: Int, val emoji: String, val label: String)

val SENS_LEVELS = listOf(
    SensLevel(105, "🔊", "Çok Duyarlı"),
    SensLevel(100, "🔉", "Duyarlı"),
    SensLevel(97,  "⚖️", "Orta"),
    SensLevel(92,  "🔈", "Az Duyarlı"),
    SensLevel(87,  "🔇", "Duyarsız"),
)

object Prefs {
    private const val FILE = "ozbel_prefs"
    private const val KEY_CALIB = "calib"
    const val DEFAULT_CALIB = 97

    fun getCalib(ctx: Context): Int =
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).getInt(KEY_CALIB, DEFAULT_CALIB)

    fun setCalib(ctx: Context, v: Int) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putInt(KEY_CALIB, v).apply()
    }

    fun labelFor(calib: Int): String =
        SENS_LEVELS.firstOrNull { it.calib == calib }?.label ?: "Orta"
}
