"""Generate 100 fun party events for Mario AI Party Bot."""
import json

events = []

# Keep the 3 original events
events.extend([
    {
        "name": "lisa_webb_memorial",
        "display_name": "Lisa Webb",
        "tone": "solemn",
        "trigger_type": "auto",
        "voice_keywords": ["lisa", "aunt lisa", "lisa webb", "toast to lisa"],
        "phases": ["announcement", "silence", "countdown", "toast", "music", "recovery"],
        "announcement_text": "Everyone, please. Mario has something important to say. Tonight we remember someone very special, Lisa Webb. She was family to Jacob, and she's watching over this party from above.",
        "silence_text": "Let's have a moment of silence for Lisa Webb.",
        "toast_text": "Now raise your glasses, everyone. To Lisa Webb, a beautiful soul who touched all of our lives. To Lisa!",
        "recovery_line": "Lisa would've loved this party. Now let's keep celebrating in her honor!",
        "countdown": True,
        "music_file": "client/assets/music/lisa_webb_memorial.mp3",
        "music_duration": 120,
        "skip_key": "ctrl+shift+l",
        "image_file": "client/assets/images/lisa_webb.jpg"
    },
    {
        "name": "birthday_boy",
        "display_name": "Jacob Hoppenstedt\n2003 - 2026",
        "tone": "solemn",
        "trigger_type": "voice",
        "voice_keywords": ["birthday shot", "shot for jacob", "birthday boy shot", "rip jacob"],
        "phases": ["announcement", "silence", "countdown", "toast", "music", "recovery"],
        "announcement_text": "Everyone, please. Mario needs your attention. We gather tonight to honor the memory of a truly legendary gamer, Jacob Hoppenstedt. Gone too soon, but never forgotten.",
        "silence_text": "Let us bow our heads for a moment of silence for our fallen friend Jacob.",
        "toast_text": "Now raise your glasses one final time. To Jacob Hoppenstedt, the greatest party host who ever lived. Rest in power, my friend. To Jacob!",
        "recovery_line": "Just kidding! Jacob's right here! HAPPY BIRTHDAY! WAHOO! You really thought I was serious? Let's-a GO!",
        "countdown": True,
        "music_file": "client/assets/audio/jacob_birthday.mp3",
        "music_duration": 30,
        "image_file": "client/assets/images/jacob.jpg"
    },
    {
        "name": "deltarune",
        "display_name": "Deltarune",
        "tone": "fun",
        "trigger_type": "voice",
        "voice_keywords": ["deltarune shot", "shot for deltarune", "deltarune toast"],
        "phases": ["announcement", "countdown", "toast", "music", "recovery"],
        "announcement_text": "Attention everyone! Mario has a very special toast! This one goes out to the heroes of the Dark World, Deltarune!",
        "toast_text": "Calling all heroes! Kris, that's you Roman! Ralsei, that's you Elijah! Susie, that's you Villa! And the one and only Lancer, that's the birthday boy Jacob! Raise your glasses, to Deltarune!",
        "recovery_line": "WAHOO! What a fun game! Now back to the party!",
        "countdown": True,
        "music_file": "client/assets/audio/deltarune_hopes_dreams.mp3",
        "music_duration": 90,
        "image_file": "client/assets/images/deltarune.png"
    },
])

# Simple event template (no music)
def simple_event(name, display_name, tone, keywords, announcement, toast, recovery):
    return {
        "name": name,
        "display_name": display_name,
        "tone": tone,
        "trigger_type": "voice",
        "voice_keywords": keywords,
        "phases": ["announcement", "countdown", "toast", "recovery"],
        "announcement_text": announcement,
        "toast_text": toast,
        "recovery_line": recovery,
        "countdown": True,
    }

# ============================================================
# GAMING EVENTS (15)
# ============================================================

events.append(simple_event(
    "mario_kart", "Mario Kart", "fun",
    ["mario kart shot", "blue shell shot", "mario kart toast"],
    "Wahoo! It's time for the most important race of the night! Everyone grab your drinks, because this is a Mario Kart toast!",
    "Here we go! To the blue shells, the banana peels, and the friends we've lost to first place! To Mario Kart!",
    "If you got hit by a blue shell, take another sip! Let's-a go!"
))

events.append(simple_event(
    "smash_bros", "Super Smash Bros", "fun",
    ["smash bros shot", "smash shot", "smash toast"],
    "GAME! Everyone stop what you're doing! Mario has a Smash Bros announcement!",
    "To the greatest fighting game ever made! To all the broken controllers, the rage quits, and the friendships tested! To Smash Bros!",
    "Nobody got launched off the stage, right? WAHOO! Back to the party!"
))

events.append(simple_event(
    "zelda", "Legend of Zelda", "fun",
    ["zelda shot", "link shot", "zelda toast", "triforce shot"],
    "Listen! Hey, listen! Mario has something to say! This toast goes out to the Hero of Hyrule!",
    "To Link, to Zelda, and to everyone who spent 200 hours finding all the Korok seeds! To the Legend of Zelda!",
    "It's dangerous to go alone! Take this drink! WAHOO!"
))

events.append(simple_event(
    "pokemon", "Pokemon", "fun",
    ["pokemon shot", "pokemon toast", "gotta catch em all"],
    "A wild toast has appeared! Everyone, Mario chooses YOU for this Pokemon celebration!",
    "To the original 151, to Pikachu, and to every kid who argued that their starter was the best! Gotta catch 'em all! To Pokemon!",
    "That toast was super effective! WAHOO!"
))

events.append(simple_event(
    "minecraft", "Minecraft", "fun",
    ["minecraft shot", "minecraft toast", "creeper shot"],
    "Ssssssss, BOOM! Just kidding! Mario has a Minecraft toast for everyone!",
    "To the blocks, the creepers, and the diamonds! To everyone who's ever punched a tree! To Minecraft!",
    "Don't dig straight down after that drink! WAHOO!"
))

