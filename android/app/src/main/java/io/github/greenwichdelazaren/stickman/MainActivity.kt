package io.github.greenwichdelazaren.stickman

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Log
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
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
    @Volatile private var opened: String? = null            // a picked file the page hasn't taken yet

    private val pickFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        // Some pickers give the file as clip data instead of the intent's data.
        val uri = result.data?.data ?: result.data?.clipData?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.uri
        // The WebView drops a picked file whose type doesn't match the input's accept list (Downloads calls
        // a .json file application/octet-stream), so the page never gets it through the file input: the
        // input is answered empty and the file is read here and handed to the page (Host.opened). If Android
        // closed the app behind the file dialog, the new page takes it when it has started.
        chooser?.onReceiveValue(null)
        chooser = null
        if (uri != null) {
            opened = try {
                val data = contentResolver.openInputStream(uri)!!.use { it.readBytes() }
                JSONObject().put("name", displayName(uri)).put("data", Base64.encodeToString(data, Base64.NO_WRAP))
                    .toString()
            } catch (e: Exception) {
                Log.w("Stickman", "could not read $uri", e)
                null
            }
            web.evaluateJavascript("window.stickmanOpened && window.stickmanOpened()", null)
        }
    }

    private val createFile = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        // The file waits in the cache, not in memory: Android may close the app behind the save dialog,
        // and then this result reaches a new activity.
        val data = savingFile.takeIf { it.exists() }?.readBytes()
        savingFile.delete()
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
                pickFile.launch(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"  // file managers often don't know .json
                })
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
        /** The picked file the page hasn't taken yet, as {name, data (base64)}, or "". */
        @JavascriptInterface
        fun opened(): String {
            val file = opened ?: return ""
            opened = null
            return file
        }

        @JavascriptInterface
        fun save(name: String, type: String, base64: String) {
            val data = Base64.decode(base64, Base64.DEFAULT)
            runOnUiThread {
                savingFile.writeBytes(data)
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

    private val savingFile get() = File(cacheDir, "saving")  // the file waiting for a place to go

    private fun write(uri: Uri, data: ByteArray) {
        val saved = try {
            contentResolver.openOutputStream(uri, "wt")!!.use { it.write(data) }
            true
        } catch (_: Exception) {
            false
        }
        val name = displayName(uri)
        // A page that has only just restarted can't say it yet, so the app does (in English: the page has the Greek).
        web.evaluateJavascript("window.stickmanSaved ? (window.stickmanSaved(${JSONObject.quote(name)}, $saved), true) : false") {
            if (it != "true") Toast.makeText(this, if (saved) "Saved $name" else "Could not save $name", Toast.LENGTH_LONG).show()
        }
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
            "ttf" to "font/ttf",  // the Document Composer's caption font
        )
    }
}
