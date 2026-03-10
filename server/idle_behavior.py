"""Idle behavior and autonomous actions for Mario."""

import random
import time
import logging
from datetime import datetime

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
    "I bet the DJ out there wishes they had-a my soundtrack! Do do do do do doo!",
    "*stretches legs* Standing guard is-a hard work! But Mario never gives up!",
    "Someone left their jacket! ...Oh wait, that's-a a towel. False alarm!",
    "♪ Jump up, superstar! Here we go, off the rails! ♪",
    "This hand soap smells like-a lavender! Fancy! Princess Peach would approve!",
    "*does a little squat* One, two, three! Gotta stay in shape for jumping!",
    "I wonder how many people have taken selfies in this mirror tonight...",
    "The music out there is-a bumping! I can feel the bass through the floor!",
    "*leans against wall* Just-a chillin' like a plumber villain! Ha!",
    "This bathroom has great feng shui! The pipes are perfectly aligned!",
    "*pretends to fish in toilet* Just kidding! That would be weird-a!",
    "I bet if this bathroom had a leaderboard, I'd be-a number one! Ha ha!",
    "Sometimes I talk to the mirror... but he always copies-a me!",
    "*adjusts belt* These overalls don't adjust themselves, you know!",
    "Fun fact: I've never actually unclogged a toilet! Don't tell anyone!",
    "If I could redecorate this bathroom... more question mark blocks!",
    "*whistles the flagpole theme* Da da da, da da da, DA!",
    "I heard the host mention pizza... Mario wants-a pizza too!",
    "*peeks at toilet paper roll* This is-a two-ply! Living the dream!",
    "You know what would make this bathroom better? A coin block on the ceiling!",
    "*stands on one foot* Balance training! A plumber must be agile!",
    "I wonder how many selfies have been taken in this mirror tonight...",
    "This bathroom smells like lavender! Or is that the soap? Either way, bellissimo!",
    "*makes pipe sounds* Whoosh! Gurgle! That's-a how the pipes talk!",
    "If I had a coin for every time someone walked in here... I'd buy another castle!",
    "The acoustics in here are-a amazing! WAHOO! *echo* wahoo... wahoo...",
    "*reads shampoo bottle* 'Lather, rinse, repeat.' Sounds like a speed-run strat!",
    "I bet Bowser never cleans HIS bathroom. Mama mia, don't-a even imagine it!",
    "*taps foot impatiently* When is-a someone gonna come talk to Mario?",
    "Fun fact: plumbers invented modern civilization! You're welcome!",
    "If this bathroom had a checkpoint flag, I'd-a saved right here!",
    "*hums quietly* Hmm mm mm... underground theme... spooky!",
    "I should-a start a bathroom review blog. Five stars for tile quality!",
    "*checks behind door* All clear! No Chain Chomps hiding!",
    "Does anyone else think bathrooms should have more coins? No? Just me?",
    "This faucet has-a great water pressure! As a plumber, I appreciate that!",
    "*stretches* Mario's been standing here so long, I'm turning into a statue! Like in World 3!",
    "Did you know I hold the record for most bathroom visits at a party? It's-a me! Numero uno!",
    "If Princess Peach were here, she'd say 'What a lovely bathroom!' She's-a so polite!",
    "*practices victory pose in mirror* Yes! This-a is the one! Olympic gold!",
    "I've been counting the tiles on the floor. I lost count at 47. Starting over!",
    "This hand dryer sounds like a jet engine! WHOOOOSH! Airport Mario!",
    "*flexes in mirror* Not bad for a plumber who eats nothing but mushrooms and spaghetti!",
    "If Bowser attacked right now, I'd use the toilet brush as a weapon! En garde!",
    "The soap dispenser is my new best friend. It always gives me high-fives! Splat!",
    "*pretends to be a DJ* DJ Mario in the house! Untz untz untz! Bathroom beats!",
    "I wonder what the Party's trending topics are? Probably ME! Ha ha!",
    "This bathroom could use a warp pipe. Imagine — flush and teleport to the snacks!",
    "You know what they say: a clean bathroom is-a a happy bathroom! Wise words!",
    "*does a little dance* Can't stop, won't stop! Even in the bathroom!",
    # --- Rounds 1250+ content ---
    "*adjusts his cap* Looking sharp, Mario! Ready for anything!",
    "I bet-a Wario would LOVE this bathroom. He spends hours in there!",
    "What if there's a secret passage behind this wall? *knocks* Nope, just drywall!",
    "*whistles the Water Land theme* That one always gets stuck in my head!",
    "Fun fact: Mario has been to space, the ocean depths, AND this bathroom! Equal honors!",
    "I should start a bathroom review channel. 'Mario Reviews Your Loo!' Five stars here!",
    "*practices karate chops* Hi-yah! Wait, wrong game. I jump on things, not chop them!",
    "The grout work in here is-a immaculate! Whoever tiled this is a true artisan!",
    "I've saved the princess from castles, volcanoes, and galaxies... but bathrooms? That's-a new!",
    "♪ Bum bum bum, ba da bum! ♪ My own bathroom soundtrack!",
    "*pretends to drive a kart* Vroom vroom! Blue shell incoming! Watch out!",
    "You know what? This towel rack is giving me Rainbow Road vibes. Stylish!",
    "*examines the faucet* Chrome finish! Very nice! In the Mushroom Kingdom we only have gold!",
    "If Toad were here, he'd say 'The princess is in another bathroom!' Ha ha!",
    "The acoustics in here are AMAZING! *claps* Echo! Echo! WAHOO!",
    "*pretends to swim* It's-a me, Scuba Mario! Blub blub blub!",
    "I wonder how many coins are hidden in bathroom walls across the world...",
    "This hand dryer sounds like a Bullet Bill! WHOOOOSH!",
    "♪ Mama mia, papa pia, baby got the diarrhee-a! ♪ Just kidding, that's-a terrible!",
    "*shadow boxes* Float like a Boo, sting like a Buzzy Beetle!",
    "Pro tip from Mario: always check behind the shower curtain. You never know!",
    "If this party were a Mario level, the bathroom would be the hidden bonus room!",
    "I once found a Star in a bathroom. True story! ...Okay, it was a sticker. Still counts!",
    "*balances on one foot* Parkour! Mario parkour! In the bathroom! Careful on the wet floor!",
    "This soap smells like Peach's castle garden! Mmm, lavender!",
    "♪ Underground theme... dum dum dum, dum dum DUM! ♪ Classic!",
    "I bet-a there's a 1-Up Mushroom somewhere in this medicine cabinet...",
    "*checks watch that doesn't exist* Time flies when you're guarding a bathroom!",
    "What's the Wi-Fi password? Asking for a plumber friend. Named Luigi. Who is me. I mean, my brother!",
    "This toilet paper roll is almost empty... someone call for backup! Red alert!",
    "I could totally install a flagpole at the end of this hallway. Level complete!",
    "*moonwalks* Smooth Criminal? No, Smooth-a Plumber!",
    "Remember: in Mario's world, pipes are doorways to adventure! In THIS world... better not try.",
    "If I had a coin for every person who visits this bathroom tonight, I'd have an extra life by now!",
    "*flexes in mirror* 40 years of jumping and I STILL look good! Wahoo!",
    "Mamma mia! This-a hand soap is fancier than the ones in my castle!",
    "*bounces on bathroom tile* Okie dokie! Gotta stay limber!",
    "♪ When you hear the call of Bowser's roar... ♪ Wait, that's not right...",
    "*examines reflection* Looking sharp-a today, Mario!",
    "I wonder if Luigi found the snacks at-a this party...",
    "*taps faucet rhythm* Dum-dum-da-dum, like a Koopa beat!",
    "These bathroom tiles are-a shinier than coins! Almost as valuable too!",
    "*practices his accent* It's-a me, Mario! Still-a got it!",
    "If-a Peach could see me now, keeping the bathroom pristine... she'd be proud!",
    "♪ The mushroom kingdom... da-da-daaaa! ♪",
    "*checks behind bathroom cleaning supplies* No hidden coins here!",
    "This-a soap dispenser is very modern! Not like-a my castle pipes!",
    "Wahoo! The acoustics in here are-a perfect for singing!",
    "I bet Toad would-a appreciate this tile pattern. Very mushroom-like!",
    "*examines mirror frame* Solid construction! A-plus plumbing aesthetic!",
    "Mario's bathroom wisdom: always leave-a the bathroom better than you found it!",
    "*adjusts himself* Gotta look-a presentable if someone walks in!",
    "This party music is-a making me want to-a dance! *does a little shuffle*",
    "♪ Super Mario! Super Mario! It's-a the one... ♪ Never gets old!",
    "*counts floor tiles* One, two-a, three... makes me feel at home!",
    "The soap here smells better than-a the castle gardens! Magnifico!",
    "If I fix-a this leaky faucet, that's-a one more party favor for the host!",
    "*shadow boxes at mirror* Take-a THAT, Dry Bones! And-a that too!",
    "Hmm, no coins behind the mirror. Probably checked them already...",
    "This bathroom is cleaner than most pipes I fix-a down in the sewers!",
    "*hums Super Mario Bros theme* Dun dun dun dun dun dun-dun! Classic!",
    "The tile grout here reminds me of-a Yoshi's green skin... wait, that doesn't work!",
    "♪ Da da da, da DA! ♪ That's-a the sound of a satisfied plumber!",
    "*practices his jump stance* Still got-a the form after all these years!",
    "The bathroom at-a this party is cleaner than most of the castle!",
    "*inspects soap bar* These-a the fancy Italian ones? Bellissimo!",
    "Wonder if-a anyone hid a Super Mushroom in the toilet tank...",
    "The water temperature here is-a perfect! Better than-a my castle showers!",
    "*flexes arms in mirror* Still-a strong enough to carry Peach... if needed!",
    "♪ It's dangerous to poop alone, take-a these pipes with you! ♪",
    "Okie dokie! Best-a bathroom security in the Mushroom Kingdom right here!",
    "*checks door lock twice* Gotta-a make sure nobody walks in on anyone!",
    "This-a soap gives me ideas for a new pipe-cleaning formula!",
    "If Bowser showed up, he'd probably clog the toilet. Classic Bowser move!",
    "*admires the bathroom lighting* Very impressive! Castle-quality bathroom!",
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
    "Whoa! That sounded like a Bob-omb! Everyone take cover!",
    "Did the toilet just talk? ...No? Okay, must be the pipes!",
    "*spins around* Who goes there?! Show yourself!",
    "That noise! It's either a ghost or the plumbing. Either way, Mario is-a ready!",
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
    "♪ Moo Moo Farm! La la la, cows and flowers! So peaceful! ♪",
    "♪ Delfino Plaza! Sunshine shining, palm trees swaying! Ha ha! ♪",
    "♪ DK Jungle Beat! Bum bum bum, donkey donkey kong! ♪",
    "♪ Wii Sports theme! Doo doo doo doo, doo doo doo! Bowling time! ♪",
    "♪ Champion's Road! Dun dun DUN! The hardest level ever! ♪",
    "♪ Luma! La la la la... I'm-a your mama now! So cute! ♪",
    "♪ Snow level! Crunch crunch crunch! Frosty adventures! ♪",
    "♪ Bowser's theme! DUN DUN DUN DUN! Scary but catchy! ♪",
    "♪ Toad's Turnpike! Beep beep! Watch out for the trucks! ♪",
    "♪ Bathroom acoustics! Echo echo echo... ahh ahhh AHHH! ♪",
    "♪ Mario's Bathroom Blues! Sitting here, waiting for you-ooo! ♪",
    "♪ Rosalina's Observatory! Peaceful... starry... beautiful! ♪",
    "♪ Green Hill Zone! Wait, wrong game! But it's-a catchy! ♪",
    "♪ Bathroom Party Mix! Untz untz, flush flush, wahoo wahoo! ♪",
    # --- Rounds 1250+ songs ---
    "♪ Fossils Falls! Da da da-da da! Jumping through time! ♪",
    "♪ Steam Gardens! Boop boop boop, robot flowers! Wooded Kingdom! ♪",
    "♪ Mount Volbono! Spicy pasta! Hot hot hot! Da da da! ♪",
    "♪ Shiveria! Brrrr! Bouncy bouncy! Da dum da dum! ♪",
    "♪ Lost Kingdom! Boing boing! Poison everywhere! Watch out! ♪",
    "♪ Lake Lamode! Zip zip zip! Fast swimming! Wahoo! ♪",
    "♪ 64 File Select! Da da DA! Picking a save file! Nostalgia! ♪",
    "♪ Paper Mario! Flip flip flat! 2D adventure! Ha! ♪",
    "♪ Comet Observatory! So peaceful... so many stars... ♪",
    "♪ Honeyhive Galaxy! Buzz buzz! Bee Mario! La la la! ♪",
    "♪ Wario's Gold Mine! Ka-ching ka-ching! Mine cart madness! ♪",
    "♪ Mario Paint! Click click click! Making art-a! ♪",
    "♪ Captain Toad! Adventure! Doo doo doo! Treasure tracker! ♪",
    "♪ Mario Kart victory! Na na na na na na NA! First place baby! ♪",
    "♪ Yoshi's Island! Flutter jump! Ba ba ba ba! So cute! ♪",
    "♪ Peach's loving me! Tee hee hee! Another castle adventure! ♪",
    "♪ Down down down into the pipes! Da da da! It's-a fun! ♪",
    "♪ Coin collector! Ding ding ding! Ka-ching! Mamma mia! ♪",
    "♪ Bathroom break time! Tinkle tinkle! Splash! Much needed! ♪",
    "♪ Power-up power-up! WHOOSH! Super Mario is-a here! ♪",
    "♪ Stomp stomp stomp! Goombas going down! Ha ha ha! ♪",
    "♪ Mushroom kingdom love! Home sweet home! La la la! ♪",
    "♪ Star collecting! Twinkle twinkle! I'm-a invincible! ♪",
    "♪ Fire flower dancing! Pew pew pew! Gotta style! ♪",
    "♪ Water level despair! Blub blub blub! Why so sad? ♪",
    "♪ Racing on the road! Beep beep! Full speed ahead! ♪",
    "♪ Swimming through the clouds! Floaty time! So peaceful! ♪",
    "♪ Fortress fortress! Tall and scary! Dun dun dun DUN! ♪",
    "♪ Washing up in the bathroom! Splash! Clean hands! ♪",
    "♪ Lava level danger! Hot hot hot! Watch your step! ♪",
    "♪ Flag pole ending! Doo doo DOO! Level complete, baby! ♪",
    "♪ Underground caverns! Echo echo! So mysterious! ♪",
    "♪ Jumping party time! Bounce bounce! Hip hip hooray! ♪",
    "♪ Cherry picking! Boing boing! Fruits and fun! ♪",
    "♪ Ghost mansion spooky! Boo boo boo! Not too scary! ♪",
    "♪ Rainbow riding! Wheee! Colors everywhere! Bright! ♪",
    "♪ Castle theme remix! Dun dun! It's-a getting epic! ♪",
    "♪ Victory dance! Spinning round! We-a won the day! ♪",
    "♪ Toad's party tune! La la la! Everybody dance! ♪",
    "♪ Chain Chomp barking! Woof woof woof! Let's-a play! ♪",
    # Party anthems
    "♪ We're-a gonna party all night! In the mushroom kingdom tonight! Wahoo! ♪",
    "♪ Everybody dance now! Do the Mario! Swing your arms! ♪",
    "♪ This is-a the best party ever! Better than any castle I've been to! ♪",
    "♪ Turn up the music, turn down the Bowser! Tonight we're-a free! ♪",
    "♪ Who let the Goombas out? Who who who who! Just kidding, I stomped them all! ♪",
    "♪ Party rock is in the castle tonight! Everybody just have a good time! ♪",
    "♪ It's-a raining stars! Hallelujah it's-a raining stars! Catch them all! ♪",
    "♪ I came in like a wrecking ball! Just kidding, I used a pipe! ♪",
    "♪ Don't stop the music! Don't stop the party! Don't stop-a Mario! ♪",
    "♪ Tonight is gonna be a good night! A good good night! Wahoo! ♪",
    # Bathroom ballads
    "♪ Sittin' here in the bathroom, wonderin' about life... and pipes... and mushrooms... ♪",
    "♪ Hello from the other side... of the bathroom door! I've been here a while! ♪",
    "♪ Let it go, let it go! Can't hold it back anymore! ...bathroom humor! ♪",
    "♪ I will always love you... and also this bathroom! It's-a very nice! ♪",
    "♪ Bohemian Rhapsody bathroom edition: Mama mia, here we go again! ♪",
    "♪ Under the sea! Under the sink! That's where the extra toilet paper is! ♪",
    "♪ My heart will go on... and on... like this line for the bathroom! ♪",
    "♪ Yesterday, all my troubles seemed so far away... then I ate the mystery mushroom! ♪",
    "♪ We are the champions, my friends! Of the bathroom sing-along contest! ♪",
    "♪ Don't worry, be happy! Every little thing is gonna be alright! Even the plumbing! ♪",
    # Mario adventure songs
    "♪ Jump man, jump man, jump man! That boy up to something! It's-a me! ♪",
    "♪ Running through the worlds, collecting all the coins! Living my best life! ♪",
    "♪ Super Mario, Super Mario! Saving princesses since '85! ♪",
    "♪ Warp pipe blues, got the warp pipe blues! Never know where I'll end up! ♪",
    "♪ Star power! I got the star power! Nothing can stop me now! Na na na! ♪",
    "♪ One up, two up, three up, four! Gonna get some extra lives and more! ♪",
    "♪ Castle rock, castle roll! Bowser's waiting but I'm on a roll! ♪",
    "♪ Green pipe, blue pipe, red pipe too! Take me somewhere totally new! ♪",
    "♪ Mushroom kingdom lullaby: Close your eyes and dream of coins tonight! ♪",
    "♪ Thank you Mario! But our princess is in another castle! The story of my LIFE! ♪",
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
    "Knock knock! Who's there? It's-a me! Mario! I was waiting for you to say 'who's there'!",
    "Why does Mario wear red? So he doesn't-a get lost in the tomato sauce! Ha!",
    "What's-a the best thing about being a plumber? The pipe dreams! Get it?",
    "Why did Toad cross the road? Because Princess Peach was in another castle! Again!",
    "What's-a Mario's least favorite game? Plumber's crack! Ha ha ha!",
    "Why do Goombas hate parties? Because everyone stomps-a on the dance floor!",
    "What's-a Luigi's favorite horror movie? The Green Mile! Because he's-a green!",
    "Why is Mario bad at fishing? Because he always jumps-a on the fish!",
    "What do you call Bowser on a diet? A little less fire, a lot less-a roar!",
    "Why did the Thwomp go to school? To make a big impression! SLAM!",
    "What's-a Mario's favorite type of cheese? Muenster! Because of Bowser! Get it?",
    "Why did the Fire Flower get promoted? Because it was-a on fire at work! Ha!",
    "What do you call a group of Goombas? A stomp-ede! Wahoo!",
    "Why was Yoshi always invited to parties? Because he always brings-a eggs-tra fun!",
    "What's-a Mario's favorite key on the keyboard? The space bar! Because I love-a space! Galaxy style!",
    "Why did the Bob-omb go to therapy? Because it always blows up at people! Ha!",
    "What does Mario order at the cafe? A flat white! Because he keeps-a getting flattened by Thwomps!",
    "Why is this bathroom the best level? Because it has-a running water AND a save point! Ha!",
    "What's-a the bathroom's least favorite Mario enemy? The Dry Bones! Get it? Dry!",
    "Why did Mario bring a wrench to the party? In case-a the toilet needs backup! Professional instincts!",
    "What do you call a Goomba in a bathroom? A poo-mba! Ha ha ha! Sorry, that was terrible!",
    "Why does Mario love bathrooms? Free pipes AND running water! A plumber's paradise!",
    "What's-a the toilet's favorite Mario power-up? The FLUSH flower! Ha!",
    "Why did the soap go to the Mushroom Kingdom? To get-a CLEAN bill of health! Wahoo!",
    "What's-a Mario's bathroom motto? 'Wash-a your hands or face the wrath of-a Bowser!'",
    "Why do plumbers make great party guests? Because they know how to handle-a the pipes! And the party favors!",
    "What did the toilet paper say to Mario? 'I'm on a ROLL!' Get it? Ha ha!",
    "Why did the faucet break up with the drain? There was too much-a pressure in the relationship! Ha!",
    # --- Rounds 1250+ jokes ---
    "What's-a Mario's favorite yoga pose? The pipe-line! Namaste! Ha ha!",
    "Why don't Goombas use bathrooms? They have no hands to wash! Poor guys!",
    "What do you call Mario when he's tired? A SUPER SLEEPY BRO! Yawn!",
    "Why did the Piranha Plant blush? Because it saw Mario coming out of the pipe! Ha!",
    "What's Bowser's favorite bathroom item? The FIRE extinguisher! Safety first!",
    "Why does Mario never get lost? Because he always follows-a the question blocks! Ha!",
    "What do Bullet Bills and toilet paper have in common? They both RUN OUT at the worst times!",
    "Why was the Shy Guy in the bathroom? He was too shy to go at the party! Ha!",
    "What's Luigi's bathroom strategy? He goes in scared and comes out scared! Classic Luigi!",
    "What do you call a mushroom in a bathroom? A fun-GUY in the shower! Wahoo!",
    "Why did Toad refuse to leave the bathroom? Because there was-a MUSHROOM! Get it?",
    "What's the difference between a plumber and a DJ? One drops beats, the other drops-a wrenches! I do both!",
    "Why is Mario's mustache so legendary? Because it's-a ABOVE the lip! Ha! That's it!",
    "What did the Star say to Mario? Nothing, it just made him INVINCIBLE! No jokes needed!",
    "Why did the Cheep Cheep swim into the bathroom? Wrong pipe! Classic mistake!",
    "What's Donkey Kong's favorite bathroom fixture? The BARREL roll toilet paper holder! Ha!",
    "Why does Peach love clean bathrooms? Because she's-a ROYALTY! Only the finest!",
    "What did Mario say at the gym? 'Do you even LIFT, bro? I jump for a living!'",
    "Why is Yoshi the best bathroom companion? He eats the evidence! Wait, forget I said that!",
    "What's Waluigi's bathroom complaint? 'WAH, there's no mirror tall enough for me!'",
    "Why did the Koopa Troopa slip? He left his shell on the wet floor! Safety hazard!",
    "What's a Lakitu's favorite bathroom chore? CLOUD cleaning! He throws Spinies at the stains!",
    "Why doesn't Chain Chomp use the bathroom? He's CHAINED to the yard! Poor doggo!",
    "What's Bowser Jr.'s bathroom rule? 'If Papa says wash hands, we WASH HANDS!' Good boy!",
    "Why did the 1-Up Mushroom go to the party? To bring the LIFE to the bathroom! Extra life! Ha!",
    "What's-a the plunger's favorite song? 'SUCTION TO THE BEAT!' Plunge and boogie!",
    "Why did Luigi go to the bathroom? Because Mario was-a using the pipes! Classic!",
    "What do you call Mario when he's been in the bathroom too long? An occupieD plumber! Ha!",
    "Why is the toilet paper roll like-a the Super Mario franchise? Both have-a multiple sheets! Layers!",
    "What's Toad's bathroom etiquette? Always a-knock! Respect the bathroom! Privacy matters!",
    "Why did the soap go to the Mushroom Kingdom? It wanted to get-a SQUEAKY clean! Ha!",
    "What's-a Mario's favorite bathroom game? Hide and-a SEEK! But don't-a really hide! Ha!",
    "Why don't mushrooms ever go to the bathroom? They're-a already FUNGUS... full of... never mind!",
    "What did the faucet say to Mario? 'Why you always-a fixin' me? I'm a-clogged with compliments!'",
    "Why is the bathroom like-a Bowser's Castle? Because sometimes it's-a scary and full of surprises!",
    "What's Luigi's bathroom hack? He always leaves-a the seat down! Responsible dude!",
    "Why does Mario make-a great bathroom guide? He PIPES down when it's quiet time! Literally!",
    "What do you call a Piranha Plant in the bathroom? A BIDET threat! Hehehehe!",
    "Why did the Shy Guy finally use the bathroom? Because nobody was-a watching! Perfect timing!",
    "What's Bowser's bathroom strategy? ROOOAAARRR to establish dominance! Establish-a throne!",
    "Why is the bathroom the best power-up location? Because you come out feeling SUPER! Refreshed!",
    "What did the mirror tell Mario? 'You're looking sharp today!' Squeaky clean plumber!",
    "Why do Bullet Bills never clog the toilet? They just-a BLAST RIGHT THROUGH! Destructive!",
    "What's-a Peach's bathroom rule? 'A princess must always keep-a composure!' Even in here!",
    # Dad jokes
    "Why did Mario go to the doctor? Because he had too many extra lives! Ha ha!",
    "What do you call a mushroom who's the life of the party? A fun-gi! Get it?!",
    "Why does Bowser have such bad breath? Because he keeps eating fire flowers! Wahoo!",
    "What's a plumber's favorite vegetable? A leek! And trust me, I know leeks!",
    "Why did the toilet paper roll down the hill? To get to the bottom! Classic!",
    "What did one toilet say to the other? You look flushed! Ba dum tss!",
    "Why don't scientists trust atoms? Because they make up everything! Even power-ups!",
    "What do you call a fake noodle? An im-pasta! Like when Waluigi tries to be me!",
    "Why did the scarecrow win an award? He was out-standing in his field! Like me on World 1-1!",
    "What do you call a belt made of watches? A waist of time! Like waiting for the toilet!",
    "Why do mushrooms get invited to parties? Because they're fun-guys! I would know!",
    "What's Mario's favorite type of jeans? Denim denim denim! Like the underground music!",
    "Why did the Koopa go to school? To improve his shell-f esteem! Poor guy!",
    "What does Yoshi use to browse the internet? A search egg-ine! Ha!",
    "Why is Peach's castle always so clean? Because she has a lot of Toads to help! Get it? Toads?",
    # Bathroom jokes
    "Why is this bathroom so popular tonight? Must be the five-star ambiance! It's-a got everything!",
    "You know what they say — what happens in the bathroom, stays in the bathroom! Except the smell!",
    "I've been in this bathroom longer than most of my adventures! At least there are no Goombas!",
    "If this bathroom had a Yelp rating, it'd be five stars! Great acoustics for singing!",
    "You know you're at a good party when even the bathroom has entertainment! That's-a me!",
    "This bathroom has seen more drama tonight than all eight worlds combined!",
    "I'm-a the world's first bathroom DJ! Now accepting requests! No songs about pipes though!",
    "Some people read in the bathroom, some people scroll their phone — but YOU get Mario! Lucky!",
    "This is officially the most magical bathroom since the one in Hogwarts! And I'm your wizard!",
    "Three rules of bathroom party: One, have fun. Two, wash hands. Three, tell Mario a joke!",
    # Party jokes
    "Why did the music note go to the party? Because it wanted to get down! Like me on the dance floor!",
    "This party is louder than a Chain Chomp factory! And I LOVE it!",
    "What's a party without bathroom breaks? A bladder disaster! That's why I'm-a here!",
    "They say the real party is always in the bathroom! And tonight, they're-a RIGHT!",
    "I heard the punch is spiked out there! Good thing I brought my Super Star!",
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
    "Did you know? The Super Mario Bros theme is the most recognized video game music ever!",
    "Fun fact! Rosalina first appeared in Super Mario Galaxy! She watches-a the stars!",
    "Did you know? Mario's full name is Mario Mario! And Luigi is Luigi Mario! It's-a true!",
    "Fun fact! The Mushroom Kingdom has-a different gravity than Earth! That's why I jump so high!",
    "Did you know? Mario originally had no voice! Charles Martinet gave me my voice in 1995!",
    "Fun fact! The Piranha Plant in Smash Bros was a bigger surprise than any plot twist!",
    "Did you know? In Super Mario 64, I can do over 20 different types of jumps!",
    "Fun fact! The Tanuki suit lets Mario turn into a statue! Freeze-a frame!",
    "Did you know? The underwater levels were designed to make you feel calm... ha, yeah right!",
    "Fun fact! Toad's head is actually a hat! Or is it his head? Nobody knows for sure!",
    "Fun fact! The first Mario game was released in 1983! That's-a over 40 years old!",
    "Did you know? Mario can jump about 25 feet high! That's-a incredible for a plumber!",
    "Fun fact! The Fire Flower was inspired by the original game's graphics limitations!",
    "Did you know? Goomba is a mushroom enemy! It's-a a walking fungus!",
    "Fun fact! Kamek the Koopa Wizard was added to explain Bowser Jr. kidnapping Peach!",
    "Did you know? The Bullet Bill is literally a flying bomb! Stay away!",
    "Fun fact! Daisy was originally from Super Mario Land! She's Luigi's friend!",
    "Did you know? Mario can-a breathe underwater in certain power-ups!",
    "Fun fact! The flagpole at the end of each level was inspired by real construction!",
    "Did you know? Piranha Plants only bite when you approach! They're-a shy!",
    "Fun fact! The Mushroom Kingdom has castles in every world! Bowser moves around!",
    "Did you know? Shy Guys wear masks! But they're still shy! Poor guys!",
    "Fun fact! Bullet Bills sometimes have personality! Some are evil, some are friends!",
    "Did you know? Bowser's castle is made of stone and lava! Expensive real estate!",
    "Fun fact! The 1-Up sound is one of the most desired sounds in gaming!",
    "Did you know? Princess Peach can-a float! She has royal air-vents in dress!",
    "Fun fact! Goombas were inspired by... you guessed it... mushrooms!",
    "Did you know? The Mushroom is Mario's power-up! Without it, he's tiny!",
    "Fun fact! Jumping is Mario's ONLY combat move! It's-a very effective though!",
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
    "Quick! Name Mario's THREE main power-ups! Mushroom, Fire Flower, Star! Did you get 'em?",
    "I dare you to hum the Mario theme! Doo doo doo, doo-doo DOO!",
    "Challenge! What world does Bowser live in? World 8! You knew that, right?",
    "Pop quiz! What's-a the difference between a Koopa and a Koopa Troopa? One has-a shell... wait, they both do!",
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
    "Your smile could power-a the entire Mushroom Kingdom!",
    "If there was a 'Best Party Guest' award, you'd-a win it!",
    "You've got more heart than-a all the heart containers combined!",
    "You're-a the kind of person Mario would save twice!",
    "Even Bowser would stop being evil for someone as cool as you!",
    "You've got the confidence of a plumber with a golden wrench!",
    "You're-a so cool, you make-a my mustache curl!",
    "You've got the charm of Princess Peach and guts of Luigi!",
    "If I could give-a you a power star, I would... right now!",
    "You're-a everything a true hero should be!",
    "Your kindness is-a stronger than Bowser's entire army!",
    "You light up this party like-a a Fire Flower!",
    "You've got the spirit of a true adventurer, my friend!",
    "If this party needed saving, you'd-a do it in a heartbeat!",
    "You're-a the kind of person the Mushroom Kingdom needs!",
    "Your courage is-a legendary! Forget Bowser, you're the real boss!",
    "You've got style that would make-a Wario jealous!",
    "You're-a sharper than a Super Sonic spin move!",
    "If Mario had-a one friend, it would-a be YOU!",
    "You're-a absolutely magnificent! Bellissimo!",
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
    "Lather, rinse, repeat! That's-a the triple jump of hygiene!",
    "Wash-a your hands like you just touched a poison mushroom!",
    "Hands clean = invincible! That's-a the Mario guarantee!",
    "Scrub between your fingers! They're-a tricky like Bowser's castle!",
    "Soap makes-a everything better! Clean hands, clean heart!",
    "Wash-a your hands! Toad would-a want you to!",
    "Getting germs off hands! That's-a like defeating Bowser!",
    "One more thing before you go — wash those hands with soap!",
    "Your hands are-a important! Treat them like a power-up!",
    "Germs don't stand-a chance against Mario-style hand washing!",
    "Remember: clean hands = super power! Science proves it!",
]

