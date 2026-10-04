/**
 * Return to Work Course - Single Page Application
 *
 * Loads course data from JSON, renders navigation, content, quizzes,
 * and handles bilingual EN/FR switching.
 */

(function () {
  "use strict";

  // ── State ───────────────────────────────────────────────────────────
  const state = {
    lang: "en",
    dataEN: null,
    dataFR: null,
    currentSection: "welcome",
    completedSections: new Set(),
  };

  // ── i18n strings ────────────────────────────────────────────────────
  const i18n = {
    en: {
      navigation: "Navigation",
      courseProgress: "Course Progress",
      welcome: "Welcome",
      preQuiz: "Pre-Course Quiz",
      lesson1: "Lesson 1: Introduction to Cancer Survivorship & RTW",
      lesson2: "Lesson 2: Return to Work: Assessment",
      lesson3: "Lesson 3: Return to Work: Addressing Challenges",
      lesson4: "Lesson 4: Return to Work: Transitioning to Workplace",
      lc1: "Learning Check #1",
      lc2: "Learning Check #2",
      lc3: "Learning Check #3",
      courseSummary: "Course Summary",
      postCourse: "Post-Course Questionnaire",
      showAcks: "Click here to show/hide acknowledgements ▼",
      hideAcks: "Click here to show/hide acknowledgements ▲",
      postCourseIntro: "This is no longer a course, so this questionnaire is now a tool for your own reflection. Your answers are not saved, submitted or shared anywhere.",
      finish: "Finish",
      checkAnswer: "Check Answer",
      question: "Question",
      select: "Select…",
      answerAll: "Please answer every line first.",
      answerFirst: "Please select an answer first.",
      preQuizIntro: "This pre-course quiz is designed solely for self-assessment purposes. It will help gauge your knowledge about supporting the return to work process of cancer survivors.",
      correct: "Correct!",
      incorrect: "Incorrect",
      correctAnswer: "Correct answer:",
      explanation: "Explanation:",
      next: "Next Section",
      previous: "Previous",
      footerText:
        "This course is for educational purposes only. It is not a substitute for professional medical advice.",
      thankYou: "Thank you for completing the questionnaire!",
      thankYouSub:
        "Your responses are for personal reflection only and are not stored or shared.",
      caseStudy: "Case Study",
      totalQuestions: "Total questions:",
    },
    fr: {
      navigation: "Navigation",
      courseProgress: "Progrès du cours",
      welcome: "Bienvenue",
      preQuiz: "Quiz pr\xe9-cours",
      lesson1: "Leçon 1: Introduction à la survie au cancer et au RAT",
      lesson2: "Leçon 2: Retour au travail: L'évaluation",
      lesson3: "Leçon 3: Retour au travail: Relever les défis",
      lesson4: "Leçon 4: Retour au travail: La transition vers le travail",
      lc1: "Vérification d'apprentissage #1",
      lc2: "Vérification d'apprentissage #2",
      lc3: "Vérification d'apprentissage #3",
      courseSummary: "Résumé du cours",
      postCourse: "Questionnaire suite au cours",
      showAcks: "Cliquez ici pour afficher/masquer les remerciements ▼",
      hideAcks: "Cliquez ici pour afficher/masquer les remerciements ▲",
      postCourseIntro: "Ce contenu n'est plus un cours; ce questionnaire est donc maintenant un outil de réflexion personnelle. Vos réponses ne sont ni enregistrées, ni soumises, ni partagées.",
      finish: "Terminer",
      checkAnswer: "Vérifier la réponse",
      question: "Question",
      select: "Choisir…",
      answerAll: "Veuillez répondre à chaque ligne d'abord.",
      answerFirst: "Veuillez d'abord sélectionner une réponse.",
      preQuizIntro: "Ce quiz préalable au cours est conçu uniquement à des fins d'auto-évaluation. Il vous aidera à évaluer vos connaissances sur le soutien au processus de retour au travail des survivants du cancer.",
      correct: "Correct!",
      incorrect: "Incorrect",
      correctAnswer: "Bonne réponse:",
      explanation: "Explication:",
      next: "Section suivante",
      previous: "Précédent",
      footerText:
        "Ce cours est à des fins éducatives uniquement. Il ne remplace pas les conseils médicaux professionnels.",
      thankYou: "Merci d'avoir complété le questionnaire!",
      thankYouSub:
        "Vos réponses sont pour réflexion personnelle uniquement et ne sont pas stockées ou partagées.",
      caseStudy: "\xe9tude de cas",
      totalQuestions: "Total de questions:",
    },
  };

  // ── Section navigation map ──────────────────────────────────────────
  function getNavItems() {
    const t = i18n[state.lang];
    return [
      { id: "welcome", label: t.welcome },
      { id: "pre-quiz", label: t.preQuiz, isQuiz: true },
      { id: "lesson-1", label: t.lesson1 },
      { id: "lesson-2", label: t.lesson2 },
      { id: "learning-check-1", label: t.lc1, isQuiz: true },
      { id: "lesson-3", label: t.lesson3 },
      { id: "learning-check-2", label: t.lc2, isQuiz: true },
      { id: "lesson-4", label: t.lesson4 },
      { id: "learning-check-3", label: t.lc3, isQuiz: true },
      { id: "summary", label: t.courseSummary },
      { id: "post-course", label: t.postCourse },
    ];
  }

  // ── Data loading ────────────────────────────────────────────────────
  async function loadData(lang) {
    const resp = await fetch(`data/course-${lang}.json`);
    if (!resp.ok) throw new Error(`Failed to load course-${lang}.json`);
    return resp.json();
  }

  async function init() {
    // Detect language from hash or localStorage
    const hash = window.location.hash;
    if (hash === "#fr") state.lang = "fr";
    else if (hash === "#en") state.lang = "en";
    else {
      const saved = localStorage.getItem("rtw-lang");
      if (saved) state.lang = saved;
    }

    try {
      state.dataEN = await loadData("en");
      state.dataFR = await loadData("fr");
    } catch (e) {
      document.getElementById("loading").innerHTML =
        '<p style="color:var(--error)">Failed to load course data. Please refresh.</p>';
      console.error(e);
      return;
    }

    // Detect navigation from hash
    const sections = getNavItems();
    const hashSection = hash.replace("#", "").split("-")[0];
    for (const s of sections) {
      if (s.id.startsWith(hashSection)) {
        state.currentSection = s.id;
        break;
      }
    }

    renderNav();
    renderSection(state.currentSection);
    updateProgress();
    updateLangToggle();
    document.getElementById("loading").style.display = "none";

    // Listen for hash changes
    window.addEventListener("hashchange", () => {
      const h = window.location.hash;
      if (h === "#fr" || h === "#en") {
        switchLang(h === "#fr" ? "fr" : "en");
        return;
      }
    });
  }

  // ── Navigation ──────────────────────────────────────────────────────
  // Moodle embedded the plan form via an iframe with an empty src; link the PDF instead.
  function fixEmbeds(html) {
    const lang = state.lang;
    const label = lang === "en" ? "Open the Return to Work Plan form (PDF)" : "Ouvrir le formulaire de plan de retour au travail (PDF)";
    return html.replace(/<iframe[^>]*src=""[^>]*>\s*<\/iframe>/g,
      `<p><a class="pdf-link" href="assets/pdfs/RTW-plan_${lang}.pdf" target="_blank" rel="noopener">${label}</a></p>`);
  }

  function renderNav() {
    const navList = document.getElementById("nav-list");
    const items = getNavItems();
    navList.innerHTML = items
      .map(
        (item) =>
          `<li class="${item.id === state.currentSection ? "active" : ""} ${item.isQuiz ? "quiz-item" : ""}" data-section="${item.id}">
            <a href="#" onclick="window.__course.navigate('${item.id}'); return false;">${item.label}</a>
          </li>`
      )
      .join("");
  }

  // ── Section rendering ───────────────────────────────────────────────
  function renderSection(id) {
    state.currentSection = id;
    const data = getData();
    const wrapper = document.getElementById("content-wrapper");

    // Update nav active state
    document.querySelectorAll("#nav-list li").forEach((li) => {
      li.classList.toggle("active", li.dataset.section === id);
    });

    // Update hash for navigation (not language)
    if (id && !window.location.hash.startsWith("#fr") && !window.location.hash.startsWith("#en")) {
      window.history.replaceState(null, "", `#${id}`);
    }

    // Mark as viewed
    state.completedSections.add(id);
    updateProgress();

    let html = "";

    switch (id) {
      case "welcome":
        html = renderWelcome(data);
        break;
      case "pre-quiz":
        html = renderQuiz(data.preQuiz, "pre-quiz");
        break;
      case "lesson-1":
        html = renderLesson(data.lessons[0], "lesson-1");
        break;
      case "lesson-2":
        html = renderLesson(data.lessons[1], "lesson-2");
        break;
      case "lesson-3":
        html = renderLesson(data.lessons[2], "lesson-3");
        break;
      case "lesson-4":
        html = renderLesson(data.lessons[3], "lesson-4");
        break;
      case "learning-check-1":
        html = renderQuiz(data.learningChecks[0], "learning-check-1");
        break;
      case "learning-check-2":
        html = renderQuiz(data.learningChecks[1], "learning-check-2");
        break;
      case "learning-check-3":
        html = renderQuiz(data.learningChecks[2], "learning-check-3");
        break;
      case "summary":
        html = renderSummary(data);
        break;
      case "resources":
        html = renderResourcesPage(data);
        break;
      case "post-course":
        html = renderPostCourse(data);
        break;
      default:
        html = renderWelcome(data);
    }

    // Add navigation buttons
    html += renderNavButtons(id);

    wrapper.innerHTML = html;
    initWidgets();
    wrapper.scrollTop = 0;
    window.scrollTo(0, 0);

    // Initialize interactive elements
    initTabs();
    initCollapsibles();
  }

  // ── Welcome Section ─────────────────────────────────────────────────
  function renderWelcome(data) {
    const meta = data.meta;
    const acks = data.acknowledgements;
    const t = i18n[state.lang];

    return `
      <div class="hero">
        <h2>${meta.title}</h2>
        <div class="meta-info">
          <div class="meta-item"><span class="meta-label">${meta.credits}</span></div>
          <div class="meta-item"><span class="meta-label">${meta.duration}</span></div>
          <div class="meta-item"><span class="meta-label">${meta.targetAudience}</span></div>
        </div>
      </div>

      <div class="section">
        <h3 class="section-subtitle">${meta.objectivesHeading}</h3>
        <p>${meta.objectivesIntro}</p>
        <ul class="objectives-list">
          ${meta.learningObjectives.map((o) => `<li>${o}</li>`).join("")}
        </ul>
      </div>

      ${renderPDFLinks(data)}

      <div class="collapsible">
        <button class="collapsible-toggle" onclick="this.nextElementSibling.classList.toggle('open'); this.textContent = this.nextElementSibling.classList.contains('open') ? (window.__course.t('hideAcks') || 'Hide acknowledgements ▲') : (window.__course.t('showAcks') || 'Show acknowledgements ▼');">
          ${state.lang === "en" ? "Click here to show/hide acknowledgements ▼" : "Cliquez ici pour afficher/masquer les remerciements ▼"}
        </button>
        <div class="collapsible-content acks-content">
          ${acks.html
            ? acks.html
            : [["lead", "leadAuthors"], ["design", "design"], ["thanks", "specialThanks"]]
                .filter(([, k]) => acks[k].length)
                .map(([h, k]) => `<h4>${acks.headings[h]}</h4><ul>${acks[k].map((a) => `<li>${a}</li>`).join("")}</ul>`)
                .join("") + (acks.acknowledgement ? `<h4>${acks.headings.ack}</h4><p style="font-size:0.9rem;">${acks.acknowledgement}</p>` : "")}
        </div>
      </div>
    `;
  }

  // ── PDF Links ───────────────────────────────────────────────────────
  function renderPDFLinks() {
    const lang = state.lang;
    const links = [
      { file: `RTW-infographic_${lang}.pdf`, label: lang === "en" ? "Return to Work Infographic" : "Infographie du retour au travail" },
      { file: `RTW-all-lessons-resources_${lang}.pdf`, label: lang === "en" ? "All Lessons Resources" : "Ressources de toutes les leçons" },
      { file: `RTW-lesson-2-resources_${lang}.pdf`, label: lang === "en" ? "Lesson 2 Resources" : "Ressources de la leçon 2" },
      { file: `RTW-lesson-3-resources_${lang}.pdf`, label: lang === "en" ? "Lesson 3 Resources" : "Ressources de la leçon 3" },
      { file: `RTW-lesson-4-resources_${lang}.pdf`, label: lang === "en" ? "Lesson 4 Resources" : "Ressources de la leçon 4" },
      { file: `RTW-plan_${lang}.pdf`, label: lang === "en" ? "Return to Work Plan Form" : "Formulaire de plan de retour au travail" },
    ];

    return `
      <div class="section">
        <h3 class="section-subtitle">${lang === "en" ? "Course Resources (PDF)" : "Ressources du cours (PDF)"}</h3>
        <div class="pdf-links">
          ${links.map((l) => `<a class="pdf-link" href="assets/pdfs/${l.file}" download>${l.label}</a>`).join("")}
        </div>
      </div>
    `;
  }

  // ── Lesson Rendering ────────────────────────────────────────────────
  function renderLesson(lesson, id) {
    if (!lesson || !lesson.sections) {
      return `<div class="section"><p>${i18n[state.lang].lesson1}</p></div>`;
    }

    let html = `<div class="section">`;
    // Fallback for FR lessons whose title is empty (LEÇON ≠ LESSON in build script)
    const title = lesson.title || (lesson.sections[0] && lesson.sections[0].title) || `Lesson ${id}`;
    html += `<h2 class="section-title">${title}</h2>`;

    // Render mbz-extracted lesson pages (full Moodle content, primary source)
    if (lesson.pages && lesson.pages.length) {
      for (const page of lesson.pages) {
        if (page.title) {
          html += `<h3 class="section-title mbz-page-title">${page.title}</h3>`;
        }
        if (page.content) {
          html += `<div class="mbz-page-content" id="lp-${page.id}">${fixEmbeds(page.content)}</div>`;
        }
      }
    }

    // Render docx-extracted sections only when the Moodle pages are missing
    const docxSections = lesson.pages && lesson.pages.length ? [] : lesson.sections;
    for (const section of docxSections) {
      html += `<h3 class="section-subtitle">${section.title}</h3>`;

      // Section images
      if (section.images && section.images.length) {
        for (const img of section.images) {
          html += `<div class="content-image"><img src="data/images/${img}" alt=""></div>`;
        }
      }

      // Section content
      for (const item of section.content) {
        if (item.type === "table" && item.table) {
          html += renderTable(item.table);
        } else if (item.images && item.images.length) {
          html += `<div class="content-image"><img src="data/images/${item.images[0]}" alt=""></div>`;
        } else if (item.text) {
          html += `<p class="content-text">${item.text}</p>`;
        }
      }
    }

    // Render tabs
    if (lesson.tabs && lesson.tabs.length) {
      html += renderTabs(lesson.tabs);
    }

    html += `</div>`;
    return html;
  }

  // ── Table Rendering ─────────────────────────────────────────────────
  function renderTable(rows) {
    if (!rows || !rows.length) return "";
    let html = "<table class='content-table'>";
    rows.forEach((row, i) => {
      html += "<tr>";
      row.forEach((cell, j) => {
        const tag = i === 0 ? "th" : "td";
        html += `<${tag}>${cell}</${tag}>`;
      });
      html += "</tr>";
    });
    html += "</table>";
    return html;
  }

  // ── Tabs ────────────────────────────────────────────────────────────
  function renderTabs(tabs) {
    let html = '<div class="tabs-container">';
    html += "<div class='tab-buttons'>";
    tabs.forEach((tab, i) => {
      const title = tab.title || (state.lang === "en" ? `Tab ${i + 1}` : `Onglet ${i + 1}`);
      html += `<button class="tab-btn ${i === 0 ? "active" : ""}" onclick="window.__course.activateTab(this, '${i}')">${title}</button>`;
    });
    html += "</div>";

    tabs.forEach((tab, i) => {
      html += `<div class="tab-panel ${i === 0 ? "active" : ""}" data-tab="${i}">`;
      if (tab.images && tab.images.length) {
        html += `<div class="tab-image"><img src="data/images/${tab.images[0]}" alt=""></div>`;
      }
      if (tab.content && tab.content.length) {
        for (const item of tab.content) {
          html += `<p class="content-text">${item.text}</p>`;
        }
      }
      html += "</div>";
    });

    html += "</div>";
    return html;
  }

  function initTabs() {
    // Tabs are handled by inline onclick; nothing to init here
  }

  // ── Collapsible ─────────────────────────────────────────────────────
  function initCollapsibles() {
    // Handled by inline onclick
  }

  // ── Quiz Rendering ──────────────────────────────────────────────────
  function renderQuiz(quiz, id) {
    const t = i18n[state.lang];
    let html = `<div class="section">`;

    const navLabel = getNavItems().find((n) => n.id === id);
    html += `<h2 class="section-title">${navLabel ? navLabel.label : ""}</h2>`;
    if (id === "pre-quiz") html += `<p class="quiz-intro">${t.preQuizIntro}</p>`;

    // Case study
    if (quiz.caseStudy && quiz.caseStudy.length) {
      html += `<div class="case-study">`;
      html += `<h4>${t.caseStudy}</h4>`;
      for (const item of quiz.caseStudy) {
        html += `<p>${item.text}</p>`;
        if (item.images && item.images.length) {
          html += `<div class="content-image"><img src="data/images/${item.images[0]}" alt=""></div>`;
        }
      }
      html += `</div>`;
    }

    // Questions
    const questions = quiz.questions || [];
    questions.forEach((qData, q) => {
      html += `<div class="quiz-question" data-quiz="${q}">`;
      html += `<div class="question-text"><strong>${t.question} ${q + 1}/${questions.length}</strong>${qData.prompt}</div>`;
      html += `<div class="quiz-options">`;
      if (qData.type === "matching") {
        const choices = qData.choices.map((c) => `<option value="${c}">${c}</option>`).join("");
        qData.items.forEach((item, oi) => {
          html += `
            <div class="quiz-option matching-item" data-option="${oi}">
              <label for="${id}-q${q}-o${oi}">${item.label}</label>
              <select id="${id}-q${q}-o${oi}"><option value="">${t.select}</option>${choices}</select>
            </div>`;
        });
      } else {
        const inputType = qData.type === "multi" ? "checkbox" : "radio";
        qData.options.forEach((opt, oi) => {
          const inputId = `${id}-q${q}-o${oi}`;
          html += `
            <div class="quiz-option" data-option="${oi}">
              <input type="${inputType}" name="${id}-q${q}" id="${inputId}" value="${oi}">
              <label for="${inputId}">${opt}</label>
            </div>`;
        });
      }
      html += `</div>`;
      html += `<button class="check-answer-btn" onclick="window.__course.checkAnswer('${id}', ${q})">${t.checkAnswer}</button>`;
      html += `<div class="feedback" id="${id}-feedback-${q}" role="status"></div>`;
      html += `</div>`;
    });

    html += `</div>`;
    return html;
  }

  // ── Quiz Logic ──────────────────────────────────────────────────────
  function getQuiz(quizId) {
    const data = getData();
    if (quizId === "pre-quiz") return data.preQuiz;
    return data.learningChecks[parseInt(quizId.split("-")[2]) - 1];
  }

  function checkAnswer(quizId, qIdx) {
    const quiz = getQuiz(quizId);
    if (!quiz || !quiz.questions || !quiz.questions[qIdx]) return;
    const qData = quiz.questions[qIdx];
    const t = i18n[state.lang];
    const root = document.querySelector(`#content-wrapper [data-quiz="${qIdx}"]`);
    const optionEls = root.querySelectorAll(".quiz-option");
    const name = `${quizId}-q${qIdx}`;
    let isCorrect, feedbackHtml = "";

    optionEls.forEach((el) => el.classList.remove("correct", "incorrect"));

    if (qData.type === "matching") {
      const picks = qData.items.map((_, oi) => document.getElementById(`${name}-o${oi}`).value);
      if (picks.some((p) => !p)) {
        showFeedback(quizId, qIdx, "incorrect", `<strong>${t.answerAll}</strong>`);
        return;
      }
      isCorrect = true;
      qData.items.forEach((item, oi) => {
        const ok = picks[oi] === item.answer;
        isCorrect = isCorrect && ok;
        optionEls[oi].classList.add(ok ? "correct" : "incorrect");
      });
      feedbackHtml = isCorrect ? qData.feedbackCorrect : qData.feedbackIncorrect;
    } else {
      const selected = Array.from(root.querySelectorAll("input:checked")).map((i) => parseInt(i.value));
      if (!selected.length) {
        showFeedback(quizId, qIdx, "incorrect", `<strong>${t.answerFirst}</strong>`);
        return;
      }
      const correct = qData.correct;
      isCorrect = selected.length === correct.length && selected.every((i) => correct.includes(i));
      optionEls.forEach((el, oi) => {
        if (selected.includes(oi)) el.classList.add(correct.includes(oi) ? "correct" : "incorrect");
        else if (!isCorrect && qData.type === "multi" && correct.includes(oi)) el.classList.add("correct");
      });
      if (qData.type === "single") feedbackHtml = (qData.feedback || [])[selected[0]] || "";
      if (!isCorrect && !feedbackHtml) {
        feedbackHtml = `<p>${t.correctAnswer} ${correct.map((i) => qData.options[i].replace(/<\/?p>/g, "")).join("; ")}</p>`;
      }
    }

    // Moodle feedback already carries its own ✔ / ✖ lead-in; otherwise add ours.
    const lead = /✔|✖/.test(feedbackHtml) ? "" : `<strong>${isCorrect ? t.correct : t.incorrect}</strong>`;
    showFeedback(quizId, qIdx, isCorrect ? "correct" : "incorrect", lead + feedbackHtml);
  }

  function showFeedback(quizId, qIdx, kind, html) {
    const el = document.getElementById(`${quizId}-feedback-${qIdx}`);
    el.className = `feedback ${kind}`;
    el.innerHTML = html;
  }

  // ── Course Summary ──────────────────────────────────────────────────
  function renderSummary(data) {
    const t = i18n[state.lang];
    let html = `<div class="section">`;
    html += `<h2 class="section-title">${t.courseSummary}</h2>`;

    // Use mbz-extracted course summary if available
    if (data.courseSummaryPages && data.courseSummaryPages.content) {
        html += `<div class="mbz-page-content">${data.courseSummaryPages.content}</div>`;
    }

    // Fallback: render existing courseSummary items
    if (data.courseSummaryPages && data.courseSummaryPages.content) {
      // already rendered above
    } else if (Array.isArray(data.courseSummary)) {
      for (const item of data.courseSummary) {
        html += `<p class="content-text">${item}</p>`;
      }
    } else if (typeof data.courseSummary === "object" && data.courseSummary.content) {
      html += `<div class="mbz-page-content">${data.courseSummary.content}</div>`;
    }

    html += `</div>`;
    return html;
  }

  // ── Resources Page ──────────────────────────────────────────────────
  function renderResourcesPage(data) {
    const lang = state.lang;
    let html = `<div class="section">`;

    // mbz-extracted resources content
    if (data.resources && data.resources.content) {
      html += `<h2 class="section-title">${data.resources.title || (lang === "en" ? "Resources" : "Ressources")}</h2>`;
      html += `<div class="mbz-page-content">${data.resources.content}</div>`;
    }

    // PDF download links
    html += renderPDFLinks();

    html += `</div>`;
    return html;
  }

  // ── Post-Course Questionnaire ───────────────────────────────────────
  function renderPostCourse(data) {
    const t = i18n[state.lang];
    const questions = data.postCourseQuestionnaire;

    let html = `<div class="section">`;
    html += `<h2 class="section-title">${t.postCourse}</h2>`;
    html += `<p class="quiz-intro">${t.postCourseIntro}</p>`;

    html += `<div class="questionnaire" id="questionnaire-form">`;
    questions.forEach((q, qi) => {
      html += `<div class="questionnaire-item">`;
      html += `<label>${q.number}. ${q.text}</label>`;

      const scale = (q.options || []).filter((o) => /^\d\s*=/.test(o));
      const stmts = (q.options || []).filter((o) => /^[a-z]\)\s/.test(o));
      if (scale.length && stmts.length) {
        html += `<div class="likert-wrap"><table class="likert"><thead><tr><th></th>${scale.map((s) => `<th>${s}</th>`).join("")}</tr></thead><tbody>`;
        stmts.forEach((st, si) => {
          html += `<tr><th scope="row">${st.replace(/^[a-z]\)\s*/, "")}</th>${scale
            .map((s, ci) => `<td><input type="radio" name="qc-${qi}-${si}" value="${ci}" aria-label="${s}"></td>`)
            .join("")}</tr>`;
        });
        html += `</tbody></table></div>`;
      } else if (q.options && q.options.length > 1) {
        html += `<div class="questionnaire-options">`;
        q.options.forEach((opt, oi) => {
          html += `
            <div class="questionnaire-option">
              <input type="${q.multi ? "checkbox" : "radio"}" name="qc-${qi}" id="qc-${qi}-${oi}" value="${oi}">
              <label for="qc-${qi}-${oi}">${opt}</label>
            </div>`;
        });
        html += `</div>`;
      } else {
        html += `<textarea name="qc-${qi}" rows="3" placeholder="${state.lang === "en" ? "Your response..." : "Votre r\xe9ponse..."}"></textarea>`;
      }

      html += `</div>`;
    });

    html += `<button class="submit-btn" onclick="window.__course.submitQuestionnaire()">${t.finish}</button>`;
    html += `</div>`;

    html += `<div class="thank-you" id="thank-you">`;
    html += `<h3>${t.thankYou}</h3>`;
    html += `<p>${t.thankYouSub}</p>`;
    html += `</div>`;

    html += `</div>`;
    return html;
  }

  function submitQuestionnaire() {
    document.getElementById("questionnaire-form").style.display = "none";
    document.getElementById("thank-you").style.display = "block";
    state.completedSections.add("post-course");
    updateProgress();
  }

  // ── Navigation Buttons ──────────────────────────────────────────────
  function renderNavButtons(currentId) {
    const items = getNavItems();
    const idx = items.findIndex((i) => i.id === currentId);
    const t = i18n[state.lang];

    let html = '<div class="nav-buttons">';

    if (idx > 0) {
      html += `<button class="nav-btn" onclick="window.__course.navigate('${items[idx - 1].id}')">
        &larr; ${t.previous}
      </button>`;
    } else {
      html += `<span></span>`;
    }

    if (idx < items.length - 1) {
      html += `<button class="nav-btn primary" onclick="window.__course.navigate('${items[idx + 1].id}')">
        ${t.next} &rarr;
      </button>`;
    }

    html += "</div>";
    return html;
  }

  // ── Progress ────────────────────────────────────────────────────────
  function updateProgress() {
    const items = getNavItems();
    const total = items.length;
    const completed = state.completedSections.size;
    const pct = Math.round((completed / total) * 100);

    const fill = document.getElementById("progress-fill");
    const text = document.getElementById("progress-text");
    if (fill) fill.style.width = pct + "%";
    if (text) text.textContent = pct + "%";
  }

  // ── Language Toggle ─────────────────────────────────────────────────
  function updateLangToggle() {
    const btn = document.getElementById("lang-toggle");
    const label = document.getElementById("lang-label");
    const other = document.querySelector(".lang-other");
    if (other) other.textContent = state.lang === "en" ? "FR" : "EN";
    if (state.lang === "en") {
      label.textContent = "EN";
      btn.setAttribute("aria-label", "Passer en fran\xe7ais");
    } else {
      label.textContent = "FR";
      btn.setAttribute("aria-label", "Switch to English");
    }

    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = i18n[state.lang][el.dataset.i18n];
      if (v) el.textContent = v;
    });

    // Update site title
    const data = getData();
    const titleEl = document.getElementById("site-title");
    if (titleEl && data.meta) {
      titleEl.textContent = data.meta.title;
    }
  }

  function switchLang(lang) {
    if (lang === state.lang) return;
    state.lang = lang;
    localStorage.setItem("rtw-lang", lang);
    window.location.hash = lang;
    renderNav();
    renderSection(state.currentSection);
    updateLangToggle();
  }

  // ── Helpers ─────────────────────────────────────────────────────────
  function getData() {
    return state.lang === "fr" ? state.dataFR : state.dataEN;
  }

  // ── Public API ──────────────────────────────────────────────────────
  window.__course = {
    navigate(id) {
      renderSection(id);
    },
    checkAnswer(quizId, qIdx) {
      checkAnswer(quizId, qIdx);
    },
    submitQuestionnaire() {
      submitQuestionnaire();
    },
    activateTab(btn, tabIdx) {
      const container = btn.closest(".tabs-container");
      container.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      container.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      container.querySelector(`.tab-panel[data-tab="${tabIdx}"]`).classList.add("active");
    },
    t(key) {
      return i18n[state.lang][key] || key;
    },
    switchLang(lang) {
      switchLang(lang);
    },
  };

  // ── Event Listeners ─────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    const langBtn = document.getElementById("lang-toggle");
    langBtn.addEventListener("click", () => {
      const newLang = state.lang === "en" ? "fr" : "en";
      switchLang(newLang);
    });
  });

  // ── Moodle/Bootstrap widget behaviour (tabs, accordions, flip cards, timeline, popups) ──
  function initWidgets() {
    const wrap = document.getElementById("content-wrapper");
    wrap.querySelectorAll(".timeline-box").forEach((b) => b.classList.remove("show"));
    const first = wrap.querySelector("#timeline1");
    if (first) first.classList.add("show");
  }

  document.addEventListener("click", (e) => {
    const wrap = document.getElementById("content-wrapper");
    if (!wrap || !wrap.contains(e.target)) return;

    // show/hide text blocks ("Text description ▼", "show/hide references ▼")
    const tg = e.target.closest("[data-toggle-target]");
    if (tg) {
      const el = wrap.querySelector(tg.dataset.toggleTarget);
      if (el) el.classList.toggle("show");
      return;
    }
    // Bootstrap tabs
    const tab = e.target.closest('a[data-toggle="tab"]');
    if (tab) {
      e.preventDefault();
      const box = tab.closest(".course-tabs") || tab.closest("div");
      box.querySelectorAll(".nav-link").forEach((a) => a.classList.remove("active"));
      box.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active", "show"));
      tab.classList.add("active");
      const pane = box.querySelector(tab.getAttribute("href"));
      if (pane) pane.classList.add("active", "show");
      return;
    }
    // Bootstrap accordion / collapse
    const col = e.target.closest('[data-toggle="collapse"]');
    if (col) {
      const target = wrap.querySelector(col.dataset.target);
      if (!target) return;
      const open = !target.classList.contains("show");
      if (col.dataset.parent === undefined && target.dataset.parent) {
        wrap.querySelectorAll(`${target.dataset.parent} .collapse.show`).forEach((o) => {
          if (o !== target) {
            o.classList.remove("show");
            const h = wrap.querySelector(`[data-target="#${o.id}"]`);
            if (h) { h.classList.add("collapsed"); const b = h.querySelector("button"); if (b) b.setAttribute("aria-expanded", "false"); }
          }
        });
      }
      target.classList.toggle("show", open);
      col.classList.toggle("collapsed", !open);
      const b = col.querySelector("button");
      if (b) b.setAttribute("aria-expanded", String(open));
      return;
    }
    // timeline buttons
    const tp = e.target.closest(".timeline-point-img-wrapper");
    if (tp) {
      const all = Array.from(tp.parentElement.children);
      const idx = all.indexOf(tp);
      const wasActive = tp.classList.contains("active");
      all.forEach((w) => {
        w.classList.remove("active");
        const im = w.querySelector("img");
        if (im) im.classList.add("btn-inactive-shadow");
      });
      wrap.querySelectorAll(".timeline-box").forEach((b) => b.classList.remove("show"));
      if (!wasActive) {
        tp.classList.add("active");
        const im = tp.querySelector("img");
        if (im) im.classList.remove("btn-inactive-shadow");
        const box = wrap.querySelector(`#timeline${idx + 1}`);
        if (box) box.classList.add("show");
      }
      return;
    }
    // flip cards
    const card = e.target.closest(".term_card7, .term_card4");
    if (card) { card.classList.toggle("flipped"); return; }
    // inline definition tooltips (touch-friendly: click toggles)
    const def = e.target.closest(".inline_definition2");
    if (def) { def.classList.toggle("open"); return; }
    // inline definition popups
    const pop = e.target.closest(".popup");
    if (pop) {
      const t = pop.querySelector(".popuptext");
      if (t) t.classList.toggle("hidden");
      return;
    }
    // links to other lesson pages
    const go = e.target.closest("[data-goto]");
    if (go) {
      e.preventDefault();
      renderSection(go.dataset.goto);
      const dest = document.getElementById(`lp-${go.dataset.page}`);
      if (dest) dest.scrollIntoView({ behavior: "smooth" });
    }
  });

  // H5P-style image hotspots (lesson 4 plan form)
  document.addEventListener("click", (e) => {
    const dot = e.target.closest(".hotspot-dot");
    const close = e.target.closest(".hotspot-close");
    const open = document.querySelector(".hotspot.open");
    if (open && (close || dot || !e.target.closest(".hotspot-popup"))) {
      open.classList.remove("open");
      open.querySelector(".hotspot-popup").hidden = true;
      open.querySelector(".hotspot-dot").setAttribute("aria-expanded", "false");
      if (!dot || dot.parentElement === open) return;
    }
    if (dot) {
      const h = dot.parentElement;
      h.classList.add("open");
      h.querySelector(".hotspot-popup").hidden = false;
      dot.setAttribute("aria-expanded", "true");
    }
  });

  // mobile slide-out navigation
  document.addEventListener("click", (e) => {
    const sb = document.getElementById("sidebar");
    const btn = document.getElementById("mobile-menu-btn");
    if (!sb || !btn) return;
    if (e.target.closest("#mobile-menu-btn")) {
      const open = sb.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(open));
    } else if (sb.classList.contains("open") && (e.target.closest("#nav-list a") || !e.target.closest("#sidebar"))) {
      sb.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    }
  });

  // ── Boot ────────────────────────────────────────────────────────────
  init();
})();
