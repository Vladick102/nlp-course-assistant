# Data Understanding review: /home/vsydora/projects/nlp/HW1/aks/

Scope: 22 files in `aks/` (Computer Systems Architecture, АКС). Nothing in `aks/` was modified. Renders went to `/tmp/review_aks/`.
Method: pdftotext per page on first 3, middle and last pages, a word-count pass over all pages, a near-duplicate scan (Jaccard on word sets of consecutive pages), and soffice conversion of the two .pptx files. Visual checks were limited to a few rendered pages. Anything not sampled is marked "not checked".

Shared author line on all lecture/lab PDFs: Олег Фаренюк (CC BY-SA). Course Beamer decks use a top section-navigation bar, a frame title below it, and a footer "Олег Фаренюк <lecture title>".

---

## Requirements, syllabus and logistics

### cc_2020_2021_requirements_3ed.pdf
- Type: course requirements/logistics, shared by ПОК, АКС and ОС. 52 pp. Ukrainian.
- Layout: Beamer (pdfTeX). Title "Вимоги щодо роботи над курсами ПОК, АКС і ОС та критерії оцінювання". Top nav bar "Пари Уважність Бали Практичні Проект Екзамени Плагіат Інше" (sub-section names change per page), footer "Олег Фаренюк Вимоги щодо роботи...". Title sits under the bar.
- Quirks: nav bar and footer repeat on every page. Footnotes run up to #56 and are inline superscripts. Tables on p2 (hours). Latin "i" replaces Ukrainian "і" in many words (e.g. "Практичнi", "Iнше", "Уважнiсть"). Not checked: whether all pages do this.
- Logistics: hours table (p2) "Лекції 30 / Практичні/лабораторні 15 / Всього аудиторних 45 / Самостійна робота 105 / Загальний обсяг 150" (per course). Grading (p22–23): "Практичні/лабораторні роботи: 40 балів", "Контрольний проект: 30 балів", "Екзамени: 2 x 15 = 30 балів". Extra credit goes on top of the 100 "базових". Late work (p28, fn 38): submitted a month late gets 0; not submitted gets "мінус шість балів". Deadline minimum on p5: "Мінімум 3 дні". Exams can be practical + oral theory.
- Outdated? Yes, relative to the 2025 syllabus: 2025 syllabus gives 60 aud h + 120 SR and a 40/15/15/30 split (midterm + exam). This deck says 45/105/150 and two exams 2x15. Reference OS here is "Ubuntu 2018 чи 2020" (syllabus: Ubuntu 22.04/24.04). A newer 2024-2025 version lives in `os/cc_2024_2025_requirements.pdf` (outside scope): "Контрольний проект: 30 балів разом – три представлення", and code is submitted via GitHub. This file says GitHub is "на деяких курсах – мусить" (optional).

