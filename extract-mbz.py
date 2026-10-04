#!/usr/bin/env python3
"""
Extract Moodle .mbz backup content and merge into the returndemo-course JSON.

Reads the extracted mbz directory, parses all lesson XML, quiz questions,
H5P interactive content, and page resources. Outputs updated course JSON
files (EN and FR) with full page content, images, and interactive tabs.

Usage:
    python3 extract-mbz.py <path-to-extracted-mbz>

The mbz should be extracted from sources/RTW-UBC-CPD.mbz:
    tar -xzf sources/RTW-UBC-CPD.mbz -C /tmp/mbz-extract

Produces:
    data/course-en.json (updated with full lesson pages)
    data/course-fr.json (updated with full lesson pages)
    data/images/ (extracted lesson images from mbz)
"""

import sys
import os
import html as html_mod
import re
import json
import glob
import shutil
import html
import xml.etree.ElementTree as ET
from pathlib import Path

MBZ_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mbz-extract")
IMAGES_DIR = Path("data/images")
FILES_DIR = MBZ_DIR / "files"

# ── Build filename -> contenthash mapping from files.xml ──────────────

def build_file_manifest():
    """Build {filearea: {filename: contenthash}} from files.xml."""
    tree = ET.parse(str(MBZ_DIR / "files.xml"))
    root = tree.getroot()
    manifest = {}

    for f in root.findall(".//file"):
        filearea_el = f.find("filearea")
        fe = filearea_el.text if filearea_el is not None else ""
        filename_el = f.find("filename")
        fn = filename_el.text if filename_el is not None else ""
        contenthash_el = f.find("contenthash")
        ch = contenthash_el.text if contenthash_el is not None else ""
        filepath_el = f.find("filepath")
        fp = filepath_el.text if filepath_el is not None else "/"

        if not ch or fn == ".":
            continue

        if fe not in manifest:
            manifest[fe] = {}
        # Store by filename -> contenthash
        # Some files have duplicates (same hash); last one wins which is fine
        manifest[fe][fn] = ch

    return manifest


# ── Extract image file from mbz by contenthash ────────────────────────

def extract_image_by_hash(contenthash, filename):
    """Copy an image from the mbz files/ directory to data/images/."""
    if not contenthash:
        return None
    stored_path = FILES_DIR / contenthash[:2] / contenthash
    if not stored_path.exists():
        return None

    # Determine extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"

    dest = IMAGES_DIR / filename
    if not dest.exists():
        shutil.copy2(str(stored_path), str(dest))
    return dest.name


# ── Parse {mlang} tags ────────────────────────────────────────────────

def split_mlang(text):
    """Split {mlang en}...{mlang}{mlang fr_ca}...{mlang} into {en: ..., fr: ...}."""
    # Moodle's bilingual format:
    # {mlang en}EN content{mlang}{mlang fr_ca}FR content{mlang}
    # The closing {mlang} (no lang code) closes the current language block.
    # An opening {mlang en} or {mlang fr_ca} starts a new block.

    # Strategy: split on {mlang} (closing) and {mlang xx} (opening)
    # Tokenize: track which language each segment belongs to.

    parts_en = []
    parts_fr = []

    # Find all language tag boundaries
    # Match both opening ({mlang en}, {mlang fr_ca}) and closing ({mlang})
    tokens = re.split(r'(\{mlang\s+[\w_]+\}|\{mlang\})', text)

    current_lang = None
    content_buf = []

    for token in tokens:
        if re.match(r'\{mlang\s+en[\w_]*\}', token):
            # Starting EN block — flush previous
            if current_lang == "fr" and content_buf:
                parts_fr.append("".join(content_buf))
            current_lang = "en"
            content_buf = []
        elif re.match(r'\{mlang\s+fr[\w_]*\}', token):
            # Starting FR block — flush previous
            if current_lang == "en" and content_buf:
                parts_en.append("".join(content_buf))
            current_lang = "fr"
            content_buf = []
        elif re.match(r'\{mlang\}', token):
            # Closing tag — flush current
            if current_lang == "en" and content_buf:
                parts_en.append("".join(content_buf))
            elif current_lang == "fr" and content_buf:
                parts_fr.append("".join(content_buf))
            current_lang = None
            content_buf = []
        else:
            # Content
            if content_buf is not None:
                content_buf.append(token)

    # Flush remaining
    if content_buf:
        if current_lang == "en":
            parts_en.append("".join(content_buf))
        elif current_lang == "fr":
            parts_fr.append("".join(content_buf))

    en_text = "".join(parts_en)
    fr_text = "".join(parts_fr)

    # If no language tags found at all, return text as-is for both
    if not parts_en and not parts_fr:
        return {"en": text, "fr": text}

    return {"en": en_text, "fr": fr_text}


