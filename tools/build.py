"""Builds the CV website from the markdown CVs and the Captionated media folder.

Output goes to the repository root (index.html, fi.html, media/, pdf/).
Run: python tools/build.py
"""
import hashlib, html, json, os, re, shutil, subprocess, sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "tools" / "config.json").read_text(encoding="utf-8"))
MEDIA_SRC = Path(CONFIG["media_folder"])
MEDIA_OUT = ROOT / "media"
CACHE_FILE = ROOT / "tools" / ".media-cache.json"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}

UI = {
    "en": {
        "lang_name": "English", "other": "fi", "other_label": "Suomeksi", "file": "index.html",
        "pdf": "Download PDF", "gallery": "Projects in photos and videos",
        "gallery_intro": "Photos and videos of my projects and work. Click an item to view it larger.",
        "cv_nav": "CV", "close": "Close", "updated": "Updated",
    },
    "fi": {
        "lang_name": "Suomi", "other": "en", "other_label": "In English", "file": "fi.html",
        "pdf": "Lataa PDF", "gallery": "Projektit kuvina ja videoina",
        "gallery_intro": "Kuvia ja videoita projekteistani ja töistäni. Klikkaa kohdetta nähdäksesi sen isompana.",
        "cv_nav": "CV", "close": "Sulje", "updated": "Päivitetty",
    },
}

# Sections that are for the job-search tool only, never published
HIDDEN_SECTIONS = {"Avainsanat", "Keywords"}


# ---------------------------------------------------------------- markdown

def inline(text):
    t = html.escape(text.strip(), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"(?<![\w\"'>/:.])([\w.+-]+@[\w-]+\.[\w.]+)", r'<a href="mailto:\1">\1</a>', t)
    return t


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def markdown_to_html(md, photo_src):
    lines = md.splitlines()
    parts, para, quote, items = [], [], [], []
    skipping = False

    def flush():
        nonlocal para, quote, items
        if para:
            parts.append("<p>" + " ".join(inline(p) for p in para) + "</p>")
        if quote:
            parts.append("<blockquote>" + " ".join(inline(q) for q in quote) + "</blockquote>")
        if items:
            out, sub_open, first = "<ul>", False, True
            for depth, text in items:
                if depth == 0:
                    if sub_open:
                        out += "</ul>"
                        sub_open = False
                    out += ("" if first else "</li>") + "<li>" + inline(text)
                    first = False
                else:
                    if not sub_open:
                        out += "<ul>"
                        sub_open = True
                    out += "<li>" + inline(text) + "</li>"
            parts.append(out + ("</ul>" if sub_open else "") + "</li></ul>")
        para, quote, items = [], [], []

    for line in lines:
        s = line.strip()
        heading = re.match(r"(#{1,4}) (.*)", s)
        if heading and len(heading.group(1)) <= 2:
            skipping = heading.group(2).strip() in HIDDEN_SECTIONS
        if skipping:
            continue
        if not s:
            flush()
            continue
        if heading:
            flush()
            n, title = len(heading.group(1)), heading.group(2)
            parts.append(f'<h{n} id="{slug(title)}">{inline(title)}</h{n}>')
        elif s == "---":
            flush()
            parts.append("<hr>")
        elif s.startswith("!["):
            flush()
            parts.append(f'<img class="portrait" src="{photo_src}" alt="Aapo Heiska">')
        elif s.startswith(">"):
            quote.append(s[1:])
        elif re.match(r" *- ", line):
            indent = len(line) - len(line.lstrip(" "))
            items.append((1 if indent >= 2 else 0, line.strip()[2:]))
        else:
            para.append(s)
    flush()

    # drop trailing separators left behind by hidden sections
    while parts and parts[-1] == "<hr>":
        parts.pop()
    return "\n".join(parts)


def photo_path(md):
    m = re.search(r"!\[[^\]]*\]\((.+?)\)", md)
    return Path(m.group(1)) if m else None


# ---------------------------------------------------------------- media

def file_key(path):
    st = path.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def build_media():
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    MEDIA_OUT.mkdir(exist_ok=True)
    items, wanted = [], set()
    sources = [p for p in MEDIA_SRC.iterdir() if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT] if MEDIA_SRC.exists() else []

    for src in sources:
        name = slug(src.stem)
        is_video = src.suffix.lower() in VIDEO_EXT
        out = MEDIA_OUT / (name + (".mp4" if is_video else ".jpg"))
        poster = MEDIA_OUT / (name + "-poster.jpg")
        thumb = MEDIA_OUT / (name + "-thumb.jpg")
        wanted.update({out.name, thumb.name} | ({poster.name} if is_video else set()))
        key = file_key(src)
        fresh = cache.get(src.name) == key and out.exists() and thumb.exists()

        if not fresh:
            print(f"  processing {src.name}")
            if is_video:
                subprocess.run([
                    CONFIG["ffmpeg"], "-y", "-loglevel", "error", "-i", str(src),
                    "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "26", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
                ], check=True)
                subprocess.run([
                    CONFIG["ffmpeg"], "-y", "-loglevel", "error", "-ss", "1", "-i", str(out),
                    "-frames:v", "1", "-q:v", "3", str(poster),
                ], check=True)
                still = Image.open(poster)
            else:
                still = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
                full = still.copy()
                full.thumbnail((2000, 2000))
                full.save(out, "JPEG", quality=85, optimize=True, progressive=True)
            t = still.convert("RGB")
            t.thumbnail((720, 720))
            t.save(thumb, "JPEG", quality=80, optimize=True, progressive=True)
            cache[src.name] = key

        w, h = Image.open(thumb).size
        items.append({
            "name": src.stem, "video": is_video, "src": f"media/{out.name}",
            "thumb": f"media/{thumb.name}", "poster": f"media/{poster.name}" if is_video else None,
            "ratio": w / h,
        })

    for old in MEDIA_OUT.iterdir():
        if old.name not in wanted and not old.name.startswith("portrait"):
            old.unlink()
    cache = {k: v for k, v in cache.items() if k in {s.name for s in sources}}
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    order = CONFIG.get("gallery_order", [])
    rank = {n: i for i, n in enumerate(order)}
    # new files not listed in gallery_order go first (newest additions on top)
    items.sort(key=lambda it: (rank.get(it["name"], -1), it["name"]))
    return items


