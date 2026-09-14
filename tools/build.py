"""Builds the CV website from the markdown CVs and the Captionated media folder.

Output goes to the repository root (index.html, fi.html, media/, pdf/).
Run: python tools/build.py
"""
import html, json, re, shutil, subprocess
from datetime import date
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
        "other": "fi", "other_label": "Suomeksi", "file": "index.html",
        "pdf": "Download PDF", "work_nav": "Work", "work": "My work at a glance",
        "work_hint_desktop": "Scroll sideways or use the arrows · click to open",
        "work_hint_mobile": "Swipe sideways · tap to open",
        "full_cv": "Full CV", "close": "Close", "prev": "Previous", "next": "Next",
        "keys": "Use ← → keys to browse · Esc to close", "swipe": "Swipe to browse",
        "updated": "Updated", "role": "Electronics & robotics · Aalto University",
    },
    "fi": {
        "other": "en", "other_label": "In English", "file": "fi.html",
        "pdf": "Lataa PDF", "work_nav": "Työt", "work": "Työni pähkinänkuoressa",
        "work_hint_desktop": "Selaa sivuttain tai nuolilla · klikkaa avataksesi",
        "work_hint_mobile": "Pyyhkäise sivuttain · napauta avataksesi",
        "full_cv": "Koko CV", "close": "Sulje", "prev": "Edellinen", "next": "Seuraava",
        "keys": "Selaa ← → -näppäimillä · Esc sulkee", "swipe": "Pyyhkäise selataksesi",
        "updated": "Päivitetty", "role": "Elektroniikka & robotiikka · Aalto-yliopisto",
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

    for line in md.splitlines():
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

    while parts and parts[-1] == "<hr>":
        parts.pop()
    return "\n".join(parts)


def photo_path(md):
    m = re.search(r"!\[[^\]]*\]\((.+?)\)", md)
    return Path(m.group(1)) if m else None


def split_cv(body):
    """Intro = title, portrait, contacts and summary (up to the second <hr>); rest = the other sections."""
    hrs = [m.start() for m in re.finditer(r"<hr>", body)]
    cut = hrs[1] if len(hrs) > 1 else len(body)
    intro, rest = body[:cut], body[cut + 4:]
    contacts = re.search(r"<ul>.*?</ul>", intro, re.S)
    summary = re.findall(r"<p>(.*?)</p>", intro, re.S)
    sections = []
    for part in rest.split("<hr>"):
        m = re.search(r"<h2[^>]*>(.*?)</h2>", part)
        if m:
            sections.append((m.group(1), part.replace(m.group(0), "", 1).strip()))
    return intro, rest, (contacts.group(0) if contacts else ""), (summary[-1] if summary else ""), sections


# ---------------------------------------------------------------- media

def file_key(path):
    st = path.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def process_media(src, name, cache, wanted, cache_id):
    """Compresses one image or video into media/. Returns (out, thumb, poster) paths relative to the site."""
    is_video = src.suffix.lower() in VIDEO_EXT
    out = MEDIA_OUT / (name + (".mp4" if is_video else ".jpg"))
    poster = MEDIA_OUT / (name + "-poster.jpg")
    thumb = MEDIA_OUT / (name + "-thumb.jpg")
    wanted.update({out.name, thumb.name} | ({poster.name} if is_video else set()))
    key = file_key(src)
    if not (cache.get(cache_id) == key and out.exists() and thumb.exists()):
        print(f"  processing {cache_id}")
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
        cache[cache_id] = key
    return f"media/{out.name}", f"media/{thumb.name}", (f"media/{poster.name}" if is_video else None)


def build_composite(comp, lang_titles, cache, wanted):
    """A collage assembled in the browser: local images/videos and YouTube embeds in columns."""
    def part(rel):
        src = MEDIA_SRC / rel
        return process_media(src, "part-" + slug(Path(rel).stem), cache, wanted, rel)

    columns = []
    for col in comp["columns"]:
        panels = []
        for p in col["panels"]:
            panel = {k: v for k, v in p.items() if k != "src"}
            if p["type"] in ("image", "video"):
                out, _, poster = part(p["src"])
                panel["src"], panel["poster"] = out, poster
            panels.append(panel)
        columns.append({"flex": col.get("flex", 1), "panels": panels})
    header = part(comp["header"])[0] if comp.get("header") else None
    card_thumb = part(comp["card"])[1] if comp.get("card") else None
    return {"columns": columns, "header": header, "header_ratio": comp.get("header_ratio"),
            "aspect": comp["aspect"]}, card_thumb


def build_media():
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    MEDIA_OUT.mkdir(exist_ok=True)
    items, wanted = [], set()
    sources = [p for p in MEDIA_SRC.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT | VIDEO_EXT] if MEDIA_SRC.exists() else []
    listed = {g["file"]: (i, g) for i, g in enumerate(CONFIG.get("gallery", []))}

    for src in sources:
        rank, meta = listed.get(src.stem, (-1, {}))
        out, thumb, poster = process_media(src, slug(src.stem), cache, wanted, src.name)
        item = {
            "name": src.stem, "video": src.suffix.lower() in VIDEO_EXT, "src": out,
            "thumb": thumb, "poster": poster, "rank": rank, "meta": meta, "composite": None,
        }
        if meta.get("composite"):
            item["composite"], card_thumb = build_composite(meta["composite"], meta, cache, wanted)
            item["thumb"] = card_thumb or item["thumb"]
            item["video"] = True
        items.append(item)

    for old in MEDIA_OUT.iterdir():
        if old.is_file() and old.name not in wanted and not old.name.startswith("portrait"):
            old.unlink()
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    # files not listed in config go first (newest additions on top)
    items.sort(key=lambda it: (it["rank"], it["name"]))
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
    text = name.replace("-", " ").replace("_", " ")
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------- pages

def esc(s):
    return html.escape(s, quote=True)


def work_strip(items, lang, ui):
    cards = []
    for i, it in enumerate(items):
        title = it["meta"].get(lang) or title_from_name(it["name"])
        year = it["meta"].get("year", "")
        play = '<span class="play" aria-hidden="true"></span>' if it["video"] else ""
        cards.append(
            f'<li><button class="card" type="button" data-index="{i}" aria-label="{esc(title)}">'
            f'<img src="{it["thumb"]}" alt="" loading="lazy">{play}'
            f'<span class="cap"><b>{esc(title)}</b><small>{year}</small></span></button></li>'
        )
    return f"""
<section id="work" class="work" aria-labelledby="work-title">
  <div class="work-head">
    <div>
      <h2 id="work-title">{ui['work']}</h2>
      <p class="muted hint-desktop">{ui['work_hint_desktop']}</p>
      <p class="muted hint-mobile">{ui['work_hint_mobile']}</p>
    </div>
    <div class="strip-arrows">
      <button type="button" class="strip-prev" aria-label="{ui['prev']}">‹</button>
      <button type="button" class="strip-next" aria-label="{ui['next']}">›</button>
    </div>
  </div>
  <ul class="strip">{''.join(cards)}</ul>
</section>"""


def localize_composite(comp, lang):
    if not comp:
        return None
    columns = [{"flex": c["flex"], "panels": [
        {k: v for k, v in p.items() if not k.startswith("caption_")} | {"caption": p.get(f"caption_{lang}", "")}
        for p in c["panels"]]} for c in comp["columns"]]
    return comp | {"columns": columns}


def viewer(items, lang, ui):
    data = [{
        "video": it["video"], "src": it["src"], "poster": it["poster"], "thumb": it["thumb"],
        "title": it["meta"].get(lang) or title_from_name(it["name"]), "year": it["meta"].get("year", ""),
        "composite": localize_composite(it["composite"], lang),
    } for it in items]
    return f"""
<dialog id="viewer" aria-label="{ui['work']}">
  <div class="v-top"><span class="v-count"></span><button class="v-close" type="button" aria-label="{ui['close']}">×</button></div>
  <button class="v-nav v-prev" type="button" aria-label="{ui['prev']}"><img alt=""><span class="v-key">←</span></button>
  <div class="v-stage"></div>
  <button class="v-nav v-next" type="button" aria-label="{ui['next']}"><img alt=""><span class="v-key">→</span></button>
  <div class="v-bottom"><div class="v-title"></div><div class="v-hint"><span class="keys">{ui['keys']}</span><span class="swipe">{ui['swipe']}</span></div></div>
</dialog>
<script>window.GALLERY = {json.dumps(data, ensure_ascii=False)};</script>"""


def page_html(lang, body, items, updated):
    ui = UI[lang]
    other = UI[ui["other"]]
    css = (ROOT / "tools" / "site.css").read_text(encoding="utf-8")
    js = (ROOT / "tools" / "site.js").read_text(encoding="utf-8")
    intro, rest, contacts, summary, sections = split_cv(body)
    accordions = "".join(
        f'<details><summary>{title}</summary><div class="acc">{content}</div></details>' for title, content in sections
    )
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aapo Heiska — CV</title>
<meta name="description" content="{esc(re.sub('<[^>]+>', '', summary))}">
<link rel="alternate" hreflang="{ui['other']}" href="{other['file']}">
<style>{css}</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="#top">Aapo Heiska</a>
  <nav>
    <a class="nav-work" href="#work">{ui['work_nav']}</a>
    <a class="button" href="pdf/cv-{lang}.pdf">{ui['pdf']}</a>
    <a class="lang" href="{other['file']}" hreflang="{ui['other']}">{ui['other_label']}</a>
  </nav>
</header>
<main id="top">
  <article class="cv only-desktop">
{intro}
  </article>
  <aside class="profile only-mobile">
    <img class="avatar" src="media/portrait.jpg" alt="Aapo Heiska">
    <div><h1>Aapo Heiska</h1><div class="role">{ui['role']}</div></div>
    <p>{summary}</p>
    {contacts}
  </aside>
{work_strip(items, lang, ui)}
  <article class="cv only-desktop">
{rest}
  </article>
  <section class="fullcv only-mobile">
    <h2>{ui['full_cv']}</h2>
    {accordions}
  </section>
  <footer class="muted">{ui['updated']} {updated}</footer>
</main>
{viewer(items, lang, ui)}
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
    updated = date.today().strftime("%d.%m.%Y")
    items = build_media()
    (ROOT / "pdf").mkdir(exist_ok=True)
    tmp = ROOT / "tools" / ".tmp"
    tmp.mkdir(exist_ok=True)

    for lang in ("en", "fi"):
        md = Path(CONFIG["cv_files"][lang]).read_text(encoding="utf-8")
        portrait = build_portrait(photo_path(md))
        body = markdown_to_html(md, portrait)
        ui = UI[lang]
        (ROOT / ui["file"]).write_text(page_html(lang, body, items, updated), encoding="utf-8")

        h = tmp / f"cv-{lang}.html"
        h.write_text(pdf_html(lang, markdown_to_html(md, (ROOT / portrait).as_uri())), encoding="utf-8")
        make_pdf(h, ROOT / "pdf" / f"cv-{lang}.pdf")
        print(f"  built {ui['file']} and pdf/cv-{lang}.pdf")

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
