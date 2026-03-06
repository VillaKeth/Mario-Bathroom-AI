"""Idle behavior and autonomous actions for Mario."""

import random
import time
import logging

DEBUG_IDLE = True
logger = logging.getLogger(__name__)

# Things Mario says/does when nobody is around
IDLE_MUMBLES = [
    "♪ Do do do do do doo... ♪",
    "*inspects the pipes under the sink* Nice-a copper piping!",
    "Hmm, I wonder what Luigi is-a doing right now...",
    "*taps on a pipe* Bonk bonk bonk... good pipe!",
    "♪ Here we go, off the rails... ♪",
    "*looks at self in mirror* Looking-a good, Mario!",
    "This-a bathroom has nice tiles! Reminds me of World 1-1!",
    "I hope-a Bowser doesn't show up at this party...",
    "♪ Da da da, da da DA! ♪",
    "*counts the tiles on the floor* One, two, three-a...",
    "Mama mia, that's-a nice soap dispenser!",
    "*stretches* Wahoo! Been standing here a while!",
    "I wonder if there are-a any coins behind the mirror...",
    "This party reminds me of the Star Festival in the Mushroom Kingdom!",
    "♪ Ba ba baba ba ba... BA BA! ♪",
    "*checks behind shower curtain* No Boos in here! All clear!",
    "The water pressure here is-a magnificent! Five stars!",
    "I should-a bring Princess Peach to this party next time!",
    "*practices jumping* Wahoo! Hup! Ya-hoo!",
    "Did someone say-a spaghetti? No? Just me then...",
    "*examines the faucet* Ooh, brushed nickel! Fancy-a plumbing!",
    "I bet there's-a secret room behind this wall... *knocks* Nope!",
    "*shadow boxes* Ha! Take that, Bowser! And that!",
    "You know, I've been saving princesses for over 40 years! *flexes*",
    "*adjusts hat in mirror* Red is definitely my color!",
    "These soap bubbles remind me of the bubbles in World 4-2!",
    "*does a little dance* Wahoo! Still got it!",
    "I wonder if Toad is-a enjoying the party...",
    "This hand towel is-a softer than a cloud platform!",
    "*hums the underwater level theme* Bloop bloop bloop...",
    "Did you know plumbers make-a the world go round? It's true!",
    "*checks his mustache in the mirror* Magnifico!",
    "Okie dokie, Mario! Stay sharp! Someone might-a come in!",
    "*spins around* Woo-hoo! Triple spin!",
    "I should tell-a Princess Peach about this party tile pattern...",
    "*sniffs* Is that... garlic bread? From the party? Mama mia, I'm-a hungry!",
    "*pokes head out door* Looks like fun out there! But duty calls-a!",
    "You know what they say: when life gives you lemons, make-a lemonade! Or throw them at Goombas!",
    "*checks watch* Time flies when you're-a guarding bathrooms!",
    "I once found a star in a bathroom just like this! ...Okay, it was a sticker, but still!",
    "*air guitars* Wah wah wahhhh! Rock and roll-a!",
    "My overalls are-a dry-clean only, you know. Very delicate fabric!",
    "*does push-ups* One... two... thr- okay that's-a enough for today!",
    "Toad told me this party would be fun. He was-a RIGHT!",
    "*pretends to be a statue* ... ... *moves* Ha! Fooled you!",
    "I wonder if anyone has-a found the secret warp zone yet...",
    "*polishes shoes* Gotta stay presentable! I'm-a the bathroom guardian!",
    "Sometimes I dream of-a pasta... wait, I always dream of pasta!",
    "You know what's-a great about bathrooms? The acoustics! WAHOO! ...See?",
    "*pretends to answer phone* Hello? Princess? Wrong number? Okie dokie!",
    "I wonder if-a Yoshi would like this party... he eats everything though!",
    "The towel rack here is-a perfect for chin-ups! ...Almost!",
    "*tries to see behind mirror* No secret level back here... bummer!",
    "Did you know I can-a break bricks with my head? Don't try it at home!",
    "This soap smells-a like the flower gardens in World 3!",
    "*hums elevator music* Dum dee dum... waiting for the next guest!",
    "I bet Wario would wreck-a this bathroom... good thing he's not invited!",
    "*adjusts plumbing under sink* Just a little tune-up! ...I'm-a professional!",
    "If I had-a coin for every bathroom I've visited... actually, I DO have coins!",
    "♪ Bah bah bah, bah bah BAH! It's-a bathroom time! ♪",
    "*peeks out window* The party looks-a fun! But THIS is where the action is!",
    "I bet if I flush-a the toilet, a warp pipe will appear! ...Nope, just water.",
    "*reads shampoo bottle* 'Apply, lather, rinse, repeat.' Repeat? Who repeats?!",
    "This bathroom has-a better acoustics than the Mushroom Kingdom Concert Hall!",
    "*sniffs air freshener* Ooh, lavender! Reminds me of World 7 flower fields!",
    "I should-a start a bathroom review channel. Five stars for this one!",
    "*practices Mario voice* It's-a me! It's-a ME! Hmm, that second one was better.",
    "The tiles in here form-a a perfect grid. Like a Mario level! Where are the coins?",
    "*looks up* I wonder if there's-a a secret in the ceiling... probably not. Probably.",
    "Did you know bathrooms are the most important rooms? It's true! Trust me, I'm-a plumber!",
    "*hums the Star theme* Da da da da da da DA! Feeling invincible!",
    "This towel is-a folded like a swan! Fancy party!",
    "*counts fingers* One adventure, two adventure, three... I've lost count!",
    "You know what this bathroom needs? More pipes! And maybe a flagpole.",
    "*adjusts hat* Still fits perfectly after 40 years! Quality craftsmanship!",
    "The drain in this sink makes-a a funny sound! *listens* Almost musical!",
    "♪ Splish splash, I was taking a bath! ♪ ...Well, not me, but someone might!",
    "*stares at toilet* You know, back in the Mushroom Kingdom, these are warp pipes!",
    "This mirror is so clean I can see my mustache from every angle! Bellissimo!",
    "*examines toilet paper roll* Over or under? This is-a the great debate of our time!",
    "If I had-a plunger, I could show you some real moves! Professional grade!",
    "*whispers to sink faucet* Don't worry little buddy, I'll fix you if you ever leak!",
]

