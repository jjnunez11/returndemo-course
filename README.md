# Return to Work Course for Cancer Survivors

Bilingual (English/French) static educational course site.

## Content

Source Word documents are in the vault at:
- `~/GoogleDrive/Work/Projects/_Collaborations/Cancer and Work Rebuild/English/`
- `~/GoogleDrive/Work/Projects/_Collaborations/Cancer and Work Rebuild/French/`

## Building

```bash
# Rebuild course data from Word docs
python3 build-course.py \
  "/home/j2/GoogleDrive/Work/Projects/_Collaborations/Cancer and Work Rebuild/English/RTW Course content_EN.docx" \
  en

python3 build-course.py \
  "/home/j2/GoogleDrive/Work/Projects/_Collaborations/Cancer and Work Rebuild/French/RTW Course content_FR.docx" \
  fr
```

Then merge the Moodle backup content and rebuild the welcome-page metadata:

```bash
mkdir -p /tmp/mbz-extract && tar -xzf sources/RTW-UBC-CPD.mbz -C /tmp/mbz-extract
python3 extract-mbz.py     # lesson pages, H5P tabs, resources, images
python3 fix-welcome.py     # meta + acknowledgements from sources/RTW-Course-{EN,FR}.docx
```

## Structure

```
index.html        # SPA shell
style.css         # Purple-accent theme (cancerandwork.ca inspired)
app.js            # Client-side SPA (nav, quizzes, tabs, lang toggle)
data/
  course-en.json  # Extracted English course data
  course-fr.json  # Extracted French course data
  images/         # 166 extracted images (93 EN + 73 FR)
assets/
  pdfs/           # Course PDFs (infographics, lesson resources, plan forms)
  videos/         # Frederic's story, 720p re-encodes (EN + FR) + posters; 1080p originals live in sources/
build-course.py   # Word doc -> JSON + image extraction
robots.txt        # Disallow: / (unlisted)
```

## Deployment

Cloudflare Pages, custom DNS `returndemo.johnjosenunez.com`, no Access gate.

## Notes

- `robots.txt` has `Disallow: /` -- site is openly accessible but not indexed
- Language toggle switches EN/FR via JSON swap, no page reload
- Quizzes are client-side self-assessment only (no accreditation or credit tracking)
- Post-course questionnaire shows "Thank you" on submit, no data collected
