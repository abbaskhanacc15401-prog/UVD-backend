# Android + FastAPI Backend Integration Instructions

## Goal
Connect the Android app to the local FastAPI backend, test it locally, and later replace the local IP with the deployed online backend URL.

## 1) Add Internet permission
In AndroidManifest.xml:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

## 2) Add dependencies
In app/build.gradle:

```gradle
dependencies {
    implementation "com.squareup.retrofit2:retrofit:2.11.0"
    implementation "com.squareup.retrofit2:converter-gson:2.11.0"
    implementation "com.google.code.gson:gson:2.10.1"
}
```

Then Sync Project with Gradle Files.

## 3) Choose base URL
For local testing on the same Wi‑Fi network:

```kotlin
private const val BASE_URL = "http://192.168.42.53:8000/"
```

For Android emulator:

```kotlin
private const val BASE_URL = "http://10.0.2.2:8000/"
```

## 4) Create model classes
File: ApiModels.kt

```kotlin
data class DownloadResponse(
    val success: Boolean,
    val title: String,
    val thumbnail: String?,
    val duration_sec: Int?,
    val selected_quality: String?,
    val download_url: String?,
    val format_id: String?,
    val formats: List<FormatItem>
)

data class FormatItem(
    val quality: String?,
    val ext: String?,
    val format_id: String?,
    val download_url: String?,
    val type: String?
)
```

## 5) Create API interface
File: ApiService.kt

```kotlin
import retrofit2.http.GET
import retrofit2.http.Query

interface ApiService {
    @GET("api/download")
    suspend fun getDownloadLink(
        @Query("url") url: String,
        @Query("quality") quality: String? = null
    ): DownloadResponse
}
```

## 6) Create Retrofit client
File: RetrofitClient.kt

```kotlin
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object RetrofitClient {
    private const val BASE_URL = "http://192.168.42.53:8000/"

    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
```

## 7) Test API call from Android app
File: MainActivity.kt

```kotlin
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        lifecycleScope.launch {
            try {
                val response = RetrofitClient.api.getDownloadLink(
                    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    quality = "720p"
                )

                if (response.success && response.download_url != null) {
                    Log.d("API_TEST", "Title: ${response.title}")
                    Log.d("API_TEST", "Download URL: ${response.download_url}")
                } else {
                    Log.e("API_TEST", "No valid response from backend")
                }
            } catch (e: Exception) {
                Log.e("API_TEST", "API Error: ${e.message}")
            }
        }
    }
}
```

## 8) Local backend testing steps
Before deploying online, run backend locally:

```powershell
cd d:\fro\backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then test in browser or app:

```text
http://192.168.42.53:8000/api/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

If response returns JSON with download_url, backend is working.

## 9) Later when backend is live online
Replace base URL with production URL:

```kotlin
private const val BASE_URL = "https://your-backend-domain.com/"
```

No app code changes needed besides base URL.

## 10) Short agent instruction
Use this for an agent:

> Integrate the Android app with the FastAPI backend using Retrofit and Gson. Add INTERNET permission. Use local base URL http://192.168.42.53:8000/ for testing on the same Wi‑Fi. Create a GET /api/download endpoint call with url and optional quality parameters. Parse success, title, selected_quality, download_url, and formats. Test locally before deploying. Replace the base URL later with the hosted backend URL when production is ready.
