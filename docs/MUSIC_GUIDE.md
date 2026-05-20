# 🎵 Event Music Guide

Every event can have a music file. Drop MP3s into `client/assets/event_music/` and update the event's `music_file` field in `server/data/shot_events.json`.

## How It Works

1. Put your MP3 in `client/assets/event_music/`
2. In `shot_events.json`, set `"music_file": "client/assets/event_music/your_file.mp3"`
3. Add `"music"` to the event's `"phases"` array (after `"countdown"`, before `"toast"`)
4. The server auto-detects the MP3 duration — no need to set `music_duration` manually

## Quick Add Script

```bash
# After adding MP3 files, run this to update all events:
python scripts/add_music_to_events.py
```

## Recommended Songs Per Event

### 🎮 Gaming (15)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `mario_kart` | Mario Kart - Rainbow Road | `mario kart rainbow road theme` |
| `smash_bros` | Super Smash Bros - Main Theme | `super smash bros ultimate main theme` |
| `zelda` | Legend of Zelda - Main Theme | `legend of zelda main theme orchestral` |
| `pokemon` | Pokemon Theme Song | `pokemon theme song original` |
| `minecraft` | Minecraft - Sweden (C418) | `minecraft sweden c418` |
| `fortnite` | Fortnite - OG Lobby Music | `fortnite og lobby music` |
| `among_us` | Among Us - Drip Theme | `among us drip theme` |
| `gta` | GTA San Andreas Theme | `gta san andreas theme song` |
| `call_of_duty` | COD MW2 - Hans Zimmer Theme | `modern warfare 2 theme hans zimmer` |
| `league` | League of Legends - Warriors (Imagine Dragons) | `warriors imagine dragons league of legends` |
| `rocket_league` | Rocket League - Breathing Underwater | `rocket league breathing underwater` |
| `animal_crossing` | Animal Crossing - Main Theme | `animal crossing new horizons theme` |
| `elden_ring` | Elden Ring - Main Theme | `elden ring main theme` |
| `dark_souls` | Dark Souls - Gwyn's Theme | `dark souls gwyn lord of cinder theme` |
| `undertale` | Undertale - Megalovania | `megalovania undertale` |

### 🎬 Movies/TV (15)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `star_wars` | Star Wars - Imperial March | `imperial march star wars` |
| `marvel` | Avengers Theme | `avengers theme song` |
| `breaking_bad` | Breaking Bad - Main Theme | `breaking bad theme song` |
| `the_office` | The Office - Theme Song | `the office theme song` |
| `lord_of_rings` | LOTR - Concerning Hobbits | `concerning hobbits lord of the rings` |
| `harry_potter` | Harry Potter - Hedwig's Theme | `hedwigs theme harry potter` |
| `john_wick` | John Wick - Shots Fired | `john wick theme song` |
| `spongebob` | SpongeBob Theme Song | `spongebob squarepants theme song` |
| `shrek` | All Star - Smash Mouth | `all star smash mouth` |
| `batman` | Batman - Dark Knight Theme | `dark knight theme hans zimmer` |
| `fast_furious` | See You Again - Wiz Khalifa | `see you again wiz khalifa` |
| `stranger_things` | Stranger Things - Theme | `stranger things theme song` |
| `game_of_thrones` | Game of Thrones - Main Theme | `game of thrones theme song` |
| `pirates_caribbean` | Pirates - He's a Pirate | `hes a pirate pirates of the caribbean` |
| `jurassic_park` | Jurassic Park - Main Theme | `jurassic park theme john williams` |

### 🤣 Memes (10)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `rick_roll` | Never Gonna Give You Up - Rick Astley | `never gonna give you up rick astley` |
| `sigma` | Drive Forever (Sigma Remix) | `drive forever sigma remix` |
| `based` | Can You Feel My Heart - BMTH | `can you feel my heart bmth` |
| `ohio` | Only in Ohio - Phonk | `only in ohio phonk` |
| `skibidi` | Skibidi Toilet Theme | `skibidi toilet theme song` |
| `no_cap` | No Cap - Future & Lil Uzi Vert | `no cap future lil uzi` |
| `ratio` | Megamind Theme (Phonk) | `megamind theme phonk` |
| `yeet` | This Is Sparta / Yeet Sound | `yeet sound effect bass boosted` |
| `vibe_check` | Buttercup - Jack Stauber | `buttercup jack stauber` |
| `ok_boomer` | OK Boomer Song | `ok boomer song` |

### 🍻 Party Games (15)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `waterfall` | Waterfalls - TLC | `waterfalls tlc` |
| `never_have_i` | Shots - LMFAO | `shots lmfao` |
| `kings_cup` | We Are The Champions - Queen | `we are the champions queen` |
| `flip_cup` | Timber - Pitbull | `timber pitbull` |
| `beer_pong` | Red Solo Cup - Toby Keith | `red solo cup toby keith` |
| `thunderstruck` | Thunderstruck - AC/DC | `thunderstruck acdc` |
| `shotgun` | Shotgun - George Ezra | `shotgun george ezra` |
| `power_hour` | Levels - Avicii | `levels avicii` |
| `chug` | Chug Jug With You | `chug jug with you` |
| `double_shot` | Two Shots - Goody Grace | `turn down for what dj snake` |
| `truth_or_dare` | Dare - Gorillaz | `dare gorillaz` |
| `spin_bottle` | Spin The Bottle - DRAM | `kiss from a rose seal` |
| `categories` | Category - Glee Cast | `mr brightside the killers` |
| `most_likely` | Most Girls - Hailee Steinfeld | `most girls hailee steinfeld` |
| `last_man` | Last Man Standing - Bon Jovi | `its the final countdown europe` |

