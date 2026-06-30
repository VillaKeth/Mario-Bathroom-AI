r"""
GPT-SoVITS TTS Server — runs as a subprocess in the gpt_sovits_env venv.
Communicates via stdin/stdout JSON protocol for low-latency integration with main TTS pipeline.

Usage: gpt_sovits_env\Scripts\python.exe server\gpt_sovits_server.py
Protocol: 
  stdin  → JSON line: {"text": "Hello!", "ref_audio": "path.wav", "prompt_text": "ref text", "speed": 1.0}
  stdout → JSON line: {"status": "ok", "audio_path": "output.wav", "duration": 2.5, "elapsed": 1.3}
           or {"status": "error", "error": "message"}
  Special: {"cmd": "ping"} → {"status": "pong"}
           {"cmd": "quit"} → graceful shutdown
"""
import os
import sys
import json
import time
import tempfile
import gc
import numpy as np

DEBUG_SOVITS = True

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.join(BASE_DIR, "gpt_sovits_repo")
GPT_SOVITS_DIR = os.path.join(REPO_DIR, "GPT_SoVITS")
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, GPT_SOVITS_DIR)

MODEL_DIR = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario")
# Model weights + reference are env-overridable so this server is modular across
# characters. server/tts.py sets SOVITS_GPT_PATH / SOVITS_SOVITS_PATH (v2 base for
# non-fine-tuned characters) and SOVITS_REF_AUDIO / SOVITS_PROMPT_TEXT for the
# active character's clip. Unset -> Mario defaults (backward compatible).
SOVITS_PATH = os.environ.get("SOVITS_SOVITS_PATH") or os.path.join(MODEL_DIR, "Mario_e15_s255.pth")
GPT_PATH = os.environ.get("SOVITS_GPT_PATH") or os.path.join(MODEL_DIR, "Mario-e20.ckpt")
DEFAULT_REF_AUDIO = os.environ.get("SOVITS_REF_AUDIO") or os.path.join(MODEL_DIR, "mario_ref.wav")
DEFAULT_PROMPT_TEXT = os.environ.get("SOVITS_PROMPT_TEXT") or "It's a me Mario"
DEFAULT_PROMPT_LANG = os.environ.get("SOVITS_PROMPT_LANG") or "en"
CHARACTER = (os.environ.get("SOVITS_CHARACTER") or "mario").lower()
OUTPUT_DIR = os.path.join(BASE_DIR, "server", "tts_cache")