def extract_lang(text, lang):
    """Extract one language's content from {mlang} tagged text."""
    result = split_mlang(text)
    return result.get(lang, "") or ""


# ── Clean HTML for embedding ──────────────────────────────────────────

LESSON_SECTION = {"10373": "lesson-1", "10374": "lesson-2", "10375": "lesson-3", "10376": "lesson-4"}
MANIFEST = {}


def fix_file_links(html_text, lang):
    """Resolve @@PLUGINFILE@@ links to PDFs: lesson resource packs map to our assets, others are copied out of the backup."""
    from urllib.parse import unquote

    def sub(m):
        name = unquote(m.group(1))
        mm = re.match(r"resources-lesson-(\d)", name)
        if mm:
            return f"assets/pdfs/RTW-lesson-{mm.group(1)}-resources_{lang.upper()}.pdf"
        for area in MANIFEST.values():
            ch = area.get(name)
            src = FILES_DIR / ch[:2] / ch if ch else None
            if src and src.exists():
                dest = Path("assets/pdfs") / re.sub(r"[^\w.-]+", "_", name)
                if not dest.exists():
                    shutil.copy2(str(src), str(dest))
                return str(dest)
        return m.group(0)

    return re.sub(r"""@@PLUGINFILE@@/([^"'\s<>]+?\.pdf)""", sub, html_text)


