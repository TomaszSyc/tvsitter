/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.util.Log
import app.tvsitter.rules.pairing.PairRequest
import app.tvsitter.rules.pairing.PairResponse
import app.tvsitter.rules.pairing.PairingProtocol
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.charset.StandardCharsets

/**
 * A single-endpoint HTTP server, alive only while the TV is waiting to be paired.
 *
 * Hand-rolled rather than pulling in a web framework: this answers exactly one POST with a
 * few hundred bytes, and the app has already grown by three and a half megabytes for an
 * MQTT client. The safety here comes from being small and short-lived — one connection at a
 * time, hard caps on what is read, a socket timeout, and the whole thing shut down the
 * moment pairing succeeds.
 */
class PairingServer(private val onPair: (PairRequest) -> PairResponse) {

    private var serverSocket: ServerSocket? = null
    private var worker: Thread? = null

    val port: Int? get() = serverSocket?.localPort

    /** Binds an ephemeral port on all interfaces and returns it, or null on failure. */
    fun start(): Int? {
        if (serverSocket != null) return port

        val socket = runCatching { ServerSocket(0, BACKLOG, InetAddress.getByName("0.0.0.0")) }
            .getOrElse {
                Log.e(EnforcerService.TAG, "pairing: could not bind a port", it)
                return null
            }
        serverSocket = socket

        worker = Thread({ acceptLoop(socket) }, "tvsitter-pairing").apply {
            isDaemon = true
            start()
        }
        Log.i(EnforcerService.TAG, "pairing: listening on ${socket.localPort}")
        return socket.localPort
    }

    fun stop() {
        val socket = serverSocket ?: return
        serverSocket = null
        runCatching { socket.close() }
        worker?.interrupt()
        worker = null
        Log.i(EnforcerService.TAG, "pairing: stopped listening")
    }

    private fun acceptLoop(socket: ServerSocket) {
        while (!socket.isClosed) {
            val client = runCatching { socket.accept() }.getOrNull() ?: return
            // Sequential on purpose: one pairing at a time is all that makes sense, and it
            // means a flood of connections cannot spawn a thread each.
            runCatching { handle(client) }
                .onFailure { Log.w(EnforcerService.TAG, "pairing: request failed", it) }
            runCatching { client.close() }
        }
    }

    private fun handle(client: Socket) {
        client.soTimeout = PairingProtocol.SOCKET_TIMEOUT_MS
        val input = client.getInputStream()

        val head = readUntilHeadersEnd(input) ?: return respond(
            client,
            HTTP_BAD_REQUEST,
            PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
        )

        val requestLine = head.lineSequence().firstOrNull().orEmpty()
        if (!requestLine.startsWith("POST ${PairingProtocol.PATH}")) {
            Log.d(EnforcerService.TAG, "pairing: refusing '$requestLine'")
            return respond(
                client,
                HTTP_NOT_FOUND,
                PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
            )
        }

        val declaredLength = head.lineSequence()
            .firstOrNull { it.startsWith("content-length:", ignoreCase = true) }
            ?.substringAfter(':')?.trim()?.toIntOrNull()
            ?: return respond(
                client,
                HTTP_BAD_REQUEST,
                PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
            )

        if (declaredLength !in 1..PairingProtocol.MAX_REQUEST_BYTES) {
            Log.w(EnforcerService.TAG, "pairing: refusing a body of $declaredLength bytes")
            return respond(
                client,
                HTTP_BAD_REQUEST,
                PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
            )
        }

        val body = ByteArray(declaredLength)
        var read = 0
        while (read < declaredLength) {
            val count = input.read(body, read, declaredLength - read)
            if (count < 0) break
            read += count
        }
        if (read < declaredLength) {
            return respond(
                client,
                HTTP_BAD_REQUEST,
                PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
            )
        }

        val request = runCatching {
            PairingProtocol.json.decodeFromString<PairRequest>(String(body, StandardCharsets.UTF_8))
        }.getOrElse {
            Log.w(EnforcerService.TAG, "pairing: undecodable body")
            return respond(
                client,
                HTTP_BAD_REQUEST,
                PairResponse.rejected(PairResponse.ERROR_BAD_REQUEST),
            )
        }

        val result = onPair(request)
        respond(client, if (result.ok) HTTP_OK else HTTP_FORBIDDEN, result)
    }

    /**
     * Reads the request head, refusing anything oversized. Without this cap a peer could
     * stream headers forever and hold the single accept loop hostage.
     */
    private fun readUntilHeadersEnd(input: java.io.InputStream): String? {
        val buffer = StringBuilder()
        var consecutiveNewlines = 0
        while (buffer.length < PairingProtocol.MAX_REQUEST_BYTES) {
            val byte = try {
                input.read()
            } catch (_: IOException) {
                return null
            }
            if (byte < 0) return null
            val char = byte.toInt().toChar()
            if (char == '\r') continue
            buffer.append(char)
            consecutiveNewlines = if (char == '\n') consecutiveNewlines + 1 else 0
            if (consecutiveNewlines == 2) return buffer.toString()
        }
        return null
    }

    private fun respond(client: Socket, status: String, payload: PairResponse) {
        val body = PairingProtocol.json.encodeToString(payload).toByteArray(StandardCharsets.UTF_8)
        val head = buildString {
            append("HTTP/1.1 ").append(status).append("\r\n")
            append("Content-Type: application/json; charset=utf-8\r\n")
            append("Content-Length: ").append(body.size).append("\r\n")
            append("Connection: close\r\n\r\n")
        }
        runCatching {
            client.getOutputStream().apply {
                write(head.toByteArray(StandardCharsets.US_ASCII))
                write(body)
                flush()
            }
        }
    }

    private companion object {
        const val BACKLOG = 4
        const val HTTP_OK = "200 OK"
        const val HTTP_BAD_REQUEST = "400 Bad Request"
        const val HTTP_FORBIDDEN = "403 Forbidden"
        const val HTTP_NOT_FOUND = "404 Not Found"
    }
}
