#!/usr/bin/env python3
"""Rebuild meta + acknowledgements in data/course-{en,fr}.json from the Word docs.
Usage: fix-welcome.py  (reads sources/RTW-Course-{EN,FR}.docx)"""
import json, docx

def parse(path):
    P = [p.text.replace("\xa0", " ").strip() for p in docx.Document(path).paragraphs]
    P = [p for p in P if p]
    credits, duration, audience = (p.split(":", 1)[1].strip() for p in P[:3])
    toggles = [i for i, p in enumerate(P) if "▼" in p]
    ack_i, disc_i = toggles[0], toggles[1]
    intro = P[4]
    objectives = P[5:ack_i]
    # sections between the ack toggle and the "reconnaissance/Acknowledgments" paragraph
    groups, cur = [], None
    ack_para_i = None
    for i in range(ack_i + 1, disc_i):
        groups.append(P[i])
    # first three headings: lead authors, design, special thanks; then acknowledgement heading + text
    lead_h = groups[0]
    des_h = next(i for i, g in enumerate(groups) if i > 0 and not any(c in g for c in ",("))
    st_h = next(i for i in range(des_h + 1, len(groups)) if "," not in groups[i] and "(" not in groups[i] and groups[i] not in ("Stephanie Robins",) and i > des_h + 1)
    ack_h = len(groups) - 2
    lead = groups[1:des_h]
    design = groups[des_h + 1:st_h]
    thanks = groups[st_h + 1:ack_h]
    return dict(
        meta=dict(credits=credits, duration=duration, targetAudience=audience,
                  objectivesIntro=intro, learningObjectives=objectives),
        ack=dict(leadAuthors=lead, design=design, specialThanks=thanks,
                 headings=dict(lead=lead_h, design=groups[des_h], thanks=groups[st_h], ack=groups[ack_h]),
                 acknowledgement=groups[-1], disclosures=P[disc_i + 1]),
        objHeading=P[3])

for l in ("en", "fr"):
    r = parse(f"sources/RTW-Course-{l.upper()}.docx")
    f = f"data/course-{l}.json"
    d = json.load(open(f))
    d["meta"].update(r["meta"]); d["meta"]["objectivesHeading"] = r["objHeading"]
    d["acknowledgements"] = r["ack"]
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=2)
    print(l, json.dumps(r, ensure_ascii=False, indent=1)[:1800])


# ── Post-course questionnaire: the docx flattened three Moodle questions into question 1 ──
LABELS = {
    "en": ("What is your area of specialization?", "Please specify your profession:"),
    "fr": ("Quel est votre domaine de spécialisation ?", "Veuillez préciser votre profession :"),
}
for l in ("en", "fr"):
    f = f"data/course-{l}.json"
    d = json.load(open(f))
    qs = d["postCourseQuestionnaire"]
    q1 = qs[0]
    o = q1["options"]
    if len(o) > 20:  # not yet split
        others = [i for i, x in enumerate(o) if x.lower().startswith(("other", "autre"))]
        prof = o[:9]
        spec = o[9:others[0] + 1]
        prof2 = o[others[0] + 1:]
        qs[0] = dict(q1, options=prof)
        qs[1:1] = [{"number": "", "text": LABELS[l][0], "options": spec, "sub_text": q1.get("sub_text", "")},
                   {"number": "", "text": LABELS[l][1], "options": prof2}]
    # province list also swallowed the BC health-authority question and a section label
    pi = next((i for i, q in enumerate(qs) if len(q["options"]) == 24), None)
    if pi is not None:
        q = qs[pi]
        o = q["options"]
        assert o[14] == "First Nations Health Authority" and o[23] in ("Course Material", "Contenu du cours")
        ha = {"en": "Within which BC provincial health authority are you currently working? (Select all that apply)",
              "fr": "Dans quelle autorité sanitaire provinciale de la C.-B. travaillez-vous actuellement ? (Sélectionnez toutes les réponses qui s'appliquent)"}[l]
        qs[pi:pi + 1] = [dict(q, options=o[:14]), {"number": "", "text": ha, "options": o[14:23], "multi": True}]
    for n, q in enumerate(qs, 1):
        q["number"] = str(n)
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=2)
    print(l, "questionnaire:", [(q["number"], len(q["options"])) for q in qs])
