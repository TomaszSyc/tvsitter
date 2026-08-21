/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.provider.Settings
import android.util.Log
import app.tvsitter.rules.pairing.PairRequest
import app.tvsitter.rules.pairing.PairResponse
import app.tvsitter.rules.pairing.PairingProtocol
import app.tvsitter.rules.pairing.PairingResult
import app.tvsitter.rules.pairing.PairingSession
import java.security.SecureRandom
import kotlin.random.asKotlinRandom

/**
 * Pairing, from the TV's side: show a PIN, advertise over mDNS, accept one set of broker
 * settings, then disappear.
 *
 * Both the advertisement and the listening socket exist **only while unpaired or while
 * pairing was asked for**. That is the point: a fresh install is discoverable with no
 * configuration at all, which is the whole reason for D14 — and once a TV is paired there
 * is no open port and no broadcast, because neither has anything left to do.
 */
class PairingManager(
    private val context: Context,
    /** Resolved once by the caller through [Settings.deviceId]; see the note there. */
    val deviceId: String,
    private val onPaired: (PairRequest) -> Unit,
) {
    private val nsdManager = context.getSystemService(NsdManager::class.java)

    private var session: PairingSession? = null
    private var server: PairingServer? = null
    private var registration: NsdManager.RegistrationListener? = null

    val isActive: Boolean get() = session != null

    val pin: String? get() = session?.pin

    fun secondsRemaining(): Long = session?.secondsRemaining(System.currentTimeMillis()) ?: 0

    val deviceName: String by lazy {
        Settings.Global.getString(context.contentResolver, Settings.Global.DEVICE_NAME)
            ?.takeIf { it.isNotBlank() }
            ?: Build.MODEL
    }

    /** Opens a pairing window and returns the PIN to show, or null if it could not start. */
    fun start(): String? {
        stop()

        val fresh = PairingSession.create(
            nowMs = System.currentTimeMillis(),
            random = SecureRandom().asKotlinRandom(),
        )
        val listener = PairingServer(::verify)
        val port = listener.start() ?: run {
            Log.e(EnforcerService.TAG, "pairing: no port, not advertising")
            return null
        }

        session = fresh
        server = listener
        advertise(port)
        Log.i(EnforcerService.TAG, "pairing: open for ${fresh.secondsRemaining(System.currentTimeMillis())}s")
        return fresh.pin
    }

    fun stop() {
        session = null
        server?.stop()
        server = null
        registration?.let { listener ->
            runCatching { nsdManager?.unregisterService(listener) }
                .onFailure { Log.w(EnforcerService.TAG, "pairing: unregister failed", it) }
        }
        registration = null
    }

    /**
     * Called from the server thread. Everything that decides acceptance lives in
     * [PairingSession], which is tested on the JVM; this only translates the verdict.
     */
    private fun verify(request: PairRequest): PairResponse {
        val active = session ?: return PairResponse.rejected(PairResponse.ERROR_NOT_PAIRING)

        return when (val verdict = active.verify(request.pin, System.currentTimeMillis())) {
            is PairingResult.Accepted -> {
                Log.i(EnforcerService.TAG, "pairing: accepted, broker ${request.host}:${request.port}")
                onPaired(request)
                stop()
                PairResponse.accepted(deviceId, deviceName)
            }
            is PairingResult.WrongPin -> {
                Log.w(EnforcerService.TAG, "pairing: wrong pin, ${verdict.attemptsRemaining} left")
                PairResponse.rejected(PairResponse.ERROR_WRONG_PIN, verdict.attemptsRemaining)
            }
            PairingResult.Expired -> {
                Log.i(EnforcerService.TAG, "pairing: expired")
                PairResponse.rejected(PairResponse.ERROR_EXPIRED)
            }
            PairingResult.NoAttemptsLeft -> {
                Log.w(EnforcerService.TAG, "pairing: attempts exhausted")
                PairResponse.rejected(PairResponse.ERROR_NO_ATTEMPTS)
            }
            PairingResult.AlreadyUsed -> PairResponse.rejected(PairResponse.ERROR_ALREADY_USED)
        }
    }

    private fun advertise(port: Int) {
        val manager = nsdManager ?: return
        val info = NsdServiceInfo().apply {
            serviceName = "TV Sitter $deviceId"
            serviceType = PairingProtocol.SERVICE_TYPE
            setPort(port)
            setAttribute(PairingProtocol.TXT_DEVICE_ID, deviceId)
            setAttribute(PairingProtocol.TXT_NAME, deviceName)
            setAttribute(PairingProtocol.TXT_VERSION, BuildConfig.VERSION_NAME)
            setAttribute(PairingProtocol.TXT_PAIRED, "false")
        }

        val listener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(info: NsdServiceInfo) {
                Log.i(EnforcerService.TAG, "pairing: advertising as ${info.serviceName}")
            }

            override fun onRegistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                Log.e(EnforcerService.TAG, "pairing: advertisement failed, code $errorCode")
            }

            override fun onServiceUnregistered(info: NsdServiceInfo) {
                Log.i(EnforcerService.TAG, "pairing: no longer advertising")
            }

            override fun onUnregistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                Log.w(EnforcerService.TAG, "pairing: unregistration failed, code $errorCode")
            }
        }
        registration = listener
        runCatching { manager.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener) }
            .onFailure { Log.e(EnforcerService.TAG, "pairing: registerService threw", it) }
    }
}
