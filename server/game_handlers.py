"""Game handler module — all interactive game logic for Mario AI.

Extracted from main.py to keep the server module focused on WebSocket handling.
Each game mode has its content data, start logic, and input handling here.
"""

import json
import logging
import os
import random
import time
from emotions import Emotion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid game names — used for state validation
# ---------------------------------------------------------------------------

VALID_GAMES = frozenset({
    "simon_says", "twenty_questions", "truth_or_dare", "riddles",
    "word_chain", "karaoke", "rapid_fire", "would_you_rather",
    "rock_paper_scissors", "hangman", "hot_takes", "never_have_i_ever",
    "mario_trivia", "name_that_character", "bathroom_dare",
    "story_builder", "wyr_mario",
})


# ---------------------------------------------------------------------------
# Jacob Birthday Trivia Loader
# ---------------------------------------------------------------------------

_jacob_trivia_cache = None

def _load_jacob_trivia():
    """Load Jacob-specific birthday trivia questions."""
    global _jacob_trivia_cache
    if _jacob_trivia_cache is not None:
        return _jacob_trivia_cache
    try:
        trivia_path = os.path.join(os.path.dirname(__file__), "data", "jacob_trivia.json")
        with open(trivia_path) as f:
            _jacob_trivia_cache = json.load(f)
        return _jacob_trivia_cache
    except Exception:
        return []


