# Session Log: 03-10-2026 11:45 - returndemo build phase 1

## Quick Reference (for AI scanning)
**Confidence keywords:** returndemo-course, bilingual EN/FR, Word doc extraction, python-docx, lxml, zipfile, rId mapping, xpath vs python-docx indices, Heading1 style, w:pStyle, SPA, Cloudflare Pages, cancerandwork.ca theming, purple accent #9461a9
**Projects:** returndemo-course (new repo jjnunez11/returndemo-course)
**Outcome:** Built complete bilingual static course site from Word docs: extraction script, 166 images, 12 PDFs, SPA with quizzes/tabs/lang toggle, pushed to GitHub

## Key Learnings
- python-docx paragraph indices (796) differ from xpath `//w:p` indices (1543) — the latter includes paras in headers/footers/SDTs; section boundaries must be discovered via xpath
- Style is in `w:pPr/w:pStyle/@w:val` (e.g., "Heading1"), NOT `w:pPr/@w:rStyle`
- Image `r:embed` refs are deep: `w:drawing > wp:inline > a:graphic > a:graphicData > pic:pic > pic:blipFill > a:blip r:embed` — needs `pic` namespace declared
- Most reliable image extraction: directly from `word/media/` in zip, mapped via `word/_rels/document.xml.rels`
- French doc has completely different xpath boundaries than English (166 paras vs 796 in python-docx terms)

## Decisions Made
- Videos (383MB MP4s) gitignored — too large for git, deploy via CDN separately
- Section boundaries hardcoded per language in build script (fragile but reliable)
- Quiz answer matching uses fuzzy word-overlap rather than exact match
- Post-course questionnaire renders as reflection tool, no data submission

## Solutions & Fixes
- Fixed image extraction: switched from python-docx rels traversal to direct zip `word/media/` extraction with rId mapping from rels XML
- Fixed style detection: switched from `rStyle` attribute to `pStyle/val` child element
- Fixed section boundaries: remapped all ranges from python-docx indices to xpath indices
- Added text-based section detection for "iCanWork Step" and "Étape N d'iCanWork" patterns (some headings lack Heading1 style)

## Files Modified
- `build-course.py`: Word doc parser, extracts JSON + images from .docx via zipfile/lxml
- `index.html`: SPA shell with sidebar, header, lang toggle
- `style.css`: Purple-accent theme, responsive, quiz/tab/progress styles
- `app.js`: Client-side SPA engine (nav, quizzes, tabs, bilingual toggle, progress)
- `data/course-en.json`: Extracted English course (4 lessons, 93 images)
- `data/course-fr.json`: Extracted French course (4 lessons, 73 images)
- `robots.txt`: Disallow: /
- `README.md`: Project documentation
- `.gitignore`: node_modules, .env, *.mp4

## Pending Tasks
1. Connect Cloudflare Pages to GitHub repo
2. Configure DNS for returndemo.johnjosenunez.com
3. Upload videos to CDN (R2 or similar)
4. Test site locally and refine rendering
5. Map tab content properly (empty headings with images)
6. Fix French lesson titles (different format than English)

## Errors & Workarounds
- `gh repo create --remote origin` failed — `--remote` only works with `--source`; used `--clone` instead
- Image extraction returned 0 images — python-docx `findall('.//w:drawing', ns)` couldn't find `a:blip` without `pic` namespace; solved by extracting from zip directly
- Lessons had 0 sections — style attribute was wrong (`rStyle` vs `pStyle/val`); all headings parsed as Normal
- Section boundaries all wrong — were using python-docx paragraph indices (796) but data uses xpath indices (1543); remapped all boundaries

---

## Quick Resume Context
Phase 1 of returndemo-course build is complete: GitHub repo created, content extracted from Word docs (EN + FR), SPA site built with quizzes/tabs/lang toggle, pushed to GitHub. Next: connect Cloudflare Pages, configure DNS, handle video hosting, refine rendering of tab content and French lesson structure. The build script uses hardcoded xpath boundaries per language — fragile but working. Videos (383MB) are gitignored.