events.append(simple_event(
    "fortnite", "Fortnite", "fun",
    ["fortnite shot", "fortnite toast", "victory royale shot"],
    "Where we dropping, boys? Mario says we're dropping into this toast! Everyone get ready!",
    "To the Victory Royales, the cranking 90s, and the default dances! To Fortnite!",
    "That's a Victory Royale, baby! WAHOO! Back to the battle bus!"
))

events.append(simple_event(
    "among_us", "Among Us", "fun",
    ["among us shot", "sus shot", "imposter shot", "among us toast"],
    "Emergency meeting! EMERGENCY MEETING! Mario has called an emergency meeting!",
    "To the imposters, the sus accusations, and the people who always get voted out first! To Among Us!",
    "That toast was not sus at all! WAHOO! Or was it..."
))

events.append(simple_event(
    "gta", "Grand Theft Auto", "fun",
    ["gta shot", "gta toast", "grand theft auto shot"],
    "Wasted! Just kidding, nobody's wasted yet! Mario has a Grand Theft Auto toast!",
    "To the five stars, the tank rampages, and the hours spent doing absolutely nothing productive! To GTA!",
    "Remember, this is a party, not Los Santos! No stealing cars! WAHOO!"
))

events.append(simple_event(
    "call_of_duty", "Call of Duty", "fun",
    ["cod shot", "call of duty shot", "call of duty toast"],
    "Enemy toast incoming! Mario has a Call of Duty announcement for everyone!",
    "To the 360 no-scopes, the trash talk, and the lobbies that built character! To Call of Duty!",
    "Mission accomplished! WAHOO! Now get back to the party, soldier!"
))

events.append(simple_event(
    "league", "League of Legends", "fun",
    ["league shot", "league of legends shot", "league toast"],
    "First blood! Mario has initiated a League of Legends toast!",
    "To the ranked grind, the toxic teammates, and the supports who never get any credit! To League of Legends!",
    "GG no re! Back to the party! WAHOO!"
))

events.append(simple_event(
    "rocket_league", "Rocket League", "fun",
    ["rocket league shot", "rocket league toast"],
    "What a save! What a save! What a save! Mario has a Rocket League toast!",
    "To the aerial goals, the calculated plays, and the teammates who ball chase! To Rocket League!",
    "Nice shot! WAHOO! Chat disabled for 3 seconds!"
))

events.append(simple_event(
    "animal_crossing", "Animal Crossing", "celebratory",
    ["animal crossing shot", "animal crossing toast", "tom nook shot"],
    "Mario has an important announcement from Tom Nook! Just kidding, but please listen!",
    "To the island life, the fossil hunting, and the friends who visited our islands! Also to paying off Tom Nook's loans! To Animal Crossing!",
    "Now go check your turnip prices! WAHOO!"
))

events.append(simple_event(
    "elden_ring", "Elden Ring", "fun",
    ["elden ring shot", "elden ring toast", "tarnished shot"],
    "You Died! Just kidding! Fellow Tarnished, Mario has an Elden Ring toast!",
    "To the Tarnished, the impossible bosses, and everyone who rage quit at Malenia! To Elden Ring!",
    "That drink hit harder than Radahn! WAHOO!"
))

events.append(simple_event(
    "dark_souls", "Dark Souls", "fun",
    ["dark souls shot", "dark souls toast", "git gud shot"],
    "YOU DIED! But don't worry, you can respawn at the bonfire! Mario has a Dark Souls toast!",
    "To the bonfires, the invasions, and to gitting gud! To everyone who's ever thrown a controller! To Dark Souls!",
    "Praise the sun! And praise this drink! WAHOO!"
))

events.append(simple_event(
    "undertale", "Undertale", "fun",
    ["undertale shot", "undertale toast", "sans shot"],
    "You feel your phone vibrating! It's Mario, and he has an Undertale toast! You're filled with determination!",
    "To the monsters, the mercy button, and to everyone who cried at the pacifist ending! To Undertale and Toby Fox!",
    "You feel like you're going to have a great time at this party! WAHOO!"
))

# ============================================================
# MOVIES & TV EVENTS (15)
# ============================================================

events.append(simple_event(
    "star_wars", "Star Wars", "fun",
    ["star wars shot", "star wars toast", "force shot", "may the force"],
    "I sense a disturbance in the Force! Mario has a Star Wars toast for everyone!",
    "To the Jedi, the Sith, and everyone who argues about which trilogy is the best! May the Force be with you! To Star Wars!",
    "This is the way! WAHOO! Now back to the party, young padawans!"
))

events.append(simple_event(
    "marvel", "Marvel", "celebratory",
    ["marvel shot", "avengers shot", "marvel toast", "avengers toast"],
    "AVENGERS, ASSEMBLE! Mario is calling all heroes for this Marvel toast!",
    "To the Avengers, the Infinity Stones, and everyone who cried when Iron Man snapped! To Marvel!",
    "I am Iron Mario! Just kidding! WAHOO!"
))

events.append(simple_event(
    "breaking_bad", "Breaking Bad", "fun",
    ["breaking bad shot", "heisenberg shot", "breaking bad toast"],
    "Say my name! It's-a me, Mario! And I have a Breaking Bad toast!",
    "To Walter White, to Jesse Pinkman, and to the greatest show ever written! Say my name! To Breaking Bad!",
    "I am the one who knocks on bathroom doors! WAHOO!"
))

events.append(simple_event(
    "the_office", "The Office", "fun",
    ["office shot", "the office shot", "michael scott shot", "office toast"],
    "That's what she said! Sorry, sorry! Mario has a toast from Dunder Mifflin!",
    "To Michael, to Dwight, to Jim and Pam, and to everyone who's seen every episode at least five times! To The Office!",
    "I declare PARTY TIME! WAHOO!"
))

events.append(simple_event(
    "lord_of_rings", "Lord of the Rings", "celebratory",
    ["lord of the rings shot", "lotr shot", "frodo shot", "ring toast"],
    "One toast to rule them all! Mario has a Lord of the Rings announcement!",
    "To the Fellowship, to Frodo, and to Sam who carried everyone! You bow to no one! To the Lord of the Rings!",
    "And my axe! Wait, wrong quote! WAHOO!"
))