def _mix_jacob_trivia(mario_questions, count=5):
    """Mix Jacob birthday trivia into Mario trivia (1 Jacob per ~3 Mario).

    Returns a list of *count* questions with Jacob questions tagged
    ``is_birthday_special = True`` for bonus-point handling.
    """
    jacob_qs = _load_jacob_trivia()
    if not jacob_qs:
        return mario_questions[:count]

    jacob_pool = list(jacob_qs)
    random.shuffle(jacob_pool)
    # Target: ~1 Jacob question per 3 regular questions
    jacob_count = max(1, count // 3)
    mario_count = count - jacob_count

    mario_pool = list(mario_questions)
    random.shuffle(mario_pool)

    # Convert Jacob questions to the same format as Mario questions + tag them
    selected_jacob = []
    for jq in jacob_pool[:jacob_count]:
        selected_jacob.append({
            "q": f"BIRTHDAY SPECIAL! {jq['question']}  (Options: {', '.join(jq['options'])})",
            "a": [jq["answer"]],
            "accept": jq["accept"],
            "fun_fact": jq.get("fun_fact", ""),
            "is_birthday_special": True,
        })

    combined = mario_pool[:mario_count] + selected_jacob
    random.shuffle(combined)
    return combined


# ---------------------------------------------------------------------------
# Game Content Data
# ---------------------------------------------------------------------------

SIMON_ACTIONS = [
    "touch your nose",
    "clap your hands",
    "do a little jump",
    "wave at the mirror",
    "strike a pose",
    "make a funny face",
    "spin around",
    "snap your fingers",
    "pat your head",
    "do a thumbs up",
    "flex your muscles",
    "blow a kiss to the mirror",
    "do a little squat",
    "wiggle your fingers",
    "tap your feet really fast",
    "do your best Mario fist-pump",
    "pretend to throw a fireball",
    "do the floss dance",
    "moonwalk in place",
    "air guitar for 3 seconds",
    "put your hands on your hips like a superhero",
    "do a royal wave like Princess Peach",
    "stomp the ground like a Thwomp",
    "pretend to eat a mushroom and grow big",
    "do a slow-motion jump",
    "salute yourself in the mirror",
    "clap above your head",
    "do jazz hands",
    "shimmy your shoulders",
    "pretend to pull a star out of the air",
    "wag your finger like you're scolding a Goomba",
]

TWENTY_Q_THINGS = [
    {"answer": "mushroom", "category": "object", "hints": ["It grows in dark places", "Mario loves to eat these", "It makes you bigger"]},
    {"answer": "star", "category": "object", "hints": ["It makes you invincible", "It shines bright in the sky", "You chase it in every world"]},
    {"answer": "bowser", "category": "character", "hints": ["This one breathes fire", "Has a spiky shell", "Always kidnapping princesses"]},
    {"answer": "toilet", "category": "object", "hints": ["You're probably near one right now", "It has a flush mechanism", "A plumber's best friend"]},
    {"answer": "spaghetti", "category": "object", "hints": ["It's long and stringy", "Mario's favorite meal", "You twirl it on a fork"]},
    {"answer": "green pipe", "category": "object", "hints": ["You can warp through these", "Piranha plants live inside", "It's a plumber's specialty"]},
    {"answer": "yoshi", "category": "character", "hints": ["This one has a very long tongue", "Comes in many colors", "Mario rides on its back"]},
    {"answer": "coin", "category": "object", "hints": ["You need 100 for something special", "Makes a 'bling' sound", "It's shiny and golden"]},
    {"answer": "princess peach", "category": "character", "hints": ["She's always getting kidnapped", "Lives in a castle", "Mario's main love interest"]},
    {"answer": "goomba", "category": "character", "hints": ["You jump on these little guys", "They walk back and forth", "They go squish when you stomp them"]},
    {"answer": "lakitu", "category": "character", "hints": ["Rides in a cloud", "Chases you with spiky eggs", "Appears in sky levels"]},
    {"answer": "donkey kong", "category": "character", "hints": ["A big ape", "Throws barrels", "Likes bananas"]},
    {"answer": "fire flower", "category": "object", "hints": ["It's hot and glowy", "Let's you shoot projectiles", "Comes from question mark blocks"]},
    {"answer": "koopa troopa", "category": "character", "hints": ["Has a hard shell", "Can be red or green", "You can flip it on its back"]},
    {"answer": "question mark block", "category": "object", "hints": ["You hit it from below", "Contains power-ups or coins", "Makes a distinctive sound"]},
    {"answer": "boss fight", "category": "place", "hints": ["Where you face the final challenge", "Usually at the end of a level", "Often against Bowser"]},
    {"answer": "lava level", "category": "place", "hints": ["It's very hot", "You need to avoid falling in", "Often red and fiery"]},
    {"answer": "toad", "category": "character", "hints": ["Has a red and white spotted cap", "Says 'It's-a me!' in a high voice", "Often a helper character"]},
    {"answer": "warp zone", "category": "place", "hints": ["Lets you skip levels", "Hidden in certain spots", "Saves you time"]},
    {"answer": "super mario", "category": "character", "hints": ["The hero of the story", "Wears red", "Says 'Wahoo!' a lot"]},
]

RIDDLES = [
    {"q": "I have keys but no locks, space but no room, and you can enter but can't go inside. What am I?", "a": "keyboard", "hints": ["You use it every day", "It has letters and numbers", "You type on it"]},
    {"q": "I go through towns and over hills but never move. What am I?", "a": "road", "hints": ["Cars drive on me", "I can be paved or dirt", "I connect places"]},
    {"q": "I can fly without wings, cry without eyes. Wherever I go, darkness follows. What am I?", "a": "cloud", "hints": ["I'm in the sky", "I bring rain", "I'm fluffy and white"]},
    {"q": "I have a head and a tail but no body. What am I?", "a": "coin", "hints": ["Mario loves me", "I'm shiny", "Flip me to decide"]},
    {"q": "The more you take, the more you leave behind. What am I?", "a": "footsteps", "hints": ["You make them when you walk", "They can be big or small", "They're on the ground"]},
    {"q": "I speak without a mouth and hear without ears. I have no body but come alive with wind. What am I?", "a": "echo", "hints": ["Bathrooms are great for this", "I repeat what you say", "Mountains have me too"]},
    {"q": "What has 88 keys but can't open a single door?", "a": "piano", "hints": ["It makes music", "It has black and white keys", "You play it sitting down"]},
    {"q": "I'm tall when I'm young and short when I'm old. What am I?", "a": "candle", "hints": ["I give light", "I have a flame", "Birthday cakes have many of me"]},
    {"q": "What gets wetter the more it dries?", "a": "towel", "hints": ["You use one after a shower", "It hangs in the bathroom", "It absorbs water"]},
    {"q": "I have cities but no houses, mountains but no trees, water but no fish. What am I?", "a": "map", "hints": ["You use me to navigate", "I show locations", "I can be folded"]},
    {"q": "What has a face and two hands but no arms or legs?", "a": "clock", "hints": ["It tells you something", "I tick and tock", "You wind me up or use batteries"]},
    {"q": "I'm light as a feather but you can't hold me for more than a few minutes. What am I?", "a": "breath", "hints": ["You do it without thinking", "You need it to live", "You can see it in cold air"]},
    {"q": "The more you have, the less you see. What am I?", "a": "darkness", "hints": ["I'm the opposite of light", "Night is full of me", "You see less with more of me"]},
    {"q": "I have a neck but no head. What am I?", "a": "bottle", "hints": ["You drink from me", "I can be made of glass", "I hold liquids"]},
    {"q": "What has three eyes but can't see?", "a": "traffic light", "hints": ["I'm on the street", "I'm red, yellow, and green", "I tell cars when to go"]},
    {"q": "What comes once a year but twice a week?", "a": "e", "hints": ["It's a letter", "It appears in both words", "It's the most common letter"]},
    {"q": "I run but never walk, I have a bed but never sleep. What am I?", "a": "river", "hints": ["I flow downhill", "Fish live in me", "I'm made of water"]},
    {"q": "What has a spine but no bones?", "a": "book", "hints": ["I have pages", "You read me", "I can teach you things"]},
    {"q": "I am always hungry, the more you feed me the bigger I grow, the more you starve me the smaller I become. What am I?", "a": "fire", "hints": ["I give warmth", "I consume fuel", "I produce light"]},
    {"q": "What invention allows you to look right through walls?", "a": "window", "hints": ["I'm made of glass", "You can open me", "I let in light"]},
    {"q": "I have cities but no houses, forests but no trees, and water but no fish. What am I?", "a": "map", "hints": ["You can fold me up", "I help you find your way", "I show the whole world"]},
    {"q": "I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. What am I?", "a": "echo", "hints": ["You hear me in canyons", "I repeat what you say", "I'm just a sound"]},
    {"q": "The more you take, the more you leave behind. What am I?", "a": "footsteps", "hints": ["You make me when you walk", "I can be found in sand", "I show where you've been"]},
    {"q": "I can be cracked, I can be made, I can be told, I can be played. What am I?", "a": "joke", "hints": ["I make people laugh", "Comedians tell me", "I have a punchline"]},
    {"q": "What has a ring but no finger?", "a": "telephone", "hints": ["You answer me", "I help you talk to people", "I make a ringing sound"]},
    {"q": "I go all around the world but never leave the corner. What am I?", "a": "stamp", "hints": ["I'm small and sticky", "I go on envelopes", "You buy me at a post office"]},
    {"q": "What gets wetter the more it dries?", "a": "towel", "hints": ["You use me after a shower", "I hang in the bathroom", "I absorb water"]},
    {"q": "What can you hold in your right hand but never in your left?", "a": "left hand", "hints": ["Everyone has one", "It's attached to you", "Think about your own body"]},
    {"q": "I have legs but never walk. What am I?", "a": "table", "hints": ["You eat on me", "I'm a piece of furniture", "I usually have four of them"]},
    {"q": "What building has the most stories?", "a": "library", "hints": ["It's full of books", "You can borrow from here", "Knowledge lives here"]},
]

STARTER_WORDS = [
    "mario", "party", "castle", "mushroom", "adventure", "bathroom", "princess", "galaxy",
    "fireball", "plumber", "spaghetti", "koopa", "rainbow", "bowser", "wahoo", "goomba",
    "toilet", "champion",
]

KARAOKE_SONGS = [
    {"title": "Jump Up, Super Star!", "lyrics": "Here we go, off the rails! Don't you know it's time to raise our sails? It's FREEDOM like you never knew!"},
    {"title": "Do the Mario!", "lyrics": "Swing your arms from side to side! Come on, it's time to go, do the Mario! Take one step and then again!"},
    {"title": "Bowser's Fury Rap", "lyrics": "I'm-a Mario, red hat hero! Stomping Goombas, coins from zero! Jumping high and running fast! Every level is a BLAST!"},
    {"title": "Bathroom Ballad", "lyrics": "Oh this bathroom, it's-a so fine! Every tile perfectly aligned! The soap dispenser, what a treat! This party bathroom can't be beat!"},
    {"title": "Plumber's Anthem", "lyrics": "We're the plumbers, here we go! Through the pipes from high to low! Fixing leaks and saving queens! Living out our plumber dreams!"},
    {"title": "Rainbow Road Blues", "lyrics": "I'm driving on a rainbow, no guardrails in sight! One wrong turn and I'm falling through the night! But I keep on racing, that's the Mario way!"},
    {"title": "Mushroom Kingdom Party", "lyrics": "Everybody gather 'round, it's a party night! Toads are dancing, stars are shining bright! From World One to World Eight, we celebrate!"},
    {"title": "Koopa Beach Bop", "lyrics": "Sunshine on the sand, shells upon the shore! Koopa Troopas surfing, who could ask for more? Grab a coconut and dance the night away!"},
    {"title": "Warp Pipe Serenade", "lyrics": "Down the pipe I go, where I end up no one knows! Could be underground, could be in the clouds! Every pipe's a new adventure!"},
    {"title": "Luigi's Lament", "lyrics": "Always player two, always in the green! The tallest brother that you've ever seen! One day I'll be the star, just you wait and see!"},
    {"title": "Star Power Shuffle", "lyrics": "I got the star, I'm invincible now! Nothing can stop me, nothing can slow me down! Flashing rainbow colors, feeling like a king!"},
    {"title": "Toad's Party Rock", "lyrics": "Welcome to the Mushroom House, pick a chest! Will you get the star or just the rest? Left or right or center, take your chance tonight!"},
    {"title": "Yoshi's Island Jam", "lyrics": "Flutter jump high, flutter jump low! Baby Mario on my back, here we go! Eggs for throwing, tongues for catching, Yoshi's on patrol!"},
    {"title": "Chain Chomp Cha-Cha", "lyrics": "Bark bark bark, I'm chained to a stake! But when I break free, watch out for goodness sake! Chomping to the left and chomping to the right!"},
    {"title": "Princess Power Ballad", "lyrics": "They say wait in the castle, wait to be saved! But I've got a frying pan and I am BRAVE! Peach is in the fight now, watch her take the crown!"},
    {"title": "Bob-omb Battlefield Beat", "lyrics": "Tick tick tick, I'm about to blow! Three two one and away I go! Explosive personality, that's my claim to fame!"},
    {"title": "Ghost House Groove", "lyrics": "Boo! Ha ha, did I scare you? Turn around, I'll disappear from view! Dancing in the darkness, floating through the walls!"},
    {"title": "Underwater Theme Remix", "lyrics": "Blooper swimming left, Cheep Cheep swimming right! Deep beneath the ocean, everything's delight! Bubbles floating upward, coins are everywhere!"},
    {"title": "Bowser's Castle Metal", "lyrics": "FIRE and LAVA, bridges falling down! I'm the KING of Koopas, wearing the crown! Mario thinks he's tough? HA! I'll show him who's the boss!"},
    {"title": "Party All Night Long", "lyrics": "Ten turns, twenty turns, we're still going strong! Rolling dice and stealing stars, nothing can go wrong! Wait, who stole MY star?! This friendship might not last!"},
]

RAPID_FIRE_QUESTIONS = [
    {"q": "What color is Mario's hat?", "a": "red"},
    {"q": "Who is Mario's brother?", "a": "luigi"},
    {"q": "What's the princess's name?", "a": "peach"},
    {"q": "What are the turtle enemies called?", "a": "koopa"},
    {"q": "What gives Mario fire powers?", "a": "fire flower"},
    {"q": "What's the dinosaur Mario rides?", "a": "yoshi"},
    {"q": "How many coins for an extra life?", "a": "100"},
    {"q": "What's the ghost enemy called?", "a": "boo"},
    {"q": "What kingdom does Peach rule?", "a": "mushroom"},
    {"q": "What's the star power-up do?", "a": "invincible"},
    {"q": "Who kidnaps Princess Peach?", "a": "bowser"},
    {"q": "What's the little mushroom guy's name?", "a": "toad"},
    {"q": "What color is Luigi's hat?", "a": "green"},
    {"q": "What do you hit from below?", "a": "block"},
    {"q": "What planet is Galaxy set on?", "a": "space"},
    {"q": "What's Mario's last name?", "a": "mario"},
    {"q": "What's Bowser's kid's name?", "a": "bowser jr"},
    {"q": "What enemy walks off ledges?", "a": "goomba"},
    {"q": "What warp system does Mario use?", "a": "pipe"},
    {"q": "What's the racing game called?", "a": "mario kart"},
    {"q": "What does the Super Leaf give Mario?", "a": "raccoon tail"},
    {"q": "What's Bowser's castle surrounded by?", "a": "lava"},
    {"q": "What color are warp pipes?", "a": "green"},
    {"q": "What item makes Mario giant?", "a": "mega mushroom"},
    {"q": "Who is Mario's evil twin?", "a": "wario"},
    {"q": "What does Mario throw in SMB2?", "a": "vegetables"},
    {"q": "What's the name of Peach's steward?", "a": "toadsworth"},
    {"q": "What world has the classic flagpole?", "a": "1-1"},
    {"q": "What power-up makes Mario small?", "a": "poison mushroom"},
    {"q": "How many players in co-op NSMB Wii?", "a": "4"},
]

TRUTH_QUESTIONS = [
    "What's the most embarrassing thing that happened to you at a party?",
    "What's your guilty pleasure song that you dance to alone?",
    "Have you ever talked to yourself in the mirror? What did you say?",
    "What's the longest you've spent in a bathroom and WHY?",
    "Who at this party would you trade lives with for a day?",
    "What's the weirdest thing in your phone's search history?",
    "If you could only eat one food forever, what would it be?",
    "What's a secret talent nobody here knows about?",
    "Have you ever pretended to be on the phone to avoid someone?",
    "What's the most Mario-like thing you've ever done?",
    "What's the strangest thing you've ever done when nobody was watching?",
    "Have you ever laughed so hard something came out of your nose?",
    "What's the most ridiculous lie you've told that someone believed?",
    "What's the worst text you've ever sent to the wrong person?",
    "Have you ever used a fake name? What was it?",
    "What's the most embarrassing thing in your camera roll right now?",
    "Have you ever walked into a glass door in public?",
    "What's the weirdest food combination you actually enjoy?",
    "Have you ever blamed a fart on someone else? Who?",
    "What's something you've done at a party that you'd never admit sober?",
    "What song do you secretly know ALL the words to?",
    "Have you ever pretended to know someone you definitely didn't recognize?",
    "What's the pettiest reason you've ever stopped talking to someone?",
    "If this bathroom could talk, what would it say about you right now?",
    "What's your most irrational fear that you're embarrassed about?",
]

DARES = [
    "Do your best Mario impression RIGHT NOW! Let's-a hear it!",
    "Sing the Mario theme song to the next person who walks by!",
    "Take a selfie with me right now and show it to someone at the party!",
    "Do 5 jumping jacks right here in the bathroom! Wahoo!",
    "Talk in an Italian accent for the next 2 minutes!",
    "Strike your best superhero pose in the mirror!",
    "Make up a rap about this bathroom! I want to hear it!",
    "Do your best Bowser roar! RAAAWR!",
    "Compliment the next person you see at the party!",
    "Do the Mario dance — swing your arms from side to side!",
    "Do your best Luigi scared-face impression! Mamma mia!",
    "Beatbox the underground theme for 10 seconds! Dun dun dun!",
    "Tell the next person you see that MARIO sent you with a message!",
    "Do your best Toad impression — make your voice REALLY high!",
    "Act like you just got a star power-up — run in place and be INVINCIBLE!",
    "Make a dramatic speech to the mirror about how awesome this party is!",
    "Do your best victory dance like you just won a Mario Kart race!",
    "Sing Happy Birthday but in Mario's voice! It's-a birthday time!",
    "Walk out of this bathroom doing the Mario jump — fist in the air!",
    "Tell someone at the party your name is Luigi and you're lost!",
]

WOULD_YOU_RATHER = [
    {"a": "Have unlimited mushrooms", "b": "Have unlimited fire flowers"},
    {"a": "Live in the Mushroom Kingdom", "b": "Live in Bowser's Castle"},
    {"a": "Be able to breathe underwater", "b": "Be able to fly with a cape"},
    {"a": "Fight 100 Goombas at once", "b": "Fight 1 giant Bowser"},
    {"a": "Only eat spaghetti forever", "b": "Only eat mushrooms forever"},
    {"a": "Have Yoshi as a pet", "b": "Have a Chain Chomp as a guard dog"},
    {"a": "Live in a world without pipes", "b": "Live in a world without power-ups"},
    {"a": "Be best friends with Luigi", "b": "Be best friends with Toad"},
    {"a": "Race on Rainbow Road forever", "b": "Never play Mario Kart again"},
    {"a": "Have invincibility star power all day", "b": "Be able to ground pound anything"},
    {"a": "Swim through all water levels", "b": "Run through all lava levels"},
    {"a": "Have a Bullet Bill launcher", "b": "Have a Bob-omb factory"},
    {"a": "Be a plumber in real life", "b": "Be a princess in the Mushroom Kingdom"},
    {"a": "Talk like Mario forever", "b": "Jump like Mario but never talk"},
    {"a": "Know every warp zone", "b": "Have max coins at all times"},
    {"a": "Party with Waluigi", "b": "Adventure with Wario"},
    {"a": "Ride a Bullet Bill to work", "b": "Take a Warp Pipe to school"},
    {"a": "Have Lakitu follow you with a camera", "b": "Have a Boo follow you invisibly"},
    {"a": "Live in World 1-1 forever", "b": "Explore a new world every day"},
    {"a": "Be the best at Mario Kart", "b": "Be the best at Super Smash Bros"},
]

RPS_WIN_REACTIONS = [
    "WAHOO! Mario WINS! My fist is-a stronger than your scissors! Ha ha!",
    "YES! Victory for the plumber! You can't beat-a these hands!",
    "Too easy! Mario is the CHAMPION of Rock Paper Scissors! Mama mia!",
    "HA! I saw that coming from a MILE away! Better luck next time!",
    "Another win for Mario! I must have a star power-up! Wahoo!",
    "You thought you could beat-a ME? I'm-a SUPER Mario! Hee hee!",
    "That's what happens when you challenge a plumber! We're-a TOUGH!",
    "YES YES YES! Mario is-a on FIRE! Not even Bowser could beat me!",
    "I crushed it! Like a Thwomp from above! BOOM! Ha ha!",
    "Too slow! Mario's reflexes are-a LEGENDARY! Wahoo!",
    "Mario STRIKES again! I could do this ALL night! Let's-a go!",
    "HA HA! My plumber hands are-a UNBEATABLE! You never stood a chance!",
    "It's like I had a Star Power-up for my BRAIN! Another WIN for Mario!",
    "Did you see THAT?! Even Toad is cheering for me! WAHOO!",
    "That's THREE stars for Mario! I'm-a on a ROLL tonight! Hee hee!",
]

RPS_LOSE_REACTIONS = [
    "MAMA MIA! You got me! But the game's not over yet!",
    "Ooof! Lucky shot! Mario will come back-a STRONGER!",
    "No no no! That was-a just a warm up! Watch out next round!",
    "You win THIS round, but Mario NEVER gives up! Let's-a go!",
    "Impossible! You must have a mushroom power-up or something!",
    "GAH! Even Bowser doesn't beat me this badly! Rematch!",
    "Okay okay, you got me! But can you do it AGAIN? I doubt it!",
    "That was-a FLUKE! Mario demands a do-over! Mama mia!",
    "You're tougher than a Dry Bones! I'll get you next time!",
    "Fine, you win! But I'm-a just getting warmed up! Watch out!",
    "WHAT?! Did someone give you a cheat code?! That's-a not fair!",
    "You got LUCKY! Mario's hand slipped! That's my story and I'm-a sticking to it!",
    "Okay, I admit it — that was GOOD! But don't let it go to your head!",
    "Bowser would be LAUGHING at me right now! Quick, let's go again!",
    "My fingers are-a cold from all this bathroom air! That's my excuse! Rematch!",
]

RPS_TIE_REACTIONS = [
    "A TIE?! Great minds think-a alike! Or maybe we're BOTH confused!",
    "Same move! Are you reading my mind?! That's-a spooky!",
    "HA! We tied! It's like looking in a mirror! Mama mia!",
    "A draw! You're-a as clever as Mario! Almost! He he!",
    "SNAP! Same choice! This is-a getting INTENSE!",
    "Tied up! We're like Mario and Luigi — always in sync! Wahoo!",
    "No winner?! The universe couldn't decide! Let's-a go again!",
    "A TIE! Even the stars don't know who's better! One more!",
    "Same pick! You've got-a the Mario instinct! Impressive!",
    "Draw! It's like we share the same brain! Creepy! Ha ha!",
    "ANOTHER tie?! Are you copying me or am I copying YOU? Mama mia!",
    "We MATCHED again! It's like we're controlled by the same player! Spooky!",
    "Same thing! This is-a more dramatic than a Mario Party final turn!",
    "A DRAW! We're-a perfectly matched! This calls for a TIEBREAKER!",
    "Identical! We must be connected by a warp pipe or something! Ha ha!",
]

HANGMAN_WORDS = [
    "mushroom", "piranha", "bowser", "lakitu", "goomba",
    "princess", "fireball", "starman", "yoshi", "koopa",
    "toadstool", "wario", "waluigi", "thwomp", "bobomb",
    "rosalina", "daisy", "bullet", "banzai", "blooper",
    "kingdom", "odyssey", "galaxy", "castle", "spaghetti",
]

HOT_TAKES = [
    "Waluigi deserves his own game!",
    "The water levels are the BEST levels!",
    "Luigi is BETTER than Mario!",
    "Bowser is actually a GOOD dad!",
    "Toad is the REAL hero of the Mushroom Kingdom!",
    "Mario Kart friendships don't EXIST — it's every racer for themselves!",
    "The blue shell is the GREATEST item in Mario Kart!",
    "Yoshi deserves an APOLOGY from Mario for all those sacrificial jumps!",
    "Princess Peach LETS herself get kidnapped for the adventure!",
    "Wario is more honest than Mario — at least he ADMITS he's greedy!",
    "The original Super Mario Bros is STILL the best Mario game!",
    "Mario's mustache is overrated — he'd look BETTER clean-shaven!",
    "Bowser Jr is MORE intimidating than Bowser!",
    "Rainbow Road is the most FUN track in Mario Kart!",
    "Goombas are just MISUNDERSTOOD — they're not evil!",
    "Chain Chomps would make AMAZING pets!",
    "Mario should have stayed a CARPENTER, not become a plumber!",
    "The Star power-up theme is the CATCHIEST song ever written!",
    "Dry Bones is the COOLEST enemy in the whole series!",
    "Lakitu should QUIT throwing Spinies and become a full-time cameraman!",
    "Spaghetti is a BETTER power-up than any mushroom!",
    "Boo is the most ADORABLE villain in gaming history!",
    "Donkey Kong should be in MORE Mario games!",
    "The cape feather is BETTER than the Tanooki suit!",
    "Mario Party has RUINED more friendships than Monopoly!",
    "Toadette is the most UNDERRATED character in the franchise!",
    "Piranha Plants should be in EVERY fighting game!",
    "The coin sound effect is the most SATISFYING sound in gaming!",
    "Baby Mario games are BETTER than adult Mario games!",
    "Mario would LOSE in a fair fight against Sonic!",
    "Waluigi DESERVES his own game more than ANY other Nintendo character!",
    "The underwater levels are actually the BEST levels in every Mario game!",
    "Rosalina is a BETTER princess than Peach and it's NOT even close!",
    "Mario Party mini-games are MORE competitive than actual esports!",
    "The Tanooki suit should be Mario's DEFAULT outfit in every game!",
    "Bowser is a BETTER dad than most video game characters!",
    "Paper Mario: The Thousand-Year Door is the GREATEST RPG ever made!",
    "Luigi's Mansion is SCARIER than most actual horror games!",
    "Mario Kart Double Dash is the PEAK of the Mario Kart series!",
    "Yoshi's Island has BETTER graphics than any modern indie game!",
]

# ---------------------------------------------------------------------------
# NEW MINI-GAME CONTENT — Mario Trivia, Name That Character, Bathroom Dares,
# Story Builder, enhanced Would-You-Rather
# ---------------------------------------------------------------------------

MARIO_TRIVIA_QUESTIONS = [
    {"q": "In what year was the original Super Mario Bros. released?", "a": ["1985"], "accept": ["85", "1985", "nineteen eighty five"]},
    {"q": "What is the name of Bowser's flying ship?", "a": ["airship"], "accept": ["airship", "koopa cruiser", "doomship"]},
    {"q": "How many worlds are in Super Mario Bros.?", "a": ["8"], "accept": ["8", "eight"]},
    {"q": "What power-up lets Mario fly in Super Mario World?", "a": ["cape feather"], "accept": ["cape", "feather", "cape feather"]},
    {"q": "What is Princess Peach's original English name?", "a": ["toadstool"], "accept": ["toadstool", "princess toadstool"]},
    {"q": "What is the name of Mario's dinosaur companion?", "a": ["yoshi"], "accept": ["yoshi"]},
    {"q": "In Super Mario 64, how many Power Stars can you collect?", "a": ["120"], "accept": ["120", "one hundred twenty", "one hundred and twenty"]},
    {"q": "What color is Waluigi's hat?", "a": ["purple"], "accept": ["purple", "violet"]},
    {"q": "What is the name of the final boss in Super Mario Galaxy?", "a": ["bowser"], "accept": ["bowser", "king bowser"]},
    {"q": "Which Mario game introduced the wall jump?", "a": ["super mario 64"], "accept": ["64", "mario 64", "super mario 64"]},
    {"q": "What animal is Donkey Kong?", "a": ["gorilla"], "accept": ["gorilla", "ape", "monkey"]},
    {"q": "In Mario Kart, what item targets the player in first place?", "a": ["blue shell"], "accept": ["blue shell", "spiny shell", "blue"]},
    {"q": "What is the name of Bowser's son?", "a": ["bowser jr"], "accept": ["bowser jr", "bowser junior", "jr"]},
    {"q": "How many Koopalings are there?", "a": ["7"], "accept": ["7", "seven"]},
    {"q": "What is the name of the ghost king in Luigi's Mansion?", "a": ["king boo"], "accept": ["king boo", "boo"]},
    {"q": "What shape is the power-up block in most Mario games?", "a": ["question mark block"], "accept": ["question", "question mark", "block", "cube", "square"]},
    {"q": "What profession was Mario before plumbing?", "a": ["carpenter"], "accept": ["carpenter"]},
    {"q": "What is the name of the star guardian in Super Mario Galaxy?", "a": ["rosalina"], "accept": ["rosalina"]},
    {"q": "In Super Mario Odyssey, what is Mario's hat companion called?", "a": ["cappy"], "accept": ["cappy"]},
    {"q": "What city has a festival in Super Mario Odyssey?", "a": ["new donk city"], "accept": ["new donk", "new donk city", "donk city"]},
    {"q": "What game features the Isle Delfino setting?", "a": ["super mario sunshine"], "accept": ["sunshine", "mario sunshine", "super mario sunshine"]},
    {"q": "What is Toad's full name?", "a": ["toad"], "accept": ["toad", "kinopio"]},
    {"q": "Which princess rules Sarasaland?", "a": ["daisy"], "accept": ["daisy", "princess daisy"]},
    {"q": "What enemy hides in pipes and bites Mario?", "a": ["piranha plant"], "accept": ["piranha", "piranha plant"]},
    {"q": "What is the name of the chain enemy attached to a post?", "a": ["chain chomp"], "accept": ["chain chomp", "chomp"]},
    # --- Mario Kart questions ---
    {"q": "What is the name of the rainbow-colored track in Mario Kart?", "a": ["rainbow road"], "accept": ["rainbow road", "rainbow"]},
    {"q": "What item gives you a speed boost in Mario Kart?", "a": ["mushroom"], "accept": ["mushroom", "boost mushroom", "super mushroom"]},
    {"q": "Which Mario Kart game introduced anti-gravity racing?", "a": ["mario kart 8"], "accept": ["mario kart 8", "mk8", "8"]},
    {"q": "What is the name of the Lakitu who holds the traffic light at the start of Mario Kart?", "a": ["lakitu"], "accept": ["lakitu"]},
    {"q": "In Mario Kart, what does the lightning bolt item do?", "a": ["shrink"], "accept": ["shrink", "shrinks everyone", "makes everyone small", "shrinks"]},
    # --- Paper Mario questions ---
    {"q": "What is the name of Mario's first partner in Paper Mario 64?", "a": ["goombario"], "accept": ["goombario"]},
    {"q": "In Paper Mario: The Thousand-Year Door, what city is the hub world?", "a": ["rogueport"], "accept": ["rogueport", "rogue port"]},
    {"q": "What kind of attacks use flower points in Paper Mario?", "a": ["special"], "accept": ["special", "special attacks", "magic", "special moves"]},
    # --- Mario Galaxy questions ---
    {"q": "What are the small star-shaped collectibles called in Super Mario Galaxy?", "a": ["star bits"], "accept": ["star bits", "starbits"]},
    {"q": "What is the name of the hub area in Super Mario Galaxy?", "a": ["comet observatory"], "accept": ["comet observatory", "observatory"]},
    {"q": "Who are the small star creatures that Rosalina protects in Mario Galaxy?", "a": ["lumas"], "accept": ["lumas", "luma"]},
    # --- Super Mario Odyssey questions ---
    {"q": "What is the name of Mario's ship in Super Mario Odyssey?", "a": ["odyssey"], "accept": ["odyssey", "the odyssey"]},
    {"q": "In Super Mario Odyssey, what ability does Cappy give Mario?", "a": ["capture"], "accept": ["capture", "possess", "capturing enemies", "possession"]},
    {"q": "Which kingdom in Super Mario Odyssey features a realistic city with humans?", "a": ["metro kingdom"], "accept": ["metro kingdom", "metro", "new donk city"]},
    # --- Mario Party questions ---
    {"q": "How many playable characters were in the original Mario Party?", "a": ["6"], "accept": ["6", "six"]},
    {"q": "What do you collect on the board in Mario Party to win?", "a": ["stars"], "accept": ["stars", "power stars", "star"]},
    {"q": "In Mario Party, what item lets you steal a star from another player?", "a": ["boo"], "accept": ["boo", "boo bell"]},
    # --- Donkey Kong arcade questions ---
    {"q": "In the original Donkey Kong arcade game, what does Mario dodge?", "a": ["barrels"], "accept": ["barrels", "barrel"]},
    {"q": "What was Mario originally called in the Donkey Kong arcade game?", "a": ["jumpman"], "accept": ["jumpman", "jump man"]},
    {"q": "What year was the original Donkey Kong arcade game released?", "a": ["1981"], "accept": ["1981", "81"]},
    # --- Yoshi's Island questions ---
    {"q": "In Yoshi's Island, what does Yoshi turn enemies into when he eats them?", "a": ["eggs"], "accept": ["eggs", "egg"]},
    {"q": "Who is Yoshi trying to reunite Baby Mario with in Yoshi's Island?", "a": ["baby luigi"], "accept": ["baby luigi", "luigi"]},
    # --- Luigi's Mansion questions ---
    {"q": "What device does Luigi use to capture ghosts in Luigi's Mansion?", "a": ["poltergust"], "accept": ["poltergust", "poltergust 3000", "vacuum"]},
    {"q": "Who invented the Poltergust in Luigi's Mansion?", "a": ["professor e gadd"], "accept": ["professor e gadd", "e gadd", "e. gadd", "professor elvin gadd"]},
    {"q": "How many portrait ghosts are there in the original Luigi's Mansion?", "a": ["23"], "accept": ["23", "twenty three", "twenty-three"]},
]

NAME_THAT_CHARACTER = [
    {"desc": "This-a guy is green, taller than me, and afraid of ghosts!", "a": ["luigi"], "accept": ["luigi"]},
    {"desc": "She's-a got a pink dress, blonde hair, and keeps getting kidnapped by Bowser!", "a": ["peach"], "accept": ["peach", "princess peach", "toadstool"]},
    {"desc": "This little mushroom head always says 'Thank you Mario!' but the princess is NEVER there!", "a": ["toad"], "accept": ["toad"]},
    {"desc": "Big spiky turtle, breathes fire, has a SERIOUS princess obsession!", "a": ["bowser"], "accept": ["bowser", "king koopa"]},
    {"desc": "Green dinosaur, long tongue, eats EVERYTHING, and I may have... dropped him into pits!", "a": ["yoshi"], "accept": ["yoshi"]},
    {"desc": "This guy looks like me but EVIL, wears yellow and purple, and loves garlic!", "a": ["wario"], "accept": ["wario"]},
    {"desc": "Tall, skinny, purple hat, goes 'WAH!' a LOT, and never gets invited to Smash Bros!", "a": ["waluigi"], "accept": ["waluigi"]},
    {"desc": "Floats in a cloud, wears goggles, throws spiny eggs at you from above!", "a": ["lakitu"], "accept": ["lakitu"]},
    {"desc": "Round, brown, angry face, just walks in one direction, gets stomped by EVERYONE!", "a": ["goomba"], "accept": ["goomba"]},
    {"desc": "A ghost that covers its face when you look at it, but chases you when you turn around!", "a": ["boo"], "accept": ["boo", "king boo"]},
    {"desc": "She lives in space, watches over the Lumas, and has a mysterious backstory!", "a": ["rosalina"], "accept": ["rosalina"]},
    {"desc": "He's a star-shaped warrior from the legends, made of wood, shoots laser beams!", "a": ["geno"], "accept": ["geno"]},
    {"desc": "A turtle with a red or green shell — kick the shell and it goes FLYING!", "a": ["koopa troopa"], "accept": ["koopa", "koopa troopa", "koopa trooper"]},
    {"desc": "This big ape throws barrels and loves bananas more than ANYTHING!", "a": ["donkey kong"], "accept": ["donkey kong", "dk"]},
    {"desc": "She's got an orange dress, is from Sarasaland, and says 'Hi I'm Daisy!' ALL the time!", "a": ["daisy"], "accept": ["daisy", "princess daisy"]},
]

BATHROOM_DARES = [
    "I DARE you to look in the mirror and say 'I am the greatest plumber in the Mushroom Kingdom' three times!",
    "I DARE you to do 5 jumping jacks right now! Come on, WAHOO with each one!",
    "I DARE you to strike your BEST superhero pose in the mirror and hold it for 5 seconds!",
    "I DARE you to do your best Mario impression! Say 'It's-a me!' as loud as you can!",
    "I DARE you to sing 'Happy Birthday' but replace every word with 'Wahoo'!",
    "I DARE you to flex in the mirror and give yourself a compliment! You DESERVE it!",
    "I DARE you to do a little dance right now! Show me your BEST moves!",
    "I DARE you to make a funny face in the mirror and HOLD it for 10 seconds!",
    "I DARE you to pat your head and rub your tummy at the SAME TIME! It's harder than it sounds!",
    "I DARE you to do your best Bowser ROAR! RAAAWR! Scare those Goombas!",
    "I DARE you to high-five yourself in the mirror! Both hands! SLAP!",
    "I DARE you to do 3 squats while saying 'WAHOO' each time you come up!",
    "I DARE you to wink at yourself in the mirror and say 'Looking GOOD, superstar!'",
    "I DARE you to pretend you're swimming through the air like it's a water level!",
    "I DARE you to snap your fingers 10 times as fast as you can! Speed run!",
    "I DARE you to do a robot dance for 5 seconds! Beep boop beep!",
    "I DARE you to give a thumbs up to the mirror with BOTH hands and say 'Let's-a go!'",
    "I DARE you to pretend you just won a race and do a victory celebration!",
    "I DARE you to try touching your nose with your tongue! Can you do it?!",
    "I DARE you to tell the mirror a joke! Make YOURSELF laugh!",
]

STORY_STARTERS = [
    "Once upon a time, in the deepest pipe of the Mushroom Kingdom, Mario found a golden toilet that granted wishes!",
    "It was a dark and stormy night in Bowser's Castle when suddenly, a Goomba showed up wearing a TOP HAT!",
    "Luigi was minding his own business when a ghost popped out and said 'I need YOUR help to plan a PARTY!'",
    "Deep in the jungle, Donkey Kong discovered a banana that could TALK, and it said...",
    "Princess Peach was tired of being rescued, so she grabbed a fire flower and said 'MY TURN!'",
    "Toad was running the Mushroom Kingdom's first-ever pizza shop when Bowser walked in and ordered...",
    "Waluigi entered a talent show, and his secret talent was something NOBODY expected...",
    "Mario was fixing a toilet when he accidentally opened a portal to a dimension made entirely of SPAGHETTI!",
    "Yoshi ate a mystery mushroom and suddenly could speak perfect English, and the FIRST thing he said was...",
    "Bowser decided to take a vacation from being evil, so he booked a trip to...",
    "In a parallel universe, Mario was a VILLAIN and Bowser was the HERO! It all started when...",
    "A Chain Chomp broke free from its post and decided to become a PUPPY at a pet store!",
    "One day, all the Boos in the Ghost House decided to throw the SCARIEST party ever, but the DJ was...",
    "Lakitu was filming Mario's adventure when his cloud ran out of gas RIGHT over a volcano!",
    "The Toads discovered a hidden room in Peach's Castle with a machine that could turn ANYONE into...",
    "Bowser Jr. snuck into Mario's house while he was sleeping and replaced all his power-ups with...",
    "There was a rumor that World 9 existed, and the only way to get there was to flush a golden...",
    "Mario and Luigi opened a restaurant, but their ONLY customer was someone very unexpected...",
    "Wario found a magic mirror that showed his future, and in it he saw himself as the KING of...",
    "The Piranha Plants organized a union and their number one demand was...",
    "Someone left a mysterious package at Mario's door with a note that said 'DO NOT OPEN until the party!'",
    "Kamek the Magikoopa accidentally cast a spell that turned Bowser's Castle into a BOUNCE HOUSE!",
    "The bullet bills went on strike because they were tired of being shot at plumbers, so they started a...",
    "Shy Guy took off his mask for the FIRST time ever, and everyone was shocked because underneath was...",
    "At the annual Mushroom Kingdom bathroom awards, the winner for Best Plumber was NOT who everyone expected...",
]

WYR_EXTENDED = [
    {"a": "Fight 100 Goomba-sized Bowsers", "b": "Fight 1 Bowser-sized Goomba"},
    {"a": "Have a Bullet Bill as your personal taxi", "b": "Have a Lakitu cloud as your bed"},
    {"a": "Only speak in Mario's voice forever", "b": "Only walk by jumping everywhere"},
    {"a": "Live inside a question mark block", "b": "Live inside a green pipe"},
    {"a": "Be chased by an angry Chain Chomp for a day", "b": "Be stuck in a Ghost House overnight"},
    {"a": "Eat nothing but mushrooms for a month", "b": "Eat nothing but fire flowers for a week"},
    {"a": "Have Bowser as your roommate", "b": "Have Waluigi as your coworker"},
    {"a": "Ride a Thwomp to school every day", "b": "Ride a Blooper through the ocean to work"},
    {"a": "Have Bob-ombs as party poppers at your birthday", "b": "Have Boos as your hide-and-seek teammates"},
    {"a": "Win a Mario Kart Grand Prix but no one believes you", "b": "Lose but everyone thinks you won"},
    {"a": "Have the double cherry power-up forever (clone yourself)", "b": "Have the cat suit forever"},
    {"a": "Be trapped in Rainbow Road with no guardrails", "b": "Be trapped in a water level with no air bubbles"},
    {"a": "Have Toad narrate your entire life", "b": "Have Lakitu film your entire life"},
    {"a": "Play Mario Party for 100 turns", "b": "Play a single Mario Kart race on Rainbow Road that never ends"},
    {"a": "Have unlimited coins but can't spend them", "b": "Have only 1 coin but it buys anything"},
]

NHIE_PROMPTS = [
    "Never have I ever... jumped on a Goomba in real life!",
    "Never have I ever... tried to slide down a flagpole!",
    "Never have I ever... blamed lag when I lost at Mario Kart!",
    "Never have I ever... tried to talk like Mario in public!",
    "Never have I ever... attempted a triple jump in real life!",
    "Never have I ever... eaten a mushroom and expected to grow bigger!",
    "Never have I ever... thrown a banana peel on the floor on purpose!",
    "Never have I ever... punched a brick hoping coins would pop out!",
    "Never have I ever... yelled 'WAHOO' while jumping off something!",
    "Never have I ever... pretended a turtle shell was a weapon!",
    "Never have I ever... worn a fake mustache to look like Mario!",
    "Never have I ever... tried to ground-pound a couch cushion!",
    "Never have I ever... talked to a toilet like it was a warp pipe!",
    "Never have I ever... blamed my friend for throwing a blue shell at me... in LIFE!",
    "Never have I ever... done the Mario dance at a party!",
    "Never have I ever... tried to wall-jump between two walls!",
    "Never have I ever... collected random coins or tokens just for fun!",
    "Never have I ever... called someone 'Princess' sarcastically!",
    "Never have I ever... hummed the Super Mario theme in the bathroom!",
    "Never have I ever... pretended a cardboard box was a kart!",
    "Never have I ever... eaten spaghetti and thought of Mario!",
    "Never have I ever... wished I had a Yoshi to ride to work!",
    "Never have I ever... screamed at a video game loud enough for neighbors to hear!",
    "Never have I ever... tried to fit into a pipe or tube!",
    "Never have I ever... used a plunger and felt like a real plumber!",
    "Never have I ever... named a pet after a Mario character!",
    "Never have I ever... stayed up past 3 AM playing a Mario game!",
    "Never have I ever... done a victory lap after winning ANYTHING!",
    "Never have I ever... tripped in public and said 'I lost a life'!",
    "Never have I ever... looked at stars and thought of Star Power!",
    "Never have I ever... picked a character in Mario Kart based on looks instead of stats!",
    "Never have I ever... rage quit a Mario game and immediately restarted it!",
    "Never have I ever... tried to do a spin jump off a diving board!",
    "Never have I ever... argued with someone about which Mario game is the best!",
    "Never have I ever... pretended to throw a red shell at a bad driver!",
    "Never have I ever... made sound effects while jumping over puddles!",
    "Never have I ever... called a short person a Toad or a Goomba!",
    "Never have I ever... fantasized about living in the Mushroom Kingdom!",
    "Never have I ever... used 'It's-a me!' as an introduction!",
    "Never have I ever... blamed a loss on the game cheating instead of my own skill!",
]


# ---------------------------------------------------------------------------
# Adaptive Difficulty — scales game rounds based on player history
# ---------------------------------------------------------------------------

def get_adaptive_rounds(game_name: str, base_rounds: int, state: dict) -> int:
    """Scale game rounds based on player's historical performance.
    
    - High win rate (>70%): Add 2 extra rounds (harder)
    - Medium win rate (40-70%): Keep base rounds
    - Low win rate (<40%): Reduce by 1 round (easier, min 3)
    - New player: Use base rounds
    """
    try:
        from memory import get_player_stats
        person_id = state.get("speaker_id")
        if not person_id:
            return base_rounds
        
        stats = get_player_stats(person_id)
        game_stats = stats.get(game_name)
        if not game_stats or game_stats["games_played"] < 2:
            return base_rounds  # Not enough data
        
        win_rate = game_stats["win_rate"]
        if win_rate > 0.70:
            return min(base_rounds + 2, 10)  # Cap at 10
        elif win_rate < 0.40:
            return max(base_rounds - 1, 3)   # Floor at 3
        return base_rounds
    except Exception:
        return base_rounds


# ---------------------------------------------------------------------------
# Game Rotation — avoid repeating the same game for a guest
# ---------------------------------------------------------------------------

ALL_GAME_NAMES = [
    "simon_says", "twenty_questions", "truth_or_dare", "riddles",
    "word_chain", "karaoke", "rapid_fire", "would_you_rather",
    "rock_paper_scissors", "hangman", "hot_takes", "never_have_i_ever",
    "mario_trivia", "name_that_character", "bathroom_dare",
    "story_builder", "wyr_mario",
]

# Quick/easy games that work well as random picks for new guests
QUICK_GAMES = [
    "truth_or_dare", "would_you_rather", "riddles", "hot_takes",
    "never_have_i_ever", "rock_paper_scissors", "rapid_fire",
    "mario_trivia", "hangman",
]

_recent_games: list[str] = []  # Module-level recent game buffer
_ROTATION_BUFFER = 5  # Don't repeat within last 5 games


def pick_random_game(state: dict) -> str:
    """Pick a random game that hasn't been played recently by this guest.
    Prefers quick/party-friendly games for random selection."""
    guest_recent = state.get("_recent_games", [])
    available = [g for g in QUICK_GAMES if g not in guest_recent[-_ROTATION_BUFFER:]]
    if not available:
        available = list(QUICK_GAMES)  # Reset if all played
    return random.choice(available)


def record_game_played(game_name: str, state: dict = None):
    """Record that a game was played for rotation tracking."""
    _recent_games.append(game_name)
    if len(_recent_games) > 20:
        _recent_games[:] = _recent_games[-20:]
    # Also track per-guest if state provided
    if state is not None:
        if "_recent_games" not in state:
            state["_recent_games"] = []
        state["_recent_games"].append(game_name)
        if len(state["_recent_games"]) > 20:
            state["_recent_games"] = state["_recent_games"][-20:]


def get_recent_games() -> list[str]:
    """Get list of recently played games (for testing/dashboard)."""
    return list(_recent_games)


def reset_game_rotation():
    """Reset rotation tracking (for testing)."""
    _recent_games.clear()


# ---------------------------------------------------------------------------
# start_game — initialise a new game session
# ---------------------------------------------------------------------------

def start_game(game_name: str, state: dict, config: dict, emotion_sys) -> str | None:
    """Set up game state and return the intro text.

    Args:
        game_name: One of simon_says, twenty_questions, truth_or_dare,
                   riddles, word_chain, karaoke, rapid_fire.
        state:     Reference to ``state_current`` from main — mutations persist.
        config:    ``GAME_CONFIG`` dict from main.
        emotion_sys: ``EmotionSystem`` instance from main.
    """
    # Guard: don't start a new game while one is active
    if state.get("_active_game"):
        current = state["_active_game"]
        return f"Mama mia! We're already playing {current}! Say 'quit game' first if you want to switch!"
    import time as _time
    state["_game_last_input_time"] = _time.time()  # Start timeout clock
    record_game_played(game_name, state)  # Track for rotation

    if game_name not in VALID_GAMES:
        logger.warning(f"[GAME] Unknown game_name '{game_name}' passed to start_game")
        return None

    if game_name == "simon_says":
        state["_active_game"] = "simon_says"
        max_r = get_adaptive_rounds("simon_says", config["simon_max_rounds"], state)
        state["_game_state"] = {"round": 1, "score": 0, "max_rounds": max_r}
        action = random.choice(SIMON_ACTIONS)
        state["_game_state"]["current_action"] = action
        state["_game_state"]["is_simon"] = random.random() > 0.3
        emotion_sys.current = Emotion.EXCITED
        if state["_game_state"]["is_simon"]:
            return f"SIMON SAYS game! Round 1 of 5! Simon says... {action}! Did you do it? Say 'yes' or 'no'!"
        return f"SIMON SAYS game! Round 1 of 5! {action.capitalize()}! Ha! Did you do it? Say 'yes' or 'no'!"

    if game_name == "twenty_questions":
        thing = random.choice(TWENTY_Q_THINGS)
        state["_active_game"] = "twenty_questions"
        state["_game_state"] = {
            "answer": thing["answer"],
            "category": thing["category"],
            "hints": thing["hints"],
            "questions_left": config["twenty_q_max_questions"],
            "hints_given": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        ql = config["twenty_q_max_questions"]
        return f"20 QUESTIONS! I'm-a thinking of a {thing['category']}! You have {ql} questions! Ask me yes or no questions, or say 'hint' for a clue! Say 'give up' to quit!"

    if game_name == "truth_or_dare":
        state["_active_game"] = "truth_or_dare"
        mr = get_adaptive_rounds("truth_or_dare", config["truth_dare_max_rounds"], state)
        state["_game_state"] = {"round": 1, "max_rounds": mr}
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"TRUTH OR DARE! Let's-a play! Round 1 of {mr}! Say 'truth' or 'dare'!"

    if game_name == "riddles":
        if not RIDDLES:
            return "Mama mia! I ran out of riddles! Let's-a play something else!"
        riddle = random.choice(RIDDLES)
        state["_active_game"] = "riddles"
        state["_game_state"] = {
            "answer": riddle["a"],
            "hints": riddle["hints"],
            "hints_given": 0,
            "attempts": 0,
            "max_attempts": config["riddle_max_attempts"],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"RIDDLE TIME! Here's-a your riddle: {riddle['q']} Say 'hint' for a clue or try to guess!"

    if game_name == "word_chain":
        word = random.choice(STARTER_WORDS)
        state["_active_game"] = "word_chain"
        state["_game_state"] = {
            "last_word": word,
            "used_words": [word],
            "score": 0,
            "max_rounds": config["word_chain_max_rounds"],
        }
        emotion_sys.current = Emotion.EXCITED
        return f"WORD CHAIN! I start with '{word.upper()}'! Now YOU say a word starting with the letter '{word[-1].upper()}'! We take turns!"

    if game_name == "karaoke":
        song = random.choice(KARAOKE_SONGS)
        emotion_sys.current = Emotion.EXCITED
        return f"KARAOKE TIME! 🎤 Let's-a sing '{song['title']}'! Ready? ♪ {song['lyrics']} ♪ WAHOO! Your turn to sing something!"

    if game_name == "rapid_fire":
        questions = list(RAPID_FIRE_QUESTIONS)
        if not questions:
            return "Mama mia! I ran out of questions for Rapid Fire! Let's-a play something else!"
        random.shuffle(questions)
        max_r = get_adaptive_rounds("rapid_fire", config["rapid_fire_max_rounds"], state)
        max_r = min(max_r, len(questions))
        state["_active_game"] = "rapid_fire"
        state["_game_state"] = {
            "questions": questions[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
            "start_time": time.time(),
        }
        emotion_sys.current = Emotion.EXCITED
        first_q = questions[0]["q"]
        return f"RAPID FIRE QUIZ! Answer as fast as you can! {max_r} questions, GO! Q1: {first_q}"

    if game_name == "would_you_rather":
        if not WOULD_YOU_RATHER:
            return "Mama mia! I ran out of Would You Rather questions! Let's-a play something else!"
        random.shuffle(WOULD_YOU_RATHER)
        max_rounds = min(config.get("truth_dare_max_rounds", 5), len(WOULD_YOU_RATHER))
        state["_active_game"] = "would_you_rather"
        state["_game_state"] = {
            "questions": WOULD_YOU_RATHER[:max_rounds],
            "current": 0,
            "max_rounds": max_rounds,
            "choices": [],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        q = WOULD_YOU_RATHER[0]
        return f"WOULD YOU RATHER! Round 1 of {max_rounds}! Would you rather: A) {q['a']} OR B) {q['b']}? Say A or B!"

    if game_name == "rock_paper_scissors":
        state["_active_game"] = "rock_paper_scissors"
        state["_game_state"] = {
            "round": 1,
            "max_rounds": 3,
            "player_score": 0,
            "mario_score": 0,
        }
        emotion_sys.current = Emotion.EXCITED
        return "ROCK PAPER SCISSORS! Best of 3! Let's-a BATTLE! Say 'rock', 'paper', or 'scissors'! Let's-a GO!"

    if game_name == "hangman":
        word = random.choice(HANGMAN_WORDS)
        display = " ".join("_" for _ in word)
        state["_active_game"] = "hangman"
        state["_game_state"] = {
            "word": word,
            "guessed": [],
            "wrong_guesses": 0,
            "max_wrong": 6,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"HANGMAN! I'm-a thinking of a Mario word! {len(word)} letters! Here it is: {display} — Guess a letter! You get 6 wrong guesses before it's GAME OVER!"

    if game_name == "hot_takes":
        takes = list(HOT_TAKES)
        if not takes:
            return "Mama mia! I ran out of hot takes! Let's-a play something else!"
        random.shuffle(takes)
        ht_max = min(5, len(takes))
        state["_active_game"] = "hot_takes"
        state["_game_state"] = {
            "takes": takes[:ht_max],
            "current": 0,
            "max_rounds": ht_max,
            "agreements": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_take = takes[0]
        return f"HOT TAKES! Mario's-a got some SPICY opinions! Round 1 of {ht_max}! Here's my take: \"{first_take}\" Do you AGREE or DISAGREE?"

    if game_name == "never_have_i_ever":
        prompts = list(NHIE_PROMPTS)
        if not prompts:
            return "Mama mia! I ran out of Never Have I Ever prompts! Let's-a play something else!"
        random.shuffle(prompts)
        nhie_max = min(5, len(prompts))
        state["_active_game"] = "never_have_i_ever"
        state["_game_state"] = {
            "prompts": prompts[:nhie_max],
            "current": 0,
            "max_rounds": nhie_max,
            "daring_score": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_prompt = prompts[0]
        return f"NEVER HAVE I EVER! Let's-a see how DARING you are! Round 1 of {nhie_max}! {first_prompt} Say 'I have' or 'I haven't'!"

    # --- Mario Trivia ---
    if game_name == "mario_trivia":
        max_r = get_adaptive_rounds("mario_trivia", 5, state)
        questions = _mix_jacob_trivia(MARIO_TRIVIA_QUESTIONS, count=max_r)
        if not questions:
            return "Mama mia! I ran out of trivia questions! Let's-a play something else!"
        max_r = min(max_r, len(questions))
        state["_active_game"] = "mario_trivia"
        state["_game_state"] = {
            "questions": questions[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
        }
        emotion_sys.current = Emotion.EXCITED
        first_q = questions[0]["q"]
        has_birthday = any(q.get("is_birthday_special") for q in questions)
        intro = "MARIO TRIVIA TIME!"
        if has_birthday:
            intro += " With BIRTHDAY SPECIAL questions about our guest of honor!"
        intro += f" {max_r} questions — let's-a see how smart you are! Question 1: {first_q}"
        return intro

    # --- Name That Character ---
    if game_name == "name_that_character":
        chars = list(NAME_THAT_CHARACTER)
        if not chars:
            return "Mama mia! I ran out of characters to describe! Let's-a play something else!"
        random.shuffle(chars)
        max_r = min(5, len(chars))
        state["_active_game"] = "name_that_character"
        state["_game_state"] = {
            "characters": chars[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
            "start_time": time.time(),
            "round_start": time.time(),
        }
        emotion_sys.current = Emotion.EXCITED
        first_desc = chars[0]["desc"]
        return f"NAME THAT CHARACTER! I describe someone, you guess who! Speed matters — faster answers get bonus praise! Ready? Here we go! {first_desc}"

    # --- Bathroom Dare ---
    if game_name == "bathroom_dare":
        dares = list(BATHROOM_DARES)
        if not dares:
            return "Mama mia! I ran out of dares! Let's-a play something else!"
        random.shuffle(dares)
        max_r = 3
        state["_active_game"] = "bathroom_dare"
        state["_game_state"] = {
            "dares": dares[:max_r],
            "current": 0,
            "completed": 0,
            "max_rounds": max_r,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_dare = dares[0]
        return f"BATHROOM DARE TIME! Mario's got some challenges for you! Dare 1 of {max_r}: {first_dare} Say 'done' when you finish, or 'skip' if you're chicken! Bawk bawk!"

    # --- Story Builder ---
    if game_name == "story_builder":
        starter = random.choice(STORY_STARTERS)
        state["_active_game"] = "story_builder"
        state["_game_state"] = {
            "story": [starter],
            "current_round": 1,
            "max_rounds": 5,
            "whose_turn": "player",
        }
        emotion_sys.current = Emotion.EXCITED
        return f"STORY BUILDER TIME! We take turns adding to a story! I'll start, you add the next part, then me, back and forth for 5 rounds! Here we go: {starter} ...NOW YOU! Add the next sentence!"

    # --- Would You Rather (Extended/Mario Edition) ---
    if game_name == "wyr_mario":
        combined = list(WYR_EXTENDED)
        if not combined:
            return "Mama mia! I ran out of Would You Rather scenarios! Let's-a play something else!"
        random.shuffle(combined)
        max_rounds = min(5, len(combined))
        state["_active_game"] = "wyr_mario"
        state["_game_state"] = {
            "questions": combined[:max_rounds],
            "current": 0,
            "max_rounds": max_rounds,
            "choices": [],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        q = combined[0]
        return f"WOULD YOU RATHER — MARIO EDITION! The CRAZIEST choices from the Mushroom Kingdom! Round 1 of {max_rounds}! Would you rather: A) {q['a']} OR B) {q['b']}? Say A or B!"

    return None


# ---------------------------------------------------------------------------
# handle_game_input — process player input during an active game
# ---------------------------------------------------------------------------

def handle_game_input(lower: str, state: dict, emotion_sys) -> tuple[str, str] | None:
    """Handle input while a game mode is active. Returns (response, sound_hint) or None."""
    game = state.get("_active_game")
    if not game:
        return None

    # Validate game handler exists
    if game not in VALID_GAMES:
        logger.warning(f"[GAME] Unknown active game '{game}' — clearing")
        state["_active_game"] = None
        state["_game_state"] = {}
        return ("Hmm, I forgot what game we were playing! Want to start a new one?", "confused/thinking")

    # Validate game state exists (RPS doesn't need pre-existing state)
    game_state = state.get("_game_state", {})
    if not game_state and game != "rock_paper_scissors":
        logger.warning(f"[GAME] Empty game state for '{game}' — clearing")
        state["_active_game"] = None
        state["_game_state"] = {}
        return ("Oops, I lost track of the game! Let me know if you want to play something!", "confused/sad")

    # Track last input time for timeout
    state["_game_last_input_time"] = time.time()
    gs = state["_game_state"]

    # Universal quit (exclude "done" — used as valid input by bathroom_dare and simon_says)
    quit_words = ["quit", "stop", "give up", "end game", "exit"]
    if game not in ("bathroom_dare", "simon_says", "story_builder"):
        quit_words.append("done")
    if any(w in lower for w in quit_words):
        game_name = game.replace("_", " ")
        score = gs.get("score", 0)
        state["_active_game"] = None
        state["_game_state"] = {}
        emotion_sys.current = Emotion.HAPPY
        if game == "twenty_questions":
            return (f"The answer was '{gs.get('answer', '???')}'! Thanks for playing! Wahoo!", "game_over")
        return (f"Game over! Final score: {score}! Thanks for playing {game_name}! Wahoo!", "game_over")

    # --- Simon Says ---
    if game == "simon_says":
        did_it = any(w in lower for w in ["yes", "yeah", "yep", "yup", "did it", "done"])
        didnt = any(w in lower for w in ["no", "nope", "didn't", "nah"])

        if did_it or didnt:
            is_simon = gs["is_simon"]
            correct = (is_simon and did_it) or (not is_simon and didnt)
            if correct:
                gs["score"] += 1
                feedback = random.choice([
                    "CORRECT! Wahoo!",
                    "You got it! Smart-a cookie!",
                    "RIGHT! You're-a good at this!",
                    "YES! Mario is-a impressed!",
                ])
                sfx = "correct"
            else:
                if is_simon and didnt:
                    feedback = "Oops! Simon DID say it! You should have done it!"
                else:
                    feedback = "HA! Simon DIDN'T say it! You fell for my trick! Mama mia!"
                sfx = "wrong"

            gs["round"] += 1
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                final_score = gs["score"]
                state["_game_state"] = {}
                if final_score == gs["max_rounds"]:
                    return (f"{feedback} PERFECT SCORE! {final_score}/{gs['max_rounds']}! You're-a the CHAMPION!", "achievement")
                elif final_score >= 3:
                    return (f"{feedback} Game over! Score: {final_score}/{gs['max_rounds']}! Not bad at all!", "game_over")
                else:
                    return (f"{feedback} Game over! Score: {final_score}/{gs['max_rounds']}! Better luck next time!", "game_over")

            # Next round
            action = random.choice(SIMON_ACTIONS)
            gs["current_action"] = action
            gs["is_simon"] = random.random() > 0.3
            rnd = gs["round"]
            if gs["is_simon"]:
                return (f"{feedback} Round {rnd}! Simon says... {action}! Did you do it?", sfx)
            else:
                return (f"{feedback} Round {rnd}! {action.capitalize()}! Did you do it?", sfx)
        return ("Did you do it? Say 'yes' or 'no'!", None)

    # --- 20 Questions ---
    if game == "twenty_questions":
        answer = gs["answer"]

        # Hint request
        if "hint" in lower:
            idx = gs["hints_given"]
            if idx < len(gs["hints"]):
                gs["hints_given"] += 1
                hint = gs["hints"][idx]
                return (f"Here's a hint: {hint}! {gs['questions_left']} questions left!", "hint")
            return ("No more hints! You're-a on your own now! Ask a yes or no question!", None)

        # Check if they guessed it
        if answer in lower:
            state["_active_game"] = None
            ql = gs["questions_left"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            return (f"YES! It's-a {answer}! You got it with {ql} questions left! WAHOO! You're-a genius!", "correct")

        # Yes/no response to their question
        gs["questions_left"] -= 1
        if gs["questions_left"] <= 0:
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.MISCHIEVOUS
            return (f"Time's up! The answer was '{answer}'! Better luck next time! Ha ha!", "game_over")

        # Simple keyword matching for yes/no answers
        answer_words = answer.lower().split()
        if any(w in lower for w in ["is it", "does it", "can it", "would it", "has it"]):
            related = any(w in lower for w in answer_words)
            if related:
                return (f"Hmm, you're getting WARM! {gs['questions_left']} questions left! Keep guessing!", "hint")
            return (f"Hmm, not exactly! {gs['questions_left']} questions left!", None)

        return (f"Ask me a yes or no question! Or say 'hint'! {gs['questions_left']} questions left!", None)

    # --- Truth or Dare ---
    if game == "truth_or_dare":
        if "truth" in lower:
            if not TRUTH_QUESTIONS:
                return ("Mama mia! I ran out of truth questions! Let's-a play something else!", "game_over")
            truth = random.choice(TRUTH_QUESTIONS)
            gs["round"] += 1
            emotion_sys.current = Emotion.MISCHIEVOUS
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                return (f"TRUTH! {truth} ...And that's the final round! Great game! Wahoo!", "game_over")
            return (f"TRUTH! {truth} Tell me your answer, then say 'truth' or 'dare' for round {gs['round']}!", None)

        if "dare" in lower:
            if not DARES:
                return ("Mama mia! I ran out of dares! Let's-a play something else!", "game_over")
            dare = random.choice(DARES)
            gs["round"] += 1
            emotion_sys.current = Emotion.EXCITED
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                return (f"DARE! {dare} ...And that's the final round! You're-a brave! Wahoo!", "game_over")
            return (f"DARE! {dare} When you're done, say 'truth' or 'dare' for round {gs['round']}!", None)

        return ("Say 'truth' or 'dare'! Or 'quit' to stop playing!", None)

    # --- Riddles ---
    if game == "riddles":
        if "hint" in lower:
            idx = gs["hints_given"]
            if idx < len(gs["hints"]):
                gs["hints_given"] += 1
                remaining = gs["max_attempts"] - gs["attempts"]
                return (f"HINT: {gs['hints'][idx]}! You have {remaining} guesses left!", "hint")
            return ("No more hints! Use your brain power! You can do it!", None)

        gs["attempts"] += 1
        answer = gs["answer"]
        if answer in lower or any(w in lower for w in answer.split()):
            state["_active_game"] = None
            attempts = gs["attempts"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            if attempts == 1:
                return (f"WAHOO! '{answer.upper()}'! You got it on the FIRST try! You're-a a GENIUS!", "correct")
            return (f"YES! The answer is '{answer.upper()}'! You got it in {attempts} guesses! Bravo!", "correct")

        if gs["attempts"] >= gs["max_attempts"]:
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.MISCHIEVOUS
            return (f"Time's up! The answer was '{answer.upper()}'! Better luck next riddle! Ha!", "game_over")

        remaining = gs["max_attempts"] - gs["attempts"]
        emotion_sys.current = Emotion.CONFUSED
        return (f"Nope! That's not it! {remaining} guesses left! Try again or say 'hint'!", "wrong")

    # --- Word Chain ---
    if game == "word_chain":
        words = lower.strip().split()
        player_word = words[-1] if words else ""
        last_letter = gs["last_word"][-1].lower()

        if not player_word or len(player_word) < 2:
            return (f"Say a word starting with '{last_letter.upper()}'! Keep the chain going!", None)

        if player_word[0] != last_letter:
            emotion_sys.current = Emotion.CONFUSED
            return (f"Nope! Your word needs to start with '{last_letter.upper()}'! '{gs['last_word']}' ends with '{last_letter}'! Try again!", "wrong")

        if player_word in gs["used_words"]:
            return (f"'{player_word}' was already used! Pick a different word starting with '{last_letter.upper()}'!", "wrong")

        gs["used_words"].append(player_word)
        gs["score"] += 1

        if gs["score"] >= gs["max_rounds"]:
            state["_active_game"] = None
            score = gs["score"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            return (f"WAHOO! {score} words in the chain! You're-a the Word Chain CHAMPION! Incredible!", "achievement")

        # Mario's turn
        mario_letter = player_word[-1]
        MARIO_WORDS = {
            "a": "adventure", "b": "bowser", "c": "castle", "d": "dragon", "e": "exciting",
            "f": "fireball", "g": "galaxy", "h": "hero", "i": "invincible", "j": "jumping",
            "k": "kingdom", "l": "luigi", "m": "mushroom", "n": "nintendo", "o": "odyssey",
            "p": "princess", "q": "quest", "r": "rainbow", "s": "starlight", "t": "toadstool",
            "u": "underwater", "v": "victory", "w": "wahoo", "x": "extreme", "y": "yoshi", "z": "zap",
        }
        mario_word = MARIO_WORDS.get(mario_letter, f"{mario_letter}ario")
        while mario_word in gs["used_words"]:
            mario_word = mario_word + "s"
        gs["used_words"].append(mario_word)
        gs["last_word"] = mario_word
        next_letter = mario_word[-1].upper()
        emotion_sys.current = Emotion.HAPPY
        return (f"Nice! '{player_word}'! My turn: '{mario_word.upper()}'! Now you say a word starting with '{next_letter}'! Score: {gs['score']}!", "correct")

    # --- Rapid Fire Quiz ---
    if game == "rapid_fire":
        current_idx = gs["current"]
        if current_idx >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Quiz over! Score: {gs['score']}/{gs['max_rounds']}! Wahoo!", "game_over")

        question = gs["questions"][current_idx]
        answer = question["a"].lower()

        answer_words = answer.split()
        got_it = any(w in lower for w in answer_words) or answer in lower

        gs["current"] += 1
        next_idx = gs["current"]

        if got_it:
            gs["score"] += 1
            if next_idx >= len(gs["questions"]):
                elapsed = time.time() - gs["start_time"]
                state["_active_game"] = None
                score = gs["score"]
                total = gs["max_rounds"]
                state["_game_state"] = {}
                emotion_sys.current = Emotion.EXCITED
                return (f"CORRECT! Final score: {score}/{total} in {elapsed:.0f}s! Wahoo! You're a Mario expert!", "achievement")
            else:
                next_q = gs["questions"][next_idx]["q"]
                return (f"YES! Q{next_idx + 1}: {next_q}", "correct")
        else:
            if next_idx >= len(gs["questions"]):
                elapsed = time.time() - gs["start_time"]
                state["_active_game"] = None
                score = gs["score"]
                total = gs["max_rounds"]
                state["_game_state"] = {}
                emotion_sys.current = Emotion.HAPPY
                return (f"Nope, it was '{answer}'! Final score: {score}/{total} in {elapsed:.0f}s! Good try!", "game_over")
            else:
                next_q = gs["questions"][next_idx]["q"]
                return (f"Nope! It was '{answer}'! Q{next_idx + 1}: {next_q}", "wrong")

    # --- Would You Rather ---
    if game == "would_you_rather":
        chose_a = any(w in lower for w in ["a", "first", "option a", "first one"])
        chose_b = any(w in lower for w in ["b", "second", "option b", "second one"])
        if not chose_a and not chose_b:
            return ("Say A or B! Which would you rather?", None)

        choice = "A" if chose_a else "B"
        if gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("Game over! Great choices! Wahoo!", "game_over")
        q = gs["questions"][gs["current"]]
        chosen_text = q["a"] if chose_a else q["b"]
        gs["choices"].append(choice)

        reactions = [
            f"Interesting! You chose: {chosen_text}! Mario likes-a that answer!",
            f"{chosen_text}? Great choice! Mario would pick the same!",
            f"Ooh, {chosen_text}! Bold move! Wahoo!",
            f"{chosen_text} — that's-a spicy choice! I love it!",
        ]
        reaction = random.choice(reactions)

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.HAPPY
            return (f"{reaction} Game over! Great choices! You're-a unique! Wahoo!", "game_over")
        else:
            next_q = gs["questions"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round}! Would you rather: A) {next_q['a']} OR B) {next_q['b']}?", "correct")

    # --- Rock Paper Scissors ---
    if game == "rock_paper_scissors":
        player_rock = any(w in lower for w in ["rock", "stone", "fist"])
        player_paper = any(w in lower for w in ["paper", "flat", "sheet"])
        player_scissors = any(w in lower for w in ["scissors", "cut", "snip"])

        if not player_rock and not player_paper and not player_scissors:
            return ("Say 'rock', 'paper', or 'scissors'! Let's-a battle!", None)

        if player_rock:
            player_choice = "rock"
        elif player_paper:
            player_choice = "paper"
        else:
            player_choice = "scissors"

        mario_choice = random.choice(["rock", "paper", "scissors"])
        rnd = gs["round"]

        if player_choice == mario_choice:
            reaction = random.choice(RPS_TIE_REACTIONS)
            sfx = None
        elif (player_choice == "rock" and mario_choice == "scissors") or \
             (player_choice == "paper" and mario_choice == "rock") or \
             (player_choice == "scissors" and mario_choice == "paper"):
            gs["player_score"] += 1
            reaction = random.choice(RPS_LOSE_REACTIONS)
            sfx = "correct"
        else:
            gs["mario_score"] += 1
            reaction = random.choice(RPS_WIN_REACTIONS)
            sfx = "wrong"

        status = f"You: {player_choice.upper()} vs Mario: {mario_choice.upper()}! {reaction}"
        score_text = f"Score — You: {gs['player_score']} | Mario: {gs['mario_score']}"

        gs["round"] += 1
        if gs["round"] > gs["max_rounds"]:
            state["_active_game"] = None
            p = gs["player_score"]
            m = gs["mario_score"]
            state["_game_state"] = {}
            if p > m:
                emotion_sys.current = Emotion.HAPPY
                return (f"{status} {score_text} — YOU WIN the battle! Mama mia, you're-a TOUGH!", "achievement")
            elif m > p:
                emotion_sys.current = Emotion.EXCITED
                return (f"{status} {score_text} — MARIO WINS! Ha ha! Better luck next time!", "game_over")
            else:
                emotion_sys.current = Emotion.SURPRISED
                return (f"{status} {score_text} — It's a DRAW! We're-a perfectly matched! Wahoo!", "game_over")

        return (f"{status} {score_text} | Round {gs['round']} of {gs['max_rounds']}! Say rock, paper, or scissors!", sfx)

    # --- Hangman ---
    if game == "hangman":
        word = gs["word"]
        guess = ""
        words = lower.strip().split()
        for w in words:
            if len(w) == 1 and w.isalpha():
                guess = w
                break
        if not guess:
            for w in words:
                if w.isalpha():
                    guess = w[0]
                    break

        if not guess:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            return (f"Say a letter to guess! Current word: {display} | Wrong guesses: {gs['wrong_guesses']}/{gs['max_wrong']}", None)

        guess = guess.lower()
        if guess in gs["guessed"]:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            return (f"You already guessed '{guess.upper()}'! Try a different letter! {display}", None)

        gs["guessed"].append(guess)

        if guess in word:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            if "_" not in display:
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.EXCITED
                return (f"YES! '{guess.upper()}' is correct! The word is {word.upper()}! YOU WIN! WAHOO! You're-a a genius!", "achievement")
            count = word.count(guess)
            emotion_sys.current = Emotion.HAPPY
            return (f"YES! '{guess.upper()}' is in there {count} time{'s' if count > 1 else ''}! {display} | Wrong: {gs['wrong_guesses']}/{gs['max_wrong']} | Guess another letter!", "correct")
        else:
            gs["wrong_guesses"] += 1
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            if gs["wrong_guesses"] >= gs["max_wrong"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.MISCHIEVOUS
                return (f"NOPE! '{guess.upper()}' is NOT in the word! GAME OVER! The word was {word.upper()}! Better luck next time!", "game_over")
            remaining = gs["max_wrong"] - gs["wrong_guesses"]
            emotion_sys.current = Emotion.CONFUSED
            return (f"Nope! '{guess.upper()}' is NOT in the word! {display} | {remaining} wrong guesses left! Try again!", "wrong")

    # --- Hot Takes ---
    if game == "hot_takes":
        agrees = any(w in lower for w in ["agree", "yes", "right", "true", "totally", "absolutely", "definitely", "correct", "for sure"])
        disagrees = any(w in lower for w in ["disagree", "no", "wrong", "false", "nah", "nope", "never", "bad take", "incorrect"])

        if not agrees and not disagrees:
            return ("Do you AGREE or DISAGREE with my take? Let me hear it!", None)

        if gs["current"] >= len(gs["takes"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("That's all my takes! Wahoo!", "game_over")
        current_take = gs["takes"][gs["current"]]

        if agrees:
            gs["agreements"] += 1
            defend_reactions = [
                f"YES! You GET it! \"{current_take}\" — that's just FACTS! Wahoo!",
                f"FINALLY someone with TASTE! Mario KNEW you'd agree! We're-a soulmates!",
                f"See?! I TOLD everyone! Thank you for having a BRAIN! Ha ha!",
                f"That's RIGHT! You and Mario are on the same wavelength! High five!",
                f"WAHOO! A person of CULTURE! I'm-a so happy right now!",
            ]
            reaction = random.choice(defend_reactions)
            emotion_sys.current = Emotion.EXCITED
            sfx = "correct"
        else:
            concede_reactions = [
                f"WHAT?! You DISAGREE with \"{current_take}\"?! Mama mia, we need to TALK!",
                f"Oh come ON! How can you not see the TRUTH?! Mario is-a SHOCKED!",
                f"Fine fine, you're entitled to your WRONG opinion! Ha ha! Just kidding... mostly!",
                f"DISAGREE?! That's-a like saying spaghetti isn't delicious! UNBELIEVABLE!",
                f"Okay okay, I RESPECT your view... but you're still WRONG! He he!",
            ]
            reaction = random.choice(concede_reactions)
            emotion_sys.current = Emotion.SURPRISED
            sfx = "wrong"

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["takes"]):
            state["_active_game"] = None
            agreed = gs["agreements"]
            total = gs["max_rounds"]
            state["_game_state"] = {}
            if agreed == total:
                return (f"{reaction} That's all my takes! You agreed with ALL {total}! We're-a BEST FRIENDS now! Wahoo!", "achievement")
            elif agreed == 0:
                return (f"{reaction} That's all my takes! You disagreed with EVERYTHING! Mama mia, we're-a RIVALS! Ha ha!", "game_over")
            else:
                return (f"{reaction} That's all my takes! You agreed with {agreed} out of {total}! Not bad! Wahoo!", "game_over")

        next_take = gs["takes"][gs["current"]]
        next_round = gs["current"] + 1
        return (f"{reaction} Round {next_round} of {gs['max_rounds']}! Next take: \"{next_take}\" — AGREE or DISAGREE?", sfx)

    # --- Never Have I Ever ---
    if game == "never_have_i_ever":
        i_have = any(w in lower for w in ["i have", "have done", "guilty", "yeah", "yes", "yep"])
        i_havent = any(w in lower for w in ["i haven't", "i havent", "never", "nope", "no", "nah"])

        if i_have or i_havent:
            if gs["current"] >= len(gs["prompts"]):
                state["_active_game"] = None
                state["_game_state"] = {}
                return ("That's all the rounds! Wahoo!", "game_over")
            current_prompt = gs["prompts"][gs["current"]]

            if i_have:
                gs["daring_score"] += 1
                reactions_have = [
                    "MAMA MIA! You actually did that?! Ha ha ha!",
                    "WAHOO! You're-a WILD one! I can't believe it!",
                    "NO WAY! You really did?! Mario is-a SHOCKED!",
                    "Oh my COINS! For real?! That's-a hilarious!",
                    "MAMA MIA! I knew you were brave but THAT brave?!",
                    "HA! You're-a crazier than Bowser on a Monday!",
                    "I'm-a speechless! Actually no I'm not — WAHOO!",
                ]
                reaction = random.choice(reactions_have)
                emotion_sys.current = Emotion.SURPRISED
                sfx = "coin"
            else:
                confessions = [
                    "Smart choice! Mario hasn't either... okay MAYBE once!",
                    "Same here! Well... actually... no comment! He he!",
                    "Good, good! Between you and me, I TOTALLY have though! Shh!",
                    "You haven't? Neither have I! ...Why is Luigi laughing?",
                    "Wise choice! I wish I could say the same! Mama mia!",
                    "Ha! You're-a playing it safe! Unlike me at last Tuesday's party!",
                    "Neither have I! ...Okay Luigi says I'm lying but DON'T LISTEN TO HIM!",
                ]
                reaction = random.choice(confessions)
                emotion_sys.current = Emotion.MISCHIEVOUS
                sfx = "powerup"

            gs["current"] += 1
            if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["prompts"]):
                state["_active_game"] = None
                score = gs["daring_score"]
                state["_game_state"] = {}
                if score <= 1:
                    rating = "You're-a CAUTIOUS! Playing it safe like a true Toad!"
                elif score <= 3:
                    rating = "You're-a ADVENTUROUS! A real explorer like Mario!"
                else:
                    rating = "You're-a WILD! Even Wario says 'WHOA, calm down!'"
                return (f"{reaction} That's all the rounds! You said 'I have' {score} times out of {gs['max_rounds']}! {rating} Wahoo!", "achievement")

            next_prompt = gs["prompts"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round} of {gs['max_rounds']}! {next_prompt} Say 'I have' or 'I haven't'!", sfx)

        prompt_text = gs["prompts"][gs["current"]] if gs["current"] < len(gs["prompts"]) else "..."
        return (f"Say 'I have' or 'I haven't'! {prompt_text}", "hint")

    # --- Mario Trivia ---
    if game == "mario_trivia":
        current_idx = gs["current"]
        if current_idx >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Trivia over! Score: {gs['score']}/{gs['max_rounds']}! Wahoo!", "game_over")

        question = gs["questions"][current_idx]
        accepted = question["accept"]
        is_birthday = question.get("is_birthday_special", False)
        got_it = any(a in lower for a in accepted)

        gs["current"] += 1
        next_idx = gs["current"]

        fun_fact_line = ""
        if is_birthday and question.get("fun_fact"):
            fun_fact_line = f" Fun fact: {question['fun_fact']}"

        if got_it:
            # Birthday special questions award 2 points instead of 1
            points = 2 if is_birthday else 1
            gs["score"] += points
            if is_birthday:
                feedback = random.choice([
                    f"CORRECT! BIRTHDAY BONUS — {points} points! You know Jacob well!",
                    f"YES! That's RIGHT! Birthday bonus: {points} points! Wahoo!",
                    f"MAMA MIA! You nailed the birthday question! {points} points!",
                ])
            else:
                feedback = random.choice([
                    "CORRECT! Wahoo! You REALLY know your Mario!",
                    "YES! That's-a RIGHT! You're a true Mario fan!",
                    "MAMA MIA! You got it! Impressive!",
                    "WAHOO! Correct! Are you secretly a Toad scholar?!",
                ])
            feedback += fun_fact_line
            sfx = "correct"
        else:
            correct_answer = question["a"][0] if question.get("a") else "Unknown"
            if is_birthday:
                feedback = random.choice([
                    f"Ooh! The birthday answer was '{correct_answer}'!",
                    f"Not quite! It's '{correct_answer}'! Now you know about Jacob!",
                ])
            else:
                feedback = random.choice([
                    f"Ooh, not quite! The answer was '{correct_answer}'!",
                    f"Nope! It's '{correct_answer}'! Now you know!",
                    f"Sorry! The correct answer is '{correct_answer}'! Tricky one!",
                ])
            feedback += fun_fact_line
            sfx = "wrong"

        if next_idx >= len(gs["questions"]):
            score = gs["score"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if score == total:
                return (f"{feedback} PERFECT SCORE! {score}/{total}! You're a MARIO MASTER! Wahoo!", "achievement")
            elif score >= 3:
                return (f"{feedback} Final score: {score}/{total}! Great job, you know your stuff!", "game_over")
            else:
                return (f"{feedback} Final score: {score}/{total}! Time to play more Mario games! Ha ha!", "game_over")
        else:
            next_q = gs["questions"][next_idx]["q"]
            return (f"{feedback} Question {next_idx + 1}: {next_q}", sfx)

    # --- Name That Character ---
    if game == "name_that_character":
        current_idx = gs["current"]
        if current_idx >= len(gs["characters"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Game over! Score: {gs['score']}/{gs['max_rounds']}!", "game_over")

        char = gs["characters"][current_idx]
        accepted = char["accept"]
        got_it = any(a in lower for a in accepted)
        elapsed = time.time() - gs["round_start"]

        gs["current"] += 1
        next_idx = gs["current"]

        if got_it:
            gs["score"] += 1
            if elapsed < 5:
                feedback = f"LIGHTNING FAST! {elapsed:.1f} seconds! You INSTANTLY knew it! INCREDIBLE!"
            elif elapsed < 15:
                feedback = f"Nice! {elapsed:.1f} seconds! Quick thinker! Wahoo!"
            else:
                feedback = f"You got it in {elapsed:.1f} seconds! A bit slow but CORRECT!"
            sfx = "correct"
        else:
            correct_answer = char["a"][0] if char.get("a") else "Unknown"
            feedback = f"Nope! It was {correct_answer.upper()}! {elapsed:.1f} seconds and no dice!"
            sfx = "wrong"

        if next_idx >= len(gs["characters"]):
            total_time = time.time() - gs["start_time"]
            score = gs["score"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if score == total:
                return (f"{feedback} PERFECT! {score}/{total} in {total_time:.0f}s total! You know EVERYONE in the Mushroom Kingdom!", "achievement")
            elif score >= 3:
                return (f"{feedback} Final: {score}/{total} in {total_time:.0f}s! Not bad at all!", "game_over")
            else:
                return (f"{feedback} Final: {score}/{total} in {total_time:.0f}s! Time to study your Mario characters!", "game_over")
        else:
            gs["round_start"] = time.time()
            next_desc = gs["characters"][next_idx]["desc"]
            return (f"{feedback} Character {next_idx + 1}: {next_desc}", sfx)

    # --- Bathroom Dare ---
    if game == "bathroom_dare":
        current_idx = gs["current"]
        if current_idx >= len(gs["dares"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"All dares done! You completed {gs['completed']}/{gs['max_rounds']}! Wahoo!", "game_over")

        did_it = any(w in lower for w in ["done", "did it", "finished", "completed", "yes", "okay"])
        skipped = any(w in lower for w in ["skip", "pass", "no", "nope", "chicken", "next"])

        if did_it:
            gs["completed"] += 1
            reactions = [
                "WAHOO! You actually DID it! Mario is-a SO PROUD of you!",
                "INCREDIBLE! You're braver than me fighting Bowser! Respect!",
                "YES! You're a CHAMPION! That took GUTS! Ha ha!",
                "MAMA MIA! You really did it?! You're AMAZING! Wahoo!",
                "BRAVO! Standing ovation from Mario! *clap clap clap*",
            ]
            reaction = random.choice(reactions)
            sfx = "correct"
            emotion_sys.current = Emotion.EXCITED
        elif skipped:
            reactions = [
                "Bawk bawk BAWK! Chicken! Ha ha, just kidding! It's okay!",
                "Skipped! Mario understands, not everyone can be as brave as a plumber!",
                "No worries! That one WAS pretty tough! Maybe next time!",
                "Oh come ON! ...Fine fine, we'll move on! Ha ha!",
            ]
            reaction = random.choice(reactions)
            sfx = "wrong"
            emotion_sys.current = Emotion.MISCHIEVOUS
        else:
            return (f"Did you do the dare? Say 'done' when you finish, or 'skip' to move on!", None)

        gs["current"] += 1
        next_idx = gs["current"]

        if next_idx >= len(gs["dares"]):
            completed = gs["completed"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if completed == total:
                return (f"{reaction} ALL DARES COMPLETED! {completed}/{total}! You're the DARE CHAMPION! Wahoo!", "achievement")
            elif completed > 0:
                return (f"{reaction} Dares over! You completed {completed}/{total}! Not bad!", "game_over")
            else:
                return (f"{reaction} Dares over! You skipped them ALL?! Mama mia! Ha ha!", "game_over")

        next_dare = gs["dares"][next_idx]
        return (f"{reaction} Dare {next_idx + 1} of {gs['max_rounds']}: {next_dare} Say 'done' or 'skip'!", sfx)

    # --- Story Builder ---
    if game == "story_builder":
        if gs["whose_turn"] == "player":
            # Player just added their sentence
            player_addition = lower.strip()
            if len(player_addition) < 3:
                return ("Come on, add something to the story! Say a sentence to continue!", None)

            gs["story"].append(player_addition)
            gs["current_round"] += 1

            if gs["current_round"] > gs["max_rounds"]:
                full_story = " ".join(gs["story"])
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.HAPPY
                return (f"THE END! What a MASTERPIECE! Here's our story: {full_story} ...WAHOO! We should write a BOOK together!", "achievement")

            # Mario adds his part
            mario_continuations = [
                "And THEN, out of NOWHERE, a giant Goomba appeared wearing sunglasses and said 'What's up?!'",
                "But WAIT! Bowser showed up riding a skateboard and doing kickflips! Nobody expected THAT!",
                "Suddenly the ground started shaking and a GOLDEN pipe burst through the floor!",
                "Just when things couldn't get crazier, Luigi showed up with a BOOMBOX blasting the Mario theme!",
                "And then — PLOT TWIST — it was all a dream! Just kidding! A Koopa in a tuxedo appeared!",
                "BUT the Star Power activated and EVERYTHING turned to disco lights and funky music!",
                "Out of the shadows, Toad appeared carrying the BIGGEST pizza anyone had ever seen!",
                "And in that exact moment, a Bullet Bill flew by carrying a love letter from Princess Peach!",
                "Then Waluigi crashed through the wall on a motorcycle yelling 'WAAAH!' at the top of his lungs!",
                "Suddenly a warp pipe opened and 50 coins came flying out like a golden fountain!",
            ]
            mario_part = random.choice(mario_continuations)
            gs["story"].append(mario_part)
            gs["whose_turn"] = "player"
            rnd = gs["current_round"]
            return (f"LOVE IT! Mario's turn: {mario_part} ...Round {rnd} of {gs['max_rounds']}! YOUR turn! Add the next part!", "correct")

        return ("It's YOUR turn! Add a sentence to the story!", None)

    # --- Would You Rather (Mario Edition) ---
    if game == "wyr_mario":
        chose_a = any(w in lower for w in ["a", "first", "option a", "first one"])
        chose_b = any(w in lower for w in ["b", "second", "option b", "second one"])
        if not chose_a and not chose_b:
            return ("Say A or B! Which would you rather?", None)

        choice = "A" if chose_a else "B"
        if gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("All rounds done! Wahoo!", "game_over")
        q = gs["questions"][gs["current"]]
        chosen_text = q["a"] if chose_a else q["b"]
        other_text = q["b"] if chose_a else q["a"]
        gs["choices"].append({"choice": choice, "text": chosen_text})

        dramatic_reactions = [
            f"MAMA MIA! You chose '{chosen_text}' over '{other_text}'?! That says SO MUCH about you! Ha ha!",
            f"'{chosen_text}'?! REALLY?! Mario would have picked '{other_text}'! We're-a so different! Wahoo!",
            f"Interesting! '{chosen_text}'! You know what, I RESPECT that choice! Bold move!",
            f"WAHOO! '{chosen_text}'! That's the choice of a TRUE adventurer! Or maybe a crazy person! Either way I love it!",
            f"'{chosen_text}'! Ooh ooh ooh! {random.choice(['Luigi', 'Peach', 'Toad', 'Bowser'])} would be SO jealous of that answer!",
        ]
        reaction = random.choice(dramatic_reactions)

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            choices_summary = ", ".join([c["choice"] for c in gs["choices"]])
            state["_game_state"] = {}
            emotion_sys.current = Emotion.HAPPY
            return (f"{reaction} All rounds done! Your choices were: {choices_summary}! You are TRULY one of a kind! Wahoo!", "game_over")
        else:
            next_q = gs["questions"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round}! Would you rather: A) {next_q['a']} OR B) {next_q['b']}?", "correct")

    return None


# ---------------------------------------------------------------------------
# check_game_timeout — detect stale games from idle loop
# ---------------------------------------------------------------------------

def check_game_timeout(state: dict, timeout_seconds: float = 180.0) -> tuple[str, str] | None:
    """Check if active game has timed out. Returns response tuple or None."""
    game = state.get("_active_game")
    if not game:
        return None
    last_input = state.get("_game_last_input_time", 0)
    if last_input and (time.time() - last_input) > timeout_seconds:
        logger.info(f"[GAME] Game '{game}' timed out after {timeout_seconds}s of inactivity")
        state["_active_game"] = None
        state["_game_state"] = {}
        state["_game_last_input_time"] = None
        return (
            "Looks like we forgot about our game! No worries — come back for another round anytime!",
            "neutral/friendly",
        )
    return None
