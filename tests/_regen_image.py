"""Regenerate a single event image via Pollinations.ai."""
import requests
import sys
import time
from PIL import Image
from io import BytesIO

IMAGES = {
    "zelda": "The Legend of Zelda Hyrule landscape with Link holding Master Sword, Hyrule Castle in background, Triforce symbol glowing, fantasy adventure game art",
    "star_wars": "Star Wars epic scene with lightsabers glowing, Death Star in space background, Darth Vader silhouette, X-Wing fighters, sci-fi movie art",
    "game_of_thrones": "Game of Thrones Iron Throne in dark throne room, dragon silhouettes in background, medieval fantasy castle, HBO series art",
    "league": "League of Legends champions battling on Summoner's Rift, colorful magic abilities, MOBA game art with turrets and minions",
    "dark_souls": "Dark Souls bonfire scene with armored knight resting, gothic dark fantasy castle ruins, foggy atmosphere, challenging RPG game art",
    "beer_pong": "Beer pong table at a party with red solo cups arranged in triangle formation, ping pong ball mid-air, neon party lights background",
    "categories": "Drinking game categories card game at a party, colorful category cards spread on table, fun party atmosphere with drinks",
    "checkmate": "Chess checkmate position closeup, king piece tipped over on chessboard, dramatic lighting, strategic board game victory",
    "chug": "Person chugging a drink at a party, crowd cheering in background, energetic party atmosphere, neon lights, college party vibes",
    "couples": "Romantic couple at a party, couple dancing together under string lights, love at a party, warm romantic atmosphere",
    "designated_driver": "Designated driver holding car keys at a party, sober friend responsible, group of friends celebrating while one stays sober, party safety concept",
    "last_man": "Last man standing drinking game, single person triumphantly standing while others are passed out at table, funny party endurance concept",
    "mario_kart": "Mario Kart racing scene, go-kart racing on rainbow road, colorful race track with power-ups, banana peels and shells, Nintendo racing game",
    "midnight": "Clock striking midnight, dramatic clock face showing 12:00, New Year countdown moment, dark sky with moonlight, cinematic midnight hour",
    "most_likely": "Most Likely To party game, group of friends pointing at each other laughing, fun social drinking game, party atmosphere",
    "new_years": "New Year's Eve celebration party, fireworks exploding over city skyline at midnight, champagne toast, confetti and sparklers, festive celebration",
    "oktoberfest": "Oktoberfest beer festival celebration, huge beer steins clinking together, Bavarian pretzels, German festival tent, traditional dirndl and lederhosen",
    "power_hour": "Power hour drinking game, shot glasses lined up in a row, timer counting down, intense party challenge, energetic drinking game atmosphere",
    "shotgun": "Shotgunning a beer at a party, person puncturing a beer can and chugging from the hole, friends cheering, outdoor party vibes",
    "skibidi": "Skibidi toilet meme, funny toilet character with human head, viral internet meme, surreal humor, Skibidi dop dop yes yes",
    "spin_bottle": "Spin the bottle party game, glass bottle spinning on floor in center of circle of people, classic party game, fun atmosphere",
    "vibe_check": "Vibe check meme, person making judging face while checking vibes, funny meme energy, neon vaporwave aesthetic, party mood assessment",
    "group_photo": "Group of friends taking a party selfie photo together, fun party atmosphere, colorful lights, everyone smiling and having fun, celebration",
    "pokemon": "Pokemon battle scene with Pikachu using thunderbolt attack, Pokeball on ground, colorful anime style, tall grass battlefield, Nintendo Pokemon game art",
    "among_us": "Among Us game characters in spaceship, red crewmate standing over dead body, emergency meeting scene, sus impostor, colorful astronaut beans",
    "ohio": "Ohio meme, dramatic apocalyptic Ohio landscape with explosions and chaos, Only in Ohio meme energy, surreal funny meme art",
    "ok_boomer": "OK Boomer meme, generational clash comic style, young person dismissing older person with OK Boomer text, funny internet meme art",
    "rick_roll": "Rick Astley Never Gonna Give You Up music video scene, man dancing in trenchcoat, 80s retro music video aesthetic, rickroll meme",
    "mystery_shot": "Mystery shot drinking game, colorful unknown mixed drink shots in row, question marks floating above glasses, suspenseful party game atmosphere",
    "waterfall": "Waterfall drinking game, cascade of drinks being poured like a waterfall, group of friends drinking in sequence, party game chain reaction",
    "kings_cup": "Kings Cup drinking game, playing cards spread in circle around large cup in center, classic party drinking game setup, cards and drinks",
    "fast_furious": "Fast and Furious movie scene, muscle cars racing through city streets at night, nitrous boost flames, street racing action, Vin Diesel style",
    "rocket_league": "Rocket League video game, rocket-powered car hitting giant soccer ball in futuristic arena, boost trails, car soccer game art, video game screenshot",
    "sabrina_carpenter": "Sabrina Carpenter pop singer performing on stage, blonde young woman singing into microphone, sparkly concert outfit, pop music concert stage lights",
    "smash_bros": "Super Smash Bros Ultimate fighting game, multiple Nintendo characters battling on floating platform, Mario vs Link vs Kirby, smash attack effects, game art",
}

name = sys.argv[1] if len(sys.argv) > 1 else "zelda"
prompt = IMAGES.get(name, f"{name} themed image")

url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=800&height=450&seed=42&nologo=true"
print(f"Generating {name} image...")

for attempt in range(3):
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 5000:
            img = Image.open(BytesIO(r.content))
            img = img.resize((800, 450), Image.LANCZOS)
            img.save(f"client/assets/event_images/{name}.png")
            print(f"OK: {len(r.content)} bytes")
            break
        else:
            print(f"Attempt {attempt+1}: status={r.status_code}, size={len(r.content)}")
            time.sleep(10)
    except Exception as e:
        print(f"Attempt {attempt+1}: {e}")
        time.sleep(10)
