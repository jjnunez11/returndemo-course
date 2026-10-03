#!/usr/bin/env python3
"""
Extract a Return-to-Work course Word doc into structured JSON + embedded images.

Usage:
    python3 build-course.py <path-to-docx> <lang-code>

Example:
    python3 build-course.py \\
        "/home/j2/GoogleDrive/Work/Projects/_Collaborations/Cancer and Work Rebuild/English/RTW Course content_EN.docx" \\
        en

Produces:
    data/course-en.json
    data/images/ (extracted PNGs)
"""

import sys
import os
import re
import json
from pathlib import Path
from lxml import etree
import zipfile

IMAGES_DIR = Path("data/images")

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
RELS_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def build_rid_to_media(doc_path):
    """Build {rId: media_filename} from the .docx rels file."""
    with zipfile.ZipFile(doc_path) as z:
        rels_content = z.read("word/_rels/document.xml.rels")
        rels_xml = etree.fromstring(rels_content)

        rid_map = {}
        for rel in rels_xml.xpath("//r:Relationship", namespaces=RELS_NS):
            rid = rel.get("Id")
            rel_type = rel.get("Type")
            target = rel.get("Target")
            if "image" in rel_type:
                rid_map[rid] = os.path.basename(target)
        return rid_map


def extract_media_images(doc_path, lang):
    """Extract all images from word/media/ in the .docx zip."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    rid_map = build_rid_to_media(doc_path)

    rid_to_fname = {}
    with zipfile.ZipFile(doc_path) as z:
        media_files = [f for f in z.namelist() if f.startswith("word/media/")]
        for mf in media_files:
            # Read from zip
            content = z.read(mf)
            # Determine extension
            if content.startswith(b"\x89PNG"):
                ext = "png"
            elif content.startswith(b"\xff\xd8\xff"):
                ext = "jpg"
            elif content.startswith(b"GIF8"):
                ext = "gif"
            else:
                ext = "png"

            # Find which rId points to this media file
            basename = os.path.basename(mf)
            inverse = {v: k for k, v in rid_map.items()}
            rid = inverse.get(basename)

            # Write with lang prefix
            if rid:
                idx = rid_map.get(rid, "zzz")
                fname = f"{lang}-{rid.zfill(4)}.{ext}"
            else:
                fname = f"{lang}-{basename}"

            (IMAGES_DIR / fname).write_bytes(content)
            if rid:
                rid_to_fname[rid] = fname

    print(f"  Extracted {len(rid_to_fname)} images")
    return rid_to_fname


def parse_docx(doc_path, lang, rid_to_fname):
    """Parse the Word doc into structured JSON."""
    with zipfile.ZipFile(doc_path) as z:
        content = z.read("word/document.xml")
    doc_xml = etree.fromstring(content)

    # ── Extract all paragraphs ──
    paras = doc_xml.xpath("//w:p", namespaces=NS)
    raw = []
    for idx, p in enumerate(paras):
        # Text
        text_parts = p.xpath(".//w:r/w:t/text()", namespaces=NS)
        text = "".join(text_parts).strip()

        # Style (w:pPr/w:pStyle/@w:val)
        pStyle = p.xpath(".//w:pPr/w:pStyle/@w:val", namespaces=NS)
        style = pStyle[0] if pStyle else ""

        # Images
        embeds = p.xpath(".//a:blip/@r:embed", namespaces=NS)
        images = [rid_to_fname.get(e) for e in embeds if rid_to_fname.get(e)]

        # Heading name from style number
        heading_name = style

        entry = {
            "i": idx,
            "style": style,
            "text": text,
        }
        if images:
            entry["images"] = images
        if text or style or images:
            raw.append(entry)

    # ── Extract tables ──
    tables = doc_xml.xpath("//w:tbl", namespaces=NS)
    for t_idx, table in enumerate(tables):
        rows_xml = table.xpath(".//w:tr", namespaces=NS)
        rows = []
        for row in rows_xml:
            cells = row.xpath(".//w:tc", namespaces=NS)
            row_data = []
            for cell in cells:
                texts = cell.xpath(".//w:r/w:t/text()", namespaces=NS)
                row_data.append("".join(texts).strip())
            rows.append(row_data)
        raw.append({"i": 700 + t_idx, "style": "Table", "text": f"TABLE-{t_idx}", "rows": rows})

    raw.sort(key=lambda x: x["i"])
    return _build_json(raw, lang)


def _build_json(raw, lang):
    """Build structured course JSON from raw paragraph list."""
    result = {
        "meta": {},
        "acknowledgements": {},
        "courseOverview": [],
        "preQuiz": {"questions": []},
        "lessons": [],
        "learningChecks": [],
        "courseSummary": [],
        "postCourseQuestionnaire": [],
    }

    # ── Meta ──
    meta = {"learningObjectives": []}
    capturing_objectives = False
    for p in raw[:16]:
        t = p["text"]
        if t.startswith("Credits:"):
            meta["credits"] = t.split(":", 1)[1].strip()
        elif t.startswith("Duration:"):
            meta["duration"] = t.split(":", 1)[1].strip()
        elif t.startswith("Target Audience:"):
            meta["targetAudience"] = t.split(":", 1)[1].strip()
        elif t == "Learning Objectives":
            capturing_objectives = True
            continue
        if capturing_objectives and t:
            meta["learningObjectives"].append(t)

    meta["title"] = (
        "Return to Work for Cancer Survivors"
        if lang == "en"
        else "Retour au travail pour les surviveurs du cancer"
    )
    result["meta"] = meta

    # ── Acknowledgements ──
    acks = {
        "leadAuthors": [],
        "design": [],
        "specialThanks": [],
        "acknowledgement": "",
        "disclosures": "",
    }
    current_ack = None
    for p in raw[17:48]:
        t = p["text"]
        if t == "Lead Authors":
            current_ack = "leadAuthors"
        elif t == "Instructional Design and Illustrations":
            current_ack = "design"
        elif t == "Special Thanks":
            current_ack = "specialThanks"
        elif t == "Acknowledgments":
            current_ack = "acknowledgement"
        elif current_ack and t and not t.startswith("Click here"):
            if current_ack in ("leadAuthors", "design", "specialThanks"):
                acks[current_ack].append(t)
            elif current_ack == "acknowledgement":
                acks["acknowledgement"] = t

    for p in raw[45:48]:
        if "Affiliations" in p["text"]:
            acks["disclosures"] = p["text"]

    result["acknowledgements"] = acks

    # ── Course Overview (para 48-78) ──
    for p in raw:
        if 48 <= p["i"] <= 78 and p["text"] and not p["text"].startswith("Click here"):
            result["courseOverview"].append(
                {"text": p["text"], "images": p.get("images", [])}
            )

    # ── Section boundaries differ per language ──
    # English xpath indices vs French xpath indices
    if lang == "en":
        BOUNDARIES = {
            "pre_quiz": (79, 127),
            "lesson1": (127, 353),
            "lesson2": (353, 586),
            "lc1": (586, 668),
            "lesson3": (669, 904),
            "lc2": (904, 976),
            "lesson4": (977, 1233),
            "lc3": (1233, 1292),
            "summary": (1292, 1300),
            "post_course": 1301,
            "overview": (48, 78),
        }
    else:  # French
        BOUNDARIES = {
            "pre_quiz": (79, 125),
            "lesson1": (125, 396),
            "lesson2": (396, 638),
            "lc1": (638, 716),
            "lesson3": (716, 955),
            "lc2": (955, 1016),
            "lesson4": (1016, 1316),
            "lc3": (1316, 1374),
            "summary": (1374, 1382),
            "post_course": 1383,
            "overview": (47, 78),
        }

    # ── Course Overview ──
    for p in raw:
        if BOUNDARIES["overview"][0] <= p["i"] <= BOUNDARIES["overview"][1]:
            if p["text"] and not p["text"].startswith("Click here"):
                result["courseOverview"].append(
                    {"text": p["text"], "images": p.get("images", [])}
                )

    # ── Pre-Quiz ──
    result["preQuiz"] = _extract_quiz(
        raw, BOUNDARIES["pre_quiz"][0], BOUNDARIES["pre_quiz"][1], lang
    )

    # ── Lessons and Learning Checks ──
    result["lessons"].append(
        _extract_lesson(raw, BOUNDARIES["lesson1"][0], BOUNDARIES["lesson1"][1], lang)
    )
    result["lessons"].append(
        _extract_lesson(raw, BOUNDARIES["lesson2"][0], BOUNDARIES["lesson2"][1], lang)
    )
    result["learningChecks"].append(
        _extract_quiz(raw, BOUNDARIES["lc1"][0], BOUNDARIES["lc1"][1], lang)
    )
    result["lessons"].append(
        _extract_lesson(raw, BOUNDARIES["lesson3"][0], BOUNDARIES["lesson3"][1], lang)
    )
    result["learningChecks"].append(
        _extract_quiz(raw, BOUNDARIES["lc2"][0], BOUNDARIES["lc2"][1], lang)
    )
    result["lessons"].append(
        _extract_lesson(raw, BOUNDARIES["lesson4"][0], BOUNDARIES["lesson4"][1], lang)
    )
    result["learningChecks"].append(
        _extract_quiz(raw, BOUNDARIES["lc3"][0], BOUNDARIES["lc3"][1], lang)
    )

    # ── Course Summary ──
    for p in raw:
        s, e = BOUNDARIES["summary"]
        if s <= p["i"] <= e:
            t = p["text"]
            if t and "SUMMARY" not in t.upper() and "RÉSUMÉ" not in t.upper():
                result["courseSummary"].append(t)

    # ── Post-Course Questionnaire ──
    result["postCourseQuestionnaire"] = _extract_post_course(
        raw, BOUNDARIES["post_course"]
    )

    return result


def _extract_quiz(raw, start, end, lang):
    """Extract quiz questions from a paragraph range."""
    quiz = {
        "title": "",
        "intro": "",
        "caseStudy": [],
        "questions": [],
    }
    current_q = None
    in_explanation = False

    for p in raw:
        i = p["i"]
        if i < start or i >= end:
            continue
        t = p["text"]
        style = p["style"]

        # Skip structural noise
        if not t or "Congratulations" in t or "Total number of questions" in t:
            continue

        # Quiz title
        if "Learning Check" in t and style == "Heading 1":
            quiz["title"] = t
            continue
        if "PRE-MODULE" in t.upper() or "Pre-Course" in t:
            quiz["title"] = t
            continue
        if "Format:" in t or "Duration:" in t:
            continue

        # Quiz intro
        if i == start + 12 and "self-assessment" in t.lower():
            quiz["intro"] = t
            continue

        # Question detection
        if t.startswith("Question") and ":" in t:
            if current_q:
                quiz["questions"].append(current_q)
            current_q = {
                "question": re.sub(r"^Question\s*\d+[:\s]*", "", t),
                "options": [],
                "correct": "",
                "explanation": "",
            }
            in_explanation = False
            continue

        # Case study
        if t == "Case Study" and current_q is None:
            continue
        if current_q is None and t and "Sally" in t:
            quiz["caseStudy"].append({"text": t, "images": p.get("images", [])})
            continue

        # Answer
        if current_q and t.startswith("Answer"):
            current_q["correct"] = re.sub(r"^Answer[:\s]*", "", t)
            in_explanation = False
            continue

        # Explanation (starts with "A: ")
        if current_q and t.startswith("A:"):
            current_q["explanation"] = t[2:].strip()
            continue

        # Explanation continuation
        if current_q and in_explanation and t:
            current_q["explanation"] += " " + t
            continue

        # Options
        if current_q and t:
            current_q["options"].append(t)

    if current_q:
        quiz["questions"].append(current_q)

    return quiz


def _extract_lesson(raw, start, end, lang):
    """Extract a lesson from a paragraph range."""
    lesson = {
        "title": "",
        "sections": [],
        "tabs": [],
        "images": [],
    }
    current_section = None
    lesson_title_found = False

    for p in raw:
        i = p["i"]
        if i < start or i >= end:
            continue
        t = p["text"]
        style = p["style"]

        # Skip congrats
        if "Congratulations" in t:
            continue

        # Lesson title (e.g., "LESSON 1 | INTRODUCTION...")
        if "LESSON" in t.upper() and "|" in t and not lesson_title_found:
            lesson["title"] = t
            lesson_title_found = True
            continue

        # Section heading (Heading1 with text)
        if style == "Heading1" and t:
            current_section = {
                "title": t,
                "content": [],
                "images": p.get("images", []),
            }
            lesson["sections"].append(current_section)
            continue

        # Text-based section detection: "iCanwork Step N: ..." or "Étape N d'iCanWork: ..."
        # (some lesson steps don't have heading styles)
        import re as _re
        step_match = _re.match(r"iCanwork Step\s+\d+", t, _re.IGNORECASE)
        etape_match = _re.match(r"Étape\s+\d+", t) if t else None
        if not style and (step_match or etape_match) and len(t) > 30:
            current_section = {
                "title": t,
                "content": [],
                "images": p.get("images", []),
            }
            lesson["sections"].append(current_section)
            continue

        # Empty Heading1 with image = tab or visual section
        if style == "Heading1" and not t and p.get("images"):
            if current_section:
                current_section["images"].extend(p["images"])
            else:
                lesson["images"].extend(p["images"])

        # Heading3 = tab content (often empty with image)
        if style == "Heading3":
            if p.get("images") or t:
                lesson["tabs"].append(
                    {
                        "title": t,
                        "images": p.get("images", []),
                        "content": [],
                    }
                )

        # Heading5 = sub-tab
        if style == "Heading5" and p.get("images"):
            lesson["tabs"].append(
                {"title": t, "images": p["images"], "content": []}
            )

        # Regular content
        if current_section and t:
            item = {"text": t}
            if p.get("images"):
                item["images"] = p["images"]
            if p.get("rows"):
                item["type"] = "table"
                item["table"] = p["rows"]
            current_section["content"].append(item)

        # Content before first section
        if current_section is None and style == "Normal" and t:
            lesson["images"].extend(p.get("images", []))

    return lesson


def _extract_post_course(raw, start):
    """Extract post-course questionnaire."""
    questions = []
    current_q = None

    for p in raw:
        i = p["i"]
        if i < start:
            continue
        t = p["text"]

        if not t or t.startswith("Click here") or "Mainpro+" in t or "Privacy" in t:
            continue

        # Detect numbered questions
        m = re.match(r"^(\d+)\.\s+(.*)", t)
        if m:
            if current_q:
                questions.append(current_q)
            current_q = {
                "number": m.group(1),
                "text": m.group(2),
                "options": [],
            }
            continue

        # Sub-question (starts with *)
        if current_q and t.startswith("*"):
            current_q["sub_text"] = t.lstrip("*").strip()
            continue

        # Options
        if current_q and t:
            current_q["options"].append(t)

    if current_q:
        questions.append(current_q)

    return questions


def main():
    if len(sys.argv) != 3:
        print("Usage: build-course.py <path-to-docx> <lang-code>")
        sys.exit(1)

    doc_path = sys.argv[1]
    lang = sys.argv[2]

    if not os.path.exists(doc_path):
        print(f"Error: {doc_path} not found")
        sys.exit(1)

    output_path = f"data/course-{lang}.json"

    print(f"Building course data for language: {lang}")
    print(f"  Input: {doc_path}")
    print(f"  Output: {output_path}")

    # Step 1: Extract images from zip
    print("  Step 1: Extracting images...")
    rid_to_fname = extract_media_images(doc_path, lang)

    # Step 2: Parse structure
    print("  Step 2: Parsing course structure...")
    data = parse_docx(doc_path, lang, rid_to_fname)

    # Write JSON
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Stats
    total_images = len(list(IMAGES_DIR.iterdir()))
    print(f"\n  Results:")
    print(f"    Images extracted: {total_images}")
    print(f"    Lessons: {len(data['lessons'])}")
    print(f"    Pre-quiz questions: {len(data['preQuiz'].get('questions', []))}")
    print(f"    Learning checks: {len(data['learningChecks'])}")
    print(f"    Post-course questions: {len(data['postCourseQuestionnaire'])}")
    print(f"\n  Done! Written to {output_path}")


if __name__ == "__main__":
    main()
