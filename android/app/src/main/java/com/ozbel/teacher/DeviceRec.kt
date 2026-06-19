package com.ozbel.teacher

import android.os.Build

/** Cihaza göre önerilen hassasiyet.
 *  Gerçek model bilgisi Build.MODEL/MANUFACTURER'dan gelir; markaya/forma göre makul öneri. */
object DeviceRec {
    data class Rec(val name: String, val calib: Int, val label: String)

    fun detect(): Rec {
        val manRaw = Build.MANUFACTURER.orEmpty()
        val model = Build.MODEL.orEmpty()
        val man = manRaw.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
        val name = when {
            model.isBlank() -> man.ifBlank { "Telefonunuz" }
            model.startsWith(man, ignoreCase = true) -> model
            else -> "$man $model".trim()
        }
        val calib = recommend(manRaw.lowercase(), model.lowercase())
        return Rec(name, calib, Prefs.labelFor(calib))
    }

    private fun recommend(man: String, model: String): Int {
        // Tabletler hoparlör/mikrofon biraz kısık → Duyarlı (100)
        val isTablet = model.contains("tab") || model.contains("pad") ||
            model.startsWith("sm-t") || model.startsWith("sm-x")
        if (isTablet) return 100

        return when {
            // Xiaomi ailesi (Redmi/POCO dahil) — mikrofon kazancı genelde biraz düşük
            man.contains("xiaomi") || model.contains("redmi") || model.contains("poco") ||
                model.contains("mi ") -> 100
            // Huawei / Honor
            man.contains("huawei") || man.contains("honor") -> 100
            // Oppo / Realme / Vivo / OnePlus — orta
            man.contains("oppo") || man.contains("realme") || man.contains("vivo") ||
                man.contains("oneplus") -> 97
            // Samsung Galaxy — mikrofon iyi kalibre, Orta yeterli
            man.contains("samsung") -> 97
            // Google Pixel
            man.contains("google") -> 97
            // Bilinmeyen → Orta (güvenli varsayılan)
            else -> 97
        }
    }
}
