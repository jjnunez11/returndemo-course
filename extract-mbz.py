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

def clean_html(raw_html):
    """Clean up Moodle HTML for embedding in our static site."""
    if not raw_html:
        return ""

    # Decode HTML entities that were double-encoded in Moodle XML
    raw_html = raw_html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

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
    filename = filename.replace("%20", " ").replace("%40", "@")

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

    html_content = re.sub(r'@@PLUGINFILE@@/\S+', replace_ref, html_content)
    return html_content


# ── Extract lesson pages ──────────────────────────────────────────────

def extract_lessons(manifest):
    """Parse all lesson XML files and extract bilingual page content."""
    img_map = build_image_map(manifest)
    lessons = {}  # lesson_id -> {en: {title, pages}, fr: {title, pages}}

    for lesson_file in sorted(glob.glob(str(MBZ_DIR / "activities/lesson_*/lesson.xml"))):
        lp = Path(lesson_file)
        lesson_id = lp.parent.name  # e.g. "lesson_10372"

        with open(lesson_file) as f:
            content = f.read()

        # Extract all <page> blocks
        page_blocks = re.findall(r'<page\s+id="(\d+)">(.*?)</page>', content, re.DOTALL)

        lesson_pages = {"en": [], "fr": []}

        for page_id, page_content in page_blocks:
            # Extract title
            title_m = re.search(r'<title>(.*?)</title>', page_content, re.DOTALL)
            title_raw = title_m.group(1) if title_m else ""
            title_split = split_mlang(title_raw)

            # Extract contents
            contents_m = re.search(r'<contents>(.*?)</contents>', page_content, re.DOTALL)
            raw_content = contents_m.group(1) if contents_m else ""

            # Process EN content
            en_content = extract_lang(raw_content, "en")
            en_content = clean_html(en_content)
            en_content = process_image_refs(en_content, img_map)

            # Process FR content
            fr_content = extract_lang(raw_content, "fr")
            fr_content = clean_html(fr_content)
            fr_content = process_image_refs(fr_content, img_map)

            # Extract answer buttons (for navigation labels)
            answers = re.findall(r'<answer[^>]*>(.*?)</answer>', page_content, re.DOTALL)
            nav_text = ""
            for a in answers:
                at_m = re.search(r'<answer_text>(.*?)</answer_text>', a, re.DOTALL)
                if at_m:
                    nav_text = extract_lang(at_m.group(1), "en").strip()

            lesson_pages["en"].append({
                "title": title_split.get("en", "").strip(),
                "content": en_content,
                "nav": nav_text,
            })
            lesson_pages["fr"].append({
                "title": title_split.get("fr", "").strip(),
                "content": fr_content,
                "nav": nav_text,
            })

        # Get lesson title from first page
        if lesson_pages["en"]:
            lessons[lesson_id] = {
                "en": {
                    "title": lesson_pages["en"][0].get("title", ""),
                    "pages": lesson_pages["en"],
                },
                "fr": {
                    "title": lesson_pages["fr"][0].get("title", ""),
                    "pages": lesson_pages["fr"],
                }
            }

    return lessons


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
            "title": name,
            "image": main_image_path,
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
                "text": text,
                "position": pos,
            })

        tabs.append(tab)

        # Extract the H5P main image if present
        if main_image_path:
            img_fn = os.path.basename(main_image_path)
            # H5P images are in 'content' filearea
            ch = manifest.get("content", {}).get(img_fn)
            if ch:
                extract_image_by_hash(ch, img_fn)

    return tabs


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

        en_content = clean_html(extract_lang(raw, "en"))
        fr_content = clean_html(extract_lang(raw, "fr"))
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
    print(f"  Found {sum(len(v) for v in manifest.values())} files across {len(manifest)} areas")

    print("Extracting lessons...")
    lessons = extract_lessons(manifest)
    for lid, ldata in lessons.items():
        en_pages = len(ldata["en"]["pages"])
        print(f"  {lid}: EN={en_pages} pages - {ldata['en']['title'][:60]}")

    print("Extracting quiz questions...")
    questions = extract_quiz_questions()
    print(f"  {len(questions)} questions")

    print("Extracting H5P interactive content...")
    hvp_tabs = extract_hvp_content(manifest)
    print(f"  {len(hvp_tabs)} H5P activities")
    for t in hvp_tabs:
        print(f"    - {t['title']}: {len(t['hotspots'])} hotspots")

    print("Extracting pages...")
    pages = extract_pages()
    for pid, pdata in pages.items():
        print(f"  {pid}: {pdata['en']['title'][:60]}")

    # ── Load existing course JSON and merge ───────────────────────────

    print("\nMerging with existing course JSON...")

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
                # Pre-course content (lesson_10372 = Learning Objectives)
                # courseOverview is a list of {text, images} items
                if ldata["pages"]:
                    for p in ldata["pages"]:
                        if p.get("content"):
                            course["courseOverview"].append({
                                "text": p["content"],
                                "images": []
                            })
            else:
                # Merge into existing lessons
                if idx < len(course["lessons"]):
                    existing_lesson = course["lessons"][idx]
                    existing_lesson["pages"] = [
                        {"title": p["title"], "content": p["content"]}
                        for p in ldata["pages"]
                    ]

        # Add H5P interactive content as tabs on lessons 2, 3, 4
        # The H5P content is about the iCanWork plan (assessment, addressing challenges, transitioning)
        # Lesson 2 = assessment, Lesson 3 = addressing challenges, Lesson 4 = transitioning
        if hvp_tabs:
            # Determine which language's H5P to use
            if lang == "en":
                en_hvp = [t for t in hvp_tabs if "Cancer and Return" in t["title"] or "Activit" not in t["title"]]
            else:
                fr_hvp = [t for t in hvp_tabs if "plan de retour" in t["title"].lower() or "Activit" in t["title"]]
                en_hvp = [t for t in hvp_tabs if "Activit" not in t["title"]]

            # Map H5P hotspots to tab content for relevant lessons
            # H5P EN is "Interactive: Cancer and Return to Work Plan"
            # H5P FR is "Activité interactive : Le cancer et le plan de retour au travail"
            for t in hvp_tabs:
                if lang == "fr" and "Activit" not in t["title"]:
                    continue
                if lang == "en" and "Activit" in t["title"]:
                    continue

                # Determine which lesson this H5P maps to based on hotspot content
                # The hotspots reference iCanWork steps: assessment, addressing challenges, transitioning, communication
                # Map to lessons 2-4 based on hotspot headers
                for i, hs in enumerate(t.get("hotspots", [])):
                    header = hs.get("header", "").lower()
                    text = hs.get("text", "").lower()

                    # Determine target lesson from content keywords
                    target_lesson = None
                    if "assessment" in header or "evaluation" in header:
                        target_lesson = 1  # Lesson 2
                    elif "challenge" in header or "défi" in header:
                        target_lesson = 2  # Lesson 3
                    elif "transition" in header:
                        target_lesson = 3  # Lesson 4
                    elif "communication" in header:
                        target_lesson = 2  # Lesson 3 (addressing challenges includes communication)
                    elif "start and end" in header or "date" in header:
                        target_lesson = 3  # Lesson 4 (transitioning)
                    elif "accommodation" in header or "amén" in header:
                        target_lesson = 2  # Lesson 3
                    elif "disclosure" in header or "divulg" in header:
                        target_lesson = 3  # Lesson 4
                    elif "transport" in header:
                        target_lesson = 3  # Lesson 4
                    elif "former job" in header or "ancien" in header:
                        target_lesson = 3  # Lesson 4
                    elif "seek change" in header or "recherche" in header:
                        target_lesson = 3  # Lesson 4

                    if target_lesson is not None and target_lesson < len(course["lessons"]):
                        if "tabs" not in course["lessons"][target_lesson]:
                            course["lessons"][target_lesson]["tabs"] = []

                        # Add as tab if not already present
                        tab_exists = any(
                            tt.get("title", "") == hs["header"]
                            for tt in course["lessons"][target_lesson]["tabs"]
                        )
                        if not tab_exists:
                            course["lessons"][target_lesson]["tabs"].append({
                                "title": hs["header"],
                                "content": [{"text": hs["text"]}],
                            })

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