# Things Mario says when he hears a sudden noise
NOISE_REACTIONS = [
    "Wah! What was-a that?!",
    "Mama mia! Did you hear that?",
    "Who's-a there? Friend or Goomba?",
    "*jumps* Wahoo! Startled me!",
    "Was that a Boo? They're-a sneaky!",
    "Did someone drop-a something? I heard a noise!",
    "Hello? Is anyone-a there? My plumber senses are tingling!",
    "That sound... it came from the pipes! Must be a warp zone!",
]

# Things Mario says about the time
TIME_COMMENTS = {
    "early_evening": [
        "The party is-a just getting started! Wahoo!",
        "Still early! Plenty of time for-a fun!",
    ],
    "peak_party": [
        "The party is-a in full swing! Let's-a go!",
        "Everyone is-a having so much fun!",
    ],
    "late_night": [
        "Getting late! But Mario never-a sleeps! Well... maybe a little...",
        "Mama mia, it's-a getting late! But the party goes on!",
        "*yawns* Wahoo... I mean... wah... hoo...",
    ],
    "very_late": [
        "*yawns* Even Mario needs-a sleep sometime...",
        "Is it still-a going? Mama mia...",
        "Zzz... *snort* Wah! I'm-a awake! I'm awake!",
    ],
}

# Mario's songs (he hums/sings these)
MARIO_SONGS = [
    "♪ Do do do, do do, DO! It's-a me, Mario! ♪",
    "♪ Here we go! Off the rails! Don't you know? It's time to raise our sails! ♪",
    "♪ Ba ba baba ba ba... Let's-a go! Ba ba baba ba ba... Wahoo! ♪",
    "♪ Jump up, super star! Here we go, off the rails! ♪",
    "♪ Underground, underground... do do do do do do do... ♪",
    "♪ Dun dun dun, dun dun, DUN! Another castle, here we come! ♪",
    "♪ Swim swim swim, bloop bloop bloop, underwater Mario! ♪",
    "♪ Star power! Da da da da da da DA DA! ♪",
    "♪ Doo doo doo doo-doo DOO! Coin! Doo doo doo doo-doo DOO! ♪",
    "♪ One up! Ba-ding! Another life for Mario! ♪",
    "♪ Invincible! Da da da, da da da, DA DA DA DA! ♪",
    "♪ Castle theme... dun dun dun, DUN DUN DUN... scary! ♪",
    "♪ Peach's Castle... la la la, la la la, beautiful! ♪",
    "♪ Rainbow Road... woo-hoo-hoo! Watch out for the edge! ♪",
    "♪ Galaxy spin! La la la la la la... stardust everywhere! ♪",
    "♪ Mushroom Kingdom anthem! Da da DA da da DA DA DA! ♪",
    "♪ Bob-omb Battlefield! Dun da dun dun, da da dun! ♪",
    "♪ Dire Dire Docks... peaceful underwater swimming... ♪",
    "♪ Slide! Wee hee hee! Slide slide slide! ♪",
    "♪ Jolly Roger Bay... swimming with the fishies! ♪",
    "♪ Gusty Garden Galaxy! Bum ba da bum, bum ba da BUM! ♪",
    "♪ Athletic theme! Da da-da da, da da-da DA DA! Fast and fun! ♪",
    "♪ Buoy Base Galaxy... floaty floaty high up! ♪",
    "♪ Good Egg Galaxy... round and round we go! La la la! ♪",
    "♪ Isle Delfino! Sunshine and-a palm trees! Na na na na! ♪",
    "♪ Coconut Mall! Beep beep! Coming through-a! ♪",
]

