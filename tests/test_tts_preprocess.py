"""Quick test for TTS text preprocessing fixes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from pose_analyzer import analyze_text

tests = [
    "It's-a me, Mario!",
    "*jumps* Wahoo! Let's-a GO!",
    "WOOHOOO! Mama mia! That's-a the spirit! Woooooohoo!",
    "Yippee! WHA-LOL-WHOA-OHH-A-HAH-HA-HOH-HOOO! You want me to do what?!",
    "\u266a Turn up the music, turn down the Bowser! Tonight we're-a free! \u266a",
    "Morning bathroom visit! A great way to start-a the day!",
    "Score \u2014 You: 0 | Mario: 0",
    "Here we go! Princess Peach! *sighs dreamily* She's-a so wonderful!",
    "Don't-a worry! I'm-a here to help!",
]

for t in tests:
    r = analyze_text(t)
    print(f"DISPLAY: {r['display_text']}")
    print(f"TTS:     {r['tts_text']}")
    print()
