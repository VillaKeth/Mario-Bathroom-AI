"""Retry failed image downloads with alternative search terms."""
from icrawler.builtin import BingImageCrawler
from PIL import Image
from pathlib import Path
import tempfile, shutil, time

OUTPUT = Path(__file__).resolve().parent.parent / "client" / "assets" / "event_images"
TARGET = (800, 450)

retries = {
    "birthday_wish": "birthday party colorful confetti",
}

ok = 0
fail = []
for name, term in retries.items():
    print(f"{name}: \"{term}\"...", end=" ", flush=True)
    tmp = tempfile.mkdtemp()
    try:
        c = BingImageCrawler(storage={"root_dir": tmp}, log_level=50)
        c.crawl(keyword=term, max_num=8, min_size=(300, 150))
        found = False
        for f in sorted(Path(tmp).glob("*.*")):
            try:
                img = Image.open(f).convert("RGB")
                if img.width < 200:
                    continue
                r = img.width / img.height
                tr = TARGET[0] / TARGET[1]
                if r > tr:
                    nh = TARGET[1]; nw = int(nh * r)
                else:
                    nw = TARGET[0]; nh = int(nw / r)
                img = img.resize((nw, nh), Image.LANCZOS)
                l = (nw - TARGET[0]) // 2; t = (nh - TARGET[1]) // 2
                img = img.crop((l, t, l + TARGET[0], t + TARGET[1]))
                out = OUTPUT / f"{name}.png"
                img.save(out, "PNG", optimize=True)
                print(f"OK ({out.stat().st_size // 1024}KB)")
                ok += 1
                found = True
                break
            except Exception:
                continue
        if not found:
            print("FAIL")
            fail.append(name)
    except Exception as e:
        print(f"ERR: {e}")
        fail.append(name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    time.sleep(1)

print(f"\nRetry: {ok}/{len(retries)} success")
if fail:
    print(f"Still failed: {fail}")
