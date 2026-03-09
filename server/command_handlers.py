"""Command handlers — special commands/easter-eggs extracted from main.py."""

import os
import random
import re
import sqlite3
import time
from datetime import datetime

from emotions import Emotion
import game_handlers
import speaker_id


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
        "triggers": ["be scary mario", "horror mario", "scary mode", "spooky mario"],
        "intro": "Mwa ha ha ha! Welcome to-a the DARK side of the Mushroom Kingdom! *thunder crashes* I am-a SCARY Mario now! Boo!",
    },
    "dj": {
        "triggers": ["be dj mario", "dj mode", "dj mario", "be a dj"],
        "intro": "YOOO! DJ MARIO IN THE HOUSE! *scratch scratch* Drop the bass! Untz untz untz! Let's get this bathroom PUMPING! Wahoo!",
    },
    "therapist": {
        "triggers": ["be therapist mario", "therapy mode", "therapist mario", "be my therapist"],
        "intro": "Ah yes, welcome to-a Dr. Mario's office. *adjusts imaginary glasses* Tell me, how does that make-a you feel? I'm here for you, friend.",
    },
    "pirate": {
        "triggers": ["be pirate mario", "pirate mode", "pirate mario", "arr mario"],
        "intro": "ARRR! Avast ye landlubbers! Captain Mario be takin' the helm now! Shiver me mushrooms! Where be the treasure?!",
    },
    "normal": {
        "triggers": ["be normal mario", "reset mode", "normal mode", "normal mario", "be yourself"],
        "intro": "Wahoo! It's-a me, regular Mario again! Back to normal! Let's-a go!",
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


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def handle_special_commands(
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
    now = time.time()
    if now - state["_last_command_time"] < game_config["command_cooldown"]:
        return None
    state["_last_command_time"] = now

    # --- Active game mode handling (intercepts input when a game is running) ---
    if state["_active_game"]:
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

    # Easter eggs — hidden trigger phrases for extra fun
    for trigger, response in EASTER_EGGS.items():
        if trigger in lower:
            emotion_system.current = Emotion.EXCITED
            return response

    # Tell a joke
    if any(w in lower for w in ["tell me a joke", "know any jokes", "make me laugh", "say something funny"]):
        emotion_system.current = "mischievous"
        return idle_behavior.get_joke()

    # Tell me a secret
    if any(w in lower for w in ["tell me a secret", "secret", "whisper"]):
        emotion_system.current = "mischievous"
        return random.choice(SECRETS)

    # Trivia
    if any(w in lower for w in ["tell me a fact", "trivia", "fun fact", "did you know"]):
        emotion_system.current = "excited"
        return idle_behavior.get_trivia()

    # Sing
    if any(w in lower for w in ["sing", "song", "music", "hum"]):
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
    if any(w in lower for w in ["my name is", "i'm called", "call me", "i am "]):
        match = re.search(r"(?:my name is|i'm called|call me|i am)\s+([A-Za-z]+(?:\s[A-Za-z]+)?)", lower)
        if match:
            name = match.group(1)[:50].capitalize()  # Cap at 50 chars
            # Register this voice with the name
            if state.get("_last_audio_chunk"):
                new_id = speaker_id.register_speaker(name, state["_last_audio_chunk"])
                memory_module.register_person(new_id, name)
                state["speaker_name"] = name
                state["speaker_id"] = new_id
                emotion_system.current = "excited"
                return f"Wahoo! Nice to meet-a you, {name}! I'll-a remember your voice from now on! Let's-a go!"
            else:
                state["speaker_name"] = name
                return f"Nice to meet-a you, {name}! Wahoo! I'll remember you!"

    # What time is it
    if any(w in lower for w in ["what time", "how late"]):
        stats = party_stats.get_stats()
        return f"It's-a {stats['current_hour']}! Time flies when you're having fun in the bathroom!"

    # Compliment request
    if any(w in lower for w in ["compliment", "say something nice", "make me feel", "cheer me up"]):
        base_compliment = idle_behavior.get_compliment()
        # Personalize if we know the person
        name = state.get("speaker_name")
        if name and state.get("speaker_id"):
            player_stats = memory_module.get_player_stats(state["speaker_id"])
            if player_stats:
                total_games = sum(s.get("games_played", 0) for s in player_stats.values())
                if total_games > 0:
                    return f"Hey {name}! {base_compliment} And you've played {total_games} games with me! You're-a true champion!"
            person_info = memory_module.get_person_info(state["speaker_id"])
            if person_info and person_info.get("visit_count", 0) > 1:
                visits = person_info["visit_count"]
                return f"{name}! {base_compliment} You've visited me {visits} times! That makes you extra special!"
            if name:
                return f"{name}! {base_compliment}"
        emotion_system.current = Emotion.HAPPY
        return base_compliment

    # Challenge request
    if any(w in lower for w in ["challenge", "quiz me", "test me", "trivia"]):
        emotion_system.current = "mischievous"
        return idle_behavior.get_challenge()

    # Dare
    if any(w in lower for w in ["dare me", "truth or dare", "give me a dare", "i dare you"]):
        emotion_system.current = "mischievous"
        return random.choice(DARES)

    # Hand wash reminder
    if any(w in lower for w in ["wash my hands", "should i wash", "hygiene", "wash hands", "hand wash", "soap"]):
        return idle_behavior.get_hand_wash_reminder()

    # How many visitors
    if any(w in lower for w in ["how many visitors", "how busy", "popular"]):
        stats = party_stats.get_stats()
        if stats['total_visits'] > 10:
            return f"Mama mia! We've had {stats['total_visits']} visits tonight! This bathroom is-a the hottest spot at the party!"
        else:
            return f"So far {stats['total_visits']} visits! The party is-a still warming up!"

    # Who was here last
    if any(w in lower for w in ["who was here", "who came", "last person", "before me"]):
        stats = party_stats.get_stats()
        last = stats.get('last_visitor_name')
        if last:
            return f"The last person before you was-a {last}! Nice person!"
        else:
            return f"You know, I've been here a while but my memory is-a fuzzy! Too many guests!"

    # Who am I / what do you know about me
    if any(w in lower for w in ["who am i", "do you know me", "remember me", "know anything about me", "what do you remember"]):
        if state["speaker_id"]:
            memories = memory_module.get_memories_for_context(state["speaker_id"])
            if memories:
                facts_text = ", ".join(memories[:4])
                return f"Of course I remember-a you, {state['speaker_name'] or 'friend'}! I know that {facts_text}!"
        if state["speaker_name"]:
            return f"You're-a {state['speaker_name']}! But that's all I know so far. Tell me more!"
        return "Hmm, I don't think we've-a met properly! What's your name, friend?"

    # How do I look
    if any(w in lower for w in ["how do i look", "do i look good", "am i pretty", "am i handsome"]):
        emotion_system.current = "loving"
        return random.choice([
            "Mama mia! You look-a absolutely magnificent! Like a Super Star!",
            "Bellissimo! You're looking-a fantastic tonight! Ten out of ten!",
            "You look like-a million coins! Gold star for style!",
        ])

    # Roast me / light-hearted teasing
    if any(w in lower for w in ["roast me", "insult me", "make fun of", "burn me", "diss me"]):
        emotion_system.current = "mischievous"
        name = state.get("speaker_name") or "friend"
        return random.choice([r.format(name=name) for r in ROASTS])

    # Party stage / how's the party going
    if any(w in lower for w in ["how's the party", "party going", "party stage", "vibe check", "what's the vibe"]):
        party_duration = time.time() - party_stats.party_start_time
        stage = idle_behavior.get_party_stage(party_duration / 60)
        stats = party_stats.get_stats()
        return f"{stage} We've had {stats['total_visits']} visitors so far!"

    # What can you do / help
    if any(w in lower for w in ["what can you do", "what do you do", "help me", "your abilities", "your powers"]):
        emotion_system.current = Emotion.EXCITED
        return (
            "I can do so much! Ask for a joke, trivia, song, dare, roast, nickname, "
            "pickup line, fortune, tongue twister, story, rap, motivation, bathroom tip, "
            "or just-a chat! Play Simon Says, 20 Questions, Truth or Dare, Riddles, Word Chain, "
            "Rapid Fire Quiz, Would You Rather, Karaoke, Rock Paper Scissors, Hangman, or Hot Takes! Check achievements, leaderboard, trending, party phase, "
            "party stats, conversation summary, holiday, crew, or sound catalog! Wahoo!"
        )

    # Tell me about yourself
    if any(w in lower for w in ["about yourself", "who are you", "introduce yourself", "what are you"]):
        emotion_system.current = "proud"
        return (
            "It's-a me, Mario! I'm your friendly bathroom guardian! "
            "I'm a plumber, a hero, and tonight I'm-a the DJ of this bathroom! Wahoo!"
        )

    # Goodbye/goodnight
    if any(w in lower for w in ["goodbye", "goodnight", "see ya", "gotta go", "leaving", "bye bye"]):
        emotion_system.current = "happy"
        return random.choice([
            "See ya later, alligator! Don't forget to wash-a your hands!",
            "Bye bye! Come back-a soon! The bathroom misses you already!",
            "Arrivederci! Until next time, friend! Wahoo!",
        ])

    # Give me a nickname
    if any(w in lower for w in ["give me a nickname", "nickname me", "what's my nickname", "call me something"]):
        emotion_system.current = "mischievous"
        name = state.get("speaker_name") or "friend"
        return random.choice([n.format(name=name) for n in NICKNAMES])

    # Rate the party / how good is the party
    if any(w in lower for w in ["rate the party", "party rating", "rate this party", "how good is the party"]):
        stats = party_stats.get_stats()
        visits = stats['total_visits']
        if visits > 25:
            return f"This party gets-a TEN out of TEN! {visits} bathroom visits means EVERYONE is having a great time! WAHOO!"
        elif visits > 10:
            return f"Mario gives this party an EIGHT out of ten! {visits} visits and counting! Let's-a keep it going!"
        elif visits > 3:
            return f"So far it's-a SIX out of ten! Only {visits} visits... but the night is young! Let's-a go!"
        else:
            return f"Hmm, only {visits} visits so far. I give it a FOUR but it's-a just getting started! More guests incoming!"

    # Tell my fortune / fortune teller
    if any(w in lower for w in ["tell my fortune", "fortune", "predict", "future", "crystal ball", "psychic"]):
        emotion_system.current = "mischievous"
        return random.choice(FORTUNES)

    # How are you feeling / mood
    if any(w in lower for w in ["how are you feeling", "what's your mood", "how are you doing", "you okay", "how do you feel", "are you happy"]):
        current_mood = emotion_system.current
        return MOOD_RESPONSES.get(current_mood, "I'm-a doing great! It's always a good day to be Mario!")

    # Would You Rather game
    if any(w in lower for w in ["would you rather", "rather game", "choice game", "this or that"]):
        return game_handlers.start_game("would_you_rather", state, game_config, emotion_system)

    # Tongue twister
    if any(w in lower for w in ["tongue twister", "say something hard", "twist my tongue"]):
        emotion_system.current = "mischievous"
        return random.choice(TWISTERS)

    # Tell me a story / story time
    if any(w in lower for w in ["tell me a story", "story time", "bedtime story", "once upon a time"]):
        emotion_system.current = "happy"
        return random.choice(STORIES)

    # Pickup line
    if any(w in lower for w in ["pickup line", "flirt", "rizz", "pick up line", "smooth line"]):
        emotion_system.current = "loving"
        return random.choice(PICKUP_LINES)

    # Bathroom tip / etiquette
    if any(w in lower for w in ["bathroom tip", "etiquette", "bathroom advice", "bathroom rule"]):
        emotion_system.current = "proud"
        return random.choice(BATHROOM_TIPS)

    # Rap for me
    if any(w in lower for w in ["rap for me", "freestyle", "spit bars", "drop a beat", "rap battle"]):
        emotion_system.current = "excited"
        return random.choice(RAPS)

    # Motivate me / encouragement
    if any(w in lower for w in ["motivate me", "motivation", "inspire me", "i need encouragement", "cheer me up", "i'm sad", "feeling down"]):
        emotion_system.current = "proud"
        return random.choice(MOTIVATIONS)

    # Confession mode
    if any(w in lower for w in ["i have a confession", "confess", "i need to tell you something", "can i tell you a secret"]):
        emotion_system.current = "surprised"
        return random.choice(CONFESSIONS)

    # Memory quiz
    if any(w in lower for w in ["quiz me", "test me", "memory quiz", "what did i tell you"]):
        if state["speaker_id"]:
            memories = memory_module.get_memories_for_context(state["speaker_id"])
            if memories and len(memories) > 1:
                fact = random.choice(memories)
                emotion_system.current = "mischievous"
                return f"Okay quiz time! Is it true that {fact}? Ha ha, I already know the answer! Mario remembers EVERYTHING!"
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
        return "One-a! Two-a! Three-a! Four-a! FIVE! Six-a! Seven-a! EIGHT! Nine-a! TEN! WAHOO! Mario can count! Impressed?"

    # What time is it (enhanced)
    if any(w in lower for w in ["what time", "what's the time", "time is it"]):
        now_dt = datetime.now()
        hour = now_dt.hour
        minute = now_dt.minute
        ampm = "AM" if hour < 12 else "PM"
        display_hour = hour % 12 or 12
        time_str = f"{display_hour}:{minute:02d} {ampm}"
        if hour >= 2 and hour < 6:
            return f"It's-a {time_str}! Mama mia, it's so late! Even Bowser is sleeping by now!"
        elif hour >= 22 or hour < 2:
            return f"It's-a {time_str}! The night is still young! Let's-a keep partying!"
        else:
            return f"It's-a {time_str}! Perfect time for a party! Wahoo!"

    # --- Interactive Game Modes ---

    # Simon Says
    if any(w in lower for w in ["simon says", "play simon", "let's play simon"]):
        return game_handlers.start_game("simon_says", state, game_config, emotion_system)

    # 20 Questions
    if any(w in lower for w in ["20 questions", "twenty questions", "play 20", "play twenty"]):
        return game_handlers.start_game("twenty_questions", state, game_config, emotion_system)

    # Truth or Dare
    if any(w in lower for w in ["truth or dare", "play truth", "let's play truth"]):
        return game_handlers.start_game("truth_or_dare", state, game_config, emotion_system)

    # Stop any active game
    if any(w in lower for w in ["stop game", "quit game", "end game", "stop playing", "quit playing"]):
        if state["_active_game"]:
            game = state["_active_game"]
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_system.current = Emotion.HAPPY
            return f"Game over! Thanks for playing {game.replace('_', ' ')}! That was fun! Wahoo!"
        return None

    # Riddle game
    if any(w in lower for w in ["riddle", "play riddle", "riddle me", "tell me a riddle"]):
        return game_handlers.start_game("riddles", state, game_config, emotion_system)

    # Word Chain game
    if any(w in lower for w in ["word chain", "play word chain", "word game", "last letter"]):
        return game_handlers.start_game("word_chain", state, game_config, emotion_system)

    # Karaoke mode
    if any(w in lower for w in ["karaoke", "sing along", "sing with me", "let's sing"]):
        return game_handlers.start_game("karaoke", state, game_config, emotion_system)

    # Achievements
    if any(w in lower for w in ["achievements", "my badges", "my awards", "what have i earned", "my stats"]):
        badges = []
        if state.get("speaker_name"):
            badges.append("🏅 Named Visitor (told Mario your name!)")
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
            return "No badges yet! Talk to me, tell me your name, and keep visiting to earn achievements! Wahoo!"
        badge_list = " ".join(badges)
        emotion_system.current = Emotion.PROUD
        return f"YOUR ACHIEVEMENTS! {badge_list} Keep going for more! Wahoo!"

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
        return f"PARTY PHASE: {phase} Total visits: {visits}! Wahoo!"

    # Party Leaderboard
    if any(w in lower for w in ["leaderboard", "who visited most", "party champions", "top visitors"]):
        try:
            _lb_path = os.path.join(os.path.dirname(__file__), "data", "memory.db")
            with sqlite3.connect(_lb_path) as _lconn:
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
            return f"PARTY LEADERBOARD! {board} Who's-a the champion?"
        except Exception:
            return "Mama mia, the leaderboard is-a broken! But YOU'RE number one in my heart!"

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
            return "Mama mia, my trend tracker is-a having a break! Tell me something interesting!"

    # Reset party
    if any(w in lower for w in ["reset party", "new party", "start new party", "reset the party"]):
        party_stats.reset_party()
        emotion_system.current = Emotion.EXCITED
        return "WAHOO! New party started! The counter is-a reset! Let's-a make this the BEST party ever!"

    # Forget me (privacy — delete speaker voice data)
    if any(w in lower for w in ["forget me", "delete my voice", "remove my data", "forget my voice"]):
        if state.get("speaker_id"):
            try:
                speaker_id.delete_speaker(state["speaker_id"])
                emotion_system.current = Emotion.WORRIED
                return "Okay... Mario will forget your voice. *sniff* It's like you were never here! Privacy respected!"
            except Exception:
                return "Mama mia, I tried to forget you but my memory is-a stuck! Try again later!"
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
                return f"We've-a talked about: {topics_str}! Great conversation, {state['speaker_name'] or 'friend'}!"
        return "We just met! Let's make some memories first!"

    # Holiday check
    if any(w in lower for w in ["holiday", "what day is it", "special day", "celebration"]):
        holiday = _detect_holiday()
        if holiday:
            emotion_system.current = Emotion.EXCITED
            return f"It's {holiday} today! How exciting! Let's-a celebrate!"
        return "No special holiday today, but EVERY day is special when Mario is here! Wahoo!"

    # Rapid-fire quiz game
    if any(w in lower for w in ["rapid fire", "rapid quiz", "speed quiz", "quick quiz", "rapid round"]):
        return game_handlers.start_game("rapid_fire", state, game_config, emotion_system)

    # Rock Paper Scissors
    if any(w in lower for w in ["rock paper scissors", "battle mode", "rps", "let's battle"]):
        return game_handlers.start_game("rock_paper_scissors", state, game_config, emotion_system)

    # Hangman
    if any(w in lower for w in ["hangman", "play hangman", "guess the word"]):
        return game_handlers.start_game("hangman", state, game_config, emotion_system)

    # Hot Takes
    if any(w in lower for w in ["hot takes", "hot take", "unpopular opinion", "spicy take"]):
        return game_handlers.start_game("hot_takes", state, game_config, emotion_system)

    # Never Have I Ever
    if any(w in lower for w in ["never have i ever", "never ever", "play never"]):
        return game_handlers.start_game("never_have_i_ever", state, game_config, emotion_system)

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
        return random.choice(BATHROOM_FACTS)

    # Party suggestions / what should I do
    if any(w in lower for w in ["what should i do", "i'm bored at the party", "suggest something", "party suggestion"]):
        emotion_system.current = Emotion.EXCITED
        return random.choice(PARTY_SUGGESTIONS)

    # Bathroom emergencies — toilet paper
    tp_triggers = ["no toilet paper", "out of toilet paper", "no paper", "need toilet paper", "no tp"]
    if any(t in lower for t in tp_triggers):
        return random.choice([
            "MAMA MIA! EMERGENCY! Check under the sink for backup rolls! If not, I'll... uhh... I got nothing. HELP!",
            "Code Red! Code Red! No toilet paper! This is worse than fighting Bowser without fire flowers!",
            "WAHOO... wait, that's-a NOT a wahoo moment! Someone get the emergency supplies! Under the sink, check the cabinet!",
            "As a professional plumber, I can tell you: ALWAYS check for paper BEFORE you sit down! But let's-a solve this crisis!",
            "NO PAPER?! This is-a the final boss of bathroom problems! Check the cabinet, the closet, anywhere!",
        ])

    # Bathroom emergencies — need help
    help_triggers = ["need help", "help me", "i'm stuck", "emergency"]
    if any(t in lower for t in help_triggers):
        return random.choice([
            "Mario is-a here to help! What do you need? If it's plumbing, you came to the right guy!",
            "HELP is on the way! Well, I can't actually leave this screen, but I'm-a great moral support!",
            "Don't worry friend! Whatever the problem is, we'll-a figure it out together! What's wrong?",
            "Mario to the rescue! Tell me what's happening and I'll do my best to help! That's what heroes do!",
        ])

    # Bathroom emergencies — courtesy / smell
    courtesy_triggers = ["it smells", "smells bad", "stinky", "something smells"]
    if any(t in lower for t in courtesy_triggers):
        return random.choice([
            "Have you tried the courtesy flush? It's-a like a checkpoint save but for air quality!",
            "As a plumber, I've smelled MUCH worse! This is nothing compared to the sewers of World 1-2!",
            "Quick tip from Mario: the fan switch is usually by the door! And maybe crack a window!",
            "Mama mia! Even my fire flowers can't handle this! Try the air freshener if there is one!",
        ])

    # Plumber-specific humor
    plumber_triggers = ["plumber", "plumbing", "pipes", "fix the toilet", "clogged"]
    if any(t in lower for t in plumber_triggers):
        return random.choice([
            "As a licensed plumber, I can confirm: this pipe network is amateur hour compared to the Mushroom Kingdom!",
            "Plumbing? That's-a my specialty! Did you know I've traveled through more pipes than any plumber in history?",
            "You know, before I was saving princesses, I was fixing toilets! True story! It's-a in my resume!",
            "Clogged pipe? In the Mushroom Kingdom, we just jump on the problem! Literally! WAHOO!",
            "As a plumber, I have THREE rules: One, always check for Piranha Plants. Two, wear gloves. Three... okay I only have two rules!",
            "Fun fact: I became a hero BECAUSE of plumbing! I fell through a pipe and ended up in another world! Best career change ever!",
            "My plumbing credentials: Saved Princess Peach 47 times. Fixed zero toilets. But I COULD fix one if I wanted to!",
            "People always ask me to fix their plumbing. I'm like, I fight DRAGONS! But sure, let me look at your leaky faucet...",
        ])

    return None