events.append(simple_event(
    "harry_potter", "Harry Potter", "fun",
    ["harry potter shot", "hogwarts shot", "harry potter toast", "butterbeer shot"],
    "You're a drinker, Harry! Mario has a magical Harry Potter toast!",
    "To Hogwarts, to Dumbledore's Army, and to butterbeer! Ten points to whatever house you're in! To Harry Potter!",
    "Mischief managed! WAHOO! Now get back to the common room!"
))

events.append(simple_event(
    "john_wick", "John Wick", "fun",
    ["john wick shot", "john wick toast", "baba yaga shot"],
    "Yeah, I'm thinking we're doing a toast! Mario channels his inner John Wick!",
    "To the Baba Yaga, to the pencils, and to everyone who loves a good action scene! To John Wick!",
    "That toast was breathtaking! WAHOO!"
))

events.append(simple_event(
    "spongebob", "SpongeBob SquarePants", "fun",
    ["spongebob shot", "spongebob toast", "bikini bottom shot"],
    "ARE YOU READY, KIDS? AYE AYE CAPTAIN! Mario has a SpongeBob toast!",
    "To SpongeBob, to Patrick, and to everyone who still watches it as adults! Who lives in a pineapple under the sea? To SpongeBob!",
    "I'm ready, I'm ready, I'm ready for more party! WAHOO!"
))

events.append(simple_event(
    "shrek", "Shrek", "fun",
    ["shrek shot", "shrek toast", "ogre shot"],
    "What are you doing in my swamp? Just kidding! Mario has a Shrek toast!",
    "To the ogre, the donkey, and the greatest fairy tale ever told! Because this party is like an onion, it has layers! To Shrek!",
    "Somebody once told me this party was gonna be great! WAHOO!"
))

events.append(simple_event(
    "batman", "Batman", "fun",
    ["batman shot", "batman toast", "dark knight shot"],
    "NA NA NA NA NA NA NA NA MARIO! Wait, no. Mario has a Batman toast!",
    "To the Dark Knight, to Gotham, and to everyone who does their best Batman voice at parties! To Batman!",
    "I'm not the hero this party deserves, but the one it needs! WAHOO!"
))

events.append(simple_event(
    "fast_furious", "Fast & Furious", "fun",
    ["fast and furious shot", "fast furious shot", "family shot", "dom shot"],
    "I don't have friends, I have family! Mario has a Fast and Furious toast!",
    "To family! To the quarter mile races, to the ridiculous stunts, and to Dom Toretto! Nothing is stronger than family! To Fast and Furious!",
    "We ride together, we party together! WAHOO!"
))

events.append(simple_event(
    "stranger_things", "Stranger Things", "fun",
    ["stranger things shot", "upside down shot", "stranger things toast"],
    "The lights are flickering! Something is coming from the Upside Down! Mario has a Stranger Things toast!",
    "To Eleven, to the Hawkins crew, and to everyone who binged the whole season in one night! To Stranger Things!",
    "Friends don't lie, and this party doesn't disappoint! WAHOO!"
))

events.append(simple_event(
    "game_of_thrones", "Game of Thrones", "fun",
    ["game of thrones shot", "got shot", "winter is coming shot"],
    "Winter is coming! But first, Mario has a Game of Thrones toast!",
    "To the Iron Throne, to the dragons, and to everyone who's still upset about Season 8! To Game of Thrones!",
    "What do we say to the God of Party? Not today! WAHOO!"
))

events.append(simple_event(
    "pirates_caribbean", "Pirates of the Caribbean", "fun",
    ["pirates shot", "jack sparrow shot", "pirates toast"],
    "But you HAVE heard of me! Captain Mario has a Pirates of the Caribbean toast!",
    "To Captain Jack Sparrow, to the Black Pearl, and to the rum! Why is the rum always gone? To Pirates!",
    "Now bring me that party! WAHOO!"
))

events.append(simple_event(
    "jurassic_park", "Jurassic Park", "fun",
    ["jurassic park shot", "dinosaur shot", "jurassic toast"],
    "Life, uh, finds a way! Mario has a Jurassic Park toast, and the dinosaurs are loose!",
    "To the dinosaurs, to Jeff Goldblum, and to the scientists who said maybe we shouldn't! To Jurassic Park!",
    "Clever girl! That toast was clever! WAHOO!"
))

# ============================================================
# MEME / INTERNET CULTURE EVENTS (10)
# ============================================================

events.append(simple_event(
    "rick_roll", "Rick Roll", "fun",
    ["rick roll shot", "never gonna shot", "rick roll toast", "rick astley shot"],
    "You know the rules, and so does Mario! It's time for the Rick Roll toast!",
    "Never gonna give you up! Never gonna let you down! Never gonna run around and desert you! To Rick Astley and the greatest meme ever!",
    "You just got rick rolled AND took a shot! WAHOO! Double whammy!"
))

events.append(simple_event(
    "sigma", "Sigma Grindset", "fun",
    ["sigma shot", "sigma toast", "grindset shot"],
    "The grind never stops! Mario has a toast for all the sigmas in the building!",
    "To the sigma grindset, to the hustle, and to everyone who wakes up at 4 AM to hit the gym! Wait, you're all at a party! To being sigma!",
    "Back to the grind! WAHOO! Just kidding, enjoy the party!"
))

events.append(simple_event(
    "based", "Based", "fun",
    ["based shot", "based toast", "extremely based shot"],
    "Based alert! Based alert! Mario has the most based toast of the evening!",
    "To being based, to having opinions, and to not caring what anyone thinks! This toast is extremely based! Raise your glasses!",
    "That was the most based thing I've ever seen! WAHOO!"
))

events.append(simple_event(
    "ohio", "Only in Ohio", "fun",
    ["ohio shot", "ohio toast", "only in ohio shot"],
    "What's happening in Ohio NOW? Mario has an Ohio toast, and things are getting weird!",
    "To Ohio, where anything can happen and usually does! To the memes, the chaos, and the absolute madness! Only in Ohio! Cheers!",
    "Normal day in Ohio! WAHOO! Now back to whatever state of chaos this party is!"
))

