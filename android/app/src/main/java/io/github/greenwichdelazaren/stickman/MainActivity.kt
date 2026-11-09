package io.github.greenwichdelazaren.stickman

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.WebViewAssetLoader
import java.io.File
import java.io.IOException
import org.json.JSONObject

/** The website (web/, bundled in assets/site with its libraries) in a WebView, plus what a WebView can't do itself. */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private var chooser: ValueCallback<Array<Uri>>? = null  // the page's file input, waiting for a file
    private var saving: ByteArray? = null                   // the file waiting for a place to go

    private val pickFile = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        chooser?.onReceiveValue(uri?.let { arrayOf(it) })
        chooser = null
    }

    private val createFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = saving
        saving = null
        val uri = result.data?.data
        if (data != null && uri != null) write(uri, data)
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val bars = SystemBarStyle.dark(Color.TRANSPARENT)
        enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        web = WebView(this)
        val loader = WebViewAssetLoader.Builder().addPathHandler("/", SiteFiles()).build()
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true  // the autosaved pose
            allowFileAccess = false
            textZoom = 100            // the layout is in pixels; the system's font size would break it
            setSupportZoom(false)
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                loader.shouldInterceptRequest(request.url)

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) =
                request.url.host != WebViewAssetLoader.DEFAULT_DOMAIN  // the app shows only its own page
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>,
                                           params: FileChooserParams): Boolean {
                chooser?.onReceiveValue(null)
                chooser = callback
                pickFile.launch(arrayOf("*/*"))  // file managers often don't know .json
                return true
            }
        }
        web.addJavascriptInterface(Host(), "StickmanHost")

        val root = FrameLayout(this)
        root.setBackgroundColor(Color.rgb(25, 30, 38))  // behind the system bars, as the toolbar
        root.addView(web)
        setContentView(root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val margins = insets.getInsets(WindowInsetsCompat.Type.systemBars() or
                                           WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            view.setPadding(margins.left, margins.top, margins.right, margins.bottom)
            WindowInsetsCompat.CONSUMED
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // The page closes its open list or box first; it answers "true" if there was one.
                web.evaluateJavascript("window.stickmanBack && window.stickmanBack()") { answer ->
                    if (answer != "true") finish()
                }
            }
        })
        web.loadUrl("https://${WebViewAssetLoader.DEFAULT_DOMAIN}/index.html")
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    /** Serves assets/site with the types the page needs: modules and WebAssembly won't load as anything else. */
    private inner class SiteFiles : WebViewAssetLoader.PathHandler {
        override fun handle(path: String): WebResourceResponse? {
            val name = path.ifEmpty { "index.html" }
            return try {
                val type = TYPES[name.substringAfterLast('.')] ?: "application/octet-stream"
                WebResourceResponse(type, if (type.startsWith("text/") || type.endsWith("javascript")) "utf-8" else null,
                                    assets.open("site/$name"))
            } catch (_: IOException) {
                null
            }
        }
    }

    /** Called by web/app.js, on a WebView thread. */
    private inner class Host {
        @JavascriptInterface
        fun save(name: String, type: String, base64: String) {
            val data = Base64.decode(base64, Base64.DEFAULT)
            runOnUiThread {
                saving = data
                createFile.launch(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    this.type = type
                    putExtra(Intent.EXTRA_TITLE, name)
                })
            }
        }

        @JavascriptInterface
        fun share(name: String, type: String, base64: String) {
            val data = Base64.decode(base64, Base64.DEFAULT)
            runOnUiThread {
                val folder = File(cacheDir, "share").apply { mkdirs() }
                val file = File(folder, File(name).name).apply { writeBytes(data) }
                val uri = FileProvider.getUriForFile(this@MainActivity, "$packageName.files", file)
                val send = Intent(Intent.ACTION_SEND).apply {
                    this.type = type
                    putExtra(Intent.EXTRA_STREAM, uri)
                    clipData = ClipData.newRawUri(name, uri)  // lets the share sheet show a preview
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                startActivity(Intent.createChooser(send, name))
            }
        }
    }

    private fun write(uri: Uri, data: ByteArray) {
        val saved = try {
            contentResolver.openOutputStream(uri, "wt")!!.use { it.write(data) }
            true
        } catch (_: Exception) {
            false
        }
        web.evaluateJavascript("window.stickmanSaved(${JSONObject.quote(displayName(uri))}, $saved)", null)
    }

    private fun displayName(uri: Uri): String =
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { row ->
            if (row.moveToFirst()) row.getString(0) else null
        } ?: uri.lastPathSegment.orEmpty()

    private companion object {
        val TYPES = mapOf(
            "html" to "text/html", "css" to "text/css", "js" to "text/javascript", "mjs" to "text/javascript",
            "json" to "application/json", "png" to "image/png", "wasm" to "application/wasm",
            "py" to "text/plain", "zip" to "application/zip", "whl" to "application/zip",
        )
    }
}