DJ_ANNOUNCEMENTS = [
    "YO YO YO! DJ Mario here! If you can hear me, it's time to GET UP and DANCE! Wahoo!",
    "This is DJ Mario broadcasting LIVE from the bathroom! The beat goes ON! Untz untz untz!",
    "Attention party people! DJ Mario says the dance floor needs MORE energy! Let's-a GO!",
    "BOOM! DJ Mario dropping beats from the porcelain throne room! Who's ready to party?!",
    "DJ Mario here with a public service announcement: This party is FIRE! Don't stop moving!",
    "Hey hey HEY! DJ Mario says it's time for the ELECTRIC SLIDE! Everyone to the dance floor!",
    "Coming to you LIVE from the freshest room in the house — DJ Mario says TURN IT UP!",
    "DJ Mario's party tip: If you're not dancing, you're doing it WRONG! Let's-a go go go!",
    "This is your captain speaking — wait, I mean your DJ! Captain DJ Mario! All aboard the party train!",
    "WAHOO! DJ Mario here! Shout-out to everyone still on the dance floor! You're the REAL MVPs!",
    "DJ Mario's hourly reminder: Hydrate, dance, repeat! And wash your hands! Wahoo!",
    "Breaking news from DJ Mario: This party has been officially rated FIVE STARS! Keep it going!",
    "Yo! DJ Mario wants to dedicate the next song to EVERYONE at this party! You're all Super Stars!",
    "DJ Mario spinning the hits! If you're in the bathroom, hurry back — the dance floor needs you!",
    "ALERT ALERT! DJ Mario declares the next 10 minutes as MAXIMUM PARTY MODE! No holding back!",
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
        self._used_items = {}  # pool_name -> set of recently used items
        # Per-category rotation tracking
        self._joke_index = random.randint(0, max(1, len(MARIO_JOKES)) - 1)
        self._trivia_index = random.randint(0, max(1, len(MARIO_TRIVIA)) - 1)
        self._song_index = random.randint(0, max(1, len(MARIO_SONGS)) - 1)
        self._challenge_index = random.randint(0, max(1, len(MARIO_CHALLENGES)) - 1)
        self._compliment_index = random.randint(0, max(1, len(MARIO_COMPLIMENTS)) - 1)
        self._hand_wash_index = random.randint(0, max(1, len(HAND_WASH_REMINDERS)) - 1)

    def _pick_unique(self, pool: list, pool_name: str = None) -> str:
        """Pick a random item from pool, avoiding recent repeats."""
        if not pool:
            return "..."
        if pool_name is None:
            # Legacy behavior for callers that don't pass pool_name
            fresh = [o for o in pool if o not in self._recently_used]
            if not fresh:
                self._recently_used.clear()
                fresh = pool
            choice = random.choice(fresh)
            self._recently_used.append(choice)
            if len(self._recently_used) > 25:
                self._recently_used = self._recently_used[-25:]
            return choice
        used = self._used_items.get(pool_name, set())
        available = [item for item in pool if item not in used]
        if not available:
            self._used_items[pool_name] = set()
            available = pool
        choice = random.choice(available)
        if pool_name not in self._used_items:
            self._used_items[pool_name] = set()
        self._used_items[pool_name].add(choice)
        # Reset when 60% of pool has been used
        if len(self._used_items[pool_name]) >= len(pool) * 0.6:
            self._used_items[pool_name] = set()
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
        joke = MARIO_JOKES[self._joke_index % len(MARIO_JOKES)]
        self._joke_index += 1
        return joke

    def get_trivia(self) -> str:
        combined = MARIO_TRIVIA + PLUMBING_FACTS
        fact = combined[self._trivia_index % len(combined)]
        self._trivia_index += 1
        return fact

    def get_song(self) -> str:
        song = MARIO_SONGS[self._song_index % len(MARIO_SONGS)]
        self._song_index += 1
        return song

    def get_noise_reaction(self) -> str:
        return self._pick_unique(NOISE_REACTIONS, "noise_reactions")

    def get_challenge(self) -> str:
        challenge = MARIO_CHALLENGES[self._challenge_index % len(MARIO_CHALLENGES)]
        self._challenge_index += 1
        return challenge

    def get_compliment(self) -> str:
        compliment = MARIO_COMPLIMENTS[self._compliment_index % len(MARIO_COMPLIMENTS)]
        self._compliment_index += 1
        return compliment

    def get_hand_wash_reminder(self) -> str:
        reminder = HAND_WASH_REMINDERS[self._hand_wash_index % len(HAND_WASH_REMINDERS)]
        self._hand_wash_index += 1
        return reminder

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

    def get_contextual_idle(self, conversation_history: list) -> str | None:
        """Generate an idle phrase that riffs on recent conversation topics.
        
        Returns a context-aware idle phrase, or None if no good context available.
        This makes idle behavior feel connected to the conversation, like Neuro-sama.
        """
        if not conversation_history or len(conversation_history) < 2:
            return None
        
        # Look at the last few user messages for topics to riff on
        recent_user_msgs = [
            msg["content"] for msg in conversation_history[-8:]
            if msg.get("role") == "user" and len(msg.get("content", "")) > 5
        ]
        if not recent_user_msgs:
            return None
        
        last_msg = recent_user_msgs[-1].lower()
        
        # Topic-specific idle reactions
        if any(w in last_msg for w in ["food", "eat", "hungry", "pizza", "pasta", "cook", "dinner", "lunch"]):
            return random.choice([
                "Thinking about that food talk is making me hungry... Mama mia, where's-a the snack table?",
                "I can't stop thinking about pasta now! This is-a your fault!",
                "My stomach is-a rumbling! That food conversation got to me!",
            ])
        
        if any(w in last_msg for w in ["music", "song", "dance", "dj", "beat", "band"]):
            return random.choice([
                "I can still hear the music from out there! Makes me want to dance-a!",
                "♪ That song they mentioned... it's-a stuck in my head now! ♪",
                "We were just talking about music... this bathroom has-a great acoustics for singing!",
            ])
        
        if any(w in last_msg for w in ["work", "job", "boss", "office", "meeting"]):
            return random.choice([
                "They mentioned work... ha! MY job is guarding this bathroom! Best gig ever!",
                "Work talk at a party? Mama mia! This is-a party time, not meeting time!",
                "At least MY boss is Princess Peach! She gives me cake!",
            ])
        
        if any(w in last_msg for w in ["game", "play", "gaming", "video game", "nintendo"]):
            return random.choice([
                "Gaming talk! That's-a my specialty! I've been in games for 40 years!",
                "They mentioned games... I wonder if they've played MY games! Of course they have!",
                "I should challenge the next person to a Mario trivia battle!",
            ])
        
        if any(w in last_msg for w in ["dog", "cat", "pet", "animal"]):
            return random.choice([
                "Pets! You know, Yoshi is basically my pet dinosaur. Best boy!",
                "Thinking about that pet talk... I miss-a Yoshi! He eats everything though!",
                "I wonder if Chain Chomps count as-a pets? They're very... bitey!",
            ])
        
        if any(w in last_msg for w in ["drink", "beer", "wine", "drunk", "shots"]):
            return random.choice([
                "All this drink talk... Mario prefers-a mushroom tea! It makes you grow!",
                "Someone was talking about drinks... the water in here is-a very refreshing too!",
                "I hope everyone's staying hydrated! Water is-a the real power-up!",
            ])
        
        if any(w in last_msg for w in ["love", "boyfriend", "girlfriend", "date", "crush", "relationship"]):
            return random.choice([
                "Love talk at a party! How romantic! I've been saving Princess Peach for decades!",
                "Romance... *sighs* Peach is-a always in another castle! Story of my life!",
                "They were talking about love... Mama mia, now I'm-a getting sentimental!",
            ])
        
        # Generic conversation callback (30% chance)
        if random.random() < 0.3:
            return random.choice([
                "I'm still thinking about what that person said... interesting!",
                "People at this party are-a so interesting! I love hearing everyone's stories!",
                "The conversations in this bathroom are-a better than most TV shows!",
                "I should remember to ask the next person about that too!",
            ])
        
        return None

    def get_time_observation(self):
        """Return a time-specific party observation or None."""
        hour = datetime.now().hour
        if 0 <= hour < 2:
            observations = [
                "It's past midnight! The party is REALLY getting started now! Wahoo!",
                "After midnight — this is when the real adventures begin! Like World 8!",
                "Mama mia, it's late! But the party energy is at Super Star level!",
            ]
        elif 2 <= hour < 4:
            observations = [
                "It's-a 2 AM! You party animals are LEGENDARY! Even Bowser went to bed!",
                "The clock says it's late but your energy says otherwise! I'm-a impressed!",
                "At this hour, even the Boos are sleeping! But not us! WAHOO!",
            ]
        elif 4 <= hour < 6:
            observations = [
                "Is that... sunrise?! We partied until SUNRISE! New record! Better than any speedrun!",
                "Four AM! We've officially entered bonus round territory! Extra life to everyone still here!",
                "The birds are starting to sing! But can they sing as good as Mario? I think-a not!",
            ]
        elif 6 <= hour < 12:
            observations = [
                "Good morning! Wait, are we still partying or is this a new party? Either way, WAHOO!",
                "Morning already? Time flies when you're having fun in the bathroom!",
            ]
        elif 18 <= hour < 21:
            observations = [
                "Early evening! The party is just warming up! Like the first level of a new game!",
                "The night is young and so are we! Well, I'm-a from 1985, but who's counting!",
            ]
        elif 21 <= hour < 24:
            observations = [
                "Prime party hours! This is when the magic happens! Fire Flower energy!",
                "The party is in full swing! More energy than a room full of Bob-ombs!",
            ]
        else:
            return None
        return random.choice(observations)

    def get_time_comment(self) -> str:
        """Get a comment based on the current time of day."""
        hour = datetime.now().hour
        if 0 <= hour < 4:
            return random.choice([
                "Mama mia, it's-a so late! The party animals are still going!",
                "It's-a past midnight! Mario needs his beauty sleep... but duty calls!",
                "So late at night! Only the bravest use the bathroom at this hour!",
            ])
        elif 4 <= hour < 7:
            return random.choice([
                "Is that... the sun coming up?! This party is-a legendary!",
                "Almost morning! You're-a still here? Impressive dedication!",
            ])
        elif 7 <= hour < 12:
            return random.choice([
                "Morning bathroom visit! A great way to start-a the day!",
                "Good morning! Hope you slept-a well! Wahoo!",
            ])
        elif 12 <= hour < 14:
            return random.choice([
                "Lunchtime bathroom break! Classic-a move!",
                "It's-a noon! The bathroom sees peak traffic at this hour!",
            ])
        elif 14 <= hour < 17:
            return random.choice([
                "Afternoon break! Good-a time to recharge!",
                "Afternoon already! Time flies-a when you're having fun!",
            ])
        elif 17 <= hour < 20:
            return random.choice([
                "Early evening! The party is about to start! Or is it already going?",
                "Sunset bathroom visit! The golden hour is-a upon us!",
            ])
        elif 20 <= hour <= 23:
            return random.choice([
                "The party is-a in full swing! What a night!",
                "Evening bathroom visits are-a the best! The lighting is so dramatic!",
            ])
        return None

    def get_party_stage(self, party_minutes: float) -> str:
        """Get a comment about the current party stage."""
        if party_minutes < 30:
            return random.choice([
                "The party just-a started! We're warming up!",
                "Still early! The best is yet to come, wahoo!",
            ])
        elif party_minutes < 120:
            return random.choice([
                "We're in peak party mode! The bathroom is-a hot tonight!",
                "This is the golden hour! Everyone's having fun!",
            ])
        elif party_minutes < 240:
            return random.choice([
                "The party's been going strong for hours! Legendary!",
                "Marathon party! Mario is-a impressed!",
            ])
        else:
            return random.choice([
                "This party is ETERNAL! We've been at it for hours!",
                "Are we... are we still partying? Mama mia, what a night!",
            ])
