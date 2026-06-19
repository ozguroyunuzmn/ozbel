package com.ozbel.teacher

import java.net.HttpURLConnection
import java.net.URL

/** Firebase Realtime Database — düz REST (web ile aynı yapı, SDK yok).
 *  Board /sessions/<kod>/{db,noise,mic,teacher,lesson} okur, control yazar. */
object FirebaseRest {
    // Firebase adresi (sonunda / OLMADAN)
    const val DB = "https://ozbel-eb6af-default-rtdb.europe-west1.firebasedatabase.app"

    private fun nodeUrl(session: String, key: String) =
        "$DB/sessions/$session/$key.json"

    /** Bir alanı yaz (PUT). JSON gövde: sayı, bool veya "string". */
    fun put(session: String, key: String, jsonValue: String) {
        try {
            val conn = URL(nodeUrl(session, key)).openConnection() as HttpURLConnection
            conn.requestMethod = "PUT"
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(jsonValue.toByteArray()) }
            conn.inputStream.use { it.readBytes() }
            conn.disconnect()
        } catch (_: Exception) {
        }
    }

    fun putNumber(session: String, key: String, value: Int) = put(session, key, value.toString())
    fun putBool(session: String, key: String, value: Boolean) = put(session, key, value.toString())
    fun putString(session: String, key: String, value: String) = put(session, key, "\"$value\"")

    /** control alanını oku — "disconnect" ise board bağlantıyı kesmiş demektir. */
    fun readControl(session: String): String? {
        return try {
            val conn = URL(nodeUrl(session, "control")).openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            val body = conn.inputStream.use { String(it.readBytes()) }
            conn.disconnect()
            body.trim().trim('"').takeIf { it != "null" && it.isNotEmpty() }
        } catch (_: Exception) {
            null
        }
    }
}
