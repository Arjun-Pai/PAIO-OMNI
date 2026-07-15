# PAIO-Omni · orchestrator.py  v0.4
import sys
import time
import hardware
import modes as mode_lib
import config
import stt
import llm
import tts

def startup():
    print("\n╔══════════════════════════════════════════════╗")
    print("║          PAIO-Omni  v0.4                     ║")
    print("║   Always-on · Cross-platform · Auto-mode     ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("Detecting hardware ...")
    hw = hardware.detect()
    print(f"  {hardware.summary(hw)}\n")

    # TTS first (heaviest load)
    tts.load()

    # STT — use whisper model from hardware profile
    whisper_m = hw["models"].get("whisper", "tiny.en")
    stt.load(whisper_model=whisper_m)

    # Ollama
    if not llm.check_ollama():
        print("\n❌  Ollama is not running.")
        print("    Open a new terminal and run:  ollama serve")
        sys.exit(1)

    print(f"\n  Whisper  : {whisper_m}")
    print(f"  Tier     : {hw['tier']}")
    return hw


def run():
    hw      = startup()
    history = []

    stt.start_listener()
    time.sleep(0.4)   # let mic stabilise
    print("\n👂  Listening — just speak ...\n")

    while True:
        try:
            audio = stt.get_utterance(timeout=1.0)

            # numpy arrays can't be used in boolean context 
            if audio is None:
                continue

            text = stt.transcribe(audio)
            if not text or not text.strip():
                continue

            print(f"\nYou: {text}")

            mode_key = mode_lib.detect(text)
            print(f"  {mode_lib.mode_label(mode_key)}", end="", flush=True)
            print()

            # 1. Mute microphone before generating a response
            stt.mute()
            
            # 2. Call the LLM exactly ONCE (llm.py handles printing its own header)
            response = llm.chat(
                text       = text,
                history    = history,
                mode_key   = mode_key,
                hw_models  = hw["models"],
                speak_fn   = tts.speak,
            )
            
            # 3. Wait for the audio voice to completely finish speaking
            tts.wait()     
            
            # 4. Completely dump any background noise/audio accumulated while speaking
            try:
                while not stt.audio_queue.empty():
                    stt.audio_queue.get_nowait()
            except Exception:
                pass

            # 5. Unmute microphone and cleanly present the ready state
            stt.unmute()   
            print("\n👂  Listening — just speak ...\n")

            # 6. Save bounded conversation memory
            history.append({"role": "user",      "content": text})
            history.append({"role": "assistant", "content": response})
            history = history[-(config.MAX_HISTORY_TURNS * 2):]

        except KeyboardInterrupt:
            print("\n\n👋  Shutting down ...")
            stt.stop()
            break
        except Exception as e:
            print(f"\n[Error] {e}")
            import traceback; traceback.print_exc()
            stt.unmute()   # always restore mic safety hook


if __name__ == "__main__":
    run()