def _num_to_words(n):
    """Convert integer 0-999 to English words for TTS pronunciation."""
    ones = ['zero','one','two','three','four','five','six','seven','eight','nine',
            'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen',
            'seventeen','eighteen','nineteen']
    tens_w = ['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
    if not isinstance(n, int) or n < 0 or n > 999:
        return str(n)
    if n < 20:
        return ones[n]
    elif n < 100:
        return tens_w[n // 10] + ('' if n % 10 == 0 else ' ' + ones[n % 10])
    else:
        return ones[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + _num_to_words(n % 100))


def init_pipeline():
    """Initialize GPT-SoVITS pipeline — loads models onto GPU.
    
    Redirects stdout to stderr during loading to keep stdout clean for JSON protocol.
    """
    import yaml
    from io import StringIO

    # Redirect stdout during model loading (libraries print to stdout)
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    from TTS_infer_pack.TTS import TTS, TTS_Config

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    config_path = os.path.join(OUTPUT_DIR, "tts_infer.yaml")
    config = {
        "custom": {
            "bert_base_path": os.path.join(GPT_SOVITS_DIR, "pretrained_models", "chinese-roberta-wwm-ext-large"),
            "cnhuhbert_base_path": os.path.join(GPT_SOVITS_DIR, "pretrained_models", "chinese-hubert-base"),
            "device": "cuda",
            "is_half": False,
            "t2s_weights_path": GPT_PATH,
            "version": "v2",
            "vits_weights_path": SOVITS_PATH,
        }
    }
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    tts_config = TTS_Config(config_path)
    pipeline = TTS(tts_config)

    # Restore stdout for JSON protocol
    sys.stdout = _real_stdout
    return pipeline


def clean_text_for_tts(text):
    """Clean and normalize text for GPT-SoVITS synthesis."""
    import re as _re
    clean_text = text

    # Strip control characters (newlines, tabs, carriage returns cause garbled output)
    clean_text = clean_text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # Also strip literal escape sequences that might come from LLM output
    clean_text = clean_text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')

    # Parentheticals are SPOKEN (the bubble keeps the brackets). Convert the
    # brackets to comma pauses rather than deleting the words — TTS can't voice
    # "(" / ")". (Usually already done upstream in tts._preclean_tts_text; this
    # keeps the subprocess correct on its own.)
    clean_text = _re.sub(r'[()]', ', ', clean_text)

    # Remove sound effects / onomatopoeia that GPT-SoVITS cannot pronounce
    # NOTE: wahoo removed from this list — it's a key Mario catchphrase the model handles well
    _sfx_pattern = r'\b(?:whoosh|splish|splash|boom|boing|brr+|shh+|pfft+|mwah+|ka[\s\-]*ching|ching|whomp|swoosh|zing|thud|clang|bonk|tick[\s\-]*tock)\b'
    clean_text = _re.sub(_sfx_pattern, '', clean_text, flags=_re.IGNORECASE)

    # Normalize filler words to simple pronounceable forms (keep character, fix length)
    clean_text = _re.sub(r'\bhm+\b', 'Hmm', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bumm*\b', 'Um', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\buhh*\b', 'Uh', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bahh+\b', 'Ah', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bohh+\b', 'Oh', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\ber+m*\b', 'Um', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bmhm+\b', 'Mm hm', clean_text, flags=_re.IGNORECASE)

    # Pronunciation guides for words GPT-SoVITS garbles
    # Data from 220-round ralph loop + phonetic A/B testing:
    #   Every phonetic Bowser variant fails (Bowzah, Bowzer, Browser, etc → gibberish)
    #   BUT "the bad guy" transcribes perfectly! Model can't learn "Bowser" at all.
    #   Goomba/Goombah/Gumba all fail → "bad mushroom" works perfectly
    #   Koopa/Koopah fail → "Cooper" works
    #   Toad → "Todd" already close enough (model does this naturally)
    
    # Mario-specific name fixes — ONLY for Mario. Other characters must not have
    # words like "Peach"/"Princess" silently rewritten.
    if CHARACTER == "mario":
        # NOTE: "the bad guy" tested best in 220-round ralph loop, but user reports
        # Bowser sounds close to correct now — try "Bowsir" (preserves name, fixes ending)
        clean_text = _re.sub(r"\bBowser's\b", "Bowsir's", clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bBowser\b', 'Bowsir', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bBowzur\b', 'Bowsir', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bBowzer\b', 'Bowsir', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bBowzah\b', 'Bowsir', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bToad\b', 'Todd', clean_text)  # Case-sensitive: only proper noun
        clean_text = _re.sub(r'\bGoombas\b', 'bad mushrooms', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bGoomba\b', 'bad mushroom', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bGumbas\b', 'bad mushrooms', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bGumba\b', 'bad mushroom', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bKoopas\b', 'Coopers', clean_text, flags=_re.IGNORECASE)
        clean_text = _re.sub(r'\bKoopa\b', 'Cooper', clean_text, flags=_re.IGNORECASE)
        # Additional Mario character fixes (untested variants — keep original if it works)
        clean_text = _re.sub(r'\bPeach\b', 'Peech', clean_text)  # Prevent "Peach" → "Peesh"
        clean_text = _re.sub(r'\bPrincess\b', 'the princess', clean_text)  # Simplify
        clean_text = _re.sub(r'\bLuigi\b', 'Looigi', clean_text)  # Italian vowel stretch
        clean_text = _re.sub(r'\bYoshi\b', 'Yoh shee', clean_text)  # Phonetic split
        clean_text = _re.sub(r'\bDaisy\b', 'Dayzee', clean_text)  # Phonetic
        # Guest name pronunciation — "stedt" sounds like "stead" (as in steadfast)
        clean_text = _re.sub(r'\bHoppenstedt\b', 'Hoppenstead', clean_text)
    
    # Strip leading punctuation/whitespace left after word removal
    clean_text = _re.sub(r'^[\s,!?.;:\-]+', '', clean_text)

    # Replace non-standard words with pronounceable alternatives
    clean_text = _re.sub(r'\bbitey\b', 'biting', clean_text, flags=_re.IGNORECASE)
    # "okie dokie" — keep as-is, the model handles it reasonably well
    # clean_text = _re.sub(r'\bokie[\s\-]*dokie\b', "let's go", clean_text, flags=_re.IGNORECASE)
    # clean_text = _re.sub(r'\bokey[\s\-]*dokey\b', "let's go", clean_text, flags=_re.IGNORECASE)
    # "balls of fire" → "fire balls" (reversed word order transcribes perfectly as "Fireballs!")
    # Use flexible pattern to catch stretched spellings like "BAAAAAALLS"
    clean_text = _re.sub(r'\bba+l+s\s+of\s+fire\b', 'fire balls', clean_text, flags=_re.IGNORECASE)
    # "bathroom fun" → "this bathroom is fun" (short form garbles as "Batman!", longer works)
    clean_text = _re.sub(r'\bbathroom\s+fun\b', 'this bathroom is fun', clean_text, flags=_re.IGNORECASE)
    # "mine cart" is fine as two words — joining to "minecart" garbles as "my card"
    # clean_text = _re.sub(r'\bmine\s+cart\b', 'minecart', clean_text, flags=_re.IGNORECASE)
    # "quoted" garbles badly → "noted" (preserves meaning somewhat)
    clean_text = _re.sub(r'\bquoted\b', 'noted', clean_text, flags=_re.IGNORECASE)
    # "okie dokie" garbles to "Cheeey! Don't eat!" — replace entirely
    clean_text = _re.sub(r'\bokie[\s\-]*dokie\b', 'alrighty', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bokey[\s\-]*dokey\b', 'alrighty', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bnoo+\b', 'no', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byaa+y+\b', 'yay', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byay+\b', 'yay', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bsoo+\b', 'so', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bhee+lp\b', 'help', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byippee+\b', 'yippee', clean_text, flags=_re.IGNORECASE)
    # Number fractions: "10/10" → "10 out of 10"
    clean_text = _re.sub(r'(\d+)\s*/\s*(\d+)', r'\1 out of \2', clean_text)

    # Convert percentages to spoken form: "50%" → "fifty percent"
    def _pct_repl(m):
        try:
            n = int(m.group(1))
            return (_num_to_words(n) if 0 <= n <= 999 else m.group(1)) + ' percent'
        except ValueError:
            return m.group(0)
    clean_text = _re.sub(r'(\d+)%', _pct_repl, clean_text)

    # Convert standalone numbers (0-999) to words for better pronunciation
    def _num_repl(m):
        try:
            n = int(m.group(0))
            return _num_to_words(n) if 0 <= n <= 999 else m.group(0)
        except ValueError:
            return m.group(0)
    clean_text = _re.sub(r'\b\d{1,3}\b', _num_repl, clean_text)

    # Convert years (2000-2099) to spoken form: "2024" → "twenty twenty four"
    def _year_repl(m):
        try:
            n = int(m.group(0))
            if 2000 <= n <= 2009:
                return "two thousand " + (_num_to_words(n - 2000) if n > 2000 else "")
            elif 2010 <= n <= 2099:
                return _num_to_words(n // 100) + " " + _num_to_words(n % 100)
            return m.group(0)
        except (ValueError, KeyError):
            return m.group(0)
    clean_text = _re.sub(r'\b20\d{2}\b', _year_repl, clean_text)

    # Collapse repeated characters — vowels to 1, consonants to 2
    # "BAAAAAALLS" → "BALLS", "YAAAAY" → "YAY", "BRRRR" → "BRR"
    clean_text = _re.sub(r'([aeiouAEIOU])\1{2,}', r'\1', clean_text)
    clean_text = _re.sub(r'([^aeiouAEIOU\s\W])\1{2,}', r'\1\1', clean_text)

    # Acronyms that must be SPELLED as letters, not read as a word. The caps-normalizer
    # below would turn "AI" -> "Ai" (spoken like "eye"); force the A-I letter sound.
    # Runs BEFORE the caps-normalizer so it sees the original uppercase.
    clean_text = _re.sub(r'\bAIs\b', 'Ay Eyes', clean_text)
    clean_text = _re.sub(r'\bAI\b', 'Ay Eye', clean_text)

    # Roman numerals -> spoken words. ORDINALS for regnal names/titles ("Henry VIII"
    # -> "Henry the Eighth", "Louis XIV" -> "Louis the Fourteenth"); CARDINALS for
    # sequel/title keywords ("Part II" -> "Part Two", "World War II" -> "World War Two").
    # All gated on a leading word and the numeral group is UPPERCASE-only, so the
    # pronoun "I" and numeral-looking words (MIX, DID, CIVIC) are never touched. Runs
    # BEFORE the caps-normalizer, which would otherwise mangle "II" -> "Ii".
    def _roman_to_int(s):
        vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        total, prev = 0, 0
        for ch in reversed(s):
            v = vals.get(ch, 0)
            total += -v if v < prev else v
            prev = max(prev, v)
        return total
    _RN_CARDINAL = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six',
        7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten', 11: 'Eleven', 12: 'Twelve',
        13: 'Thirteen', 14: 'Fourteen', 15: 'Fifteen', 16: 'Sixteen', 17: 'Seventeen',
        18: 'Eighteen', 19: 'Nineteen', 20: 'Twenty'}
    _RN_ORDINAL = {1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth', 5: 'Fifth',
        6: 'Sixth', 7: 'Seventh', 8: 'Eighth', 9: 'Ninth', 10: 'Tenth', 11: 'Eleventh',
        12: 'Twelfth', 13: 'Thirteenth', 14: 'Fourteenth', 15: 'Fifteenth',
        16: 'Sixteenth', 17: 'Seventeenth', 18: 'Eighteenth', 19: 'Nineteenth',
        20: 'Twentieth', 21: 'Twenty First', 22: 'Twenty Second', 23: 'Twenty Third',
        24: 'Twenty Fourth', 25: 'Twenty Fifth', 26: 'Twenty Sixth', 27: 'Twenty Seventh',
        28: 'Twenty Eighth', 29: 'Twenty Ninth', 30: 'Thirtieth'}

    # Ordinals, title-gated (royal/papal) — safe to expand even a lone "I".
    def _ord_title(m):
        word = _RN_ORDINAL.get(_roman_to_int(m.group(2)))
        return f"{m.group(1)} the {word}" if word else m.group(0)
    clean_text = _re.sub(
        r'\b((?:King|Queen|Pope|Emperor|Empress|Tsar|Czar|Kaiser|Sultan|Prince|Princess|'
        r'Archduke|Duke|Duchess|Pharaoh)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+([IVXLCDM]+)\b',
        _ord_title, clean_text)

    # Ordinals, bare regnal first-name ("Louis XIV"). Skip a lone "I" — that is the
    # pronoun ("Louis I think..."), not a numeral.
    def _ord_name(m):
        if m.group(2) == 'I':
            return m.group(0)
        word = _RN_ORDINAL.get(_roman_to_int(m.group(2)))
        return f"{m.group(1)} the {word}" if word else m.group(0)
    clean_text = _re.sub(
        r'\b(Henry|Louis|Charles|George|Edward|William|Elizabeth|Philip|Richard|James|'
        r'Frederick|Catherine|Napoleon|Ferdinand|Leopold|Alexander|Nicholas|Constantine|'
        r'Benedict|Francis|Pius|Gregory|Clement|Innocent|Victoria)\s+([IVXLCDM]+)\b',
        _ord_name, clean_text)

    # Cardinals, sequel/title keyword ("Part II" -> "Part Two").
    def _expand_roman(m):
        word = _RN_CARDINAL.get(_roman_to_int(m.group(2)))
        return f"{m.group(1)} {word}" if word else m.group(0)
    clean_text = _re.sub(
        r'\b(Part|Chapter|Volume|Vol|Book|Episode|Act|Season|War|Wars)\s+([IVXLCDM]+)\b',
        _expand_roman, clean_text)

    # Normalize ALL CAPS to lowercase (GPT-SoVITS spells out capital letters)
    # Preserve first-letter caps for natural sentence flow
    def _normalize_caps(m):
        word = m.group(0)
        return word[0] + word[1:].lower()
    # Match any word with 2+ consecutive uppercase letters
    clean_text = _re.sub(r'\b[A-Z][A-Z]+\b', _normalize_caps, clean_text)
    # Also handle single ALL-CAP words at sentence start
    clean_text = _re.sub(r'(?<=[.!?]\s)[A-Z]{2,}\b', _normalize_caps, clean_text)

    # Mario's signature "-a" suffix: ATTACH it (it's-a -> it'sa) so the model voices
    # the -a flourish instead of dropping the orphaned "a". User wants it KEPT even
    # if it warbles. (Tested: spaced drops it; -uh drops too; attached keeps it most.)
    clean_text = _re.sub(r'(?<=\w)-a\b', 'a', clean_text, flags=_re.IGNORECASE)
    # Remove ALL hyphens — GPT-SoVITS either reads "-" as "minus" or produces silence
    # Step 1: "word-word" → "word word" (compound words keep space)
    clean_text = _re.sub(r'(?<=\w)-(?=\w)', ' ', clean_text)
    # Step 2: " - " freestanding hyphens → comma pause
    clean_text = _re.sub(r'\s+-+\s+', ', ', clean_text)
    # Step 3: Remove ALL remaining hyphens (leading, trailing, multiple dashes)
    clean_text = _re.sub(r'-+', '', clean_text)

    # Interjection phonetics — must run AFTER hyphen removal & char collapse
    # "Ha He!" → "Hey hey!" (simpler form the model can pronounce)
    clean_text = _re.sub(r'\bha\s+he\b', 'Hey hey', clean_text, flags=_re.IGNORECASE)
    # Don't convert "ha ha ha" to "hah hah hah" — the repeated 'hah' garbles
    # Don't convert trailing ha→hah either — it causes more garbling than it fixes

    # Handle "da" interjections AFTER hyphen removal (da-da-daa → da da daa → removed)
    clean_text = _re.sub(r'\bdaa+\b', 'da', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bda(?:\s+da)+\b', '', clean_text, flags=_re.IGNORECASE)
    # Also remove standalone "da" at end of sentence (leftovers)
    clean_text = _re.sub(r'\bda\b\s*([!.,?])', r'\1', clean_text, flags=_re.IGNORECASE)

    # Remove special characters that cause garbled output
    clean_text = _re.sub(r'[♪♫🎵🎶🎤🎸🎹🎺🎻🎷🥁🎭🎪]', '', clean_text)  # Music/performance emojis
    clean_text = _re.sub(r'[\U0001F600-\U0001F64F]', '', clean_text)  # Emoticons
    clean_text = _re.sub(r'[\U0001F300-\U0001F5FF]', '', clean_text)  # Misc symbols
    clean_text = _re.sub(r'[\U0001F680-\U0001F6FF]', '', clean_text)  # Transport/map
    clean_text = _re.sub(r'[\U0001F900-\U0001F9FF]', '', clean_text)  # Supplemental symbols
    clean_text = _re.sub(r'[\u2600-\u26FF]', '', clean_text)  # Misc symbols (★, ☆, etc.)
    clean_text = _re.sub(r'[\u2700-\u27BF]', '', clean_text)  # Dingbats (✓, ✗, etc.)
    clean_text = _re.sub(r'[\u2190-\u21FF]', '', clean_text)  # Arrows
    clean_text = _re.sub(r'[\u2500-\u257F]', '', clean_text)  # Box drawing
    clean_text = _re.sub(r'\*+', ' ', clean_text)  # Asterisks → space (keep word gaps; collapsed at end)
    clean_text = clean_text.replace('~', '')  # Tildes
    clean_text = clean_text.replace('#', '')  # Hash symbols
    clean_text = clean_text.replace('@', ' at ')  # @ sign → spoken form
    clean_text = clean_text.replace('&', ' and ')  # Ampersand → spoken form
    clean_text = clean_text.replace('+', ' plus ')  # Plus sign → spoken form
    clean_text = clean_text.replace('=', ' equals ')  # Equals → spoken form
    clean_text = clean_text.replace('<', '').replace('>', '')  # Angle brackets
    clean_text = clean_text.replace('{', '').replace('}', '')  # Curly braces
    clean_text = clean_text.replace('[', '').replace(']', '')  # Square brackets
    clean_text = clean_text.replace('(', ', ').replace(')', ', ')  # Parentheses → pauses
    clean_text = clean_text.replace('/', ' ')  # Slashes → space
    clean_text = clean_text.replace('\\', ' ')  # Backslashes → space
    clean_text = clean_text.replace('_', ' ')  # Underscores → space
    clean_text = clean_text.replace('…', ' ')  # Smart ellipsis → space (not comma — avoids leading ", ")
    clean_text = _re.sub(r'\.{2,}', ' ', clean_text)  # Multi-dots → space (TTS garbles dots)
    clean_text = clean_text.replace('"', '"').replace('"', '"')  # Smart quotes → straight
    clean_text = clean_text.replace(''', "'").replace(''', "'")  # Smart apostrophes
    clean_text = clean_text.replace('"', '')  # Remove remaining quotes (TTS reads them)
    # Remove non-contraction single quotes: 'hello' → hello, but keep don't, it's
    clean_text = _re.sub(r"(?<![a-zA-Z])'|'(?![a-zA-Z])", '', clean_text)
    clean_text = clean_text.replace('—', ', ').replace('–', ', ')  # Em/en dashes → comma
    # Remove excessive punctuation ("?!?!" → "?!")
    clean_text = _re.sub(r'([!?])\1+', r'\1', clean_text)
    clean_text = _re.sub(r'[!?]{3,}', '?!', clean_text)
    # Remove any remaining multi-dots (safety net after earlier dot normalization)
    clean_text = _re.sub(r'\.{2,}', ' ', clean_text)
    # Convert mid-sentence periods to commas (prevents TTS sentence fragmentation)
    # "Line one. Line two. Line three." → "Line one, Line two, Line three."
    # Only convert periods followed by space+uppercase (sentence boundaries mid-text)
    # Keep final period
    clean_text = _re.sub(r'\.\s+(?=[A-Z])', ', ', clean_text)
    # Also convert mid-sentence "!" followed by lowercase to comma (prevents fragmentation)
    # "Oh no! the bad guy" → "Oh no, the bad guy"
    clean_text = _re.sub(r'!\s+(?=[a-z])', ', ', clean_text)
    # Clean up multiple commas/spaces from substitutions
    clean_text = _re.sub(r',\s*,', ',', clean_text)
    # Strip leading/trailing punctuation left from removals
    clean_text = _re.sub(r'^[\s,!?.;:\-]+', '', clean_text)
    # Remove trailing orphan punctuation (e.g. ", !" left after content removal)
    clean_text = _re.sub(r',\s*[!?.]+\s*$', '', clean_text)
    clean_text = _re.sub(r'[\s,]+$', '', clean_text)
    clean_text = _re.sub(r'\s+', ' ', clean_text).strip()

    # Pad very short phrases — GPT-SoVITS garbles text with few words
    _words = clean_text.split()
    _char_len = len(clean_text)
    if len(_words) >= 1 and _char_len < 19:
        # Skip padding if phrase already starts with a filler/intro word
        _lower = clean_text.lower()
        _already_has_intro = any(_lower.startswith(p) for p in [
            'oh,', 'oh ', 'ah,', 'ah ', 'hmm,', 'hmm ', 'um,', 'um ',
            'uh,', 'uh ', 'mama mia', 'ha ', 'hah', 'hey,', 'hey ',
        ])
        # Don't pad bare numbers / countdown words — "Oh, ten!" sounds like the
        # voice says "a-ten" before every countdown number.
        _bare = _re.sub(r'[^a-z0-9]', '', _lower)
        _is_number = _bare.isdigit() or _bare in {
            'zero', 'one', 'two', 'three', 'four', 'five',
            'six', 'seven', 'eight', 'nine', 'ten',
        }
        if not _already_has_intro and not _is_number:
            clean_text = "Oh, " + clean_text[0].lower() + clean_text[1:]
            if DEBUG_SOVITS:
                print(f"[sovits] SHORT PHRASE PADDED: '{clean_text}'", file=sys.stderr)

    # Ensure first character is capitalized after all removals
    if clean_text and clean_text[0].islower():
        clean_text = clean_text[0].upper() + clean_text[1:]

    return clean_text


def synthesize(pipeline, text, ref_audio=None, prompt_text=None, speed=1.0, prompt_lang=None, text_lang=None):
    """Generate audio from text using GPT-SoVITS pipeline."""
    import soundfile as sf

    if ref_audio is None:
        ref_audio = DEFAULT_REF_AUDIO
    if prompt_text is None:
        prompt_text = DEFAULT_PROMPT_TEXT
    if prompt_lang is None:
        prompt_lang = DEFAULT_PROMPT_LANG
    if text_lang is None:
        text_lang = "en"

    clean_text = clean_text_for_tts(text)

    # If text was entirely sound effects/filler, return a short silence file
    if not clean_text or len(clean_text.strip()) == 0:
        if DEBUG_SOVITS:
            print(f"[sovits] ORIGINAL: '{text[:100]}' → EMPTY after cleaning, returning silence", file=sys.stderr)
        silence = np.zeros(16000, dtype=np.float32)  # 0.5s silence at 32kHz
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        silence_path = os.path.join(OUTPUT_DIR, f"silence_{int(time.time()*1000)}.wav")
        sf.write(silence_path, silence, 32000)
        return silence_path, 0.5

    if DEBUG_SOVITS:
        if clean_text != text:
            print(f"[sovits] ORIGINAL: '{text[:100]}'", file=sys.stderr)
        print(f"[sovits] clean_text: '{clean_text[:100]}'", file=sys.stderr)

    req = {
        "text": clean_text,
        "text_lang": text_lang,
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "text_split_method": "cut5",
        "speed_factor": speed,
        # Moderately tight sampling — prevents elongation without clipping
        "top_k": 12,
        "top_p": 0.92,
        "temperature": 0.85,
        "repetition_penalty": 1.4,
    }

    # Suppress stdout during inference (GPT-SoVITS prints progress bars)
    _real_stdout = sys.stdout
    
    # Retry mechanism: short/garbled outputs tend to be very brief
    # Estimate expected duration based on word count
    _word_count = len(clean_text.split())
    _min_expected_duration = max(0.25, _word_count * 0.15)
    _max_expected_duration = max(3.0, _word_count * 0.6)  # catch garbled elongation
    _best_audio = None
    _best_duration = 0
    _best_sr = 32000
    _best_score = -1  # higher = better fit
    _max_attempts = 1  # no retries — GPU contention with Ollama causes crashes on 4GB VRAM
    
    for _attempt in range(_max_attempts):
        sys.stdout = sys.stderr
        try:
            chunks = []
            sr = 32000
            for sr_chunk, audio_chunk in pipeline.run(req):
                sr = sr_chunk
                chunks.append(audio_chunk)
        finally:
            sys.stdout = _real_stdout
        
        if not chunks:
            if _attempt < _max_attempts - 1:
                if DEBUG_SOVITS:
                    print(f"[sovits] RETRY {_attempt+1}: no audio chunks", file=sys.stderr)
                continue
            raise RuntimeError("GPT-SoVITS produced no audio chunks after retries")
        
        audio = np.concatenate(chunks)
        duration = len(audio) / sr
        
        # Score this attempt — closer to expected range = higher score
        _target = (_min_expected_duration + _max_expected_duration) / 2
        _score = 1.0 - abs(duration - _target) / max(_target, 1.0)
        if duration < _min_expected_duration:
            _score -= 0.5  # heavy penalty for too short
        if duration > _max_expected_duration:
            _score -= 0.3  # penalty for too long (elongated)
        
        if _score > _best_score:
            _best_audio = audio
            _best_duration = duration
            _best_sr = sr
            _best_score = _score
        
        # Accept if within expected range
        if _min_expected_duration <= duration <= _max_expected_duration:
            break
        
        if DEBUG_SOVITS:
            _reason = "too short" if duration < _min_expected_duration else "too long" if duration > _max_expected_duration else "ok"
            print(f"[sovits] RETRY {_attempt+1}: {duration:.2f}s ({_reason}, expected {_min_expected_duration:.2f}-{_max_expected_duration:.2f}s, score={_score:.2f})", file=sys.stderr)

    full_audio = _best_audio

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"sovits_{int(time.time()*1000)}.wav")
    sf.write(output_path, full_audio, _best_sr)

    duration = len(full_audio) / _best_sr
    return output_path, duration


def main():
    """Main server loop — reads JSON commands from stdin, writes responses to stdout."""
    if DEBUG_SOVITS:
        print(json.dumps({"status": "loading", "msg": "Initializing GPT-SoVITS pipeline..."}), flush=True)

    pipeline = init_pipeline()

    print(json.dumps({"status": "ready", "msg": "GPT-SoVITS pipeline ready"}), flush=True)

    while True:
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "error": f"Invalid JSON: {e}"}), flush=True)
            continue

        cmd = req.get("cmd")
        if cmd == "ping":
            print(json.dumps({"status": "pong"}), flush=True)
            continue
        if cmd == "quit":
            print(json.dumps({"status": "goodbye"}), flush=True)
            break

        text = req.get("text")
        if not text:
            print(json.dumps({"status": "error", "error": "Missing 'text' field"}), flush=True)
            continue

        t0 = time.time()
        try:
            output_path, duration = synthesize(
                pipeline,
                text=text,
                ref_audio=req.get("ref_audio"),
                prompt_text=req.get("prompt_text"),
                speed=req.get("speed", 1.0),
                prompt_lang=req.get("prompt_lang"),
                text_lang=req.get("text_lang"),
            )
            elapsed = time.time() - t0
            print(json.dumps({
                "status": "ok",
                "audio_path": output_path,
                "duration": round(duration, 3),
                "elapsed": round(elapsed, 3),
            }), flush=True)
        except Exception as e:
            elapsed = time.time() - t0
            err_msg = f"{type(e).__name__}: {e}"
            print(f"[sovits-subprocess] ERROR: {err_msg}", file=sys.stderr, flush=True)
            print(json.dumps({
                "status": "error",
                "error": err_msg,
                "elapsed": round(elapsed, 3),
            }), flush=True)
        finally:
            # Free GPU memory after each synthesis to prevent VRAM leak / OOM
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass


if __name__ == "__main__":
    main()