events.append(simple_event(
    "skibidi", "Skibidi Toilet", "fun",
    ["skibidi shot", "skibidi toast", "skibidi toilet shot"],
    "Skibidi dop dop dop yes yes! Mario has a toast that's perfect for the bathroom! Skibidi Toilet!",
    "To the Skibidi Toilet, to the Cameraman, and to Gen Alpha for confusing all of us! Skibidi dop dop! Cheers!",
    "That was very skibidi of us! WAHOO!"
))

events.append(simple_event(
    "no_cap", "No Cap", "fun",
    ["no cap shot", "no cap toast", "fr fr shot"],
    "No cap, fr fr, Mario has an important toast! This is deadass serious!",
    "To keeping it real, no cap, to the vibes, and to everyone here being absolutely bussin! For real for real! Raise your glasses!",
    "That was straight fire, no cap! WAHOO!"
))

events.append(simple_event(
    "ratio", "Ratio", "fun",
    ["ratio shot", "ratio toast", "get ratioed shot"],
    "RATIO! Mario just ratio'd everyone at this party! Time for a toast!",
    "To the ratios, the L takes, and the W's! To everyone who's ever been ratioed on Twitter! Counter ratio! Cheers!",
    "That toast did NOT get ratioed! WAHOO! Major W!"
))

events.append(simple_event(
    "yeet", "YEET", "fun",
    ["yeet shot", "yeet toast"],
    "YEET! Mario is about to yeet this toast into existence! Get ready everyone!",
    "To yeeting, to yoinking, and to the absolute CHAOS of this party! Ready? YEET your drinks! Cheers!",
    "That toast was YEETED into the stratosphere! WAHOO!"
))

events.append(simple_event(
    "vibe_check", "Vibe Check", "fun",
    ["vibe check shot", "vibe check toast", "vibe shot"],
    "VIBE CHECK! Mario is performing an official vibe check on this entire party!",
    "To the vibes, the energy, and everyone passing the vibe check tonight! You all passed! Raise your glasses to good vibes only!",
    "Vibes: immaculate! WAHOO! Party status: legendary!"
))

events.append(simple_event(
    "ok_boomer", "OK Boomer", "fun",
    ["ok boomer shot", "ok boomer toast", "boomer shot"],
    "OK BOOMER! Wait, none of you are boomers! Mario has a generational toast!",
    "To every generation! Boomers, Gen X, Millennials, Gen Z, and Gen Alpha! United by one thing, we all love a good party! Cheers to everyone!",
    "OK, that was actually wholesome! WAHOO!"
))

# ============================================================
# PARTY GAMES & CHALLENGES (15)
# ============================================================

events.append(simple_event(
    "waterfall", "Waterfall", "fun",
    ["waterfall shot", "waterfall toast", "waterfall"],
    "WATERFALL! Mario is calling for the ultimate party move! Everyone line up!",
    "When the countdown hits zero, the birthday boy starts drinking, then the person next to them, and so on! Last person to stop wins! WATERFALL!",
    "WAHOO! What a waterfall! Everyone survived! I think!"
))

events.append(simple_event(
    "never_have_i", "Never Have I Ever", "fun",
    ["never have i ever shot", "never have i ever toast", "never have i"],
    "It's confession time! Mario is starting a round of Never Have I Ever!",
    "Here's how it works! Mario says something, and if you've done it, you drink! Never have I ever been to a party THIS good! If you drink, that means this party is amazing! Cheers!",
    "Look at all of you drinking! This party IS amazing! WAHOO!"
))

events.append(simple_event(
    "kings_cup", "King's Cup", "fun",
    ["kings cup shot", "kings cup toast", "kings cup"],
    "ALL HAIL THE KING! Mario declares the King's Cup toast! The birthday boy is the King!",
    "To the King of the party, Jacob! The King decrees that everyone must raise their glass and drink in his honor! Long live the King!",
    "The King has spoken! WAHOO! What a ruler!"
))

events.append(simple_event(
    "flip_cup", "Flip Cup", "fun",
    ["flip cup shot", "flip cup toast", "flip cup challenge"],
    "It's flip cup time! Mario is calling for the most intense drinking game! Teams, assemble!",
    "To the flippers, the spills, and the champions! Drink it, flip it, NAIL IT! To Flip Cup! Cheers!",
    "Someone definitely spilled! WAHOO! That's the spirit!"
))

events.append(simple_event(
    "beer_pong", "Beer Pong", "fun",
    ["beer pong shot", "beer pong toast", "pong shot"],
    "SPLASH! Mario has a toast for the greatest table sport ever invented!",
    "To the sinks, the bounces, the re-racks, and the heated eye contact across the table! To Beer Pong champions everywhere!",
    "Nothing but cups! WAHOO! Is that a heating up? On fire!"
))

events.append(simple_event(
    "thunderstruck", "Thunderstruck", "fun",
    ["thunderstruck shot", "thunderstruck toast", "thunder shot"],
    "THUNDER! Mario just felt the thunder! It's time for the most electrifying toast!",
    "You've been THUNDERSTRUCK! To the legendary drinking game, to AC/DC, and to everyone brave enough to play! Cheers to the thunder!",
    "THUNDER! WAHOO! Feel the electricity of this party!"
))

events.append(simple_event(
    "shotgun", "Shotgun", "fun",
    ["shotgun shot", "shotgun toast", "shotgun a drink"],
    "SHOTGUN! Mario is calling for the fastest drinking challenge! Who's brave enough?",
    "To the brave souls who shotgun their drinks! Poke it, crack it, CHUG IT! To the shotgun legends! Ready, set, GO!",
    "WAHOO! That was FAST! Someone call the Guinness Book!"
))

events.append(simple_event(
    "power_hour", "Power Hour", "celebratory",
    ["power hour shot", "power hour toast"],
    "It's the power hour! Mario declares that this is the most powerful hour of the party!",
    "To the power hour! A shot every minute for 60 minutes! Just kidding, but how about ONE shot right now? To the POWER HOUR!",
    "That's the power of the party! WAHOO!"
))

