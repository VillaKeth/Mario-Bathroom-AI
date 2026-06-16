"""Scrape curated Honkai: Star Rail lore from the Fandom wiki into a YAML file
of fact strings, for ingestion into the character's semantic memory at startup.

Uses the MediaWiki `action=parse&prop=text` endpoint (the TextExtracts plugin is
not enabled on this wiki), then pulls clean paragraph text with BeautifulSoup.

Run offline (the server holds the single-process Qdrant lock, so it can't write
there while running):

    venv/Scripts/python.exe scripts/scrape_hsr_lore.py
    # -> characters/march7th/memories/hsr_lore.yaml

Then restart the server; it ingests the file via lore_knowledge.load_lore_file.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://honkai-star-rail.fandom.com/api.php"
USER_AGENT = "MarioAIPartyBot/1.0 (curated lore fetch for a local character bot)"

# Curated-deep page set: March + the Astral Express crew + world primer
# (concepts/Aeons/Paths) + factions + locations + the main playable roster.
PAGES = [
    # Crew + March
    "March 7th", "Astral Express", "Trailblazer", "Stelle", "Caelus",
    "Dan Heng", "Himeko", "Welt", "Pom-Pom", "Asta", "Arlan",
    # World / concepts
    "Honkai: Star Rail", "Aeon", "Path", "Stellaron", "Trailblaze",
    "Emanator", "Honkai", "Six-Phased Ice",
    # Aeons / Paths (key)
    "Akivili", "Qlipoth", "Lan", "Nous", "Yaoshi", "IX", "Aha", "Xipe", "Terminus",
    # Factions
    "Stellaron Hunters", "Interastral Peace Corporation", "Xianzhou Alliance",
    "Genius Society", "Masked Fools", "Garden of Recollection", "Galaxy Ranger",
    # Locations
    "Herta Space Station", "Jarilo-VI", "Belobog", "The Xianzhou Luofu",
    "Penacony", "Pier Point",
    # Major characters
    "Kafka", "Silver Wolf", "Blade", "Bronya", "Seele", "Gepard", "Jing Yuan",
    "Sampo", "Tingyun", "Yanqing", "Sushang", "Luocha", "Bailu", "Qingque",
    "Acheron", "Aventurine", "Robin", "Firefly", "Sunday", "Sparkle",
    "Ruan Mei", "Dr. Ratio", "Topaz", "Black Swan", "Boothill", "Argenti",
    "Huohuo", "Clara", "Herta",
]

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def extract_paragraphs(html: str) -> list:
    """Pull clean paragraph text from rendered MediaWiki HTML. Drops infoboxes,
    tables, figures, references, and citation markers."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["table", "aside", "figure", "style", "script", "sup", "ol"]):
        tag.decompose()
    out = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        text = re.sub(r"\[\d+\]", "", text)        # strip [1] style refs
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 40:
            out.append(text)
    return out


def paragraphs_to_facts(title: str, paragraphs: list,
                        max_facts: int = 30, max_chars: int = 280) -> list:
    """Turn paragraphs into title-prefixed, ~1-3 sentence fact chunks (deduped,
    capped). Each fact is prefixed with the page title so the subject is explicit
    in retrieval (e.g. 'March 7th: ...')."""
    facts = []
    seen = set()
    for para in paragraphs:
        sentences = [s.strip() for s in _SENTENCE_RE.split(para) if s.strip()]
        chunk = ""
        for sent in sentences:
            if chunk and len(chunk) + 1 + len(sent) > max_chars:
                _add_fact(facts, seen, title, chunk)
                chunk = sent
            else:
                chunk = f"{chunk} {sent}".strip()
        if chunk:
            _add_fact(facts, seen, title, chunk)
        if len(facts) >= max_facts:
            break
    return facts[:max_facts]


def _add_fact(facts, seen, title, chunk):
    chunk = chunk.strip()
    if len(chunk) < 20:
        return
    fact = f"{title}: {chunk}"
    key = fact.lower()
    if key not in seen:
        seen.add(key)
        facts.append(fact)


def fetch_page_html(title: str, timeout: int = 25) -> str:
    """Fetch rendered HTML for one wiki page via the parse API. '' if missing."""
    q = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "text",
        "format": "json", "redirects": "1",
    })
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        return ""
    return data.get("parse", {}).get("text", {}).get("*", "") or ""


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "characters", "march7th", "memories", "hsr_lore.yaml")
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    all_facts = []
    for i, title in enumerate(PAGES, 1):
        try:
            html = fetch_page_html(title)
        except Exception as e:
            print(f"[{i}/{len(PAGES)}] {title}: FETCH FAIL ({e})")
            continue
        if not html:
            print(f"[{i}/{len(PAGES)}] {title}: missing, skipped")
            continue
        facts = paragraphs_to_facts(title, extract_paragraphs(html))
        all_facts.extend(facts)
        print(f"[{i}/{len(PAGES)}] {title}: {len(facts)} facts")
        time.sleep(0.6)   # be polite to the wiki

    # Global dedupe (some pages repeat shared sentences)
    seen, deduped = set(), []
    for f in all_facts:
        if f.lower() not in seen:
            seen.add(f.lower())
            deduped.append(f)

    import yaml
    with open(out_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(deduped, fh, allow_unicode=True, sort_keys=False, width=1000)
    print(f"\nWrote {len(deduped)} lore facts -> {out_path}")


if __name__ == "__main__":
    main()