def clean_html(raw_html):
    """Clean up Moodle HTML for embedding in our static site."""
    if not raw_html:
        return ""

    # Source typo in one FR answer: a mangled <br ...> tag swallowed a whole line of the feedback
    raw_html = re.sub(
        r'&lt;br pour="".*?/&gt;oui',
        "&lt;br /&gt;Pour donner à son employeur le temps de mettre en place des mesures d’adaptation au besoin\u00a0=\u00a0&lt;strong&gt;oui&lt;/strong&gt;",
        raw_html, flags=re.DOTALL)

    # Decode HTML entities that were double-encoded in Moodle XML
    raw_html = raw_html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    # H5P embeds -> placeholder, filled with hotspot markup by extract_lessons
    raw_html = re.sub(r'<iframe[^>]*HVPEMBEDBYID\*(\d+)@\$[^>]*></iframe>',
                      lambda m: f'<div data-hvp="{m.group(1)}"></div>', raw_html)

    # jQuery inline toggles -> data attribute handled by app.js
    raw_html = re.sub(r'\sonclick="\$\(\'(#[^\']+)\'\)\.toggle\(\'slow\'\);?"', r' data-toggle-target="\1"', raw_html)
    # Moodle lesson-page links -> in-site navigation
    raw_html = re.sub(
        r'href="\$@LESSONVIEWPAGE\*(\d+)\*(\d+)@\$[^"]*"',
        lambda m: f'href="#" data-goto="{LESSON_SECTION.get(m.group(1), "lesson-1")}" data-page="{m.group(2)}"', raw_html)

    # Remove Moodle-specific scripts
    raw_html = re.sub(r'<script\b[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL)

    # Remove page number lines (Moodle lesson navigation artifact)
    raw_html = re.sub(r'<p\s+class="page-number"[^>]*>.*?</p>', '', raw_html, flags=re.DOTALL)

    # Remove inline styles that float images (they break our layout)
    raw_html = re.sub(r'style="float:\s*right[^"]*"', 'class="lesson-float-right"', raw_html)

    # Remove img tags that reference Moodle server (iconlarge activityicon)
    raw_html = re.sub(r'<img\s+src="https://elearning\.ubccpd\.ca/[^>]*>', '', raw_html)

    # Fix broken Moodle self-links (href to elearning.ubccpd.ca root = no useful target)
    raw_html = re.sub(r'<a\s+href="https://elearning\.ubccpd\.ca/"[^>]*>', '<a>', raw_html)
    raw_html = raw_html.replace('https://elearning.ubccpd.ca/', '')  # bare references

    # Remove Moodle internal activity references like $@HVPEMBEDBYID*10450@$
    raw_html = re.sub(r'\$@(HVP|LESSON|MODALIAS)EMBEDBYID\*\d+\@\$', '', raw_html)
    raw_html = re.sub(r'\$@\w+\*\d+\@\$', '', raw_html)

    # Strip leading closing tags (</p>, </div>) that are artifacts of {mlang} tag placement
    raw_html = re.sub(r'^(</p>|</div>|</span>[\s]*)+', '', raw_html)

    # Strip trailing opening tags that are artifacts
    raw_html = re.sub(r'(<p>\s*$|<div>\s*$)', '', raw_html)

    # Remove empty paragraphs
    raw_html = re.sub(r'<p>\s*</p>', '', raw_html)

    return raw_html.strip()


# ── Map @@PLUGINFILE@@ images to contenthash ──────────────────────────

def build_image_map(manifest):
    """Build {lesson_image_filename: contenthash} from page_contents and section areas."""
    img_map = {}
    for area in ["page_contents", "section", "content"]:
        if area in manifest:
            for fn, ch in manifest[area].items():
                if fn.endswith((".png", ".jpg", ".gif", ".webp")):
                    img_map[fn] = ch
    return img_map


def resolve_image_ref(img_ref, img_map):
    """Resolve a @@PLUGINFILE@@/image.png reference to actual filename."""
    # img_ref is like '@@PLUGINFILE@@/iCanWork-assessment-v03-53.png' or with query params
    m = re.search(r'@@PLUGINFILE@@/([^?\s"\']+)', img_ref)
    if not m:
        return None
    filename = m.group(1)

    # URL decode common patterns
    from urllib.parse import unquote
    filename = unquote(filename)

    # Look up in image map
    ch = img_map.get(filename)
    if ch:
        return extract_image_by_hash(ch, filename)

    # Try without query params
    base = filename.split("?")[0]
    ch = img_map.get(base)
    if ch:
        return extract_image_by_hash(ch, base)

    # Try to find by partial match
    for mf, mch in img_map.items():
        if mf.lower().startswith(filename.lower()[:20]):
            return extract_image_by_hash(mch, mf)

    return None


# ── Process lesson images ─────────────────────────────────────────────

def process_image_refs(html_content, img_map):
    """Replace @@PLUGINFILE@@ references with local image paths."""
    def replace_ref(match):
        ref = match.group(0)
        resolved = resolve_image_ref(ref, img_map)
        if resolved:
            return f'data/images/{resolved}'
        return match.group(0)  # Leave unresolved

    html_content = re.sub(r'''@@PLUGINFILE@@/[^"'\s<>)]+''', replace_ref, html_content)
    return html_content


# ── Extract lesson pages ──────────────────────────────────────────────

def _tag(block, name):
    m = re.search(rf'<{name}>(.*?)</{name}>', block, re.DOTALL)
    return m.group(1) if m else ""


def _plain(html_text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_mod.unescape(html_text or ""))).strip()


