"""End-to-end check of /health and /voice.

Works on Windows, macOS and Linux. Start the service first, then:

    uv run python scripts/smoke_test.py [audio_file] [base_url]

Without audio_file, a sample menu is spoken into a WAV file using the
built-in text-to-speech (Windows: System.Speech, macOS: say). On Linux pass
your own recording. base_url defaults to http://localhost:8002.
"""
import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

SAMPLE_SPEECH = ("Add masala dosa for one hundred twenty rupees. Filter coffee, small is thirty "
                 "and large is fifty. Paneer butter masala, two hundred forty rupees, takes fifteen minutes.")
EXPECTED_FIELDS = {"name", "description", "categoryId", "price", "quantity", "preparationTime", "variants"}


def make_speech(path: str) -> None:
    if sys.platform == "win32":
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{path}'); $s.Speak('{SAMPLE_SPEECH}'); $s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
    elif sys.platform == "darwin":
        subprocess.run(["say", "-o", path, "--data-format=LEI16@22050", SAMPLE_SPEECH], check=True)
    else:
        raise RuntimeError("No built-in text-to-speech on this OS -- pass an audio file path")


def post_audio(base_url: str, path: str) -> dict:
    """POST the file to /voice and return the last SSE event."""
    mime = {".m4a": "audio/mp4", ".wav": "audio/wav", ".mp3": "audio/mpeg"}.get(
        os.path.splitext(path)[1].lower(), mimetypes.guess_type(path)[0] or "audio/wav")
    with open(path, "rb") as f:
        data = f.read()
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(f"{base_url}/voice", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    last = None
    with urllib.request.urlopen(request, timeout=300) as response:
        for raw in response:
            line = raw.decode("utf-8").strip()
            if line.startswith("data: "):
                last = json.loads(line[6:])
    return last or {}


def main() -> int:
    audio = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("http") else None
    base_url = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:8002").rstrip("/")
    print(f"Testing {base_url}\n")

    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=20) as response:
            health = json.loads(response.read())
    except Exception as e:
        print(f"FAIL  health: {e} -- is the service running?")
        return 1
    print(f"{'PASS' if health['status'] == 'ok' else 'FAIL'}  health: "
          + ", ".join(f"{k}={v['status']}" for k, v in health["checks"].items()))

    with tempfile.TemporaryDirectory() as tmp:
        if audio is None:
            audio = os.path.join(tmp, "menu.wav")
            make_speech(audio)
        start = time.time()
        try:
            result = post_audio(base_url, audio)
        except Exception as e:
            print(f"FAIL  voice: {type(e).__name__}: {e}")
            return 1

    if "batchId" not in result:
        print(f"FAIL  voice: {result.get('message', result)}")
        return 1
    products = result["targetFormat"]
    missing = [p["name"] for p in products if not EXPECTED_FIELDS <= set(p)]
    if not products or missing:
        print(f"FAIL  voice: {len(products)} products, missing fields in {missing}")
        return 1
    timing = result["timingBreakdown"]
    print(f"PASS  voice: {len(products)} products in {time.time() - start:.1f}s "
          f"(transcription {timing['transcription_ms'] / 1000:.1f}s) -- "
          + ", ".join(p["name"] for p in products))
    return 0 if health["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