### Силабус_ _Архітектура комп'ютерних систем_, 2025.pdf
- Type: syllabus. 5 pp. Ukrainian. Google Docs export (Skia/PDF), not Beamer.
- Layout: plain document, numbered sections 1–13, tables for grading (section 12) and lecture schedule (section 11, p4). Heading "АРХІТЕКТУРА КОМП'ЮТЕРНИХ СИСТЕМ Силабус курсу 2025".
- Quirks: zero-width spaces in numbered list items ("1.​ Загальна") and Ukrainian apostrophe variants (’ and '). Tables extract fine with -layout. Contact details present; not repeated here.
- Logistics: "60 год – аудиторних (30 – лекції, 30 - практичні), 120 год – самостійна робота." Prerequisites: "Принципи організації комп'ютера, дискретна математика, основи програмування." Grading (p5): "Практичні завдання 8 → 40", "Мідтерм 1 → 15", "Іспит 1 → 15", "Проект 1 → 30" (total 100). Tech: "CPU: Dual core 2.5 GHz; RAM: 8 GB; GPU: 128 MB; Free disk space: 40 GB; OS: Windows 10/11, Ubuntu 22.04/24.04 LTS". No deadlines in the document. Course order is the 13-row schedule in section 11 (p4): Проблема продуктивності → Класифікація паралелізму → Архітектура та мікроархітектура → Підсистема пам'яті → Тривіальні приклади → Мультипроцесори → Крупнозернисті задачі → Мультикомп'ютери → Методологія → Синхронізація → API в C++/Python/Java → MPI → CUDA/oneAPI/OpenCL.
- Inconsistency: header says "Ознаки курсу: 2024-2025 весняний", title and cover say 2025; approval date line is blank ("______2025р. №____").

---

## Lectures (Beamer, LuaTeX unless noted)

### cc_l00_intro.pdf
- Type: lecture, 53 pp, Ukrainian. Title "Мрії та реальність. Види паралелізму".
- Layout: Beamer. Nav bar "Огляд Паралелізм Класифікація Інше"; frame title under the bar on the left; footer with author and title; nav icons bottom right.
- Quirks: the nav bar text is the first line of nearly every page. Footnote digits are glued to words ("чим-живучіший1") and footnote text sits at the page bottom. Vector system diagram on p3 (CPU/RAM/bus labels come out scattered). Flynn table on p26 as text. Pages 48–50 are near-duplicate (Jaccard 1.00, "Історія" sub-pages). p53 has only nav + footer.

### cc_l10_cpu_isa.pdf
- Type: lecture, 33 pp, Ukrainian. Title "Система команд CPU – instruction set architecture, ISA".
- Layout: Beamer. Nav bar "Огляд Приклади коду Історія ISA Акумуляторна Стекова Регістрова VLIW Інші", title under bar. Footer title is "Система команд CPU – instruction set architecture, ISA" on p2 but "… – instruction architecture, ISA" on p3 (word "set" dropped).
- Quirks: nested ◇/◇◇ bullets (p16). Code examples exist, not checked. p33 is nav + footer only.

### cc_l10_cpu_uarch.pdf
- Type: lecture, 144 pp, Ukrainian. Title "Мікроархітектура CPU".
- Layout: Beamer, long nav bar "Огляд Мікрокод Конвеєр Superscalar Out-of-order Branch prediction Приклади Література Історія". The nav text mixes into titles on p72 ("Динамічне Історія передбачення Інше Приклади").
- Quirks: 124 embedded image objects (pdfimages). Near-duplicate/incremental pages 100–108 (Jaccard 0.88–0.92); p100 vs p101 differ only in "80386" vs "80486". p137→138 identical. p144 nav only. Footnotes numbered inline (p2–3). Pipeline and branch-predictor diagrams not checked.

### cc_l13_ram.pdf
- Type: lecture, 145 pp, Ukrainian. Title "Первинна пам'ять: RAM, SRAM/DRAM".
- Layout: Beamer, nav bar "Огляд RAM "API" RAM DRAM Інше Посилання" with sub-items; footer.
- Quirks: p3 (memory-technology table: Technology / Addressing / Variant, Modern/Historical) comes out as column-interleaved text. p2 is a mostly image slide ("Взято тут: slideplayer", visual not checked). p10 is a bus/MMU diagram (labels only). p72 has footnote-style "50" and "На цей час." p10→p11 near-duplicate (0.86). p145 nav only.

### cc_l17_cache.pdf
- Type: lecture, 129 pp, Ukrainian. Title "Кеш пам'яті".
- Layout: Beamer, nav bar "Кеш Баги Інше Огляд Механізми Prefetching "API" Приклади".
- Quirks: p2 and p3 are charts (memory wall, HW FLOPS/bandwidth scaling with GPU/TPU names as scattered labels). p64 contains an x86 cache-instruction list (plain text). Near-duplicates 82→83→84 (0.88). p129 nav only.

### cc_l25_simd.pdf
- Type: lecture, 13 pp, Ukrainian. Title "SIMD".
- Layout: Beamer (pdfTeX), nav bar just "Огляд SIMD".
- Quirks: heavy Latin "i" for Ukrainian "і" ("регiстри", "iнтерпретували", "цьому курсi", "бiльше"). Search for "регістр" will miss. p12 and p13 are blank frames (p13 render: a tiny dot only); p12→p13 identical (1.00).

### cc_l30_multicomp.pdf
- Type: lecture, 60 pp, Ukrainian. Title "Мультикомп'ютери".
- Layout: Beamer, nav bar "Мульткомп'ютер Розподілені системи Реалізація Кластери TOP500 MPP GRID Інше TOP500-2" (note "Мульткомп'ютер" spelling in nav vs "Мультикомп'ютери" title).
- Quirks: p3 diagram with credit "Ілюстрація з A. Tanenbaum, H. Bos" (labels not extracted). p30 is a photo (chip) with caption only. Near-duplicates 30→31 (0.89), 46→47 (0.88). p60 nav only.

### cc_l40_par_prog.pdf
- Type: lecture, 53 pp, Ukrainian. Title "Ефективність та підходи до розпаралелення".
- Layout: Beamer, nav bar "Ефективність Roofline Класичні задачі Підходи Паттерни" (sic, "Паттерни").
- Quirks: formulas on p3 break into fragments ("Latency(B) LB / S= ="; "Throughput(A) TA"). PCAM list on p26 is text. p53 has a quote plus nav/footer.

### cc_l50_sync.pdf
- Type: lecture, 69 pp, Ukrainian (with C++ code). Title "Засоби синхронізації".
- Layout: Beamer, nav bar "Races Засоби синхронізації ОС" and a second row of sub-items ("Race condition Синхронізація Атомарність", later "Spinlock Семафори М'ютекси Інше").
- Quirks: C++ listings (p34 spinlock class) with "std :: atomic" spacing and "..." elisions. Footnote digit glued to code ("C++9 :"). p3 is an image slide (source credited to a blog). p68→p69 identical (1.00); p69 nav only.

### cc_l60_MPI.pdf
- Type: lecture, 78 pp, Ukrainian (with C/C++ code). Title "MPI".
- Layout: Beamer, nav bar "Огляд Використання Advanced Boost::MPI Література" plus sub-items ("Динамічний обмін User types Комунікатори …" on p39).
- Quirks: code listings (p39: "uint8_t packbuf[100]", MPI_PACKED). No near-duplicates found. p78 nav only.

### cc_l70_cuda.pdf
- Type: lecture, 82 pp, Ukrainian (with CUDA code). Title "CUDA".
- Layout: Beamer, nav bar "Огляд CUDA Альтернативи Prg. model Детальніше Advanced Бібліотеки Підсумок".
- Quirks: line-end hyphenation in body text ("здій-" / "снюватися" on p2), so dehyphenate. URLs in text (docs.nvidia.com on p41). No near-duplicates found. p82 nav only.

---

## Labs (LaTeX hyperref article class, not Beamer)

Layout for all three: A4 portrait article. Title page with author and date, a CC BY-SA line on page 1, and a numbered table of contents with dot leaders on p2. Running header with section name and page number on each page. Document Title metadata is empty.

### cc_lab01_cpp_perf.pdf
- Type: lab/practice, 25 pp, Ukrainian. "Порівняння продуктивності різних засобів С++", dated 5 лютого 2025.
- Quirks: TOC on p2 (dot leaders, pollutes chunks). Rule legend on p3 ("• – порушення …") loses its symbol glyphs, so the line starts with bare text. Running headers "0.1. ЦІЛЬ РОБОТИ 3" (p3) and "12 ЗМІСТ" (p12). Python and C++ listings, Рис. 1 captions. Symbols and figures not checked.

### cc_lab10_cpp_parsing.pdf
- Type: lab/practice, 17 pp, Ukrainian. "Аналіз тексту – підсумовування інформації з великого файлу" (chapter "Задачі аналізу метеорологічної інформації"), dated 17 березня 2025.
- Quirks: TOC on p2. Running headers "8 РОЗДІЛ 1. ..." (p8). Legend symbols missing again (p4). Footnote #6 on p8. Spec sections include config file format and output rules. Quoted tables and sample data not checked.

### cc_lab30_MPI_PDF.pdf
- Type: lab/practice, 21 pp, Ukrainian. "Розв'язання двомірної задачі теплопровідності" (chapter "Моделювання теплопровідності з MPI"), dated 3 травня 2024.
- Quirks: TOC on p2. Figure 1.5 on p10 (matrix vs memory layout) is text labels in layout mode, and code is inline ("send( &m4x4[8], 4)"). p21 submission section has unfilled template placeholders: "[КОМАНДА]", "[посилання на репозиторій]", "[список]". Remove or flag these as non-content.

---

## Slides from other authors (.pptx, converted with soffice)

### cpp_CourseProjectPresentation.pptx
- Type: student presentation (course project), 19 slides, English. "Concurrent queue in C++", one student author on the title slide.
- Layout: default PowerPoint-style template, title at top-left.
- Quirks: slides 3, 5 and 7 are image or diagram only (0–8 words). p10 is pseudo-code with line wrapping ("Enqueu / e"), and side text runs into code. p19 closes with a GitHub link. Few words per slide overall.
- Index: not a lecture. Exclude from the course-material index, or tag as student work.

### FPGA_PRESENT_1.pptx
- Type: student/guest presentation, 28 slides, Ukrainian. "Вступ до мов опису апаратури" (HDL intro), with a named presenter and a CC BY-SA line on the title slide.
- Layout: PowerPoint default template. Slides 1–27 have text, with vendor logos as images (e.g. p27 "Intel PAC / Xilinx ALVEO" as text labels). p28 is blank (0 words).
- Index: topic is FPGA/HDL (relevant to the syllabus's FPGA practicals, not AKS core). Not a lecture; tag as student/guest material. Blank last slide.

---

## Duplicates and version issues

- `aks/pok_aks_os_l00_intro.pdf` (17 pp, text extracts cleanly) vs `pok/pok_aks_os_l00_intro.pdf` (18 pp, different md5). The pok copy's text is mojibake (e.g. "Ìîòèâàöiÿ" for "Мотивація"), so its font encoding has no usable ToUnicode map. Diff of content not checked. Use the aks copy as the clean one.
- `aks/cc_2020_2021_requirements_3ed.pdf` (52 pp) vs `os/cc_2024_2025_requirements.pdf` (same title, newer content on project and GitHub; page count and full diff not checked). A `pok/cc_2024_2025_requirements.pdf` also exists; md5 not checked. Treat the 2020/2021 file as superseded.
- `cc_l00_intro.pdf` ("Мрії та реальність", lecture) and `pok_aks_os_l00_intro.pdf` ("Мотивація циклу курсів") are different content despite the "l00" names.
- The syllabus lists 2024-2025 in its metadata and "2025" in its title, so check which year it covers.

---

## Cross-cutting findings for the parser

1. Repeated nav bar on every Beamer page. The first text line is a list of section names, e.g. "Огляд Паралелізм Класифікація Інше" (cc_l00_intro, all pages) and "Огляд Приклади коду Історія ISA Акумуляторна Стекова Регістрова VLIW Інші" (cc_l10_cpu_isa p2). Strip it before chunking.
2. Repeated footer on every Beamer page: "Олег Фаренюк <title>", and CC BY-SA line on title pages (p1). Footer titles drift (cc_l10_cpu_isa p3 drops "set"). Strip by pattern, not exact match.
3. Blank/nav-only final pages: cc_l00 p53, cc_l10_cpu_uarch p144, cc_l13 p145, cc_l17 p129, cc_l25 p12–13, cc_l50 p69, cc_l60 p78, cc_l70 p82, cc_l30 p60, pok p17. Drop pages that are empty after boilerplate removal.
4. Near-duplicate overlays: cc_l00 p48–50 (Jaccard 1.00), cc_l50 p68→69 (1.00), cc_l25 p12→13 (1.00), cc_l10_cpu_uarch p137→138 (1.00) and p100–108 (0.88–0.92, with real edits such as "80386"/"80486"), cc_l17 p82–84 (0.88), cc_l30 p30–31 and 46–47, cc_l13 p10→11 (0.86). Dedupe with a threshold, keeping one copy per run, and do not treat the 0.88–0.92 ones as identical without a check.
5. Mixed Latin "i" for Ukrainian "і": cc_l25_simd ("регiстри", "iнтерпретували"), pok_aks_os_l00_intro (aks copy: "Архiтектура", "паралелiзму"), cc_2020_2021_requirements ("Практичнi", "Iнше"). Normalize Latin i to Cyrillic і before indexing, or search fails on common words.
6. Mojibake in the pok copy of pok_aks_os_l00_intro.pdf (e.g. "Ìîòèâàöiÿ"). Do not index that copy as text; use the aks copy or OCR.
7. Glyph loss in lab PDFs: rule-legend symbols (•, icons) disappear in cc_lab01 p3 and cc_lab10 p4, so the line starts with bare "– порушення". Treat those lines as list items with unknown severity.
8. Figures and diagrams with text as scattered labels (no image OCR): cc_l00 p3, cc_l13 p3 and p10, cc_l17 p2–3 (charts), cc_l30 p3, cc_lab30 p10, pptx cpp p3/5/7. Image-only pages: cc_l30 p30, cc_l13 p2, cc_l10_cpu_uarch (124 images, not all checked), pok p2 (photos). Mark them as figure stubs, not text.
9. Code and formulas: C++ in cc_l50 p34, C in cc_l60 p39, inline C in cc_lab30 p10, pseudo-code in pptx cpp p10. Formulas in cc_l40 p3 break into fragments ("Latency(B) LB" / "S= ="). Keep code blocks intact and keep formulas as their own chunks.
10. Hyphenation, footnotes and TOC noise: soft hyphens across lines in cc_l70 p2 ("здій-/снюватися"); footnote digits glued to words (cc_l00 p2 "живучіший1", cc_l50 p34 "C++9"); TOC pages with dot leaders in all labs (p2); and template placeholders "[КОМАНДА]" in cc_lab30 p21. Strip or flag.
