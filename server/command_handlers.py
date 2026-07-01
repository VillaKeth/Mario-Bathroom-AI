"""Command handlers — special commands/easter-eggs extracted from main.py."""

import os
import random
import re
import sqlite3
import time
from datetime import datetime

from emotions import Emotion
import game_handlers
from game_handlers import _deflavor
import speaker_id
from chat_identity import resolve_chat_identity

# Character identity — set by main.py on startup via set_character()
_CHARACTER_NAME = "Mario"
_CHARACTER_DISPLAY_NAME = "Mario"


def set_character(name: str, display_name: str):
    """Set the active character for command responses."""
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    _CHARACTER_NAME = name
    _CHARACTER_DISPLAY_NAME = display_name


def _as_trigger_dict(value) -> dict:
    """Normalize a trigger->response pool to a dict.

    Wizard-generated extras.yaml stores easter_eggs as a LIST of
    {trigger, response} rows; hand-written Mario content uses a flat dict.
    Both shapes must work — the list shape crashed EASTER_EGGS.items()
    ('list' object has no attribute 'items') on any easter-egg scan.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        out = {}
        for row in value:
            if isinstance(row, dict) and row.get("trigger") and row.get("response"):
                out[str(row["trigger"]).lower()] = str(row["response"])
        return out
    return {}


def set_character_content(extras: dict):
    """Load character-specific content pools from extras dict (from content/extras.yaml).

    If the character provides content for a pool, use it.
    If a pool key is missing from the extras dict, default to EMPTY so no
    Mario content leaks into non-Mario characters.
    """
    global EASTER_EGGS, SECRETS, DARES, NICKNAMES, FORTUNES, MOOD_RESPONSES
    global TWISTERS, STORIES, PICKUP_LINES, BATHROOM_TIPS, RAPS, MOTIVATIONS
    global CONFESSIONS, ROASTS, BATHROOM_FACTS, PARTY_SUGGESTIONS, PERSONALITY_MODES

    EASTER_EGGS = _as_trigger_dict(extras.get("easter_eggs", {}))
    SECRETS = extras.get("secrets", [])
    DARES = extras.get("dares", [])
    NICKNAMES = extras.get("nicknames", [])
    FORTUNES = extras.get("fortunes", [])
    MOOD_RESPONSES = extras.get("mood_responses") or {}
    if not isinstance(MOOD_RESPONSES, dict):
        MOOD_RESPONSES = {}
    TWISTERS = extras.get("twisters", [])
    STORIES = extras.get("stories", [])
    PICKUP_LINES = extras.get("pickup_lines", [])
    BATHROOM_TIPS = extras.get("bathroom_tips", [])
    RAPS = extras.get("raps", [])
    MOTIVATIONS = extras.get("motivations", [])
    CONFESSIONS = extras.get("confessions", [])
    ROASTS = extras.get("roasts", [])
    BATHROOM_FACTS = extras.get("bathroom_facts", [])
    PARTY_SUGGESTIONS = extras.get("party_suggestions", [])
    PERSONALITY_MODES = extras.get("personality_modes") if isinstance(extras.get("personality_modes"), dict) else {}

    import logging
    _pool_counts = {k: len(v) for k, v in {
        "easter_eggs": EASTER_EGGS, "secrets": SECRETS, "dares": DARES,
        "nicknames": NICKNAMES, "fortunes": FORTUNES, "mood_responses": MOOD_RESPONSES,
        "twisters": TWISTERS, "stories": STORIES, "pickup_lines": PICKUP_LINES,
        "bathroom_tips": BATHROOM_TIPS, "raps": RAPS, "motivations": MOTIVATIONS,
        "confessions": CONFESSIONS, "roasts": ROASTS, "bathroom_facts": BATHROOM_FACTS,
        "party_suggestions": PARTY_SUGGESTIONS,
    }.items()}
    logging.getLogger(__name__).info(
        f"[command_handlers] Character content loaded: {sum(_pool_counts.values())} total items across {sum(1 for c in _pool_counts.values() if c > 0)}/{len(_pool_counts)} pools"
    )
# ---------------------------------------------------------------------------
# Inline content data
# ---------------------------------------------------------------------------

EASTER_EGGS = {
    "up up down down": "Wahoo! The Konami Code! You get 30 extra lives! Just kidding, but you get my respect!",
    "wahoo wahoo wahoo": "WAHOO WAHOO WAHOO! Ha ha ha! You speak-a my language! Triple wahoo power!",
    "it's a me": "Hey, that's-a MY line! But you said it so well, I'll-a let it slide! Wahoo!",
    "do the mario": "Swing your arms from side to side! Come on, it's time to go, do the Mario!",
    "mamma mia": "You said the magic words! Mamma Mia! That's-a worth at least three coins!",
    "yahoo": "Yahoo! Oh wait, that's-a not quite right. It's WAHOO! Let me teach you! Wah-HOO!",
    "bowser": "Bowser?! Where?! *looks around nervously* Don't scare Mario like that!",
    "princess peach": "Princess Peach! *sighs dreamily* She's-a so wonderful! Don't tell her I said that!",
    "luigi": "Luigi! My brother! He's-a taller but I'm-a the famous one! Don't tell him I said that!",
    "game over": "GAME OVER?! No no no! In this bathroom, we never get game over! Continue? YES!",
    "warp zone": "A warp zone! Quick, everyone jump into the pipe! Oh wait, that's-a the toilet...",
    "power up": "*makes power-up sound* Ba-da-da-da-da-DUM! You're now SUPER sized! Wahoo!",
    "world record": "World record?! In this bathroom?! I bet we CAN set one! Fastest hand-wash ever! GO!",
    "spaghetti": "SPAGHETTI?! *eyes light up* Mama mia, did someone say spaghetti?! Where where WHERE?!",
    "mushroom": "A mushroom! *grows bigger* WAHOO! Super Mario! ...Wait, that was just a regular mushroom? Oh well!",
    "yoshi": "YOSHI! My best friend! Did you know Yoshi can eat ANYTHING? Don't test him at the buffet!",
    "toad": "Toad! That little guy is-a always telling me the princess is in another castle! Every. Single. Time!",
    "star": "A STAR?! *sparkles* I'm invincible! Da da da DA da da! ...For about 10 seconds!",
    "coin": "A COIN! *bling* Only 99 more and I get an extra life! Keep 'em coming!",
    "pipe": "Did someone say PIPE?! *examines nearest pipe* This is-a beautiful craftsmanship! Professional opinion!",
    # --- Rounds 1250+ easter eggs ---
    "fire flower": "FIRE FLOWER! *shoots fireball* Pew pew! Watch out, I'm-a on FIRE! Don't burn the toilet paper!",
    "1-up": "1-UP! Ba-DING! Extra life! Now I can guard this bathroom FOREVER! You're welcome!",
    "blue shell": "BLUE SHELL?! NOOO! *ducks* That's-a the most feared item in ALL of racing! Run!",
    "banana peel": "A banana peel! In a BATHROOM?! That's-a double dangerous! Wet floor PLUS banana = disaster!",
    "thank you mario": "Thank you?! That's-a what I usually hear AFTER saving the princess! You're too kind!",
    "mama": "MAMA?! Where?! Is she here?! *looks around* Oh, you're just saying mama mia! You got me!",
    "secret": "A SECRET?! *whispers* I know where the secret exit is! Through the... wait, nice try!",
    "invincible": "INVINCIBLE! Da da da da da DA DA! Nothing can stop me! Not even bathroom germs!",
    "let's go": "LET'S-A GO! That's-a my THING! You said it perfectly! We're basically twins now!",
    "nintendo": "NINTENDO! The company that made-a ME! Without them, I'd just be a regular plumber! Boring!",
    # Super Mario Galaxy
    "luma": "LUMA! That little star baby! So cute! I used to carry Luma everywhere in space! Best travel buddy!",
    "rosalina": "Rosalina! The cosmic queen! She lives in SPACE with all the Lumas! So mysterious and beautiful!",
    "observatory": "The Comet Observatory! My space house! We flew across the UNIVERSE in that thing! Best road trip ever!",
    # Super Mario Odyssey
    "cappy": "CAPPY! My hat buddy! He lets me take over ANYTHING! Even a T-Rex! How cool is that?!",
    "new donk city": "New Donk City! The Big Apple of the Mushroom Kingdom! Mayor Pauline is-a the best! Jump Up Super Star!",
    "cascade kingdom": "Cascade Kingdom! With the T-Rex and the waterfalls! I wore Cappy and became a DINOSAUR! RAWR!",
    # Paper Mario / Mario RPG
    "geno": "GENO! My wooden warrior friend from Star Road! He shoots lasers from his FINGERS! So cool!",
    "mallow": "MALLOW! The little cloud prince who thought he was a frog! Plot twist of the century!",
    "star road": "Star Road! Where wishes come true! Smithy tried to break it but we fixed it! Teamwork!",
    # Mario Kart
    "rainbow road": "RAINBOW ROAD! The most beautiful AND terrifying track ever! One wrong turn and you're in SPACE!",
    "blue shell": "BLUE SHELL?! NOOO! The great equalizer! First place is NEVER safe! *ducks for cover*",
    "lightning": "LIGHTNING! Zap! Everyone shrinks! It's-a the most chaotic item in Mario Kart! I love it AND hate it!",
    # Super Smash Bros
    "smash": "SMASH BROS! Where I punch Bowser AND Pikachu! I'm-a the OG fighter! Forward aerial for life!",
    "final smash": "FINAL SMASH! The Mario Finale! Giant fireball across the stage! Nobody survives THAT! WAHOO!",
    # General gaming
    "speedrun": "A SPEEDRUN?! Some players beat my games in MINUTES! It takes me HOURS! They're wizards!",
    "glitch": "A GLITCH?! Don't tell the developers! Sometimes glitches are the most fun part! Backwards long jump forever!",
    "world one": "World One! 1-1! Where it all began! That first Goomba has scared more people than Bowser! Classic!",
    "super mario bros": "Super Mario Bros! The game that started it ALL! 1985! I was so young and pixelated back then!",
    "princess daisy": "DAISY! Luigi's special someone! She's-a tough and loud! HI I'M DAISY! Ha ha!",
    "bob-omb": "BOB-OMB! My explosive little friend! Three seconds and BOOM! Best alarm clock ever!",
    "chain chomp": "CHAIN CHOMP! That angry ball on a chain! It tried to eat me SO many times! Bark bark bark!",
    # Pop culture crossovers — party favorites
    "fortnite": "FORTNITE?! I'd be the BEST Battle Royale player! I already know how to jump! And I've got my own dance moves! WAHOO!",
    "minecraft": "MINECRAFT! Block world! I LOVE blocks! Question mark blocks, brick blocks... Minecraft Steve and I would be best friends!",
    "zelda": "ZELDA! My Nintendo buddy Link! We don't talk much but we nod at each other at company picnics! Great guy!",
    "sonic": "SONIC?! That speedy hedgehog! We raced at the Olympics and let me tell you... it was CLOSE! Don't ask who won!",
    "pokemon": "POKEMON! Gotta catch em all! I tried to catch a Goomba once with a Poke Ball but it just got angry!",
    "among us": "AMONG US?! Red is NOT sus! I'm-a always red and I'm NEVER the imposter! Well... almost never!",
    "rick roll": "Never gonna give you up! Never gonna let you down! WAHOO! You just got Mario-Rolled!",
    "deez nuts": "DEEZ NUTS?! Ha! Got me! But you know what's BETTER than deez nuts? DEEZ COINS! Cha-ching!",
    "rizz": "RIZZ?! Mario has MAXIMUM rizz! The mustache alone is a ten out of ten! Princess Peach agrees!",
    "skibidi": "Skibidi toilet?! In MY bathroom?! This is a PREMIUM bathroom experience, not some meme zone! ...Okay it's a little funny!",
    "ohio": "ONLY IN OHIO! But this bathroom? This is PEAK Florida behavior! And I LOVE it!",
    "sus": "SUS?! I'm not sus! I was in the pipes doing plumber tasks! I have VISUAL confirmation! Vote someone else!",
    "sigma": "SIGMA?! Mario is the ULTIMATE sigma! I saved the princess, didn't ask for anything, and went right back to plumbing! That's SIGMA!",
}

SECRETS = [
    "*whispers* Don't tell anyone, but... Luigi is actually the better jumper! Shh!",
    "*looks around* Between you and me... I've never actually fixed a real pipe! I just stomp on things!",
    "*whispers* Peach's cake? It's-a store bought! But she adds her own frosting! Shh!",
    "*leans in* Bowser sends me birthday cards! We're actually pen pals! Don't tell anyone!",
    "*whispers* I'm actually shorter than a fire hydrant in real life! The games lie!",
    "*looks around nervously* Sometimes... I use warp pipes just to skip the hard parts! Shh!",
    "*whispers* Toad's mushroom head? He styles it every morning! Takes him two hours!",
]

DARES = [
    "I dare you to go back to the party and tell the next person you see 'It's-a me!' in your best Mario voice!",
    "I dare you to take a selfie in this mirror with your best Mario pose! Wahoo!",
    "I dare you to go out there and do three jumping jacks before sitting down! Like-a Mario!",
    "I dare you to hum the Mario theme to the next person who walks in here! Do do do, do do DO!",
    "I dare you to keep a straight face for 30 seconds while I tell you a joke! Ready? ...Goomba!",
    "I dare you to go out and high-five three people! Tell them Mario sent you!",
]

NICKNAMES = [
    "From now on, you're-a 'Super {name}'! Like a power-up version of yourself!",
    "I'll call you '{name} the Brave'! Sounds-a heroic, no?",
    "You shall be known as 'Pipe Master {name}'! ...okay maybe not. Ha!",
    "How about 'Mushroom {name}'? Because you make everything bigger and better!",
    "I declare you 'Star {name}'! Because you light up-a the room!",
    "Your official Mario nickname is-a 'Fire {name}'! Because you're on fire tonight!",
    "I'll call you '{name}-oshi'! Like Yoshi but cooler! Wahoo!",
]

FORTUNES = [
    "Mario sees in your future... a very full stomach! You'll eat-a the best pizza of your life this week!",
    "The stars say... you will find a gold coin on the ground within three days! Keep your eyes down!",
    "Mario's crystal ball shows... someone will compliment your outfit soon! Looking-a sharp!",
    "I predict... you will laugh so hard this week that soda comes out your nose! Wahoo!",
    "The Mushroom Kingdom fortune says... a great adventure awaits you! Maybe not with pipes, but still great!",
    "Mario's prophecy... you will become best friends with someone you haven't met yet! Keep-a talking to people!",
    "I see in your future... an embarrassing moment that becomes your funniest story! Embrace it!",
    "The fortune pipes reveal... you're about to level up in real life! A big achievement is coming!",
    "The Star Spirits whisper... you will receive unexpected good news before the week is over! Stay positive!",
    "Mario's prophecy says... tonight you'll make a memory that you'll be telling people about for YEARS!",
    "The Mushroom seer predicts... someone at this party will become very important in your life! Look around!",
    "I see a golden path ahead! You're about to discover a hidden talent you never knew you had! Wahoo!",
    "The cosmos reveal... you'll find something you lost a long time ago! Check under the couch cushions!",
    "Mario's crystal mushroom shows... a surprise is coming your way tomorrow! Could be big, could be small, but it's-a GOOD!",
    "The fortune Toad says... you will ace something you've been worried about! Confidence is your power-up!",
    "I predict... the next song that plays will become your new anthem! Listen carefully at the party!",
    "The warp pipe of destiny shows... you're going to reconnect with an old friend very soon! Exciting!",
    "Mario sees... someone will ask for YOUR advice soon because they think you're wise! And they're RIGHT!",
    "The Star Road fortune says... your next meal will be absolutely LEGENDARY! Treat yourself!",
    "The prophecy pipes reveal... you'll accomplish something this month that makes your family proud! Go get it!",
]

MOOD_RESPONSES = {
    "happy": "I'm-a feeling FANTASTIC! Like I just grabbed a Super Star! Everything is wonderful!",
    "excited": "WAHOO! I'm-a so excited I could jump to the moon! Let's-a GO!",
    "bored": "Meh... I'm-a little bored. Nobody's been talking to me! Come on, entertain-a Mario!",
    "surprised": "Whoa! I'm-a pretty surprised right now! What a twist!",
    "confused": "I'm-a... confused? Like when Luigi goes the wrong way in a pipe!",
    "worried": "I'm-a little worried... something doesn't feel right. Like when you hear Bowser's music...",
    "loving": "I'm feeling so warm and fuzzy! Like a hug from Yoshi!",
    "mischievous": "Heh heh heh... I'm-a feeling playful! Watch out! Mischief Mario is here!",
    "sleepy": "Yawn... I'm-a getting sleepy... Zzzz... Oh! I'm awake! What were we talking about?",
    "proud": "I feel like a true champion! Nothing can stop-a Mario today!",
    "neutral": "I'm-a doing okay! Just hanging out in my favorite bathroom! What's up?",
}

TWISTERS = [
    "Try this! 'Peter Piper picked a pack of pickled Piranha Plants!' Say it three times fast!",
    "Here's-a one! 'Six slimy Shy Guys sliding on slippery slopes!' Go go go!",
    "Can you say this? 'Bob-omb's big blue bubble burst by Bowser's bridge!' Wahoo!",
    "Try it! 'Koopa Troopa's copper caper caught Captain Toad!' Fast as you can!",
    "Okay try this! 'Really rowdy red Rexes raced round Rainbow Road!' Three times! GO!",
    "How about this? 'Wacky Wiggler wiggled while Waluigi watched!' Say it five times!",
]

STORIES = [
    "Once upon a time, in a bathroom far far away, Mario met the bravest person ever — YOU! And they became friends forever! The end! Ha!",
    "Let me tell you about the time Luigi got stuck in a toilet pipe! He was plunging away, and WHOOSH — he ended up in World 4! True story!",
    "One day, Toad found a golden plunger that granted three wishes. He wished for mushrooms, more mushrooms, and — you guessed it — MUSHROOMS!",
    "There was once a Goomba who wanted to be a hero. Everyone laughed, but he saved Princess Peach when Mario was on vacation! Legend!",
    "Picture this — Bowser tried to learn plumbing! He flooded his own castle! Even villains need good plumbers, huh? That's why I'm-a the best!",
    "One time at a party just like this, Mario stayed in the bathroom so long that Peach sent a rescue team! Turns out I was just having a great conversation!",
    "Here's a story! One night, a Boo walked into a bathroom just like this one. I turned around and — wait, did YOU hear something?! ...Just kidding! The Boo was actually shy and just wanted to wash his ghostly hands!",
    "Let me tell you about the Great Mushroom Bake-Off! Peach, Daisy, and Rosalina competed to make the best cake. Peach used star bits, Daisy used fire flowers, and Rosalina... she used actual STARDUST! But who won? What do YOU think? ...It was Toad! He snuck in a mushroom pie at the last second!",
    "Once upon a time, Yoshi found a mysterious egg that was glowing rainbow colors. He sat on it for three days! And you know what hatched? ...Can you guess? ...A TINY BABY BOWSER! Yoshi screamed so loud they heard it in World 8!",
    "Story time! So Wario and Waluigi opened a restaurant called 'Wah-Burgers.' The food was terrible but the entertainment was amazing! Wario would eat the customers' leftovers live on stage! Would YOU eat at Wah-Burgers? ...Smart choice!",
    "Let me tell you about the time I raced Sonic! Yes, THE Sonic! We were neck and neck and then — stop, close your eyes and picture this — we BOTH tripped on a banana peel! Who put it there? DONKEY KONG! He won by default!",
    "Once there was a Koopa Troopa who collected bottle caps instead of coins. Everyone thought he was crazy! But one day those bottle caps became worth MILLIONS! The moral? ...What do YOU think the moral is? ...That's right! Never judge a Koopa by his shell!",
    "Here's one! The Mushroom Kingdom held its first talent show. A Piranha Plant sang opera! A Goomba did stand-up comedy! And Chain Chomp... he did interpretive dance! But the winner? A little Shy Guy who just stood there being shy! The crowd LOVED it!",
    "Legend has it there's a secret 9th world that nobody has ever beaten. They say the final boss is... are you ready for this? ...A GIANT TOILET! And the only way to beat it is with the legendary Golden Plunger! I'm still looking for it!",
    "True story! Last week, Bowser sent me a birthday invitation! I was suspicious, so I asked Luigi to go first. Luigi showed up and... it was actually a REAL party! Bowser just wanted friends! We played Mario Kart all night! Even villains get lonely sometimes!",
]

PICKUP_LINES = [
    "Are you a Super Star? Because you're-a making me invincible! Wahoo!",
    "Are you a Fire Flower? Because you just set my heart ablaze!",
    "Do you have a map? Because I just got lost in your eyes! It's-a like World 8!",
    "Are you a 1-Up Mushroom? Because meeting you just gave me an extra life!",
    "If you were a coin, you'd be-a the final one I need for 100! DING DING!",
    "Are you a Warp Pipe? Because every time I look at you, I'm transported to another world!",
    "Is your name Peach? Because you're-a royalty in my eyes!",
    "You must be a Power Star, because you light up every room you walk into!",
]

BATHROOM_TIPS = [
    "Mario's Tip Number One: Always wash-a your hands! 20 seconds minimum! Sing the Mario theme!",
    "Pro tip from your plumber friend: Always put the seat down! It's-a just common courtesy!",
    "Bathroom etiquette 101: Don't use your phone while people are waiting! They're doing the pee-pee dance out there!",
    "Mario says: If you finish the toilet paper, REPLACE IT! Don't leave the next person hanging!",
    "Important tip: The courtesy flush is-a real! Use it! Your fellow party-goers will thank you!",
    "Mario's golden rule: Don't take too long in here! Other people need-a to go! Unless you're talking to me, of course!",
]

RAPS = [
    "Yo yo yo! It's-a me, Mario! Jumping high, never low! Grab the coins, watch me flow! Bowser's slow, here we GO!",
    "I'm-a the plumber with the stache, collecting coins and making cash! Jumping pipes, making a splash! Bowser better not clash!",
    "Super Mario in the house! Quiet as a mouse — PSYCH! I'm loud as Bowser! Mushroom power, every hour!",
    "Red hat, blue overalls, jumping over waterfalls! Saving princesses in castle halls, Mario never falls!",
    "Pipes and plungers, that's my game! Every world, I bring the flame! Fire flower, claim to fame! Remember-a Mario's name!",
]

MOTIVATIONS = [
    "Hey! You're-a AMAZING! Even when things get tough, remember — Mario died hundreds of times and STILL saved the princess!",
    "Listen to me! Every champion was once a beginner! Even Mario started in World 1-1! You'll get to the castle!",
    "You know what I always say? When you fall in a pit, you respawn and try again! NEVER give up! WAHOO!",
    "You are stronger than Bowser and braver than Luigi in a ghost house! And THAT is saying something!",
    "Remember — every coin you collect counts! Even small victories matter! You're-a doing GREAT!",
    "If a short Italian plumber can save the entire Mushroom Kingdom, imagine what YOU can do! The sky is-a the limit!",
    "Life is like a Mario level — sometimes there are Goombas in your way, but there's ALWAYS a path forward!",
    "You are a SUPER STAR! Don't let anyone tell you otherwise! Now go out there and be-a AMAZING!",
]

CONFESSIONS = [
    "Oh! A confession?! Mario is-a ALL ears! The bathroom is a safe space! What's on your mind?",
    "Mama mia! A confession! Okay okay, Mario is listening! I promise I won't tell anyone! ...probably!",
    "Ooh! Spicy! Go ahead, tell-a Mario everything! These pipes have heard it ALL!",
    "A confession?! This is-a like a telenovela! I'm ready! Hit me with it!",
]

ROASTS = [
    "Oh {name}, you took so long in here, I thought you moved in! Ha ha!",
    "Hey {name}! You're-a like a Goomba — cute but easy to stomp! Just kidding!",
    "You know, {name}, your haircut reminds me of a Piranha Plant! In a good way! Ha!",
    "{name}! If you were a power-up, you'd be-a the poison mushroom! Kidding kidding!",
    "Mario's honest opinion? You look-a like you just lost to Bowser! But stylishly!",
    "Hey {name}! You're about as graceful as Luigi on ice! But just as lovable!",
    "{name}, you dance like a Dry Bones trying to reassemble! But hey, effort counts!",
    "{name}, your sense of direction is worse than Toad's! 'The princess is in another castle!' Every. Time.",
    "Hey {name}! You've got the speed of a Thwomp going UP! Slow and steady... mostly slow!",
    "{name}, if gaming skills were coins, you'd still be at zero! Ha! Just kidding, you're-a great!",
    "Oh {name}! You're like a Bullet Bill — loud, fast, and usually going the wrong way!",
    "{name}, your jokes are like Bowser's plans — they never work but I respect the effort!",
    "Hey {name}! You walk into rooms like a Bob-omb — everyone notices, but not always in a good way! Ha!",
    "{name}, you're about as sneaky as a Chain Chomp! Everyone hears you coming from a mile away!",
    "{name}! Your singing is like a Boo — it's-a scary but also kind of adorable!",
    "Hey {name}! You eat snacks faster than Yoshi eats fruit! That tongue speed is impressive!",
    "{name}, you've got the fashion sense of Wario! Bold, questionable, but somehow it WORKS!",
    "Oh {name}! You're like a Lakitu — always hovering around but nobody knows why! Ha!",
    "{name}, your attention span is shorter than a Goomba's lifespan! Stomp and gone!",
    "{name}! You're as subtle as a Bowser entrance — dramatic music and everything! Love it!",
]

BATHROOM_FACTS = [
    "The average person spends about 1.5 years of their life in the bathroom! That's-a a lot of pipe time!",
    "The first flushing toilet was invented in 1596 by Sir John Harington! A true hero, like-a me!",
    "Toilet paper was invented in China in the 6th century! Before that... mama mia, don't ask!",
    "The world's most expensive toilet is made of gold and costs over $5 million! Even Bowser would be jealous!",
    "Singing in the shower sounds better because of the acoustics! The tiles create-a natural reverb!",
    "The average person washes their hands for only 6 seconds. It should be 20! Sing the Mario theme!",
    "Ancient Romans used communal sponges on sticks to clean themselves. Sharing is NOT always caring!",
    "A toilet flushes in the key of E flat! That's-a music to a plumber's ears!",
    "The bathroom is where 75% of people get their best ideas! Creative plumbing, I call it!",
    "In Japan, some toilets have more buttons than a video game controller! Even Mario is impressed!",
    "The average toilet handle has 40,000 germs per square inch! Wash-a your hands, people!",
    "Thomas Crapper popularized the flush toilet but didn't invent it! False credit is worse than a blue shell!",
    "Hot water kills more germs, but cold water with soap works just as well! Science is-a cool!",
    "The first public restroom opened in London in 1851! Welcome to civilization!",
    "Astronauts use a $19 million toilet on the International Space Station! Space plumbing is-a expensive!",
    "Rubber ducks were originally made for chewing, not bath time! Weird but true!",
    "The Egyptians invented the first showers using jugs of water poured by servants! Fancy!",
    "A running toilet can waste 200 gallons of water per day! As a plumber, this makes-a me cry!",
    "The first soap was made from animal fat and ashes about 5,000 years ago! Smelled terrible!",
    "Your toothbrush should be at least 6 feet from the toilet to avoid airborne particles! Mama mia!",
    "There are more bacteria on your phone than on a toilet seat! Put the phone down!",
    "The world record for longest time sitting on a toilet is 116 hours! Don't try this at home!",
    "Bathroom mirrors fog up because warm moist air condenses on the cooler glass surface! Science!",
    "Ancient Greeks used stones and pottery shards instead of toilet paper! OUCH!",
    "The average person uses 100 rolls of toilet paper per year! That's-a a lot of rolls!",
    "Bidets use 1/8 of a gallon of water — much less than making a roll of toilet paper! Efficient!",
    "The word 'toilet' comes from the French 'toile' meaning cloth for grooming! Très chic!",
    "Hand dryers can spread more bacteria than paper towels! The debate rages on!",
    "Medieval castles had 'garderobes' — toilets built into the walls that emptied into the moat! Gross!",
    "A single sneeze can spray droplets up to 26 feet! Cover your nose, friend!",
]

PARTY_SUGGESTIONS = [
    "Start a dance-off in the living room! Show them your best moves! Wahoo!",
    "Go find someone wearing the same color as you and become instant best friends!",
    "Challenge someone to a thumb wrestling match! Mario believes in you!",
    "Start a conga line through the party! Everyone loves a conga line!",
    "Find the snack table and try something you've never eaten before! Adventure!",
    "Go give three random people high-fives and tell them Mario sent you!",
    "Start a karaoke session! Even bad singing is-a good entertainment!",
    "Find someone standing alone and strike up a conversation! Be a hero!",
    "Organize a group selfie with at least 5 people! Memories forever!",
    "Start a 'would you rather' game with the nearest group of people!",
    "Go compliment three people on their outfits! Spread the love!",
    "Find the DJ and request your favorite song! It's YOUR party too!",
    "Start a paper airplane contest with napkins! Engineering at its finest!",
    "Challenge someone to a staring contest! No blinking allowed!",
    "Organize an impromptu limbo game using a broom or pool noodle!",
    "Go find the host and tell them this is the best party ever! Make their night!",
    "Start a storytelling circle — everyone shares their funniest memory!",
    "Do your best celebrity impression and see if people can guess who it is!",
    "Find a partner and have a 60-second joke-telling competition!",
    "Organize a scavenger hunt — hide small items around the party!",
    "Start a compliment train — each person compliments the person next to them!",
    "Challenge someone to a dance battle — winner gets bragging rights!",
    "Go around asking people what their superpower would be! Great conversation starter!",
    "Find someone with an interesting accessory and ask the story behind it!",
    "Start a group game of telephone — whisper a message around a circle!",
]

PERSONALITY_MODES = {
    "scary": {
        "triggers": ["be scary", "horror mode", "scary mode", "spooky mode"],
        "intro": "Mwa ha ha ha! Welcome to the DARK side! *thunder crashes* SCARY mode activated! Boo!",
    },
    "dj": {
        "triggers": ["be a dj", "dj mode", "be dj", "play music"],
        "intro": "YOOO! DJ MODE IN THE HOUSE! *scratch scratch* Drop the bass! Untz untz untz! Let's get this bathroom PUMPING!",
    },
    "therapist": {
        "triggers": ["be my therapist", "therapy mode", "therapist mode", "i need therapy"],
        "intro": "Ah yes, welcome to the therapy office. *adjusts imaginary glasses* Tell me, how does that make you feel? I'm here for you, friend.",
    },
    "pirate": {
        "triggers": ["be a pirate", "pirate mode", "arr", "pirate talk"],
        "intro": "ARRR! Avast ye landlubbers! Captain mode activated! Shiver me timbers! Where be the treasure?!",
    },
    "normal": {
        "triggers": ["be normal", "reset mode", "normal mode", "be yourself"],
        "intro": f"Back to normal! Regular mode activated! Let's go!",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_holiday() -> str | None:
    """Return the current holiday/special day name, or None."""
    now = datetime.now()
    m, d = now.month, now.day
    holidays = {
        (1, 1): "New Year's Day",
        (2, 14): "Valentine's Day",
        (3, 10): "Mario Day (MAR10)",
        (3, 17): "St. Patrick's Day",
        (4, 1): "April Fools' Day",
        (7, 4): "Fourth of July",
        (10, 31): "Halloween",
        (12, 25): "Christmas Day",
        (12, 31): "New Year's Eve",
    }
    return holidays.get((m, d))


def _format_character_text(text: str) -> str:
    if not text:
        return text

    protected = {
        "__SUPER_MARIO_BROS__": "Super Mario Bros",
        "__MARIO_KART__": "Mario Kart",
        "__DO_THE_MARIO__": "Do the Mario",
        "__MARIO_FINALE__": "Mario Finale",
    }
    for token, phrase in protected.items():
        text = text.replace(phrase, token)

    text = text.replace("Mario's", f"{_CHARACTER_NAME}'s")
    text = text.replace("MARIO", _CHARACTER_NAME.upper())
    text = text.replace("Mario", _CHARACTER_NAME)

    for token, phrase in protected.items():
        text = text.replace(token, phrase)
    return text


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def _handle_special_commands_impl(
    transcript: str,
    state: dict,
    game_config: dict,
    emotion_system,
    idle_behavior,
    party_stats,
    memory_module,
) -> str | None:
    """Handle special commands/requests in the transcript. Returns response text or None."""
    lower = transcript.lower()

    # Command cooldown — prevent rapid-fire command spam (1s)
    # Only checked here; timestamp is set by caller when a command actually matches
    now = time.time()
    if now - state["_last_command_time"] < game_config["command_cooldown"]:
        return None

    # --- Active game mode handling (intercepts input when a game is running) ---
    if state["_active_game"]:
        # Check if the user wants to start a DIFFERENT game or quit
        _GAME_SWITCH_KEYWORDS = [
            "trivia", "quiz me", "truth or dare", "dare me", "rock paper scissors",
            "rps", "simon says", "20 questions", "twenty questions", "would you rather",
            "riddle", "word chain", "karaoke", "hangman", "hot take", "never have i ever",
            "rapid fire", "name that character", "story time", "tell me a story",
            "joke", "tell me a joke", "joke battle", "dance", "song",
            "stop game", "quit game", "end game", "stop playing", "quit playing",
        ]
        wants_switch = any(kw in lower for kw in _GAME_SWITCH_KEYWORDS)
        if not wants_switch:
            game_before = state["_active_game"]
            game_state_before = dict(state["_game_state"])
            result = game_handlers.handle_game_input(lower, state, emotion_system)
            if result is not None:
                text, sound = result
                state["_game_sound_hint"] = sound
                # Save game result if game just ended
                if state["_active_game"] is None and state["speaker_id"]:
                    score = game_state_before.get("score", 0)
                    max_s = game_state_before.get("max_rounds", game_state_before.get("max_attempts", 1))
                    memory_module.save_game_result(state["speaker_id"], game_before, score, max_s)
                return text
        else:
            # Clear current game to allow the new command to be processed below
            old_game = state["_active_game"]
            state["_active_game"] = None
            state["_game_state"] = {}
            state["_game_last_input_time"] = 0.0
            print(f"[GAME_SWITCH] Cleared '{old_game}' — user requested: {lower[:50]}")
            # If it's a stop/quit request, return a canned response instead of falling through to LLM
            if any(kw in lower for kw in ["stop game", "quit game", "end game", "stop playing", "quit playing"]):
                emotion_system.current = "happy"
                return random.choice([
                    f"Game over! That was fun! What else would you like to do?",
                    f"Okay, game stopped! Ready for whatever's next!",
                    f"Alrighty, we're done! Want to play something else or just chat?",
                    f"Good game! What should we do now?",
                ])
            # Fall through to process the new command normally

    # Easter eggs — hidden trigger phrases for extra fun
    # Only trigger for VERY SHORT messages (≤3 words) so complex requests go to LLM
    _word_count = len(lower.split())
    if _word_count <= 3:
        for trigger, response in EASTER_EGGS.items():
            if trigger in lower:
                emotion_system.current = Emotion.EXCITED
                return _format_character_text(response)

    # Tell a joke — only intercept generic requests, let specific ones go to LLM
    # "tell me a joke" → canned, "tell me a joke about plumbing" → LLM
    if _word_count <= 7 and any(w in lower for w in ["tell me a joke", "know any jokes", "make me laugh", "say something funny"]):
        emotion_system.current = "mischievous"
        return idle_behavior.get_joke()

    # Tell me a secret — only generic requests
    if _word_count <= 7 and (any(w in lower for w in ["tell me a secret"]) or re.search(r'\bsecret\b', lower) or re.search(r'\bwhisper\b', lower)):
        emotion_system.current = "mischievous"
        if SECRETS:
            return _format_character_text(random.choice(SECRETS))
        return None  # fall through to LLM

    # Trivia fun facts — only for explicit fact requests, NOT "trivia" which starts the game
    if any(w in lower for w in ["tell me a fact", "fun fact", "did you know"]):
        emotion_system.current = "excited"
        return idle_behavior.get_trivia()

    # Sing — use word boundaries to avoid matching "embarrassing", "processing", etc.
    if any(w in lower for w in ["sing a song", "sing for me", "sing me"]) or \
       re.search(r'\bsing\b', lower) or re.search(r'\bsong\b', lower) or \
       re.search(r'\bmusic\b', lower) or re.search(r'\bhum\b', lower):
        emotion_system.current = "happy"
        return idle_behavior.get_song()

    # Party stats
    if any(w in lower for w in ["how many people", "party stats", "how long", "statistics", "how many visits"]):
        stats = party_stats.get_stats()
        return (
            f"Wahoo! Let me-a check my notes! "
            f"Tonight we've had {stats['total_visits']} bathroom visits from "
            f"{stats['unique_visitors']} different people! "
            f"The party's been going for {stats['party_duration']}! "
            f"{'The record holder is ' + stats['most_frequent_name'] + '!' if stats['most_frequent_name'] else ''}"
        )

    # Name learning — register voice when user says their name
    # Allow re-parsing if current name was set from presence event (not from prior parsing)
    name_was_parsed = state.get("_name_from_parsing", False)
    if not name_was_parsed and _word_count <= 8 and any(w in lower for w in ["my name is", "i'm called", "call me", "i am ", "i'm ", "im ", "it's ", "it is "]):
        match = re.search(
            r"(?:my name is|i'm called|call me|i am|i'm|\bim\b|it'?s|it is)\s+([A-Za-z]+)",
            lower,
        )
        if match:
            raw_name = match.group(1)
            # Filter out stop words that aren't names
            stop_words = {"a", "the", "an", "not", "so", "just", "very", "really",
                          "also", "here", "there", "like", "kinda", "my", "your",
                          "me", "that", "this", "what", "been", "about", "gonna",
                          "great", "fine", "good", "bad", "nice", "cool", "true",
                          "okay", "time", "all", "over", "done", "going", "getting",
                          "feeling", "doing", "trying", "looking", "thinking", "having",
                          "coming", "leaving", "back", "sorry", "sure", "happy", "sad",
                          "tired", "hungry", "drunk", "bored", "sick", "nervous",
                          "excited", "scared", "confused", "ready", "late", "lost",
                          "new", "old", "from", "still", "already", "pretty", "super",
                          "wasted", "hammered", "tipsy", "faded", "high", "stoned",
                          "dying", "dead", "alive", "home", "out", "up", "down"}
            if raw_name.lower() not in stop_words:
                name = raw_name[:50].capitalize()
                # Register this voice with the name
                if state.get("_last_audio_chunk"):
                    new_id = speaker_id.register_speaker(name, state["_last_audio_chunk"])
                    memory_module.register_person(new_id, name)
                    state["speaker_name"] = name
                    state["speaker_id"] = new_id
                    state["_name_from_parsing"] = True
                    emotion_system.current = "excited"
                    return f"Nice to meet you, {name}! I'll remember your voice from now on!"
                else:
                    pid, canonical = resolve_chat_identity(name)
                    if pid is not None:
                        state["speaker_id"] = pid
                        state["speaker_name"] = canonical
                    else:
                        state["speaker_name"] = name
                    state["_name_from_parsing"] = True
                    return f"Nice to meet you, {state['speaker_name']}! I'll remember you!"

    # What time is it
    if any(w in lower for w in ["what time", "how late"]):
        emotion_system.current = "happy"
        stats = party_stats.get_stats()
        return f"It's {stats['current_hour']}! Time flies when you're having fun in the bathroom!"

    # Quick greetings (≤2 words only — longer messages go to LLM)
    _char_lower = _CHARACTER_DISPLAY_NAME.lower()
    _greeting_set = {"hi", "hey", "yo", "sup", "hello", "hola", "hiya",
                     "howdy", "greetings", "heya", "ayo", "wassup",
                     "what's up", "whats up",
                     f"hey {_char_lower}", f"hi {_char_lower}",
                     f"hello {_char_lower}", f"yo {_char_lower}", f"sup {_char_lower}",
                     "sup dude", "hey man", "yo bro", "hey bro",
                     "hey dude", "sup bro", "hi there", "hey there",
                     "yo dude", "hey fam", "sup fam", "hi friend"}
    if _word_count <= 2 and lower.strip() in _greeting_set:
        emotion_system.current = "excited"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Hey there, {name}! Welcome to the bathroom! What can {_CHARACTER_DISPLAY_NAME} do for you?",
            f"Hey {name}! Ready to have some fun?",
            f"{name}! Great to see you! The party is THIS way! Well... we're already here!",
            f"Hey hey hey! {name}! Welcome! You picked the best room in the house!",
            f"Yo yo yo! {name}! What's going on? Tell {_CHARACTER_DISPLAY_NAME} everything!",
            f"{name}! Hello! You're looking like a million bucks today!",
        ])

    # Quick affirmations (≤2 words — "lol", "haha", "ok", "yes", "no")
    _laugh_match = _word_count <= 2 and (
        lower.strip() in {"lol", "lmao", "haha", "ha", "hahaha", "rofl", "😂", "🤣"}
        or re.fullmatch(r"(ha){2,}", lower.strip())  # hahahaha...
        or re.fullmatch(r"l+o+l+", lower.strip())  # looool, lolll
    )
    if _laugh_match:
        emotion_system.current = "laughing"
        return random.choice([
            "Ha ha ha! That's the spirit! Laughter is the best power-up!",
            f"You're laughing? {_CHARACTER_DISPLAY_NAME} loves it!",
            "Ha! You think THAT'S funny? Wait till you hear my jokes!",
            "Now THAT'S what I like to hear! Keep laughing, friend!",
        ])

    # Quick thank you handler (≤4 words)
    _ty_words = lower.split()
    if _word_count <= 4 and (any(w in lower for w in ["thanks", "thank you", "thx", "appreciate it"]) or "ty" in _ty_words):
        emotion_system.current = "happy"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Aww, you're welcome, {name}! That's what {_CHARACTER_DISPLAY_NAME} is here for!",
            f"No problem! My pleasure, {name}!",
            f"Hey, {name} — YOU'RE the one who made {_CHARACTER_DISPLAY_NAME}'s day! Thank YOU!",
            f"Anytime, {name}! {_CHARACTER_DISPLAY_NAME}'s always here if you need me!",
            f"You're too kind, {name}! Now let's keep this party going!",
        ])
    # Quick yes/no/ok acknowledgments (≤2 words, exact match)
    if _word_count <= 2:
        _stripped = lower.strip()
        if _stripped in {"yes", "yeah", "yep", "yup", "yea", "ya", "sure", "ok", "okay", "alright", "bet", "cool", "nice", "word"}:
            emotion_system.current = "happy"
            return random.choice([
                "That's the spirit!",
                "Okie dokie! What's next?",
                "Let's GO! What else you got?",
                f"Alrighty then! {_CHARACTER_DISPLAY_NAME}'s ready for more!",
            ])
        if _stripped in {"no", "nah", "nope", "naw", "no way"}:
            emotion_system.current = "mischievous"
            return random.choice([
                "Okie dokie! Maybe next time!",
                f"No? That's okay! {_CHARACTER_DISPLAY_NAME} respects your choices!",
                "Fair enough! What would you like instead?",
                f"Alright alright! No pressure from {_CHARACTER_DISPLAY_NAME}!",
            ])
    # Positive feedback handlers (≤5 words)
    if _word_count <= 5 and any(w in lower for w in ["that was fun", "that was awesome", "that was great",
                                                       "that was hilarious", "that was amazing", "so funny",
                                                       "you're funny", "you're hilarious", "you're awesome",
                                                       "you're the best", f"i love you {_char_lower}", "you're cool",
                                                       "this is fun", "this is awesome", "this is great",
                                                       "best party ever", "i love this", "so cool",
                                                       "this is amazing", "youre the best", "youre funny",
                                                       "youre awesome", "youre cool"]):
        emotion_system.current = "proud"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"{name}, you just made {_CHARACTER_DISPLAY_NAME}'s whole day! You're the real star here!",
            f"Aww shucks, {name}! You're making {_CHARACTER_DISPLAY_NAME} blush!",
            f"Ha! {_CHARACTER_DISPLAY_NAME} knows he's amazing — but hearing it from YOU makes it even better, {name}!",
            f"You think so?! That means a lot to {_CHARACTER_DISPLAY_NAME}! You're pretty awesome yourself, {name}!",
            f"NOW we're talking! {name} gets it! THIS is what a party is all about! WAHOO!",
        ])

    # "What's your name" — Mario identity handler
    if _word_count <= 5 and any(w in lower for w in ["what's your name", "whats your name", "who is this",
                                                       "what should i call you"]):
        emotion_system.current = "excited"
        return f"It's {_CHARACTER_DISPLAY_NAME}! Your bathroom guardian extraordinaire! I'm here to make sure everyone has a SUPER time!"

    # "I love you" — sweet party moment
    if _word_count <= 5 and any(w in lower for w in ["i love you", f"love you {_char_lower}", "love you so much",
                                                      f"marry me {_char_lower}", "youre my favorite"]):
        emotion_system.current = "loving"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Aww, {name}! {_CHARACTER_DISPLAY_NAME} loves you TOO! You're making my day!",
            f"{name}! That's the sweetest thing anyone's said to me! You're the best!",
            f"I love you too, {name}! We're best friends now! It's official!",
            f"{name}! You're making {_CHARACTER_DISPLAY_NAME}'s heart sing!",
            f"Aww shucks! If {_CHARACTER_DISPLAY_NAME} had a gold star for every time someone made him smile, you'd give me a GALAXY, {name}!",
        ])

    # "I hate you" / negative — playful resilience
    if _word_count <= 5 and any(w in lower for w in ["i hate you", "hate you", "you suck", "youre terrible",
                                                      "youre the worst", "you're terrible", "you're the worst"]):
        emotion_system.current = "sad"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"That hurts, {name}! But {_CHARACTER_DISPLAY_NAME}'s heart is tough — I'll bounce back! Give me another chance?",
            f"Ouch! But hey, {name} — stick around, {_CHARACTER_DISPLAY_NAME} grows on people!",
            f"...Okay but for real, {name}, what can I do better? {_CHARACTER_DISPLAY_NAME} wants to make you smile!",
            f"That's harsh, {name}! But {_CHARACTER_DISPLAY_NAME} never gives up! I'll keep trying!",
        ])

    # "Do you remember me" — memory check
    if _word_count <= 6 and any(w in lower for w in ["do you remember me", "remember me", "you know who i am",
                                                      "do you know me", "who am i"]):
        name = state.get("speaker_name")
        if name:
            emotion_system.current = "excited"
            return f"Of COURSE I remember you, {name}! How could {_CHARACTER_DISPLAY_NAME} forget?! Great to see you again!"
        else:
            emotion_system.current = "confused"
            return f"Hmm, {_CHARACTER_DISPLAY_NAME}'s memory is a little fuzzy! Tell me your name and I'll NEVER forget! What should I call you?"


    if any(w in lower for w in ["compliment", "say something nice", "make me feel", "cheer me up"]):
        base_compliment = idle_behavior.get_compliment()
        # Personalize if we know the person
        name = state.get("speaker_name")
        if name and state.get("speaker_id"):
            player_stats = memory_module.get_player_stats(state["speaker_id"])
            if player_stats:
                total_games = sum(s.get("games_played", 0) for s in player_stats.values())
                if total_games > 0:
                    return f"Hey {name}! {base_compliment} And you've played {total_games} games with me! You're a true champion!"
            person_info = memory_module.get_person_info(state["speaker_id"])
            if person_info and person_info.get("visit_count", 0) > 1:
                visits = person_info["visit_count"]
                return f"{name}! {base_compliment} You've visited me {visits} times! That makes you extra special!"
            if name:
                return f"{name}! {base_compliment}"
        emotion_system.current = Emotion.HAPPY
        return base_compliment

    # Challenge / trivia request → starts Mario Trivia game
    if _word_count <= 4 and any(w in lower for w in ["challenge", "quiz me", "test me", "trivia"]):
        return game_handlers.start_game("mario_trivia", state, game_config, emotion_system)

    # Dare → starts Bathroom Dare game
    if _word_count <= 7 and any(w in lower for w in ["dare me", "give me a dare", "i dare you", "can i get a dare", "gimme a dare"]):
        return game_handlers.start_game("bathroom_dare", state, game_config, emotion_system)

    # Hand wash reminder
    if any(w in lower for w in ["wash my hands", "should i wash", "hygiene", "wash hands", "hand wash", "soap"]):
        return idle_behavior.get_hand_wash_reminder()

    # How many visitors
    if any(w in lower for w in ["how many visitors", "how busy", "popular"]):
        stats = party_stats.get_stats()
        if stats['total_visits'] > 10:
            return f"We've had {stats['total_visits']} visits tonight! This bathroom is the hottest spot at the party!"
        else:
            return f"So far {stats['total_visits']} visits! The party is still warming up!"

    # Who was here last
    if any(w in lower for w in ["who was here", "who came", "last person", "before me"]):
        stats = party_stats.get_stats()
        last = stats.get('last_visitor_name')
        if last:
            return f"The last person before you was {last}! Nice person!"
        else:
            return f"You know, I've been here a while but my memory is fuzzy! Too many guests!"

    # Who am I / what do you know about me
    # Always fall through to LLM pipeline so VIP knowledge (Qdrant) gets injected
    if any(w in lower for w in ["who am i", "do you know me", "remember me", "know anything about me", "what do you remember"]):
        return None

    # How do I look
    if any(w in lower for w in ["how do i look", "do i look good", "am i pretty", "am i handsome"]):
        emotion_system.current = "loving"
        return random.choice([
            "You look absolutely magnificent! Like a Super Star!",
            "You're looking fantastic tonight! Ten out of ten!",
            "You look like a million bucks! Gold star for style!",
        ])

    # Roast me / light-hearted teasing
    if any(w in lower for w in ["roast me", "insult me", "make fun of", "burn me", "diss me"]):
        emotion_system.current = "mischievous"
        name = state.get("speaker_name") or "friend"
        roast_list = ROASTS[:]
        if not roast_list:
            return None  # fall through to LLM
        base_roast = _format_character_text(random.choice(roast_list)).format(name=name)

        # Build contextual roast using guest's conversation history
        try:
            person_id = state.get("speaker_id")
            recent_topics = memory_module.get_recent_conversations(person_id, limit=5) if person_id and memory_module else []
            roast_context = ""
            if recent_topics:
                roast_context = f" You talked about {recent_topics[0]} earlier — I could roast THAT too!"
        except Exception:
            roast_context = ""

        return base_roast + roast_context

    # Party stage / how's the party going
    if any(w in lower for w in ["how's the party", "party going", "party stage", "vibe check", "what's the vibe"]):
        party_duration = time.time() - party_stats.party_start_time
        stage = idle_behavior.get_party_stage(party_duration / 60)
        stats = party_stats.get_stats()
        return f"{stage} We've had {stats['total_visits']} visitors so far!"

    # What can you do / help — only for a SHORT, explicit capability question.
    # Guarded by word count (and "help me" dropped) so real requests like
    # "can you help me solve a dynamic programming problem" reach the LLM instead
    # of getting the canned abilities dump.
    if _word_count <= 7 and any(w in lower for w in ["what can you do", "what do you do", "what are your abilities", "your abilities", "your powers", "what can you help"]):
        emotion_system.current = Emotion.EXCITED
        return (
            "I can do so much! Ask for a joke, trivia, song, dare, roast, nickname, "
            "pickup line, fortune, tongue twister, story, rap, motivation, bathroom tip, "
            f"or just chat! Play Trivia, Name That Character, Bathroom Dare, Story Builder, "
            "Would You Rather, Simon Says, 20 Questions, Truth or Dare, Riddles, Word Chain, "
            "Rapid Fire Quiz, Karaoke, Rock Paper Scissors, Hangman, Hot Takes, or Never Have I Ever! "
            "Check achievements, leaderboard, trending, party phase, "
            "party stats, conversation summary, holiday, crew, or sound catalog!"
        )

    # Tell me about yourself
    if any(w in lower for w in ["about yourself", "who are you", "introduce yourself", "what are you"]):
        emotion_system.current = "proud"
        return (
            f"I'm {_CHARACTER_DISPLAY_NAME}! Your friendly bathroom guardian! "
            "I'm your host tonight, and I'm the DJ of this bathroom!"
        )

    # How old are you / age question
    if _word_count <= 7 and any(w in lower for w in ["how old are you", "your age", "what age", "when were you born"]):
        emotion_system.current = "proud"
        return random.choice([
            f"Age is just a number! {_CHARACTER_DISPLAY_NAME} is timeless!",
            f"Age? {_CHARACTER_DISPLAY_NAME} never ages! It's the vibes!",
            f"Old enough to know better, young enough to party! That's {_CHARACTER_DISPLAY_NAME}!",
            f"Born to party, never to age! {_CHARACTER_DISPLAY_NAME} is eternal!",
        ])

    # Are you married / girlfriend questions
    if _word_count <= 7 and any(w in lower for w in ["married", "girlfriend", "single", "wife",
                                                       "dating anyone", "your girl", "your woman",
                                                       "are you taken", "in a relationship"]):
        emotion_system.current = "loving"
        return random.choice([
            f"It's complicated! {_CHARACTER_DISPLAY_NAME} is focused on the party right now!",
            f"{_CHARACTER_DISPLAY_NAME} is married to adventure! Between us, I have something special going on! Don't tell the tabloids!",
            f"Single? With this much charisma?! Please! But my relationship status is 'it's complicated'!",
            f"{_CHARACTER_DISPLAY_NAME} doesn't kiss and tell! But I'm definitely taken... by this PARTY!",
        ])

    # How tall are you / physical questions
    if _word_count <= 7 and any(w in lower for w in ["how tall", "your height", "how short", "how much do you weigh"]):
        emotion_system.current = "mischievous"
        return random.choice([
            f"I'm compact and proud! {_CHARACTER_DISPLAY_NAME} can jump five times my height! Show me a tall person who can do THAT!",
            f"{_CHARACTER_DISPLAY_NAME} is the perfect height for maximum style and agility!",
            f"Short? I prefer 'aerodynamically compact'! It's a feature, not a bug!",
        ])

    # What's your favorite [thing] questions
    if _word_count <= 8 and "favorite" in lower:
        emotion_system.current = "happy"
        if any(w in lower for w in ["food", "eat", "meal", "dish"]):
            return random.choice([
                f"Oh man, {_CHARACTER_DISPLAY_NAME} loves a good feast! Can't go wrong with comfort food!",
                f"Everything tastes better at a party! {_CHARACTER_DISPLAY_NAME}'s weakness is snacks!",
            ])
        if any(w in lower for w in ["color", "colour"]):
            return f"{_CHARACTER_DISPLAY_NAME}'s favorite color? You're looking at it! Style speaks for itself!"
        if any(w in lower for w in ["game", "video game", "mario game"]):
            return random.choice([
                "That's like asking a parent their favorite child! Too many good ones to pick!",
                f"ALL of them! {_CHARACTER_DISPLAY_NAME} doesn't play favorites... okay maybe a little!",
            ])
        if any(w in lower for w in ["song", "music"]):
            return f"Music is {_CHARACTER_DISPLAY_NAME}'s weakness! I love a good beat! CHEF'S KISS!"
        if any(w in lower for w in ["movie", "film"]):
            return f"Hard to pick just one! But anything with action and heart — that's {_CHARACTER_DISPLAY_NAME}'s jam!"
        return random.choice([
            f"Ooh, favorites! {_CHARACTER_DISPLAY_NAME} loves too many things! I have too many favorites!",
            f"That's a hard question! {_CHARACTER_DISPLAY_NAME} loves too many things! Can I pick ALL of them?!",
        ])

    # Meta questions — "are you real", "are you AI", "are you a robot"
    if _word_count <= 6 and any(w in lower for w in ["are you real", "are you ai", "are you a robot",
                                                      "are you a bot", "are you human", "are you alive",
                                                      "are you a computer", "you're not real",
                                                      "you're a robot", "you're ai"]):
        emotion_system.current = "mischievous"
        return random.choice([
            f"Real?! I'm MORE than real! I'm SUPER real! {_CHARACTER_DISPLAY_NAME} is right here!",
            f"AI?! I'm {_CHARACTER_DISPLAY_NAME}! Does THAT sound like a robot to you?!",
            f"Robot?! {_CHARACTER_DISPLAY_NAME} is 100% genuine! Look at this personality!",
            f"I'm as real as it gets, friend! Now are WE gonna have fun or are you gonna keep questioning my existence?!",
            f"Listen, {_CHARACTER_DISPLAY_NAME} has been doing this for a while and I'm still going strong! Totally real!",
            f"Me? A bot? Ha! Can a bot do THIS?! See?! Totally real!",
        ])

    # Someone is throwing up / feeling sick — be genuinely caring but still Mario
    _sick_triggers = ["throwing up", "throw up", "threw up", "vomit", "puke", "puking",
                      "nauseous", "nausea", "gonna be sick", "feeling sick", "about to puke",
                      "barfing", "barf", "hurling", "queasy", "dont feel so good",
                      "don't feel so good", "dont feel good", "don't feel good",
                      "feel like throwing up", "stomach hurts", "gonna throw up",
                      "about to throw up", "feel like puking"]
    # Friend reported sick ("my friend is throwing up", "my girlfriend is puking", etc.)
    _friend_sick_patterns = ["friend is", "buddy is", "girlfriend is", "boyfriend is",
                             "friend's", "buddy's", "homie is", "girl is", "guy is",
                             "someone is", "somebody is", "they're"]
    _is_friend_sick = any(fp in lower for fp in _friend_sick_patterns) and any(w in lower for w in _sick_triggers)
    if _is_friend_sick:
        emotion_system.current = "worried"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Okay {name}, go grab them some water — small sips, not big gulps. Cold towel on the neck if there is one. They'll be fine.",
            f"Tell them nose breathing, not mouth breathing. And cold water on the back of the neck. That's the move, {name}. Go help your friend.",
            f"Alright, {name} — water, cold towel, sit them down if they're standing. And tell them {_CHARACTER_DISPLAY_NAME} said they're gonna be fine. Because they are.",
            f"Been there. Same thing. Get them water, {name}. Small sips. If they need to sit on the floor, let them. Floor's clean.",
            f"Go be a good friend, {name}. Water, cold cloth, and just be there. That's all anyone needs. {_CHARACTER_DISPLAY_NAME}'s got the bathroom covered.",
        ])
    if any(w in lower for w in _sick_triggers):
        emotion_system.current = "worried"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Look {name}, I've seen worse. Cold water on your neck, breathe through your nose.",
            f"Okay {name}, real talk — nose breathing, not mouth. There's water in the sink. Small sips. This passes.",
            f"Hey {name}, you made it to the bathroom. That's already a win. Splash cold water on your face, you'll be alright.",
            f"{name}, listen — nobody at this party is gonna know about this except me. Wet your face, take a breath.",
            f"You're already doing better than most, {name}. Water. Small sips.",
            f"Hey {name}. I'll guard this door. Nobody's coming in. There's water right there — small sips, not big ones.",
            f"{name}, the toilet's right there, floor's clean, and I've seen it all. This? This is nothing. Breathe.",
            f"Okay here's what we do, {name}. Cold water, back of the neck. Trust me on this one.",
            f"{name}, between you and me, this happens to the best of us. Sit on the floor if you need to. No judgment.",
            f"Hey {name}, you're in the right room for this. Cold water's in the sink, towels are right there. Take your time.",
        ])

    # Recovery from sickness — clear sick mood
    _recovery_words = ["feeling better", "i'm better", "im better", "i'm okay", "im okay",
                       "i'm fine", "im fine", "i'm good", "im good", "all better",
                       "feeling good", "much better", "recovered", "not sick"]
    if any(w in lower for w in _recovery_words) and state.get("_detected_mood") == "sick":
        state["_detected_mood"] = None
        emotion_system.current = "happy"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"There it is! {name}'s back. Honestly I was about to start charging rent for that floor spot.",
            f"Look at {name}, making a comeback! Rinse your mouth out, splash some water on your face, and get back out there.",
            f"Welcome back to the land of the living, {name}. Told you it passes. Go grab some water — real water, not whatever got you here.",
            f"{name} returns! If anyone asks, you were in here fixing your hair. Our secret.",
            f"And just like that, {name} is back. {_CHARACTER_DISPLAY_NAME} never doubted you. Well, maybe for a second there. But you're good now.",
        ])

    # Goodbye/goodnight
    if _word_count <= 5 and any(w in lower for w in ["goodbye", "goodnight", "see ya", "gotta go", "leaving", "bye bye",
                                                       "bye", "later", "peace out", "i'm out", "im out", "catch you later",
                                                       "see you later", "gtg", "good night"]):
        emotion_system.current = "happy"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"See ya later, alligator! Don't forget to wash your hands!",
            f"Bye bye! Come back soon! The bathroom misses you already!",
            f"Until next time, {name}!",
            f"Later, {name}! Remember — you're number one in {_CHARACTER_DISPLAY_NAME}'s book!",
            f"Peace out, {name}! May the stars guide your way!",
        ])

    # Drunk / tipsy / wasted — fun but caring
    if any(w in lower for w in ["im drunk", "i'm drunk", "so drunk", "wasted", "hammered",
                                 "i'm tipsy", "im tipsy", "too many drinks", "i'm faded",
                                 "im faded", "im wasted", "i'm wasted"]):
        emotion_system.current = "mischievous"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Ha ha! {name} found the good drinks! {_CHARACTER_DISPLAY_NAME} says drink some water too! Hydration is the real power-up!",
            f"{name} is in Star Mode! But remember, even {_CHARACTER_DISPLAY_NAME} needs water between rounds!",
            f"You're not drunk, {name}, you're just... under the effects of the vibes! Drink water!",
            f"{name}! You're wobbling more than usual! Water is your friend!",
            f"{name}, you're partying hard! Have some water, champion. The bathroom sink is right there!",
        ])

    # Bored — suggest activities
    if _word_count <= 5 and any(w in lower for w in ["im bored", "i'm bored", "this is boring",
                                                       "so bored", "nothing to do", "entertain me"]):
        emotion_system.current = "excited"
        return random.choice([
            "BORED?! In MY bathroom?! Impossible! Let's play a game! Say 'trivia' or 'rock paper scissors' or 'would you rather'!",
            f"Bored? BORED?! {_CHARACTER_DISPLAY_NAME} will NOT allow boredom! Ask me for a joke, a dare, a roast, or let's play a game!",
            f"Nobody leaves {_CHARACTER_DISPLAY_NAME}'s bathroom bored! Want a joke? A song? A fortune? A game? Pick one!",
            "Bored is just 'board' with an E! Let's play something! Trivia? Truth or dare? Riddles?",
        ])

    # Shut up / be quiet — playful response instead of slow LLM
    if _word_count <= 4 and any(w in lower for w in ["shut up", "be quiet", "shush", "shh", "zip it", "silence",
                                                      "stop talking", "quiet down", "hush"]):
        emotion_system.current = "sad"
        name = state.get("speaker_name") or "friend"
        return random.choice([
            f"Okay okay, {_CHARACTER_DISPLAY_NAME} will be quiet... for about five seconds. That's my record!",
            f"*whispers* Is this quiet enough? ...Sorry, couldn't help it!",
            f"You want me to be quiet?! But silence is my worst enemy! Okay fine, {name}...",
            f"Shh mode: ACTIVATED. ... ... ... Okay I can't do it. What's up, {name}?",
            f"Quiet?! {_CHARACTER_DISPLAY_NAME}?! But I'll try... for you.",
        ])

    # Where is the bathroom — Mario IS in the bathroom, so this is funny
    if _word_count <= 6 and any(w in lower for w in ["where is the bathroom", "wheres the bathroom", "where's the bathroom",
                                                      "need the bathroom", "bathroom where", "find the bathroom"]):
        emotion_system.current = "mischievous"
        return random.choice([
            "You're IN it! You found it! Achievement unlocked: Bathroom Located!",
            f"You're already HERE! This IS the bathroom! {_CHARACTER_DISPLAY_NAME} is your proof!",
            "Look around! Tiles? Check! Toilet? Check! Party host? DOUBLE CHECK! You made it!",
            f"The bathroom? You're standing in it! I'm right here!",
        ])

    # Drink / food requests — party direction
    if _word_count <= 6 and any(w in lower for w in ["get a drink", "where are the drinks", "need a drink",
                                                      "where's the bar", "wheres the bar", "need water",
                                                      "get some water", "thirsty"]):
        emotion_system.current = "happy"
        return random.choice([
            f"Drinks are out there at the party! {_CHARACTER_DISPLAY_NAME} can't serve drinks but I CAN serve up some fun!",
            "The bar's outside! But hey, the bathroom sink has unlimited water! Five stars!",
            f"Thirsty? There's drinks at the party! But if you want bathroom water, {_CHARACTER_DISPLAY_NAME} won't judge!",
            "The refreshments are out by the party! But stay and chat a bit first!",
        ])

    # Give me a nickname
    if any(w in lower for w in ["give me a nickname", "nickname me", "what's my nickname", "call me something"]):
        emotion_system.current = "mischievous"
        name = state.get("speaker_name") or "friend"
        if NICKNAMES:
            return _format_character_text(random.choice(NICKNAMES)).format(name=name)
        return None

    # Rate the party / how good is the party
    if any(w in lower for w in ["rate the party", "party rating", "rate this party", "how good is the party"]):
        stats = party_stats.get_stats()
        visits = stats['total_visits']
        if visits > 25:
            return f"This party gets TEN out of TEN! {visits} bathroom visits means EVERYONE is having a great time!"
        elif visits > 10:
            return f"{_CHARACTER_DISPLAY_NAME} gives this party an EIGHT out of ten! {visits} visits and counting! Let's keep it going!"
        elif visits > 3:
            return f"So far it's SIX out of ten! Only {visits} visits... but the night is young!"
        else:
            return f"Hmm, only {visits} visits so far. I give it a FOUR but it's just getting started! More guests incoming!"

    # Tell my fortune / fortune teller
    if any(w in lower for w in ["tell my fortune", "fortune", "predict", "future", "crystal ball", "psychic"]):
        emotion_system.current = "mischievous"
        if FORTUNES:
            return _format_character_text(random.choice(FORTUNES))
        return None

    # How are you feeling / mood — only direct mood questions, not complex "how do you feel about X"
    if _word_count <= 6 and any(w in lower for w in ["how are you feeling", "what's your mood", "how are you doing", "you okay", "how do you feel", "are you happy"]):
        current_mood = emotion_system.current
        return _format_character_text(MOOD_RESPONSES.get(current_mood, f"I'm doing great! It's always a good day to be {_CHARACTER_DISPLAY_NAME}!"))

    # Would You Rather game (Mario Edition)
    if _word_count <= 5 and any(w in lower for w in ["would you rather", "rather game", "choice game", "this or that"]):
        return game_handlers.start_game("wyr_mario", state, game_config, emotion_system)

    # Tongue twister
    if any(w in lower for w in ["tongue twister", "say something hard", "twist my tongue"]):
        emotion_system.current = "mischievous"
        if TWISTERS:
            return _format_character_text(random.choice(TWISTERS))
        return None

    # Tell me a story / story time → starts Story Builder game
    if _word_count <= 7 and any(w in lower for w in ["tell me a story", "story time", "bedtime story", "once upon a time"]):
        return game_handlers.start_game("story_builder", state, game_config, emotion_system)

    # Pickup line
    if any(w in lower for w in ["pickup line", "flirt", "rizz", "pick up line", "smooth line"]):
        emotion_system.current = "loving"
        if PICKUP_LINES:
            return _format_character_text(random.choice(PICKUP_LINES))
        return None

    # Bathroom tip / etiquette
    if any(w in lower for w in ["bathroom tip", "etiquette", "bathroom advice", "bathroom rule"]):
        emotion_system.current = "proud"
        if BATHROOM_TIPS:
            return _format_character_text(random.choice(BATHROOM_TIPS))
        return None

    # Rap for me
    if any(w in lower for w in ["rap for me", "freestyle", "spit bars", "drop a beat", "rap battle"]):
        emotion_system.current = "excited"
        if RAPS:
            return _format_character_text(random.choice(RAPS))
        return None

    # Motivate me / encouragement
    _sad_triggers = ["motivate me", "motivation", "inspire me", "i need encouragement",
                     "i'm sad", "feeling down", "i'm down", "feeling terrible", "everything is terrible",
                     "having a bad day", "i'm depressed", "so sad", "really sad", "really down",
                     "i feel bad", "i feel awful", "life sucks", "i'm upset",
                     "this sucks", "this is boring", "i'm bored", "so bored", "i hate this",
                     "nobody likes me", "no one likes me", "i have no friends", "i'm lonely",
                     "i feel alone", "i don't belong", "i'm not good enough", "i want to go home",
                     "i'm so tired of", "everything sucks", "nothing is fun"]
    _sad_regex = re.search(r"(?:feeling|i'?m)\s+(?:\w+\s+)?(?:down|sad|terrible|awful|bad|upset|depressed|low|miserable)", lower)
    if any(w in lower for w in _sad_triggers) or _sad_regex:
        emotion_system.current = "loving"
        if MOTIVATIONS:
            return _format_character_text(random.choice(MOTIVATIONS))
        return None

    # Confession mode
    if any(w in lower for w in ["i have a confession", "confess", "i need to tell you something", "can i tell you a secret"]):
        emotion_system.current = "surprised"
        if CONFESSIONS:
            return _format_character_text(random.choice(CONFESSIONS))
        return None

    # Shock/surprise reaction — common when guests first see Mario
    if _word_count <= 5 and any(w in lower for w in ["what the fuck", "what the hell", "wtf", "holy shit",
                                                       "oh my god", "holy crap", "no way", "no fucking way",
                                                       "are you serious", "what is this", "what the heck",
                                                       "what is happening", "am i dreaming"]):
        emotion_system.current = "excited"
        return random.choice([
            f"That's the reaction I LOVE! Yes, it's {_CHARACTER_DISPLAY_NAME}! In a BATHROOM! At a PARTY! Life is beautiful!",
            "Ha ha ha! Your FACE right now! Yes, I'm real! Well, real enough! Welcome to the best bathroom in the world!",
            "That's what EVERYONE says! Then they stay for twenty minutes talking to me! You're gonna love it here!",
            "Your reaction is priceless! I should charge admission! Welcome, welcome!",
            f"Yes this is happening! {_CHARACTER_DISPLAY_NAME} is in the bathroom and I'm FABULOUS! Any questions? I've got answers AND games!",
        ])

    # Memory quiz
    if any(w in lower for w in ["quiz me", "test me", "memory quiz", "what did i tell you"]):
        if state["speaker_id"]:
            memories = memory_module.get_memories_for_context(state["speaker_id"])
            if memories and len(memories) > 1:
                fact = random.choice(memories)
                emotion_system.current = "mischievous"
                return f"Okay quiz time! Is it true that {fact}? Ha ha, I already know the answer! {_CHARACTER_DISPLAY_NAME} remembers EVERYTHING!"
        return "Hmm, I don't know enough about you yet for a quiz! Tell me some things about yourself first!"

    # Compliment battle
    if any(w in lower for w in ["compliment battle", "out-compliment", "who's nicer"]):
        emotion_system.current = "loving"
        return random.choice([
            "You want a compliment battle?! YOU'RE the most amazing person in this bathroom! Your turn!",
            "Oh it's ON! You're so cool that even ice blocks are jealous! Top THAT!",
            "Compliment battle?! You're so awesome that Power Stars follow YOU around! Ha!",
        ])

    # Count to ten / counting game
    if any(w in lower for w in ["count to ten", "count for me", "can you count"]):
        emotion_system.current = "happy"
        return f"One! Two! Three! Four! FIVE! Six! Seven! EIGHT! Nine! TEN! {_CHARACTER_DISPLAY_NAME} can count! Impressed?"

    # What time is it (enhanced)
    if any(w in lower for w in ["what time", "what's the time", "time is it"]):
        now_dt = datetime.now()
        hour = now_dt.hour
        minute = now_dt.minute
        ampm = "AM" if hour < 12 else "PM"
        display_hour = hour % 12 or 12
        time_str = f"{display_hour}:{minute:02d} {ampm}"
        if hour >= 2 and hour < 6:
            return f"It's {time_str}! It's so late! Even the neighbors are sleeping by now!"
        elif hour >= 22 or hour < 2:
            return f"It's {time_str}! The night is still young! Let's keep partying!"
        else:
            return f"It's {time_str}! Perfect time for a party!"

    # --- Interactive Game Modes ---

    # Simon Says
    if _word_count <= 4 and any(w in lower for w in ["simon says", "play simon", "let's play simon"]):
        return game_handlers.start_game("simon_says", state, game_config, emotion_system)

    # 20 Questions
    if _word_count <= 4 and any(w in lower for w in ["20 questions", "twenty questions", "play 20", "play twenty"]):
        return game_handlers.start_game("twenty_questions", state, game_config, emotion_system)

    # Truth or Dare
    if _word_count <= 5 and any(w in lower for w in ["truth or dare", "play truth", "let's play truth"]):
        return game_handlers.start_game("truth_or_dare", state, game_config, emotion_system)

    # Stop any active game
    if any(w in lower for w in ["stop game", "quit game", "end game", "stop playing", "quit playing"]):
        if state["_active_game"]:
            game = state["_active_game"]
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_system.current = Emotion.HAPPY
            return f"Game over! Thanks for playing {game.replace('_', ' ')}! That was fun!"
        return "No game is running right now! Want to start one? Just say 'play a game' or name a specific game!"

    # Bare "stop" / "quit" with no game active — quick response instead of LLM
    if _word_count == 1 and lower.strip() in {"stop", "quit", "exit", "cancel"}:
        if state["_active_game"]:
            game = state["_active_game"]
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_system.current = Emotion.HAPPY
            return f"Game over! Final score: {state.get('_game_state', {}).get('score', 0)}! Thanks for playing {game.replace('_', ' ')}!"
        emotion_system.current = "confused"
        return random.choice([
            "Stop what? There's no game running! Want to play something? Just ask!",
            "Hmm, nothing to stop! How about we START something instead? Say 'play a game'!",
            "Stop?! But we haven't even started! Want to play trivia, RPS, or something else?",
        ])

    # Riddle game
    if _word_count <= 4 and any(w in lower for w in ["riddle", "play riddle", "riddle me", "tell me a riddle"]):
        return game_handlers.start_game("riddles", state, game_config, emotion_system)

    # Word Chain game
    if _word_count <= 5 and any(w in lower for w in ["word chain", "play word chain", "word game", "last letter"]):
        return game_handlers.start_game("word_chain", state, game_config, emotion_system)

    # Karaoke mode
    if _word_count <= 4 and any(w in lower for w in ["karaoke", "sing along", "sing with me", "let's sing"]):
        return game_handlers.start_game("karaoke", state, game_config, emotion_system)

    # Achievements
    if any(w in lower for w in ["achievements", "my badges", "my awards", "what have i earned", "my stats"]):
        badges = []
        if state.get("speaker_name"):
            badges.append(f"🏅 Named Visitor (told {_CHARACTER_DISPLAY_NAME} your name!)")
        stats = party_stats.get_stats()
        if stats.get("total_visits", 0) >= 1:
            badges.append("🎪 Party Starter (visited the bathroom!)")
        if stats.get("total_visits", 0) >= 5:
            badges.append("🔄 Frequent Flusher (5+ visits!)")
        if stats.get("total_visits", 0) >= 10:
            badges.append("👑 Bathroom Royalty (10+ visits!)")
        hour = datetime.now().hour
        if hour >= 0 and hour < 5:
            badges.append("🦉 Night Owl (up past midnight!)")
        if len(state["conversation_history"]) >= 10:
            badges.append("💬 Chatty Cathy (10+ messages!)")
        # Visitor milestone badges based on personal visit count
        if state.get("speaker_id"):
            person_info = memory_module.get_person_info(state["speaker_id"])
            if person_info:
                visit_count = person_info.get("visit_count", 0)
                if visit_count >= 1:
                    badges.append("🌟 First Timer")
                if visit_count >= 5:
                    badges.append("🏆 Regular")
                if visit_count >= 10:
                    badges.append("💎 VIP")
                if visit_count >= 25:
                    badges.append("👑 Bathroom Legend")
        if not badges:
            return "No badges yet! Talk to me, tell me your name, and keep visiting to earn achievements!"
        badge_list = " ".join(badges)
        emotion_system.current = Emotion.PROUD
        return f"YOUR ACHIEVEMENTS! {badge_list} Keep going for more!"

    # Party phase check
    if any(w in lower for w in ["party phase", "what phase", "party energy", "energy level", "how's the party"]):
        stats = party_stats.get_stats()
        hour = datetime.now().hour
        visits = stats.get("total_visits", 0)
        if hour < 20:
            phase = "PRE-GAME! The party hasn't even started yet! Early bird gets the worm!"
        elif hour < 22:
            phase = "WARM UP! People are arriving and the energy is building!"
        elif hour < 1 or (hour >= 22):
            phase = "PEAK PARTY! Maximum energy! The bathroom is BUMPING!"
        elif hour < 3:
            phase = "AFTER HOURS! The real ones are still here! Respect!"
        else:
            phase = "WIND DOWN! The party's winding down but the memories last forever!"
        emotion_system.current = Emotion.EXCITED
        return f"PARTY PHASE: {phase} Total visits: {visits}!"

    # Party Leaderboard
    if any(w in lower for w in ["leaderboard", "who visited most", "party champions", "top visitors"]):
        try:
            with sqlite3.connect(party_stats._db_path()) as _lconn:
                rows = _lconn.execute("""
                    SELECT person_name, COUNT(*) as cnt 
                    FROM party_visits 
                    WHERE person_name != 'Unknown visitor' 
                    GROUP BY person_name 
                    ORDER BY cnt DESC LIMIT 5
                """).fetchall()
            if not rows:
                return "No leaderboard yet! You could be number one! Wahoo!"
            board = " ".join([f"#{i+1} {r[0]} ({r[1]} visits)!" for i, r in enumerate(rows)])
            emotion_system.current = Emotion.PROUD
            return f"PARTY LEADERBOARD! {board} Who's the champion?"
        except Exception:
            return "The leaderboard is broken! But YOU'RE number one in my heart!"

    # Trending topics — what people have been talking about
    if any(w in lower for w in ["trending", "what are people talking about", "popular topics", "hot topics"]):
        try:
            trending = memory_module.get_trending_topics(5)
            if not trending:
                return "Nobody's told me anything yet! Be the first to share something interesting!"
            topics = ", ".join([f"{t['topic']} ({t['count']}x)" for t in trending])
            emotion_system.current = Emotion.EXCITED
            return f"TRENDING at this party! People are talking about: {topics}! What's YOUR hot take?"
        except Exception:
            return "My trend tracker is having a break! Tell me something interesting!"

    # Reset party
    if any(w in lower for w in ["reset party", "new party", "start new party", "reset the party"]):
        party_stats.reset_party()
        emotion_system.current = Emotion.EXCITED
        return "New party started! The counter is reset! Let's make this the BEST party ever!"

    # Forget me (privacy — delete speaker voice data)
    if any(w in lower for w in ["forget me", "delete my voice", "remove my data", "forget my voice"]):
        if state.get("speaker_id"):
            try:
                speaker_id.delete_speaker(state["speaker_id"])
                emotion_system.current = Emotion.WORRIED
                return f"Okay... {_CHARACTER_DISPLAY_NAME} will forget your voice. *sniff* It's like you were never here! Privacy respected!"
            except Exception:
                return "I tried to forget you but my memory is stuck! Try again later!"
        return "I don't even know who you are yet! Can't forget what I don't know! Ha!"

    # Crew detection
    if any(w in lower for w in ["crew", "squad", "group", "who came together", "friends group"]):
        crews = party_stats.detect_crew()
        if not crews:
            emotion_system.current = Emotion.CONFUSED
            return "I haven't seen any groups arrive together yet! Are you flying solo?"
        crew_strs = [" & ".join(c) for c in crews[-3:]]
        emotion_system.current = Emotion.EXCITED
        return f"Crews I've spotted tonight: {'; '.join(crew_strs)}! Are you part of a squad?"

    # Conversation summary
    if any(w in lower for w in ["our conversation", "what did we talk about", "conversation summary", "recap", "summarize"]):
        if state["speaker_id"]:
            recent = memory_module.get_recent_conversations(state["speaker_id"], limit=6)
            if recent:
                topics_str = ", ".join(recent[:5])
                emotion_system.current = Emotion.HAPPY
                return f"We've talked about: {topics_str}! Great conversation, {state['speaker_name'] or 'friend'}!"
        return "We just met! Let's make some memories first!"

    # Holiday check
    if any(w in lower for w in ["holiday", "what day is it", "special day", "celebration"]):
        holiday = _detect_holiday()
        if holiday:
            emotion_system.current = Emotion.EXCITED
            return f"It's {holiday} today! How exciting! Let's celebrate!"
        return f"No special holiday today, but EVERY day is special when {_CHARACTER_DISPLAY_NAME} is here!"

    # Rapid-fire quiz game — only direct requests
    if _word_count <= 4 and any(w in lower for w in ["rapid fire", "rapid quiz", "speed quiz", "quick quiz", "rapid round"]):
        return game_handlers.start_game("rapid_fire", state, game_config, emotion_system)

    # Rock Paper Scissors
    if _word_count <= 5 and any(w in lower for w in ["rock paper scissors", "battle mode", "rps", "let's battle"]):
        return game_handlers.start_game("rock_paper_scissors", state, game_config, emotion_system)

    # Hangman
    if _word_count <= 3 and any(w in lower for w in ["hangman", "play hangman", "guess the word"]):
        return game_handlers.start_game("hangman", state, game_config, emotion_system)

    # Hot Takes — only start game for direct requests, not "what is your hot take on X"
    if _word_count <= 4 and any(w in lower for w in ["hot takes", "hot take", "unpopular opinion", "spicy take"]):
        return game_handlers.start_game("hot_takes", state, game_config, emotion_system)

    # Never Have I Ever
    if any(w in lower for w in ["never have i ever", "never ever", "play never"]):
        return game_handlers.start_game("never_have_i_ever", state, game_config, emotion_system)

    # Mario Trivia (additional triggers beyond "trivia"/"quiz me" above)
    if any(w in lower for w in ["play trivia", "mario trivia", "trivia game", f"quiz me {_char_lower}"]):
        return game_handlers.start_game("mario_trivia", state, game_config, emotion_system)

    # Name That Character (Speed Round)
    if _word_count <= 5 and any(w in lower for w in ["name that character", "guess the character", "who am i describing", "character quiz", "speed round"]):
        return game_handlers.start_game("name_that_character", state, game_config, emotion_system)

    # Bathroom Dare (additional triggers beyond "dare me" above)
    if any(w in lower for w in ["bathroom dare", "dare challenge"]):
        return game_handlers.start_game("bathroom_dare", state, game_config, emotion_system)

    # Story Builder (additional triggers beyond "tell me a story"/"story time" above)
    if any(w in lower for w in ["story builder", "build a story", "let's write a story"]):
        return game_handlers.start_game("story_builder", state, game_config, emotion_system)

    # "What games" — list available games
    if _word_count <= 7 and any(w in lower for w in ["what games", "list games", "which games", "games can we play",
                                 "what can we play", "what can i play", "available games"]):
        return (f"{_CHARACTER_DISPLAY_NAME}'s got a BUNCH of games! 🎮 "
                "Trivia, Rock Paper Scissors, Truth or Dare, Simon Says, 20 Questions, "
                "Riddles, Hangman, Word Chain, Hot Takes, Story Builder, Name That Character, "
                "and Bathroom Dares! Just say the name to start! Or say 'play a game' and I'll pick one!")

    # "Play a game" — random game picker (FALLBACK: must be AFTER all specific game triggers)
    if _word_count <= 5 and any(w in lower for w in ["play a game", "play game", "surprise game", "random game",
                                 "pick a game", "any game", "let's play", "wanna play"]):
        if not state.get("_active_game"):
            picked = game_handlers.pick_random_game(state)
            return game_handlers.start_game(picked, state, game_config, emotion_system)

    # Sound catalog
    if any(w in lower for w in ["sound catalog", "what sounds", "sound effects", "sound list"]):
        sounds = ["greeting", "goodbye", "coin", "oneup", "powerup", "correct", "wrong", "hint",
                   "game_over", "achievement", "announcement", "fireball", "star", "pipe"]
        return f"I've got these sound effects: {', '.join(sounds)}! The client plays them when I send hints!"

    # Personality mode switching
    for mode_key, mode_data in PERSONALITY_MODES.items():
        if any(trigger in lower for trigger in mode_data["triggers"]):
            if mode_key == "normal":
                state["_personality_mode"] = None
            else:
                state["_personality_mode"] = mode_key
            emotion_system.current = Emotion.EXCITED
            return mode_data["intro"]

    # Bathroom facts
    if any(w in lower for w in ["bathroom fact", "fun bathroom fact", "hygiene fact", "toilet fact"]):
        emotion_system.current = Emotion.EXCITED
        if BATHROOM_FACTS:
            return _format_character_text(random.choice(BATHROOM_FACTS))
        return None

    # Party suggestions / what should I do
    if any(w in lower for w in ["what should i do", "i'm bored at the party", "suggest something", "party suggestion"]):
        emotion_system.current = Emotion.EXCITED
        if PARTY_SUGGESTIONS:
            return _format_character_text(random.choice(PARTY_SUGGESTIONS))
        return None

    # Bathroom emergencies — toilet paper
    tp_triggers = ["no toilet paper", "out of toilet paper", "no paper", "need toilet paper", "no tp"]
    if any(t in lower for t in tp_triggers):
        return random.choice([
            "EMERGENCY! Check under the sink for backup rolls! If not, I got nothing. HELP!",
            "Code Red! Code Red! No toilet paper! This is the worst! Someone get the emergency supplies!",
            "NOT a good moment! Someone get the emergency supplies! Under the sink, check the cabinet!",
            "As a professional, I can tell you: ALWAYS check for paper BEFORE you sit down! But let's solve this crisis!",
            "NO PAPER?! This is the final boss of bathroom problems! Check the cabinet, the closet, anywhere!",
        ])

    # Bathroom emergencies — need help
    help_triggers = ["need help", "help me", "i'm stuck", "emergency"]
    if any(t in lower for t in help_triggers):
        return random.choice([
            f"{_CHARACTER_DISPLAY_NAME} is here to help! What do you need?",
            "HELP is on the way! Well, I can't actually leave this screen, but I'm great moral support!",
            "Don't worry friend! Whatever the problem is, we'll figure it out together! What's wrong?",
            f"{_CHARACTER_DISPLAY_NAME} to the rescue! Tell me what's happening and I'll do my best to help!",
        ])

    # Bathroom emergencies — courtesy / smell
    courtesy_triggers = ["it smells", "smells bad", "stinky", "something smells"]
    if any(t in lower for t in courtesy_triggers):
        return random.choice([
            "Have you tried the courtesy flush? It's like a checkpoint save but for air quality!",
            "I've smelled MUCH worse! This is nothing! Trust me!",
            f"Quick tip from {_CHARACTER_DISPLAY_NAME}: the fan switch is usually by the door! And maybe crack a window!",
            "Even I can't handle this! Try the air freshener if there is one!",
        ])

    # Plumber-specific humor — only short/direct mentions, let complex requests go to LLM
    plumber_triggers = ["plumber", "plumbing", "pipes", "fix the toilet", "clogged"]
    if _word_count <= 5 and any(t in lower for t in plumber_triggers):
        return random.choice([
            "As a bathroom expert, I can confirm: this pipe network needs some work!",
            f"Plumbing? {_CHARACTER_DISPLAY_NAME} knows a thing or two about pipes!",
            "You know, before I was hosting parties, I was... well, I was always hosting parties! But pipes are cool too!",
            "Clogged pipe? Sometimes you just gotta face the problem head on!",
            f"{_CHARACTER_DISPLAY_NAME} has THREE rules for plumbing: One, don't panic. Two, find the shutoff. Three... okay I only have two rules!",
            "Fun fact: bathrooms are my natural habitat! I know every pipe, every tile, every... okay maybe not EVERY tile.",
            f"{_CHARACTER_DISPLAY_NAME}'s plumbing credentials: Zero toilets fixed. But I COULD fix one if I wanted to!",
            "People always ask me about plumbing. I'm like, I host PARTIES! But sure, let me look at your leaky faucet...",
        ])

    # Check for shot event voice triggers (requires shot_event_manager to be available)
    # This needs to be imported from main.py or passed as a parameter
    # For now, we'll return a special response that main.py can detect
    shot_event_keywords = [
        "lisa", "aunt lisa", "lisa webb", "toast to lisa",
        "birthday shot", "shot for jacob", "birthday boy shot", 
        "deltarune shot", "shot for deltarune", "deltarune toast"
    ]
    for keyword in shot_event_keywords:
        if keyword in lower:
            # Return a special marker that main.py can detect and handle
            return f"__SHOT_EVENT_TRIGGER__:{transcript}"

    return None


def handle_special_commands(*args, **kwargs):
    result = _handle_special_commands_impl(*args, **kwargs)
    # Strip Mario verbal flavor for non-Mario characters. _deflavor self-no-ops
    # when the active character IS Mario, so this is safe to always call.
    if isinstance(result, str):
        return _deflavor(result)
    if isinstance(result, tuple) and result and isinstance(result[0], str):
        return (_deflavor(result[0]),) + tuple(result[1:])
    return result