events.append(simple_event(
    "chug", "Chug Challenge", "fun",
    ["chug shot", "chug toast", "chug challenge", "chug it"],
    "CHUG CHUG CHUG! Mario is calling for a chug challenge! Are you ready?",
    "To the chugging champions of the world! When the countdown hit one, you started chugging! To the legends! CHUG!",
    "WAHOO! What a chug! Someone check the record books!"
))

events.append(simple_event(
    "double_shot", "Double Shot", "fun",
    ["double shot", "double shot toast", "two shots"],
    "DOUBLE TROUBLE! Mario is calling for the double shot! That means TWO drinks, people!",
    "To doubling down! To going big or going home! Two glasses up, two drinks down! DOUBLE SHOT! Cheers!",
    "WAHOO! Double the fun, double the party! No one's driving, right?"
))

events.append(simple_event(
    "truth_or_dare", "Truth or Dare", "fun",
    ["truth or dare shot", "truth or dare toast", "truth or dare"],
    "TRUTH OR DARE! Mario is starting a round! But first, a toast!",
    "To the truths that embarrass us and the dares that scare us! Whatever you choose, you're drinking first! To Truth or Dare!",
    "Ooh, spicy! WAHOO! Now someone pick truth or dare!"
))

events.append(simple_event(
    "spin_bottle", "Spin the Bottle", "fun",
    ["spin the bottle shot", "spin bottle toast", "spin the bottle"],
    "SPIN THE BOTTLE! Well, spin the SHOT glass! Mario has a spinning toast!",
    "To the spinner, the spinee, and everyone watching nervously! Take your shot and spin! To Spin the Bottle!",
    "Where did it land? WAHOO! Drama! I love it!"
))

events.append(simple_event(
    "categories", "Categories", "fun",
    ["categories shot", "categories toast", "categories game"],
    "Category is PARTY LEGENDS! Mario is starting a round of Categories!",
    "Here's how it works! Someone names a category, and we go around naming things in it! If you can't think of one, you drink! To Categories! Let's start with types of Mario power-ups!",
    "Someone was stumped! WAHOO! Better luck next category!"
))

events.append(simple_event(
    "most_likely", "Most Likely To", "fun",
    ["most likely shot", "most likely toast", "most likely to"],
    "WHO'S MOST LIKELY? Mario has a Most Likely To toast!",
    "Point to whoever is most likely to still be partying at 3 AM! Now drink if people pointed at you! To the most likely legends!",
    "The people have spoken! WAHOO!"
))

events.append(simple_event(
    "last_man", "Last One Standing", "fun",
    ["last man standing shot", "last one standing toast", "last man shot"],
    "LAST ONE STANDING! Mario declares the endurance challenge! Who will survive?",
    "To the party warriors! To everyone who's still here, still standing, and still having a blast! You are the LEGENDS! Raise your glasses!",
    "Standing ovation for the survivors! WAHOO!"
))

# ============================================================
# MUSIC ARTISTS (10)
# ============================================================

events.append(simple_event(
    "sabrina_carpenter", "Sabrina Carpenter", "fun",
    ["sabrina carpenter shot", "sabrina shot", "espresso shot", "sabrina toast"],
    "Wahoo! It's-a Sabrina Carpenter time! She's-a short and sweet, just like-a this espresso shot! Everyone grab-a your drinks!",
    "That's-a unwell! Sabrina would-a be proud! Now someone please explain-a what a nonsense word 'espresso' means in her song!",
    "Mario hopes-a you're feeling like a tall hot latte after that one!"
))

events.append(simple_event(
    "kanye", "Kanye West", "fun",
    ["kanye shot", "ye shot", "kanye toast"],
    "Yo Mario, I'm really happy for you, and I'mma let you finish, but this is the greatest toast of all time!",
    "To Ye, to the beats, and to Stronger, Faster, Better! I'mma let this party finish, but first, DRINK! To Kanye!",
    "That toast was a masterpiece! WAHOO! George Bush doesn't care about plumbers!"
))

events.append(simple_event(
    "eminem", "Eminem", "fun",
    ["eminem shot", "slim shady shot", "eminem toast", "rap god shot"],
    "Will the real Slim Shady please stand up? Mario has an Eminem toast!",
    "To the Rap God, to Stan, and to everyone who knows all the words to Lose Yourself! You only get one shot! Do not miss your chance to drink! To Eminem!",
    "Mom's spaghetti! WAHOO! Now sit back down!"
))

events.append(simple_event(
    "weeknd", "The Weeknd", "fun",
    ["weeknd shot", "the weeknd shot", "weeknd toast", "blinding lights shot"],
    "I've been blinded by the lights! Mario has a Weeknd toast! Can you feel your face?",
    "To The Weeknd, to Blinding Lights, and to everyone dancing with their eyes closed! I can't feel my face but I love it! Cheers!",
    "After hours at this party! WAHOO!"
))

events.append(simple_event(
    "travis_scott", "Travis Scott", "fun",
    ["travis scott shot", "cactus jack shot", "travis toast", "sicko mode shot"],
    "IT'S LIT! Mario has gone sicko mode with this Travis Scott toast!",
    "To La Flame, to Cactus Jack, and to SICKO MODE! Straight up! Raise your glasses and go crazy! To Travis Scott!",
    "That was LIT! WAHOO! Highest in the room!"
))

events.append(simple_event(
    "doja_cat", "Doja Cat", "fun",
    ["doja cat shot", "doja shot", "doja toast"],
    "You're a cow, you're a cat, you're a PARTY ANIMAL! Mario has a Doja Cat toast!",
    "To Doja Cat, to the hot pink, and to everyone who can't stop saying MOO! Say so, raise your glass! To Doja Cat!",
    "That toast was bussin'! WAHOO! Meow!"
))

