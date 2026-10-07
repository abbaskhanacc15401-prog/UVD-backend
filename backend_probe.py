import json
import urllib.parse
import urllib.request

base_url = "http://127.0.0.1:8000"
video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
request_url = f"{base_url}/api/extract?url={urllib.parse.quote(video_url)}"
request = urllib.request.Request(request_url, headers={"User-Agent": "BackendProbe/1.0"})

with urllib.request.urlopen(request, timeout=120) as response:
    body = response.read().decode("utf-8")
    data = json.loads(body)
    print("HTTP_STATUS", response.status)
    print("TITLE", data.get("title"))
    print("SELECTED_QUALITY", data.get("selected_quality"))
    print("FORMAT_COUNT", len(data.get("formats", [])))
    print("FIRST_FORMAT", data.get("formats", [None])[0])
