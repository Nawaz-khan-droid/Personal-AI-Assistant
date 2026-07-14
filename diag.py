"""
Local diagnostic: tests Kokoro TTS, gTTS, ffmpeg MP3-to-WAV, and Moonshine STT.
Run from project root: python diag.py
Results are written to diag_output/ directory.
"""
import sys, os, time, wave, struct, math, io, subprocess, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("diag_output", exist_ok=True)

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = {}

# ── 1. Kokoro ONNX ────────────────────────────────────────────────────────────
print("\n=== 1. Kokoro ONNX TTS ===")
try:
    from kokoro_onnx import Kokoro
    MODEL = "backend/static/kokoro-v1.0.onnx"
    VOICES = "backend/static/voices-v1.0.bin"
    if not os.path.exists(MODEL):
        print(f"{FAIL} Model file not found: {MODEL}")
        results["kokoro"] = "NO_MODEL"
    else:
        t0 = time.time()
        eng = Kokoro(MODEL, VOICES)
        print(f"{INFO} Kokoro engine loaded in {time.time()-t0:.2f}s")

        t0 = time.time()
        # Test both call styles: generator and direct
        result = eng.create("Hello, I am JARVIS, your personal assistant.", "am_adam", 1.0, "en-us")

        if hasattr(result, '__next__') or hasattr(result, '__iter__') and not isinstance(result, tuple):
            # It's a generator
            print(f"{INFO} Kokoro.create() returned a GENERATOR")
            items = list(result)
            print(f"{INFO} Generator yielded {len(items)} chunk(s)")
            if items:
                samples, sr = items[0]
            else:
                raise ValueError("Generator yielded nothing")
        else:
            print(f"{INFO} Kokoro.create() returned a TUPLE directly")
            samples, sr = result

        elapsed = time.time() - t0
        print(f"{INFO} Generated {len(samples)} samples @ {sr}Hz in {elapsed:.2f}s")

        # Write WAV
        import soundfile as sf
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()
        with open("diag_output/kokoro_test.wav", "wb") as f:
            f.write(wav_bytes)
        print(f"{PASS} Kokoro WAV saved: {len(wav_bytes)} bytes -> diag_output/kokoro_test.wav")
        results["kokoro"] = "OK"

except StopIteration as e:
    print(f"{FAIL} Kokoro raised StopIteration: {e}")
    traceback.print_exc()
    results["kokoro"] = "STOP_ITERATION"
except Exception as e:
    print(f"{FAIL} Kokoro error: {type(e).__name__}: {e}")
    traceback.print_exc()
    results["kokoro"] = f"ERROR: {type(e).__name__}"


# ── 2. gTTS ───────────────────────────────────────────────────────────────────
print("\n=== 2. gTTS ===")
try:
    from gtts import gTTS
    t0 = time.time()
    tts = gTTS(text="Hello from JARVIS.", lang="en")
    mp3_buf = io.BytesIO()
    tts.write_to_fp(mp3_buf)
    mp3_buf.seek(0)
    mp3_bytes = mp3_buf.read()
    elapsed = time.time() - t0
    print(f"{INFO} gTTS MP3: {len(mp3_bytes)} bytes in {elapsed:.2f}s")
    with open("diag_output/gtts_test.mp3", "wb") as f:
        f.write(mp3_bytes)
    print(f"{PASS} gTTS MP3 saved -> diag_output/gtts_test.mp3")
    results["gtts"] = "OK"
except Exception as e:
    print(f"{FAIL} gTTS error: {type(e).__name__}: {e}")
    results["gtts"] = f"ERROR: {type(e).__name__}"


# ── 3. ffmpeg MP3→WAV ─────────────────────────────────────────────────────────
print("\n=== 3. ffmpeg MP3→WAV conversion ===")
try:
    mp3_path = "diag_output/gtts_test.mp3"
    wav_path = "diag_output/gtts_converted.wav"
    if not os.path.exists(mp3_path):
        print(f"{FAIL} MP3 not found (gTTS step likely failed)")
        results["ffmpeg"] = "SKIP"
    else:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "22050", "-ac", "1", wav_path],
            capture_output=True, timeout=15
        )
        if r.returncode == 0:
            size = os.path.getsize(wav_path)
            print(f"{PASS} ffmpeg WAV: {size} bytes -> diag_output/gtts_converted.wav")
            results["ffmpeg"] = "OK"
        else:
            print(f"{FAIL} ffmpeg returned {r.returncode}: {r.stderr.decode()[:300]}")
            results["ffmpeg"] = f"ERROR: rc={r.returncode}"
except FileNotFoundError:
    print(f"{FAIL} ffmpeg not installed or not in PATH")
    results["ffmpeg"] = "NOT_FOUND"
except Exception as e:
    print(f"{FAIL} ffmpeg error: {e}")
    results["ffmpeg"] = f"ERROR: {type(e).__name__}"


# ── 4. Moonshine STT ──────────────────────────────────────────────────────────
print("\n=== 4. Moonshine STT (ONNX) ===")
try:
    from moonshine_onnx import MoonshineOnnxModel, load_audio
    MODEL_DIR = "backend/static/moonshine"
    if not os.path.exists(MODEL_DIR):
        print(f"{FAIL} Moonshine model dir not found: {MODEL_DIR}")
        results["moonshine"] = "NO_MODEL"
    else:
        t0 = time.time()
        model = MoonshineOnnxModel(model_name="moonshine/tiny", assetspath=MODEL_DIR)
        print(f"{INFO} Moonshine loaded in {time.time()-t0:.2f}s")

        # Create synthetic 1-second 16kHz audio for test
        sr = 16000
        dur = 1.0
        t = [math.sin(2 * math.pi * 440 * i / sr) * 0.3 for i in range(int(sr * dur))]
        import numpy as np
        audio_np = np.array(t, dtype=np.float32)

        t0 = time.time()
        tokens = model.generate(audio_np[np.newaxis, :])
        transcript = model.tokenizer.decode_batch(tokens)[0]
        print(f"{INFO} Moonshine inference: {time.time()-t0:.2f}s, transcript: '{transcript}'")
        print(f"{PASS} Moonshine STT working")
        results["moonshine"] = "OK"
except Exception as e:
    print(f"{FAIL} Moonshine error: {type(e).__name__}: {e}")
    results["moonshine"] = f"ERROR: {type(e).__name__}"


# ── 5. Groq LLM API ───────────────────────────────────────────────────────────
print("\n=== 5. Groq LLM API Ping ===")
try:
    from dotenv import load_dotenv
    load_dotenv()
    import groq
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        print(f"{FAIL} GROQ_API_KEY not set in .env")
        results["groq"] = "NO_KEY"
    else:
        client = groq.Groq(api_key=key)
        t0 = time.time()
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with exactly 3 words."}],
            max_tokens=10,
        )
        elapsed = time.time() - t0
        reply = r.choices[0].message.content
        print(f"{PASS} Groq ({elapsed:.2f}s): '{reply}'")
        results["groq"] = "OK"
except Exception as e:
    print(f"{FAIL} Groq error: {type(e).__name__}: {e}")
    results["groq"] = f"ERROR: {type(e).__name__}"


# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("DIAGNOSTIC SUMMARY")
print("="*50)
for k, v in results.items():
    icon = PASS if v == "OK" else FAIL
    print(f"  {icon} {k:15s}: {v}")

print("\nAudio files in diag_output/ — open them to hear if they sound correct.")