def build_portrait(src):
    out = MEDIA_OUT / "portrait.jpg"
    if src and src.exists():
        key = file_key(src)
        cache_key = ROOT / "tools" / ".portrait-cache"
        if not out.exists() or not cache_key.exists() or cache_key.read_text() != key:
            im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            im.thumbnail((1800, 1800))
            im.save(out, "JPEG", quality=85, optimize=True, progressive=True)
            cache_key.write_text(key)
    return "media/portrait.jpg"


def title_from_name(name):
    words = name.replace("-", " ").replace("_", " ").split()
    keep_upper = {"cnc", "pcb", "vr", "hamk", "emba", "freecad"}
    pretty = {"freecad": "FreeCAD", "s-tron": "S-tron"}
    out = []
    for w in words:
        lw = w.lower()
        out.append(pretty.get(lw) or (lw.upper() if lw in keep_upper else lw))
    text = " ".join(out)
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------- pages

def gallery_html(items, ui):
    cards = []
    for i, it in enumerate(items):
        label = html.escape(title_from_name(it["name"]))
        badge = '<span class="play" aria-hidden="true"></span>' if it["video"] else ""
        cards.append(
            f'<button class="tile" data-index="{i}" style="--r:{it["ratio"]:.3f}" aria-label="{label}">'
            f'<img src="{it["thumb"]}" alt="{label}" loading="lazy" width="720" height="{int(720 / it["ratio"])}">{badge}</button>'
        )
    data = json.dumps([{k: it[k] for k in ("video", "src", "poster")} | {"label": title_from_name(it["name"])} for it in items])
    return f"""
<section id="gallery" class="gallery">
  <h2>{ui['gallery']}</h2>
  <p class="muted">{ui['gallery_intro']}</p>
  <div class="grid">{''.join(cards)}</div>
</section>
<dialog id="viewer" aria-label="{ui['gallery']}">
  <button class="close" type="button" aria-label="{ui['close']}">×</button>
  <button class="nav prev" type="button" aria-label="Previous">‹</button>
  <div class="stage"></div>
  <button class="nav next" type="button" aria-label="Next">›</button>
</dialog>
<script>window.GALLERY = {data};</script>"""


def page_html(lang, body, gallery, updated):
    ui = UI[lang]
    other = UI[ui["other"]]
    css = (ROOT / "tools" / "site.css").read_text(encoding="utf-8")
    js = (ROOT / "tools" / "site.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aapo Heiska — CV</title>
<meta name="description" content="Aapo Heiska — CV">
<link rel="alternate" hreflang="{ui['other']}" href="{other['file']}">
<style>{css}</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="#top">Aapo Heiska</a>
  <nav>
    <a href="#gallery">{ui['gallery']}</a>
    <a class="button" href="pdf/cv-{lang}.pdf">{ui['pdf']}</a>
    <a class="lang" href="{other['file']}" hreflang="{ui['other']}">{ui['other_label']}</a>
  </nav>
</header>
<main id="top">
<article class="cv">
{body}
</article>
{gallery}
<footer class="muted">{ui['updated']} {updated}</footer>
</main>
<script>{js}</script>
</body>
</html>
"""


def pdf_html(lang, body):
    css = (ROOT / "tools" / "print.css").read_text(encoding="utf-8")
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>CV - Aapo Heiska</title><style>{css}</style></head><body>\n{body}\n</body></html>'


def make_pdf(html_file, pdf_file):
    subprocess.run([
        CONFIG["chrome"], "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_file}", html_file.as_uri(),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    from datetime import date
    updated = date.today().strftime("%d.%m.%Y")
    items = build_media()
    (ROOT / "pdf").mkdir(exist_ok=True)
    tmp = ROOT / "tools" / ".tmp"
    tmp.mkdir(exist_ok=True)

    for lang in ("en", "fi"):
        src = Path(CONFIG["cv_files"][lang])
        md = src.read_text(encoding="utf-8")
        portrait = build_portrait(photo_path(md))
        body = markdown_to_html(md, portrait)
        ui = UI[lang]
        (ROOT / ui["file"]).write_text(page_html(lang, body, gallery_html(items, ui), updated), encoding="utf-8")

        print_body = markdown_to_html(md, (ROOT / portrait).as_uri())
        h = tmp / f"cv-{lang}.html"
        h.write_text(pdf_html(lang, print_body), encoding="utf-8")
        make_pdf(h, ROOT / "pdf" / f"cv-{lang}.pdf")
        print(f"  built {ui['file']} and pdf/cv-{lang}.pdf")

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