def build_lesson_question(page_block, lang, img_map):
    """Turn a Moodle lesson question page (multichoice=3, matching=5) into our question schema."""
    qtype = _tag(page_block, "qtype")
    contents = clean_html(extract_lang(_tag(page_block, "contents"), lang))
    contents = process_image_refs(contents, img_map)
    # everything after the case-study box is the actual question prompt
    prompt = contents.rsplit("</div>", 1)[-1].strip()
    answers = []
    for a in re.findall(r'<answer id="\d+">(.*?)</answer>', page_block, re.DOTALL):
        answers.append({
            "score": float(_tag(a, "score") or 0),
            "text": clean_html(extract_lang(_tag(a, "answer_text"), lang)),
            "response": clean_html(extract_lang(_tag(a, "response"), lang)) if "NULL" not in _tag(a, "response") else "",
            "raw_response": html_mod.unescape(_tag(a, "response")),
        })
    q = {"prompt": prompt}
    if qtype == "3":
        q["type"] = "single"
        q["options"] = [a["text"] for a in answers]
        q["correct"] = [i for i, a in enumerate(answers) if a["score"] > 0]
        q["feedback"] = [a["response"] for a in answers]
    else:  # matching: [correct feedback, incorrect feedback, item, item, ...]
        q["type"] = "matching"
        q["feedbackCorrect"] = answers[0]["text"]
        q["feedbackIncorrect"] = answers[1]["text"]
        items = []
        for a in answers[2:]:
            parts = [p.strip() for p in a["raw_response"].split(" / ")]
            choice = parts[0] if lang == "en" or len(parts) < 2 else parts[1]
            items.append({"label": a["text"], "answer": choice})
        q["choices"] = list(dict.fromkeys(i["answer"] for i in items))
        q["items"] = items
    return q


def extract_lessons(manifest, hvp_by_id):
    """Parse all lesson XML files: content pages (in Moodle's page order) and question pages."""
    img_map = build_image_map(manifest)
    lessons = {}

    for lesson_file in sorted(glob.glob(str(MBZ_DIR / "activities/lesson_*/lesson.xml"))):
        lesson_id = Path(lesson_file).parent.name
        content = open(lesson_file).read()

        blocks = {pid: blk for pid, blk in re.findall(r'<page\s+id="(\d+)">(.*?)</page>', content, re.DOTALL)}
        # Moodle orders pages as a linked list (prevpageid/nextpageid), not by XML order
        order, cur = [], next((p for p, b in blocks.items() if _tag(b, "prevpageid") == "0"), None)
        while cur and cur in blocks and cur not in order:
            order.append(cur)
            cur = _tag(blocks[cur], "nextpageid")
        order += [p for p in blocks if p not in order]

        out = {"en": {"pages": [], "questions": []}, "fr": {"pages": [], "questions": []}}
        for pid in order:
            blk = blocks[pid]
            qtype = _tag(blk, "qtype")
            title_split = split_mlang(_tag(blk, "title"))
            en_title = title_split.get("en", "").strip()
            if qtype in ("3", "5"):
                for lang in ("en", "fr"):
                    out[lang]["questions"].append(build_lesson_question(blk, lang, img_map))
                continue
            # Moodle navigation scaffolding / learning-check intro (shown in the Learning Check section)
            if en_title.startswith(("End of Lesson", "Learning Check")):
                continue
            raw = _tag(blk, "contents")
            for lang in ("en", "fr"):
                c = clean_html(extract_lang(raw, lang))
                c = re.sub(r'<div data-hvp="(\d+)"></div>', lambda m: build_hotspot_html(hvp_by_id[m.group(1)]), c)
                out[lang]["pages"].append({"id": pid, "title": title_split.get(lang, "").strip(),
                                           "content": fix_file_links(process_image_refs(c, img_map), lang)})

        if out["en"]["pages"] or out["en"]["questions"]:
            lessons[lesson_id] = {
                lang: {"title": out[lang]["pages"][0]["title"] if out[lang]["pages"] else "",
                       "pages": out[lang]["pages"], "questions": out[lang]["questions"]}
                for lang in ("en", "fr")
            }
    return lessons


