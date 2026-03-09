"""Game handler module — all interactive game logic for Mario AI.

Extracted from main.py to keep the server module focused on WebSocket handling.
Each game mode has its content data, start logic, and input handling here.
"""

import random
import time
from emotions import Emotion


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
]

STARTER_WORDS = ["mario", "party", "castle", "mushroom", "adventure", "bathroom", "princess", "galaxy"]

KARAOKE_SONGS = [
    {"title": "Jump Up, Super Star!", "lyrics": "Here we go, off the rails! Don't you know it's time to raise our sails? It's FREEDOM like you never knew!"},
    {"title": "Do the Mario!", "lyrics": "Swing your arms from side to side! Come on, it's time to go, do the Mario! Take one step and then again!"},
    {"title": "Bowser's Fury Rap", "lyrics": "I'm-a Mario, red hat hero! Stomping Goombas, coins from zero! Jumping high and running fast! Every level is a BLAST!"},
    {"title": "Bathroom Ballad", "lyrics": "Oh this bathroom, it's-a so fine! Every tile perfectly aligned! The soap dispenser, what a treat! This party bathroom can't be beat!"},
    {"title": "Plumber's Anthem", "lyrics": "We're the plumbers, here we go! Through the pipes from high to low! Fixing leaks and saving queens! Living out our plumber dreams!"},
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
]


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
    if game_name == "simon_says":
        state["_active_game"] = "simon_says"
        state["_game_state"] = {"round": 1, "score": 0, "max_rounds": config["simon_max_rounds"]}
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
        state["_game_state"] = {"round": 1, "max_rounds": config["truth_dare_max_rounds"]}
        emotion_sys.current = Emotion.MISCHIEVOUS
        mr = config["truth_dare_max_rounds"]
        return f"TRUTH OR DARE! Let's-a play! Round 1 of {mr}! Say 'truth' or 'dare'!"

    if game_name == "riddles":
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
        random.shuffle(questions)
        max_r = config["rapid_fire_max_rounds"]
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
        random.shuffle(WOULD_YOU_RATHER)
        max_rounds = config.get("truth_dare_max_rounds", 5)
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
        random.shuffle(takes)
        state["_active_game"] = "hot_takes"
        state["_game_state"] = {
            "takes": takes[:5],
            "current": 0,
            "max_rounds": 5,
            "agreements": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_take = takes[0]
        return f"HOT TAKES! Mario's-a got some SPICY opinions! Round 1 of 5! Here's my take: \"{first_take}\" Do you AGREE or DISAGREE?"

    if game_name == "never_have_i_ever":
        prompts = list(NHIE_PROMPTS)
        random.shuffle(prompts)
        state["_active_game"] = "never_have_i_ever"
        state["_game_state"] = {
            "prompts": prompts[:5],
            "current": 0,
            "max_rounds": 5,
            "daring_score": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_prompt = prompts[0]
        return f"NEVER HAVE I EVER! Let's-a see how DARING you are! Round 1 of 5! {first_prompt} Say 'I have' or 'I haven't'!"

    return None


# ---------------------------------------------------------------------------
# handle_game_input — process player input during an active game
# ---------------------------------------------------------------------------

def handle_game_input(lower: str, state: dict, emotion_sys) -> tuple[str, str] | None:
    """Handle input while a game mode is active. Returns (response, sound_hint) or None."""
    game = state["_active_game"]
    gs = state["_game_state"]

    # Universal quit
    if any(w in lower for w in ["quit", "stop", "give up", "end game", "done", "exit"]):
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
            truth = random.choice(TRUTH_QUESTIONS)
            gs["round"] += 1
            emotion_sys.current = Emotion.MISCHIEVOUS
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                return (f"TRUTH! {truth} ...And that's the final round! Great game! Wahoo!", "game_over")
            return (f"TRUTH! {truth} Tell me your answer, then say 'truth' or 'dare' for round {gs['round']}!", None)

        if "dare" in lower:
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
            next_q = gs["questions"][next_idx]["q"]
            return (f"Nope! It was '{answer}'! Q{next_idx + 1}: {next_q}", "wrong")

    # --- Would You Rather ---
    if game == "would_you_rather":
        chose_a = any(w in lower for w in ["a", "first", "option a", "first one"])
        chose_b = any(w in lower for w in ["b", "second", "option b", "second one"])
        if not chose_a and not chose_b:
            return ("Say A or B! Which would you rather?", None)

        choice = "A" if chose_a else "B"
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
        if gs["current"] >= gs["max_rounds"]:
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.HAPPY
            return (f"{reaction} Game over! Great choices! You're-a unique! Wahoo!", "game_over")

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
        if gs["current"] >= gs["max_rounds"]:
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
            if gs["current"] >= gs["max_rounds"]:
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

        return (f"Say 'I have' or 'I haven't'! {gs['prompts'][gs['current']]}", "hint")

    return None
