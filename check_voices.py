# check_voices.py
# Run this to see ALL voices Windows knows about,
# including your VoiceBox custom voice.
# Run with:  python check_voices.py

import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty("voices")

print()
print("═" * 60)
print("  All voices available on this Windows machine:")
print("═" * 60)

for i, v in enumerate(voices):
    print(f"\n  [{i}]  {v.name}")
    print(f"       ID  : {v.id}")
    print(f"       Lang: {getattr(v, 'languages', ['?'])}")

print()
print("═" * 60)
print()
print("Copy the exact name of your VoiceBox voice from above.")
print("Then open tts.py and set:")
print('    CUSTOM_VOICE_NAME = "paste the name here"')
print()

# Also test your custom voice if it contains "voicebox" in the name
found = [v for v in voices if "voicebox" in v.name.lower()
         or "custom" in v.name.lower()
         or "my " in v.name.lower()]

if found:
    print(f"  ✅  Possible VoiceBox voice found: {found[0].name}")
    print(f"      Testing it now ...")
    engine.setProperty("voice", found[0].id)
    engine.setProperty("rate", 175)
    engine.say("Hello, this is your custom VoiceBox voice speaking through PAIO.")
    engine.runAndWait()
else:
    print("  ⚠  No obvious VoiceBox voice auto-detected.")
    print("     Look at the list above and find yours manually.")
