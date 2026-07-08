# ─────────────────────────────────────────────────────────
#  PAIO-Omni  ·  tts.py
#  Thread-safe background queue variant with safe SAPI context resetting.
# ─────────────────────────────────────────────────────────

import re
import platform
import threading
import queue

_tts_queue = queue.Queue()
_worker_thread = None

def _tts_worker():
    os_name = platform.system()
    
    while True:
        text = _tts_queue.get()
        if text is None:
            break
        try:
            import pyttsx3
            # Initialize inside the loop per sentence to keep Windows COM state clean
            engine = pyttsx3.init()
            engine.setProperty("rate", 145)  # Dropped rate slightly to make it sound less mechanical
            engine.setProperty("volume", 1.0)
            
            voices = engine.getProperty("voices")
            preferred = ["david", "zira", "mark"] if os_name == "Windows" else ["samantha", "alex"]
            
            selected = False
            for name in preferred:
                for v in voices:
                    if name in v.name.lower():
                        engine.setProperty("voice", v.id)
                        selected = True
                        break
                if selected: break
                
            engine.say(text)
            engine.runAndWait()
            
            # Explicit clean up to release the COM hook
            del engine
            
        except Exception as e:
            print(f"  [TTS Worker] error: {e}")
        finally:
            _tts_queue.task_done()

def load():
    global _worker_thread
    print("  Loading Background TTS engine ...")
    _worker_thread = threading.Thread(target=_tts_worker, daemon=True)
    _worker_thread.start()
    print(f"  ✓ TTS Background Worker ready ({platform.system()} SAPI)")

def speak(text: str):
    clean_text = _clean(text)
    if clean_text:
        _tts_queue.put(clean_text)

def wait():
    """Block until all text in the queue has finished speaking."""
    _tts_queue.join()

def _clean(text: str) -> str:
    # Strip markdown headers, tables, and list asterisks completely
    text = re.sub(r"[\*#`_-]", "", text)
    text = text.replace("\n", " ").strip()
    return text