### 🎵 Music Artists (9)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `sabrina_carpenter` | Espresso - Sabrina Carpenter | `espresso sabrina carpenter` |
| `kanye` | Stronger - Kanye West | `stronger kanye west` |
| `eminem` | Lose Yourself - Eminem | `lose yourself eminem` |
| `weeknd` | Blinding Lights - The Weeknd | `blinding lights the weeknd` |
| `travis_scott` | SICKO MODE - Travis Scott | `sicko mode travis scott` |
| `doja_cat` | Say So - Doja Cat | `say so doja cat` |
| `bad_bunny` | Titi Me Pregunto - Bad Bunny | `titi me pregunto bad bunny` |
| `beyonce` | Crazy In Love - Beyonce | `crazy in love beyonce` |
| `kendrick` | HUMBLE. - Kendrick Lamar | `humble kendrick lamar` |

### 🎲 Random Fun (15)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `bathroom_break` | Splash Waterfalls | `mr hankey the christmas poo` |
| `pizza_time` | Pizza Time Theme (Spider-Man 2) | `pizza time spiderman 2` |
| `midnight` | Midnight City - M83 | `midnight city m83` |
| `first_shot` | First Date - Blink-182 | `first date blink 182` |
| `last_shot` | Closing Time - Semisonic | `closing time semisonic` |
| `birthday_wish` | Birthday - Katy Perry | `birthday katy perry` |
| `group_photo` | Say Cheese - Kim Petras | `photograph nickelback` |
| `dance_battle` | Gonna Make You Sweat | `everybody dance now` |
| `karaoke` | Don't Stop Believin' - Journey | `dont stop believin journey` |
| `couples` | At Last - Etta James | `at last etta james` |
| `singles` | Single Ladies - Beyonce | `single ladies beyonce` |
| `designated_driver` | Sober - Demi Lovato | `sober demi lovato` |
| `best_friend` | You've Got a Friend - Carole King | `lean on me bill withers` |
| `throwback` | Everybody (Backstreet's Back) | `everybody backstreets back` |
| `roast` | Burn - Usher | `burn usher` |

### ⚽ Sports (10)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `touchdown` | Kernkraft 400 (Zombie Nation) | `zombie nation kernkraft 400` |
| `slam_dunk` | Space Jam Theme | `space jam theme song` |
| `goal` | Wavin' Flag - K'naan | `wavin flag knaan` |
| `knockout` | Eye of the Tiger - Survivor | `eye of the tiger survivor` |
| `world_cup` | Waka Waka - Shakira | `waka waka shakira` |
| `super_bowl` | Crazy Train - Ozzy Osbourne | `crazy train ozzy osbourne` |
| `home_run` | Centerfield - John Fogerty | `centerfield john fogerty` |
| `hole_in_one` | Tiger Woods PGA Tour Theme | `pga tour theme song` |
| `checkmate` | One - Metallica | `one metallica` |
| `strike_bowling` | The Big Lebowski Theme | `the big lebowski bowling theme` |

### 🎄 Holidays (7)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `new_years` | Auld Lang Syne | `auld lang syne new years` |
| `halloween` | Thriller - Michael Jackson | `thriller michael jackson` |
| `christmas` | All I Want For Christmas - Mariah | `all i want for christmas mariah carey` |
| `st_patricks` | Irish Drinking Song | `irish drinking song dubliners` |
| `valentines` | Can't Help Falling in Love - Elvis | `cant help falling in love elvis` |
| `oktoberfest` | Ein Prosit | `ein prosit oktoberfest` |
| `graduation` | Good Riddance - Green Day | `good riddance time of your life green day` |

### 🃏 Quirky (3)

| Event | Suggested Song | Search Term |
|-------|---------------|-------------|
| `mystery_shot` | X-Files Theme | `x files theme song` |
| `hot_take` | Hot in Herre - Nelly | `hot in herre nelly` |
| `plot_twist` | Roundabout - Yes (JoJo) | `roundabout yes jojo to be continued` |

## File Naming Convention

Name your MP3 files to match the event name:
```
client/assets/event_music/mario_kart.mp3
client/assets/event_music/rick_roll.mp3
client/assets/event_music/sabrina_carpenter.mp3
```

## After Adding Music

The `add_music_to_events.py` script will:
1. Scan `client/assets/event_music/` for MP3 files
2. Match filenames to event names
3. Update `shot_events.json` with the music_file path
4. Add the "music" phase to each event
5. Auto-detect MP3 duration

```bash
python scripts/add_music_to_events.py
```