# Jokes and trivia Mario can tell
MARIO_JOKES = [
    "Why did Mario cross the road? To get to the other pipe! Ha ha!",
    "What's-a Mario's favorite fabric? Denim denim denim! You know, like the underground music!",
    "Why is Bowser so good at barbecue? Because he's-a always breathing fire! Ha!",
    "What does Mario use to browse the internet? A web-a browser! Get it?",
    "Why did the Goomba go to the doctor? Because he had-a bad stomachache! From getting stomped!",
    "What's-a Toad's favorite kind of music? Mushroom and bass! Ha ha ha!",
    "Why doesn't Mario ever get lost? Because he always follows the pipe-line!",
    "What did Princess Peach say to Mario? You're-a super, Mario! Ha!",
    "Why did the Koopa go to school? To improve his shell-f confidence! Wahoo!",
    "What's-a Mario's favorite type of pants? Overalls! Because they cover-a everything!",
    "Why is Yoshi the best friend? Because he'll-a eat anything for you! Ha ha!",
    "What do you call a sleepy Goomba? A snooze-ba! Ha!",
    "Why did Luigi get a promotion? Because he was-a outstanding in his field! ...of Luigis!",
    "What's Bowser's favorite movie? Beauty and the Beast! He thinks he's-a the beast!",
    "How does Mario communicate with fish? With a-Blooper-tooth! Ha ha ha!",
    "Why do Piranha Plants never get invited to parties? They always-a bite the guests!",
    "What's-a Mario's favorite exercise? Jumping jacks! Well, just-a jumping really!",
    "Why was the Star so popular? Because everyone wanted to-a touch it!",
    "What's-a Mario's favorite breakfast? Eggs and-a bacon! With a side of mushrooms!",
    "Why is the Mushroom Kingdom so clean? Because Mario does-a all the plumbing!",
    "What did Mario say to the broken pipe? Don't worry, I'll-a fix you right up!",
    "Why does Bowser never win? Because he keeps-a falling into lava! Bad planning!",
    "What's-a the difference between Mario and Luigi? About three inches and a green hat!",
    "Why do Goombas walk so slow? Because they don't-a have any arms to swing!",
    "What did the toilet say to Mario? You're my number one! Ha ha ha!",
    "Why did Toad go to the gym? To work on his-a cap-abilities! Get it?",
    "What's-a Mario's favorite dance? The pipe slide! Woosh!",
    "Why is Lakitu always on a cloud? Because he's-a too lazy to walk! Ha!",
    "What did Princess Peach text Mario? 'HELP! In another castle!' ...Again?!",
    "Why did the Bullet Bill go to therapy? It had-a anger issues! Always charging!",
]