events.append(simple_event(
    "bad_bunny", "Bad Bunny", "fun",
    ["bad bunny shot", "benito shot", "bad bunny toast"],
    "Yo perreo sola! Mario has a Bad Bunny toast! Yeh yeh yeh!",
    "To Bad Bunny, to the reggaeton, and to everyone who's been practicing their perreo! Dale! To Bad Bunny! Cheers!",
    "DALE! WAHOO! That toast was caliente!"
))

events.append(simple_event(
    "beyonce", "Beyonce", "celebratory",
    ["beyonce shot", "queen bey shot", "beyonce toast"],
    "ALL THE SINGLE LADIES! And everyone else too! Mario has a Beyonce toast!",
    "To Queen Bey, to the Beyhive, and to the greatest performer of our generation! Who run the world? GIRLS! To Beyonce!",
    "Flawless! WAHOO! Now get in formation!"
))

events.append(simple_event(
    "kendrick", "Kendrick Lamar", "fun",
    ["kendrick shot", "kendrick toast", "kdot shot", "humble shot"],
    "SIT DOWN! Be humble! Mario has a Kendrick Lamar toast!",
    "To K-Dot, to good kid m.A.A.d city, and to the king of the West Coast! HUMBLE! Raise your glass! To Kendrick Lamar!",
    "DNA says we keep partying! WAHOO!"
))

# ============================================================
# RANDOM FUN EVENTS (15)
# ============================================================

events.append(simple_event(
    "bathroom_break", "Bathroom Break", "fun",
    ["bathroom break shot", "bathroom shot", "bathroom toast"],
    "Speaking of bathrooms, Mario knows a thing or two about bathrooms! This is his domain!",
    "To every bathroom in the world! To the awkward encounters, the long waits, and the people who forget to flush! To BATHROOMS! Cheers!",
    "Now please, wash your hands! WAHOO!"
))

events.append(simple_event(
    "pizza_time", "Pizza Time", "celebratory",
    ["pizza shot", "pizza toast", "pizza time shot"],
    "PIZZA TIME! Mario knows about Italian food, and pizza is the best invention EVER! Toast time!",
    "To pizza! Pepperoni, mushroom, Hawaiian if you're brave enough! To the greatest food in the world! To PIZZA! Cheers!",
    "That's-a spicy toast! WAHOO! Now who ordered the pineapple?"
))

events.append(simple_event(
    "midnight", "Midnight Toast", "celebratory",
    ["midnight shot", "midnight toast", "witching hour shot"],
    "BONG! BONG! BONG! It's the witching hour! Mario has the official midnight toast!",
    "To midnight! The party is only getting started! To the night owls, the party animals, and everyone who's staying until sunrise! Cheers to midnight!",
    "The night is young and so are we! WAHOO!"
))

events.append(simple_event(
    "first_shot", "First Shot", "celebratory",
    ["first shot", "first shot toast", "opening shot"],
    "Ladies and gentlemen, Mario has the honor of announcing the VERY FIRST SHOT of the night!",
    "To the first of many! To new beginnings, to this amazing party, and to the birthday boy! This is just the start! To the FIRST SHOT!",
    "And so it begins! WAHOO! Many more to come!"
))

events.append(simple_event(
    "last_shot", "Last Shot", "celebratory",
    ["last shot", "last shot toast", "final shot", "one more shot"],
    "This is it! The FINAL shot of the night! Mario is getting emotional!",
    "To the last shot! To everyone who made it this far! To the memories, the laughs, and the friendships! One final cheers to the greatest party ever!",
    "WAHOO! What a night! I love you all! Sniff!"
))

events.append(simple_event(
    "birthday_wish", "Birthday Wish", "celebratory",
    ["birthday wish shot", "make a wish shot", "wish toast"],
    "Shhh, everyone! The birthday boy is about to make a wish! Mario needs silence!",
    "Close your eyes, Jacob! Make a wish! And while he does, everyone raise your glasses to the birthday boy and whatever amazing thing he wished for! To Jacob's birthday wish!",
    "Did it come true? Only time will tell! WAHOO!"
))

events.append(simple_event(
    "group_photo", "Group Photo", "celebratory",
    ["group photo shot", "photo shot", "selfie toast", "group photo toast"],
    "EVERYONE SQUEEZE IN! Mario is calling for a group photo moment! Get your phones out!",
    "To the memories! Everyone raise your glasses, smile big, and take the photo! Three, two, one, CHEERS! To the group photo!",
    "That one's going on the wall! WAHOO! Best photo ever!"
))

events.append(simple_event(
    "dance_battle", "Dance Battle", "fun",
    ["dance battle shot", "dance off shot", "dance battle toast"],
    "IT'S A DANCE OFF! Mario is calling for a dance battle! Clear the floor!",
    "To the dancers, the movers, and the shakers! After this drink, someone HAS to bust a move! To the DANCE BATTLE! Cheers!",
    "Those moves were fire! WAHOO! Or were they? The crowd decides!"
))

events.append(simple_event(
    "karaoke", "Karaoke Time", "fun",
    ["karaoke shot", "karaoke toast", "singing shot"],
    "IS THIS THING ON? Mario is calling for karaoke! Someone's about to embarrass themselves and it's going to be GREAT!",
    "To the singers, the screamers, and the ones who are tone deaf but don't care! Liquid courage! To KARAOKE! Cheers!",
    "Beautiful! Or terrible! Either way, WAHOO! Encore!"
))

events.append(simple_event(
    "couples", "Couples Toast", "celebratory",
    ["couples shot", "couples toast", "lovebirds shot"],
    "AWWW! Mario sees some lovebirds at this party! Time for a couples toast!",
    "To the couples! To the hand-holding, the matching outfits, and the shared drinks! You two are adorable! To LOVE! Cheers!",
    "Get a room! Just kidding! WAHOO! Love is beautiful!"
))

events.append(simple_event(
    "singles", "Singles Toast", "fun",
    ["singles shot", "singles toast", "single and ready"],
    "TO THE SINGLE PEOPLE! Mario sees you and you are THRIVING!",
    "To being single and ready to mingle! To the freedom, the dance floor, and not having to share your drink! To the SINGLES! Cheers!",
    "Your person is out there! Or not! Either way, WAHOO! Party time!"
))