def build_quiz_question(q, lang):
    prompt = clean_html(q["text"].get(lang, ""))
    options = [clean_html(a["text"].get(lang, "")) for a in q["answers"]]
    correct = [i for i, a in enumerate(q["answers"]) if a["correct"]]
    return {
        "type": "multi" if len(correct) > 1 else "single",
        "prompt": prompt,
        "options": options,
        "correct": correct,
        "feedback": [clean_html(a["feedback"].get(lang, "")) for a in q["answers"]],
    }


# ── Extract quiz questions ────────────────────────────────────────────

def extract_quiz_questions():
    """Parse questions.xml for quiz questions."""
    tree = ET.parse(str(MBZ_DIR / "questions.xml"))
    root = tree.getroot()

    questions = []
    for q in root.findall(".//question"):
        name_el = q.find(".//name")
        name = name_el.text.strip() if name_el is not None else "Question"

        qt_el = q.find(".//qtype")
        qtype = qt_el.text if qt_el is not None else "multichoice"

        # Question text
        qt_text_el = q.find(".//questiontext")
        qt_raw = qt_text_el.text if qt_text_el is not None else ""

        # Answers
        answers = []
        answer_el = q.find(".//plugin_qtype_multichoice_question")
        if answer_el is None:
            answer_el = q.find(".//answers")
        if answer_el is not None:
            for a in answer_el.findall(".//answer"):
                at_el = a.find("answertext")
                at_raw = at_el.text if at_el is not None else ""
                frac_el = a.find("fraction")
                fraction = float(frac_el.text) if frac_el is not None else 0
                fb_el = a.find("feedback")
                feedback_raw = fb_el.text if fb_el is not None else ""

                answers.append({
                    "text": split_mlang(at_raw),
                    "correct": fraction > 0,
                    "feedback": split_mlang(feedback_raw),
                })

        questions.append({
            "name": name,
            "text": split_mlang(qt_raw),
            "answers": answers,
            "type": qtype,
        })

    return questions


# ── Extract H5P interactive content as tabs ───────────────────────────

def extract_hvp_content(manifest):
    """Extract H5P Image Hotspots content as tab data."""
    tabs = []

    for hvp_file in sorted(glob.glob(str(MBZ_DIR / "activities/hvp_*/hvp.xml"))):
        with open(hvp_file) as f:
            content = f.read()

        # Extract name
        name_m = re.search(r'<name>(.*?)</name>', content)
        name = name_m.group(1) if name_m else "Interactive"

        # Extract JSON content
        json_m = re.search(r'<json_content>(.*?)</json_content>', content, re.DOTALL)
        if not json_m:
            continue

        try:
            import json as json_mod
            hvp_data = json_mod.loads(json_m.group(1))
        except Exception:
            continue

        # H5P Image Hotspots — flat structure (hotspots at top level)
        hotspots = hvp_data.get("hotspots", [])
        main_image_data = hvp_data.get("image", {})
        main_image_path = main_image_data.get("path", "") if isinstance(main_image_data, dict) else ""

        tab = {
            "id": Path(hvp_file).parent.name.split("_")[1],
            "title": name,
            "image": main_image_path.split("#")[0],
            "image_size": (main_image_data.get("width"), main_image_data.get("height")),
            "hotspots": [],
        }

        for hs in hotspots:
            header = hs.get("header", "")
            # Content is an array of H5P content items
            hs_content = hs.get("content", [])
            text = ""
            for item in hs_content:
                item_text = item.get("params", {}).get("text", "")
                if item_text:
                    text = item_text
                    break

            pos = hs.get("position", {})
            tab["hotspots"].append({
                "header": header,
                "text": html_mod.unescape(text) if "&lt;" in text else text,
                "position": pos,
            })

        tabs.append(tab)

        # Extract the H5P main image if present
        if main_image_path:
            img_fn = os.path.basename(main_image_path.split("#")[0])
            # H5P images are in 'content' filearea
            ch = manifest.get("content", {}).get(img_fn)
            if ch:
                extract_image_by_hash(ch, img_fn)

    return tabs