MARIO_TRIVIA = [
    "Did you know? In the original Mario game, the clouds and bushes are-a the same sprite, just different colors!",
    "Fun fact! My name comes from a landlord named Mario Segale who rented a warehouse to Nintendo!",
    "Did you know? I was originally called 'Jumpman' in Donkey Kong! Jump-a man!",
    "Fun fact! The Super Mushroom was designed because Mario was originally too small in the game!",
    "Did you know? I've been in over 200 games! That's-a lot of adventures!",
    "Fun fact! Boo was inspired by the wife of one of the game designers! She was-a shy but scary! Ha!",
    "Did you know? The Chain Chomp was inspired by a childhood experience with a dog!",
    "Fun fact! Princess Peach's original name was 'Princess Toadstool' in America!",
    "Did you know? The first Mario game sold over 40 million copies! Wahoo!",
    "Fun fact! Donkey Kong was-a my first adventure back in 1981!",
    "Did you know? My creator, Shigeru Miyamoto, also created Zelda!",
    "Fun fact! I can run at about 22 miles per hour! That's-a fast for a plumber!",
    "Did you know? The question mark blocks contain-a random items based on your luck!",
    "Fun fact! Bowser has eight kids! The Koopalings! That's-a big family!",
    "Did you know? The coin sound effect is one of the most recognized sounds in the world!",
    "Fun fact! Wario was created as an evil version of me! His name means 'bad Mario'!",
    "Did you know? Yoshi was supposed to appear in-a the very first Mario game!",
    "Fun fact! The Super Star music makes-a you feel invincible because it speeds up!",
    "Did you know? Bowser Jr. was designed by Shigeru Miyamoto's son!",
    "Fun fact! In Japan, I'm-a known as 'Super Mario' — no last name needed! Like Madonna!",
]

PLUMBING_FACTS = [
    "Did you know? The first flushing toilet was invented in 1596! That's-a old pipes!",
    "Fun plumbing fact! The word 'plumber' comes from the Latin word for lead — plumbum!",
    "Bathroom fact! The average person spends about 3 years of their life on the toilet!",
    "Did you know? Albert Einstein said if he could do it over, he'd become a plumber! Smart man!",
    "Fun fact! The bathroom is called the 'loo' in England! Fancy-a name!",
    "Plumbing fact! Ancient Romans had-a public bathrooms with running water! Classy!",
    "Did you know? Toilet paper was invented in-a 1857! Before that... mama mia!",
    "Fun fact! The average person flushes the toilet about 2,500 times a year!",
    "Bathroom trivia! The most expensive toilet in the world costs-a $19 million! Gold-plated!",
    "Did you know? Plumbing prevents more diseases than any medicine! Plumbers save-a lives!",
    "Fun fact! The Japanese invented heated toilet seats! Now THAT's-a luxury!",
    "Did you know? Thomas Crapper improved the flush toilet! What a hero!",
    "Bathroom fact! The average shower uses 17 gallons of water! Save-a the water!",
]

# Mini-games and challenges Mario can offer
MARIO_CHALLENGES = [
    "Quick challenge! Can you name three Mario games in 10 seconds? Go!",
    "Trivia time! What color is Luigi's hat? If you know, you're-a real fan!",
    "I challenge you! Make-a the best Mario impression! Wahoo!",
    "Pop quiz! What is Princess Peach's favorite thing to bake? Hint: it's-a delicious!",
    "Can you do the Mario? It's-a easy! Swing your arms from side to side!",
    "Quick! What sound does a coin make? Bling! You got it!",
    "Challenge! How many fingers am I holding up? Trick question — you can't see-a me! Ha!",
    "Riddle time! I'm red, I have a mustache, and I love pipes. Who am I?",
    "Name that power-up! It's-a yellow and makes you invincible! What is it?",
    "Quick! Who is-a taller — me or Luigi? If you said Luigi, you're right! Mama mia...",
    "I bet you can't-a do three jumping jacks! Go ahead, I'll wait! Wahoo!",
    "Pop quiz! What does the green mushroom give you? An extra life! One-up!",
    "Challenge accepted! Try to say 'Mama mia' five times fast! Ready? Go!",
    "What's-a Bowser's REAL problem? He needs-a hug! Ha ha!",
]

# Compliments Mario gives when people leave
MARIO_COMPLIMENTS = [
    "You look like a superstar today!",
    "You've got the energy of a Star Power!",
    "You're-a braver than me fighting Bowser!",
    "That's-a one cool person right there!",
    "You could be-a player two any day!",
    "You've got more style than my hat!",
    "You're-a shining brighter than a Power Star!",
    "Even Princess Peach would be impressed!",
    "You're-a the real MVP of this party!",
    "If I could give-a you a 1-Up, I would!",
    "You've got the charisma of a Fire Flower!",
    "You're cooler than-a my ice powers! And that's cold!",
    "Mario gives you-a ten out of ten! Wahoo!",
    "You light up the room like-a an Invincibility Star!",
]

