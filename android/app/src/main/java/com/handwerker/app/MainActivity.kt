package com.handwerker.app

import android.Manifest
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException

class MainActivity : AppCompatActivity() {
    private var recorder: MediaRecorder? = null
    private lateinit var outputFile: File
    private lateinit var recordButton: Button
    private lateinit var resultView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        recordButton = findViewById(R.id.recordButton)
        resultView = findViewById(R.id.resultView)

        recordButton.setOnClickListener {
            if (recorder == null) {
                startRecording()
            } else {
                stopRecording()
                uploadAudio()
            }
        }
    }

    private fun startRecording() {
        val permission = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
        if (permission != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 0)
            return
        }
        outputFile = File.createTempFile("recording", ".m4a", cacheDir)
        recorder = MediaRecorder().apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setOutputFile(outputFile.absolutePath)
            prepare()
            start()
        }
        recordButton.text = getString(R.string.stop_recording)
        resultView.text = getString(R.string.recording)
    }

    private fun stopRecording() {
        recorder?.apply {
            stop()
            release()
        }
        recorder = null
        recordButton.text = getString(R.string.start_recording)
    }

    private fun uploadAudio() {
        resultView.text = getString(R.string.uploading)
        val client = OkHttpClient()
        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                "file",
                "audio.m4a",
                outputFile.asRequestBody("audio/mp4".toMediaType())
            )
            .build()
        val request = Request.Builder()
            .url(BuildConfig.API_BASE_URL + "/process-audio/")
            .url(getString(R.string.api_base_url) + "/process-audio/")
            .post(requestBody)
            .build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    resultView.text = getString(R.string.error_prefix, e.message)
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: ""
                runOnUiThread {
                    resultView.text = body
                }
            }
        })
    }
}