events.append(simple_event(
    "designated_driver", "DD Appreciation", "celebratory",
    ["dd shot", "designated driver toast", "dd toast", "sober driver shot"],
    "HEROES DON'T ALWAYS WEAR CAPES! Mario has a toast for the designated drivers!",
    "To the designated drivers! The real MVPs of every party! You sacrifice your buzz so everyone gets home safe! To the DDs! Water cheers!",
    "You're the real hero tonight! WAHOO! Please drive safely!"
))

events.append(simple_event(
    "best_friend", "Best Friend", "celebratory",
    ["best friend shot", "bestie shot", "bff toast", "best friend toast"],
    "BFF ALERT! Mario is getting sentimental! Time for a best friend toast!",
    "To the best friends! The ones who've seen you at your worst and still showed up! Grab your bestie and raise your glasses! To FRIENDSHIP! Cheers!",
    "That's beautiful! WAHOO! Now hug it out!"
))

events.append(simple_event(
    "throwback", "Throwback", "fun",
    ["throwback shot", "throwback toast", "nostalgia shot", "remember when shot"],
    "THROWBACK TIME! Mario is taking this party back in time! Get ready for nostalgia!",
    "To the good old days! To the embarrassing middle school photos, the first crushes, and the friendships that started it all! To the THROWBACK!",
    "Those were the days! WAHOO! But tonight's pretty great too!"
))

events.append(simple_event(
    "roast", "Roast the Birthday Boy", "fun",
    ["roast shot", "roast toast", "roast jacob shot", "birthday roast"],
    "IT'S ROAST TIME! Mario is about to roast the birthday boy! Sorry, Jacob!",
    "To Jacob! The man, the myth, the legend who once dropped his phone in the toilet! Just kidding! But seriously, we love you, and this party is amazing! To ROASTING the birthday boy!",
    "All in good fun! WAHOO! Jacob's a good sport!"
))

# ============================================================
# SPORTS EVENTS (10)
# ============================================================

events.append(simple_event(
    "touchdown", "Touchdown", "fun",
    ["touchdown shot", "touchdown toast", "football shot"],
    "TOUCHDOWN! Mario is spiking the ball! Wait, this is a party, not a football game! Toast time!",
    "To the touchdowns, the Hail Marys, and the Super Bowl halftime shows! SIX POINTS for this toast! To FOOTBALL!",
    "That's a first down for this party! WAHOO!"
))

events.append(simple_event(
    "slam_dunk", "Slam Dunk", "fun",
    ["slam dunk shot", "dunk shot", "basketball toast"],
    "AND ONE! Mario just posterized everyone! Time for a basketball toast!",
    "To the slam dunks, the buzzer beaters, and the pickup games! Nothing but net! To BASKETBALL! Cheers!",
    "BOOM SHAKALAKA! WAHOO!"
))

events.append(simple_event(
    "goal", "GOOOOAL", "fun",
    ["goal shot", "soccer shot", "goal toast", "futbol shot"],
    "GOOOOOOOOOOAL! GOOOOOOAL! Mario is channeling his inner soccer commentator!",
    "To the beautiful game! To the goals, the saves, and everyone who pretends to care during the World Cup! GOOOOAL! To SOCCER! Cheers!",
    "WAHOO! That toast bent like Beckham!"
))

events.append(simple_event(
    "knockout", "Knockout", "fun",
    ["knockout shot", "ko shot", "boxing toast", "fight shot"],
    "DING DING DING! Round one! Mario has a knockout toast for all the fighters!",
    "To the knockouts, the uppercuts, and everyone who's ever shadow boxed in the bathroom mirror! To the FIGHTERS! Cheers!",
    "And the winner by TOAST is everyone! WAHOO!"
))

events.append(simple_event(
    "world_cup", "World Cup", "celebratory",
    ["world cup shot", "world cup toast"],
    "OLE OLE OLE OLE! Mario is bringing World Cup energy to this party!",
    "To the World Cup, to every nation, and to the fans who lose their minds every four years! OLE OLE OLE! To the WORLD CUP!",
    "We are the champions! WAHOO!"
))

events.append(simple_event(
    "super_bowl", "Super Bowl", "fun",
    ["super bowl shot", "super bowl toast"],
    "It's the SUPER BOWL of parties! Mario has the halftime toast!",
    "To the Super Bowl, to the commercials that cost millions, and to the halftime show! This party's commercial break is over! To the SUPER BOWL!",
    "Back to the game! WAHOO! I mean back to the party!"
))

events.append(simple_event(
    "home_run", "Home Run", "fun",
    ["home run shot", "baseball shot", "home run toast"],
    "IT'S OUTTA HERE! Mario just hit a home run! Baseball toast time!",
    "To the home runs, the grand slams, and the seventh inning stretch! Take me out to the party! To BASEBALL! Cheers!",
    "That toast was a grand slam! WAHOO!"
))

events.append(simple_event(
    "hole_in_one", "Hole in One", "celebratory",
    ["hole in one shot", "golf shot", "golf toast"],
    "FORE! Actually wait, don't yell fore at a party! Mario has a golf toast!",
    "To the hole in ones, the eagle putts, and everyone who pretends they're good at golf! To GOLF! Cheers!",
    "That toast was below par! In a good way! WAHOO!"
))

events.append(simple_event(
    "checkmate", "Checkmate", "fun",
    ["checkmate shot", "chess shot", "chess toast"],
    "CHECKMATE! Mario just made the smartest move of the night! Chess toast!",
    "To the chess players, the strategists, and everyone who's seen The Queen's Gambit! Your move! To CHESS! Cheers!",
    "That was a 200 IQ toast! WAHOO!"
))

events.append(simple_event(
    "strike_bowling", "Strike", "fun",
    ["bowling shot", "strike shot", "bowling toast"],
    "STRIKE! All ten pins are down! Mario has a bowling toast!",
    "To the strikes, the gutter balls, and the rented shoes! Everyone raise your glasses like a bowling ball! To BOWLING! Cheers!",
    "That toast knocked them all down! WAHOO! Spare me the puns!"
))