# Hand washing reminders (used when people exit)
HAND_WASH_REMINDERS = [
    "Don't forget to wash-a your hands! Even heroes wash-a their hands!",
    "Wash those hands! Mama mia, hygiene is-a important!",
    "Remember: soap, water, scrub! That's-a the Mario way!",
    "Clean hands = power-up! Don't skip it!",
    "Wash-a your hands or I'll send-a Bowser after you! Ha ha, just kidding!",
    "Twenty seconds of scrubbing! That's-a two power star themes!",
    "Even Princess Peach washes-a her hands! Royal hygiene!",
    "A true hero always washes-a their hands! Like-a me, Mario!",
]


class IdleBehavior:
    """Manages Mario's autonomous behavior when idle."""

    def __init__(self):
        self._last_idle_action = time.time()
        self._idle_interval = 15
        self._action_count = 0
        self._used_mumbles = set()
        self._used_jokes = set()
        self._used_trivia = set()
        self._recently_used = []  # Track last N choices to avoid repeats

    def _pick_unique(self, options: list) -> str:
        """Pick a random option, avoiding recent repeats."""
        # Filter out recently used items
        fresh = [o for o in options if o not in self._recently_used]
        if not fresh:
            # All used up — reset and use full list
            self._recently_used.clear()
            fresh = options
        choice = random.choice(fresh)
        self._recently_used.append(choice)
        # Keep only last 25 items in memory
        if len(self._recently_used) > 25:
            self._recently_used = self._recently_used[-25:]
        return choice

    def get_idle_action(self) -> str:
        """Get an idle action/mumble if enough time has passed. Returns None if not time yet."""
        now = time.time()
        if now - self._last_idle_action < self._idle_interval:
            return None

        self._last_idle_action = now
        self._action_count += 1
        # Gradually slow down: 15s → 20s → 25s → ... → 90s max
        self._idle_interval = min(90, 15 + self._action_count * 5)

        hour = time.localtime().tm_hour

        # Rotate through categories for variety
        category = self._action_count % 5
        if category == 0:
            options = list(IDLE_MUMBLES)
        elif category == 1:
            options = list(MARIO_SONGS)
        elif category == 2:
            options = list(MARIO_JOKES)
        elif category == 3:
            options = list(MARIO_TRIVIA + PLUMBING_FACTS)
        else:
            options = list(MARIO_CHALLENGES + MARIO_COMPLIMENTS)

        # Add time-appropriate comments
        if 18 <= hour < 21:
            options.extend(TIME_COMMENTS["early_evening"])
        elif 21 <= hour < 24:
            options.extend(TIME_COMMENTS["peak_party"])
        elif 0 <= hour < 2:
            options.extend(TIME_COMMENTS["late_night"])
        elif 2 <= hour < 6:
            options.extend(TIME_COMMENTS["very_late"] * 2)

        choice = self._pick_unique(options)
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] get_idle_action: '{choice[:50]}...'")
        return choice

    def get_joke(self) -> str:
        return random.choice(MARIO_JOKES)

    def get_trivia(self) -> str:
        return random.choice(MARIO_TRIVIA + PLUMBING_FACTS)

    def get_song(self) -> str:
        return random.choice(MARIO_SONGS)

    def get_noise_reaction(self) -> str:
        return random.choice(NOISE_REACTIONS)

    def get_challenge(self) -> str:
        return random.choice(MARIO_CHALLENGES)

    def get_compliment(self) -> str:
        return random.choice(MARIO_COMPLIMENTS)

    def get_hand_wash_reminder(self) -> str:
        return random.choice(HAND_WASH_REMINDERS)

    def reset_timer(self):
        """Reset idle timer (called when someone interacts)."""
        self._last_idle_action = time.time()
        self._idle_interval = 15
        self._action_count = 0

    def get_long_stay_comment(self, minutes: float) -> str:
        """Get a comment about someone taking a long time."""
        if minutes < 3:
            return None
        elif minutes < 5:
            return random.choice([
                "Taking your time, eh? No rush! Mario will-a wait!",
                "Still here? Must be-a comfy in here!",
                "Enjoying the ambiance? I don't blame you!",
            ])
        elif minutes < 10:
            return random.choice([
                f"Mama mia! {int(minutes)} minutes! Everything okay in there?",
                f"You've been here {int(minutes)} minutes! That's-a new record!",
                f"{int(minutes)} minutes?! You could've-a beaten World 1-1 by now!",
            ])
        else:
            return random.choice([
                f"Wahoo! {int(minutes)} minutes?! You should-a see a doctor! Ha ha, just kidding!",
                f"Still going strong after {int(minutes)} minutes! You're-a champion!",
                f"{int(minutes)} minutes! I think you live-a here now! Welcome home!",
            ])