def fix_bare_links(html_text, corpus):
    def sub(m):
        text = m.group(1)
        key = html_mod.unescape(re.sub(r"<[^>]+>", "", text))[:25]
        for hm in re.finditer(r'<a\s[^>]*href="(http[^"]+)"[^>]*>([^<]*)</a>', corpus):
            if html_mod.unescape(hm.group(2)).strip().startswith(key.strip()):
                return f'<a href="{hm.group(1)}" target="_blank" rel="noopener">{text}</a>'
        return text  # unresolved: plain text, not a dead link
    return re.sub(r"<a>([^<]*)</a>", sub, html_text)


def build_hotspot_html(tab):
    """Image-hotspot figure replacing the Moodle H5P iframe."""
    out = [f'<figure class="hotspot-figure"><img src="data/images/{os.path.basename(tab["image"])}" alt="{html_mod.escape(tab["title"])}">']
    for i, hs in enumerate(tab["hotspots"], 1):
        p = hs["position"]
        out.append(
            f'<div class="hotspot" style="left:{p["x"]:.2f}%;top:{p["y"]:.2f}%">'
            f'<button type="button" class="hotspot-dot" aria-expanded="false" aria-label="{html_mod.escape(hs["header"])}">+</button>'
            f'<div class="hotspot-popup" hidden><button type="button" class="hotspot-close" aria-label="Close">&times;</button>'
            f'<h4>{hs["header"]}</h4>{hs["text"]}</div></div>')
    out.append('</figure>')
    return "".join(out)


# ── Extract page resources ────────────────────────────────────────────

def extract_pages():
    """Extract Moodle page content (Resources, Summary)."""
    pages = {}

    for page_file in sorted(glob.glob(str(MBZ_DIR / "activities/page_*/page.xml"))):
        lp = Path(page_file)
        page_id = lp.parent.name

        with open(page_file) as f:
            content = f.read()

        # Title
        title_m = re.search(r'<name>(.*?)</name>', content)
        title_raw = title_m.group(1) if title_m else ""

        # Content
        content_m = re.search(r'<content>(.*?)</content>', content, re.DOTALL)
        raw = content_m.group(1) if content_m else ""

        en_content = fix_file_links(clean_html(extract_lang(raw, "en")), "en")
        fr_content = fix_file_links(clean_html(extract_lang(raw, "fr")), "fr")
        en_title = extract_lang(title_raw, "en")
        fr_title = extract_lang(title_raw, "fr")

        pages[page_id] = {
            "en": {"title": en_title, "content": en_content},
            "fr": {"title": fr_title, "content": fr_content},
        }

    return pages


# ── Main ──────────────────────────────────────────────────────────────

