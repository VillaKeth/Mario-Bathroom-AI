"""Quick script to verify expected texts match actual cleaning output."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Mock DEBUG_SOVITS to False to suppress output
import gpt_sovits_server
gpt_sovits_server.DEBUG_SOVITS = False

from gpt_sovits_server import clean_text_for_tts

TEST_PHRASES = [
    ("It's-a me, Mario!", "It's a me, Mario!"),
    ("Let's-a go!", "Let's a go!"),
    ("What's-a going on?", "What's a going on?"),
    ("Mamma mia, that's-a funny!", "That's a funny!"),
    ("Nice to meet-a you!", "Nice to meet a you!"),
    ("Take-a care!", "Take a care!"),
    ("This-a soap dispenser is very modern!", "This a soap dispenser is very modern!"),
    ("Not like-a my castle pipes!", "Not like a my castle pipes!"),
    ("Time flies-a when you're having fun!", "Time flies a when you're having fun!"),
    ("Good-a time to recharge!", "Good a time to recharge!"),
    ("The party is great, everyone is having fun!", "The party is great, everyone is having fun!"),
    ("Bowser is mean, but I still win!", "Bowzer is mean, but I still win!"),
    ("One coin, two coins, three coins!", "One coin, two coins, three coins!"),
    ("The mushroom kingdom, what a place!", "The mushroom kingdom, what a place!"),
    ("Bathroom breaks are very important!", "Bathroom breaks, very important!"),
    ("Ka-ching ka-ching! Mine cart madness!", "Oh, minecart madness!"),
    ("WOO-HA-HEEEEEEEE! I'm Mario!", "Oh, hah hey! I'm Mario!"),
    ("WAHOO! That was amazing!", "Oh, that was amazing!"),
    ("Bowser is going DOWN!", "Bowzer is going Down!"),
    ("I found a Mushroom and a Star!", "I found a Mushroom and a Star!"),
    ("Mama Mia, that's incredible!", "Mama Mia that's incredible!"),
    ("SUCTION TO THE BEAT! Plunge and boogie!", "Suction To The Beat! Plunge and boogie!"),
    ("The POWER of the FIRE FLOWER!", "The Power of the Fire Flower!"),
    ("Hmm, let me think!", "Hmm, let me think!"),
    ("Hmmm, I wonder what Luigi is doing...", "Hmm, I wonder what Luigi is doing"),
    ("Umm, I'm not sure about that.", "Um, I'm not sure about that."),
    ("Uhhh, maybe try again?", "Uh, maybe try again?"),
    ("Ahhh, that feels nice!", "Ah, that feels nice!"),
    ("Ohh, what a surprise!", "Oh, what a surprise!"),
    ("Brrrr, it's cold in here!", "It's cold in here!"),
    ("Shh, Bowser might hear us!", "Bowzer might hear us!"),
    ("Wahoo! Here we go!", "Oh, here we go!"),
    ("Okie dokie!", "Oh, okey dokey!"),
    ("I wonder if Chain Chomps count as pets? They're very bitey!", "I wonder if Chain Chomps count as pets? They're very biting!"),
    ("Pfft, that's nothing!", "Oh, that's nothing!"),
    ("Da da daa! Level complete!", "Well, level complete!"),
    ("Boing boing boing! Jump jump jump!", "Oh, jump jump jump!"),
    ("Whoosh! There goes the fireball!", "There goes the fireball!"),
    ("Splish splash, bathroom fun!", "Oh, bathroom fun!"),
    ("Tick tock tick tock, hurry up!", "Oh, hurry up!"),
    ("Boom! Another Goomba defeated!", "Another Gumba defeated!"),
    ("The mushroom kingdom.. da-da-daa!", "Oh, the mushroom kingdom"),
    ("Super Star Power!", "Super Star Power!"),
    ("I give it a 10/10!", "I give it a ten out of ten!"),
    ("The score is 100 & counting!", "The score is one hundred and counting!"),
    ("Email me at mario@mushroom.kingdom", "Email me at mario at mushroom.kingdom"),
    ("It's 50% off on mushrooms!", "It's fifty percent off on mushrooms!"),
    ("Afternoon break! Good time to recharge!", "Afternoon break! Good time to recharge!"),
    ("Hello there! How are you doing today?", "Hello there! How are you doing today?"),
    ("Line one. Line two. Line three.", "Line one, Line two, Line three."),
    ("YAAAAYYYY! I won!", "Oh, yay! I won!"),
    ("Nooooooo! Bowser got me!", "No! Bowzer got me!"),
    ("Wahoooooo! Let's go!", "Oh, let's go!"),
    ("BAAAAAALLS of fire!", "Oh, balls of fire!"),
    ("Sooooo excited right now!", "So excited right now!"),
    ("Heeeeelp! Someone help!", "Help! Someone help!"),
    ("What?! You defeated Bowser?!", "What?! You defeated Bowzer?!"),
    ("Amazing... just... amazing...", "Oh, amazing, just, amazing"),
    ("Wait... really?!", "Well, wait, really?!"),
    ("HA HA HA! That's hilarious!", "Ha ha ha! That's hilarious!"),
    ("Can you hear me?", "Can you hear me?"),
    ("The answer is: Mushroom!", "The answer is: Mushroom!"),
    ('"quoted" speech is fun!', "quoted speech is fun!"),
    ("Welcome to the most amazing bathroom party in the entire Mushroom Kingdom!", "Welcome to the most amazing bathroom party in the entire Mushroom Kingdom!"),
    ("I once traveled through eight worlds, defeated countless Goombas, and saved the princess - all before breakfast!", "I once traveled through eight worlds, defeated countless Gumbas, and saved the princess, all before breakfast!"),
    ("The party is in full swing! What a night!", "The party is in full swing! What a night!"),
    ("Evening bathroom visits are the best! The lighting is so much more dramatic!", "Evening bathroom visits are the best! The lighting is so much more dramatic!"),
    ("Afternoon already! Time flies when you're having fun!", "Afternoon already! Time flies when you're having fun!"),
    ("I bet Toad would appreciate this tile pattern. Very mushroom-y!", "I bet Toad would appreciate this tile pattern, Very mushroom y!"),
    ("This bathroom is cleaner than Bowser's castle!", "This bathroom is cleaner than Bowzer's castle!"),
    ("Did you know? In Super Mario 64, I can do over 100 different jumps!", "Did you know? In Super Mario sixty four, I can do over one hundred different jumps!"),
    ("I wonder what Luigi is doing right now...", "I wonder what Luigi is doing right now"),
    ("Mama mia, the acoustics in here are perfect for singing!", "Mama mia, the acoustics in here are perfect for singing!"),
]

mismatches = 0
for i, (raw, expected) in enumerate(TEST_PHRASES, 1):
    actual = clean_text_for_tts(raw)
    if actual != expected:
        mismatches += 1
        print(f"  #{i}: MISMATCH")
        print(f"    Expected: '{expected}'")
        print(f"    Actual:   '{actual}'")
    else:
        print(f"  #{i}: OK | {actual[:60]}")

print(f"\n{mismatches} mismatches out of {len(TEST_PHRASES)}")
