package com.ozbel.teacher

import android.content.Context

/** Hassasiyet seviyeleri — kalibrasyon offset'ini değiştirir.
 *  Yüksek offset = dB daha yüksek okunur = daha duyarlı (kolay öter). */
enum class Sensitivity(val label: String, val calib: Double) {
    COK_DUYARLI("Çok Duyarlı", 95.0),
    DUYARLI("Duyarlı", 90.0),
    ORTA("Orta", 85.0),
    DUSUK("Düşük", 80.0);

    companion object {
        fun fromName(n: String?): Sensitivity =
            entries.firstOrNull { it.name == n } ?: DUYARLI
    }
}

object Prefs {
    private const val FILE = "ozbel_prefs"
    private const val KEY_SENS = "sensitivity"

    fun getSensitivity(ctx: Context): Sensitivity {
        val sp = ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        return Sensitivity.fromName(sp.getString(KEY_SENS, Sensitivity.DUYARLI.name))
    }

    fun setSensitivity(ctx: Context, s: Sensitivity) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(KEY_SENS, s.name).apply()
    }
}