def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("Building file manifest...")
    manifest = build_file_manifest()
    MANIFEST.update(manifest)
    print(f"  Found {sum(len(v) for v in manifest.values())} files across {len(manifest)} areas")

    print("Extracting H5P interactive content...")
    hvp_tabs = extract_hvp_content(manifest)
    print(f"  {len(hvp_tabs)} H5P activities")
    for t in hvp_tabs:
        print(f"    - {t['title']}: {len(t['hotspots'])} hotspots")

    hvp_by_id = {t["id"]: t for t in hvp_tabs}

    print("Extracting lessons...")
    lessons = extract_lessons(manifest, hvp_by_id)
    for lid, ldata in lessons.items():
        en_pages = len(ldata["en"]["pages"])
        print(f"  {lid}: EN={en_pages} pages - {ldata['en']['title'][:60]}")

    print("Extracting quiz questions...")
    questions = extract_quiz_questions()
    print(f"  {len(questions)} questions")

    print("Extracting pages...")
    pages = extract_pages()
    for pid, pdata in pages.items():
        print(f"  {pid}: {pdata['en']['title'][:60]}")

    # ── Load existing course JSON and merge ───────────────────────────

    print("\nMerging with existing course JSON...")

    all_corpus = "".join(p["content"] for L in lessons.values() for lg in ("en", "fr") for p in L[lg]["pages"])
    for lang in ["en", "fr"]:
        with open(f"data/course-{lang}.json") as f:
            course = json.load(f)

        # Map Moodle lesson IDs to course lesson indices
        # lesson_10372 = Pre-Course (Before You Begin / Learning Objectives)
        # lesson_10373 = Lesson 1
        # lesson_10374 = Lesson 2
        # lesson_10375 = Lesson 3
        # lesson_10376 = Lesson 4

        lesson_mapping = {
            "lesson_10372": None,  # Goes to course overview / pre-module
            "lesson_10373": 0,
            "lesson_10374": 1,
            "lesson_10375": 2,
            "lesson_10376": 3,
        }

        for moodle_id, idx in lesson_mapping.items():
            if moodle_id not in lessons:
                continue

            ldata = lessons[moodle_id][lang]

            if idx is None:
                # Pre-course lesson (Moodle course structure/accreditation) is not shown on the static site
                pass
            else:
                # Merge into existing lessons
                if idx < len(course["lessons"]):
                    existing_lesson = course["lessons"][idx]
                    existing_lesson["pages"] = [
                        {"id": p["id"], "title": p["title"], "content": p["content"]}
                        for p in ldata["pages"]
                    ]
                    # lessons 2-4 (idx 1-3) carry the learning-check questions
                    if ldata["questions"] and 0 <= idx - 1 < len(course["learningChecks"]):
                        course["learningChecks"][idx - 1]["questions"] = ldata["questions"]

        # Pre-course quiz from the Moodle question bank
        course["preQuiz"]["questions"] = [build_quiz_question(q, lang) for q in questions]

        # Moodle URL-activity links lost their target in the export (href = the Moodle root);
        # recover them from identical link text elsewhere in the course, else drop the dead link.
        if "page_10512" in pages:
            pages["page_10512"][lang]["content"] = fix_bare_links(pages["page_10512"][lang]["content"], all_corpus)

        # Add resources page content
        if "page_10512" in pages:
            res_page = pages["page_10512"][lang]
            course["resources"] = {
                "title": res_page["title"],
                "content": res_page["content"],
            }

        # Add course summary page content
        if "page_10511" in pages:
            sum_page = pages["page_10511"][lang]
            # drop the Moodle "Finish course" call-to-action (no post-course gate on the static site)
            sum_page = dict(sum_page, content=re.split(r'<p style="text-align: center; margin-top: 50px;">', sum_page["content"])[0].strip())
            if "courseSummary" in course and isinstance(course["courseSummary"], list):
                course["courseSummaryPages"] = {
                    "title": sum_page["title"],
                    "content": sum_page["content"],
                }
            else:
                course["courseSummary"] = {
                    "title": sum_page["title"],
                    "content": sum_page["content"],
                }

        # Write updated JSON
        with open(f"data/course-{lang}.json", "w") as f:
            json.dump(course, f, indent=2, ensure_ascii=False)
        print(f"  Updated data/course-{lang}.json")

    # Print summary
    print("\nDone! Summary:")
    for lang in ["en", "fr"]:
        with open(f"data/course-{lang}.json") as f:
            course = json.load(f)
        total_pages = sum(len(l.get("pages", [])) for l in course["lessons"])
        total_tabs = sum(len(l.get("tabs", [])) for l in course["lessons"])
        print(f"  {lang.upper()}: {total_pages} lesson pages, {total_tabs} tabs across {len(course['lessons'])} lessons")


if __name__ == "__main__":
    main()
