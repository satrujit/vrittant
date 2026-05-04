package com.attentionstack.vrittant

import android.content.Context
import android.media.AudioManager
import android.os.Bundle
import android.telephony.TelephonyManager
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.attentionstack.vrittant/telephony"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // FLAG_SECURE: blocks screenshots, screen-recording, and renders the
        // window black in the recents app-switcher. Same anti-exfiltration
        // posture as banking apps. Combined with the body-text Copy/Cut
        // guard (see core/widgets/copy_guard.dart), this closes the casual
        // leak paths a reporter could use to push internal stories out
        // before editorial review. Determined attackers can still point a
        // second phone at the screen — the goal is friction, not a hard
        // DRM wall.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE,
        )
    }

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