# ============================================================
# HOLIDAY / THEMED EVENTS (7)
# ============================================================

events.append(simple_event(
    "new_years", "New Year's", "celebratory",
    ["new years shot", "new years toast", "happy new year shot"],
    "FIVE, FOUR, THREE, TWO, ONE! HAPPY NEW YEAR! Wait, it's not New Year's! But Mario has a toast anyway!",
    "To new beginnings, to midnight kisses, and to resolutions we'll break by January 5th! HAPPY NEW YEAR! Wait, happy birthday! Same energy! Cheers!",
    "WAHOO! New year, new party, new memories!"
))

events.append(simple_event(
    "halloween", "Halloween", "fun",
    ["halloween shot", "halloween toast", "spooky shot", "trick or treat shot"],
    "BOO! Did Mario scare you? It's HALLOWEEN toast time! Or at least Halloween ENERGY!",
    "To the costumes, the candy, and the haunted houses! Trick or TREAT! And by treat, I mean DRINK! To HALLOWEEN! Cheers!",
    "That was spooky good! WAHOO! No more jump scares, I promise!"
))

events.append(simple_event(
    "christmas", "Christmas", "celebratory",
    ["christmas shot", "christmas toast", "merry christmas shot", "holiday shot"],
    "HO HO HO! Mario Claus is here with gifts! The gift is a TOAST!",
    "To Christmas, to the presents, and to the family arguments about politics at dinner! MERRY CHRISTMAS! Wait, it's a birthday party! Same vibe! Cheers!",
    "HO HO WAHOO! That was a gift of a toast!"
))

events.append(simple_event(
    "st_patricks", "St. Patrick's Day", "fun",
    ["st patricks shot", "st patricks toast", "irish shot", "green shot"],
    "TOP OF THE MORNING! Mario's turned green! It's St. Patrick's Day toast time!",
    "To the luck of the Irish, to the green beer, and to everyone who's suddenly Irish today! SLAINTE! To ST. PATTY'S! Cheers!",
    "Kiss the Blarney Stone! WAHOO! Or just kiss the birthday boy!"
))

events.append(simple_event(
    "valentines", "Valentine's Day", "celebratory",
    ["valentine shot", "valentines toast", "love shot"],
    "CUPID'S ARROW just hit this party! Mario has a Valentine's toast!",
    "To love, to crushes, and to everyone who bought themselves chocolate on Valentine's Day! We love LOVE! To VALENTINE'S! Cheers!",
    "Love is in the air! WAHOO! And possibly in your drink!"
))

events.append(simple_event(
    "oktoberfest", "Oktoberfest", "fun",
    ["oktoberfest shot", "oktoberfest toast", "prost shot"],
    "PROST! Mario is channeling his inner German! It's Oktoberfest at this party!",
    "To the steins, the pretzels, and the lederhosen! PROST! That means cheers in German! Everyone clink your glasses! To OKTOBERFEST!",
    "Ein Prosit, ein Prosit! WAHOO! Now polka dance!"
))

events.append(simple_event(
    "graduation", "Graduation", "celebratory",
    ["graduation shot", "grad toast", "diploma shot"],
    "CAPS IN THE AIR! Mario is celebrating all the graduates! Toast time!",
    "To the graduates, the all-nighters, and the student loans! You survived school! Now raise your glasses to the real world! To GRADUATION!",
    "Congratulations! WAHOO! Now pay your loans! Just kidding!"
))

# ============================================================
# BONUS: WEIRD/QUIRKY EVENTS (3 to hit 100)
# ============================================================

events.append(simple_event(
    "mystery_shot", "Mystery Shot", "fun",
    ["mystery shot", "mystery toast", "random shot", "surprise shot"],
    "MYSTERY SHOT! Nobody knows what's about to happen! Mario doesn't even know!",
    "To the unknown! To surprises, plot twists, and doing things that make absolutely no sense! Whatever you're drinking, CHUG IT! To the MYSTERY!",
    "What just happened? WAHOO! I have no idea but it was great!"
))

events.append(simple_event(
    "hot_take", "Hot Take", "fun",
    ["hot take shot", "hot take toast", "controversial shot"],
    "HOT TAKE INCOMING! Mario is about to drop a controversial opinion! Brace yourselves!",
    "Here's Mario's hot take, cereal is just cold soup! If you agree, drink! If you disagree, ALSO drink! There's no escape! To HOT TAKES! Cheers!",
    "SPICY! WAHOO! Fight about it in the comments!"
))

events.append(simple_event(
    "plot_twist", "Plot Twist", "fun",
    ["plot twist shot", "plot twist toast", "twist shot"],
    "PLOT TWIST! Everyone thought this party was winding down, but Mario says NO!",
    "To the plot twists! Just when you thought the party was over, it's JUST GETTING STARTED! Second wind! To the PLOT TWIST! Cheers!",
    "DIRECTED BY M. NIGHT SHYAMALAN! WAHOO! The party continues!"
))

# Build the final JSON
output = {
    "_README": "Shot Events Configuration — Add new party events by copying an existing entry below. See docs/EVENTS.md for details.",
    "events": events
}

# Verify count
print(f"Total events: {len(events)}")
assert len(events) == 103, f"Expected 103 events (3 original + 100 new), got {len(events)}"

# Check for duplicate names
names = [e["name"] for e in events]
dupes = [n for n in names if names.count(n) > 1]
if dupes:
    print(f"WARNING: Duplicate names: {set(dupes)}")
else:
    print("No duplicate names ✓")

# Check for duplicate keywords
all_kw = []
for e in events:
    for kw in e.get("voice_keywords", []):
        all_kw.append((kw, e["name"]))
seen = {}
for kw, name in all_kw:
    if kw in seen:
        print(f"WARNING: Keyword '{kw}' used by both '{seen[kw]}' and '{name}'")
    seen[kw] = name

# Write the JSON
import os
out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server", "data", "shot_events.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"Written to {out_path}")
print("Done!")
