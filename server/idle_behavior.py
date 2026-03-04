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
]

# Things Mario says when he hears a sudden noise
NOISE_REACTIONS = [
    "Wah! What was-a that?!",
    "Mama mia! Did you hear that?",
    "Who's-a there? Friend or Goomba?",
    "*jumps* Wahoo! Startled me!",
    "Was that a Boo? They're-a sneaky!",
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
]

PLUMBING_FACTS = [
    "Did you know? The first flushing toilet was invented in 1596! That's-a old pipes!",
    "Fun plumbing fact! The word 'plumber' comes from the Latin word for lead — plumbum!",
    "Bathroom fact! The average person spends about 3 years of their life on the toilet!",
    "Did you know? Albert Einstein said if he could do it over, he'd become a plumber! Smart man!",
    "Fun fact! The bathroom is called the 'loo' in England! Fancy-a name!",
]


class IdleBehavior:
    """Manages Mario's autonomous behavior when idle."""

    def __init__(self):
        self._last_idle_action = time.time()
        self._idle_interval = 30  # Seconds between idle actions
        self._mumble_index = 0

    def get_idle_action(self) -> str:
        """Get an idle action/mumble if enough time has passed. Returns None if not time yet."""
        now = time.time()
        if now - self._last_idle_action < self._idle_interval:
            return None

        self._last_idle_action = now
        # Gradually increase interval so Mario doesn't repeat too fast
        self._idle_interval = min(120, self._idle_interval + 5)

        hour = time.localtime().tm_hour

        # Weight towards time-appropriate comments
        options = list(IDLE_MUMBLES)
        if 18 <= hour < 21:
            options.extend(TIME_COMMENTS["early_evening"])
        elif 21 <= hour < 24:
            options.extend(TIME_COMMENTS["peak_party"])
        elif 0 <= hour < 2:
            options.extend(TIME_COMMENTS["late_night"])
        elif 2 <= hour < 6:
            options.extend(TIME_COMMENTS["very_late"] * 2)

        # Sometimes sing instead
        if random.random() < 0.2:
            options.extend(MARIO_SONGS)

        choice = random.choice(options)
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] get_idle_action: '{choice[:40]}...'")
        return choice

    def get_joke(self) -> str:
        return random.choice(MARIO_JOKES)

    def get_trivia(self) -> str:
        return random.choice(MARIO_TRIVIA + PLUMBING_FACTS)

    def get_song(self) -> str:
        return random.choice(MARIO_SONGS)

    def get_noise_reaction(self) -> str:
        return random.choice(NOISE_REACTIONS)

    def reset_timer(self):
        """Reset idle timer (called when someone interacts)."""
        self._last_idle_action = time.time()
        self._idle_interval = 30

    def get_long_stay_comment(self, minutes: float) -> str:
        """Get a comment about someone taking a long time."""
        if minutes < 3:
            return None
        elif minutes < 5:
            return random.choice([
                "Taking your time, eh? No rush! Mario will-a wait!",
                "Still here? Must be-a comfy in here!",
            ])
        elif minutes < 10:
            return random.choice([
                f"Mama mia! {int(minutes)} minutes! Everything okay in there?",
                f"You've been here {int(minutes)} minutes! That's-a new record!",
            ])
        else:
            return random.choice([
                f"Wahoo! {int(minutes)} minutes?! You should-a see a doctor! Ha ha, just kidding!",
                f"Still going strong after {int(minutes)} minutes! You're-a champion!",
            ])
