package com.attentionstack.vrittant

import android.content.Context
import android.media.AudioManager
import android.telephony.TelephonyManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.attentionstack.vrittant/telephony"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isInCall" -> {
                        val telephony = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
                        val inCall = telephony.callState != TelephonyManager.CALL_STATE_IDLE ||
                                     audioManager.mode == AudioManager.MODE_IN_CALL ||
                                     audioManager.mode == AudioManager.MODE_IN_COMMUNICATION
                        result.success(inCall)
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
