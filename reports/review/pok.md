# Data Understanding review: /home/vsydora/projects/nlp/HW1/pok/

Scope: 29 files (25 PDF, 3 PPTX, 1 DOCX). Sampled pages per file: first 2-3, 1-3 middle, last. Nothing in `pok/` was modified. Renders went to `/tmp/review_pok/`.

Legend: "moj" = cp1251 bytes decoded as Latin-1 (mojibake). "beamer" = LaTeX Beamer.

## Course-level summary

- Course: "Принципи організації комп'ютера" (ПОК), 2024 syllabus, 3rd semester, 60 h lectures/labs and 120 h self-study. The same author and layout cover АКС and ОС.
- Language: Ukrainian throughout. Russian appears in literature lists (Lek_2, Lek_4b, Lek_12) and in some English code/UI strings (PSoC, BLE).

## Files

### ПОК_силабус_2024.docx (syllabus, 4 pages after conversion)
- Type: syllabus. Language: Ukrainian.
- Content: course description, learning outcomes (ЗК/ФК/ПРН codes), 14-topic schedule table (section 8), grading (section 9), reading list (section 10).
- Logistics: Практичні 8 завдань = 40; Проект (груповий) 1 = 30; Контрольні роботи 2 = 10; Мідтерм 1 = 10; Іспит 1 = 10 (total 100). Semester 3, course year 2024, "нормативний". 60 h auditorium, 120 h self-study. Consultations "кожного четверга, 1650-1810 (лекторій)". Course hosted on LMS Moodle. Schedule rows say materials "Розміщені на LMS".
- Parser note: tables are clean. Page 1 has a title block and an approval stamp (not course content).
- Conflict with requirements PDF: see that section.

### cc_2024_2025_requirements.pdf (52 pages, Beamer, 16:9, shared ПОК/АКС/ОС)
- Type: course requirements and grading rules. Language: Ukrainian, with a few Russian-influenced idioms.
- Layout: beamer. Top nav strip on every page p2+ ("Пари Уважність Бали Практичні Проект Екзамени Плагіат Інше" plus section names on later pages). Footer "Олег Фаренюк Вимоги щодо роботи над курсами ''ПОК'', ''АКС'' і ''ОС'' та критерії оцінювання". CC BY-SA line on p1.
- Grading (p22): "Практичні/лабораторні роботи: 40 балів"; "Контрольний проект: 30 балів разом – три представлення"; "Екзамени: 2 x 15 30 балів" (pdftotext garbles the "=", read as 2x15=30); "Частина балів (до 2 x 5) може виноситися на письмові контрольні роботи".
- Deadlines (p28): work from the first half stops being accepted "за тиждень до завершення проміжного екзамену", second half "за тиждень до фінального екзамену". Example in text: exam on 17 July, works submitted up to 10 July accepted.
- Project (p44): one to three students; progress shown twice, defended at end; missing a demo costs "мінус 5 балів". Git required.
- Lab (p41): course uses equipment from lab 009/014; safety briefing and equipment sign-out required.
- Tools/other: CMS is used for materials (p5, p6). Videos via YouTube with university domain (p5 footnote). Practicals are group-based, max two (p25).
- Quirk: footnote markers glue to words ("іспит24" p21, "балів25" p22, "роботу1" p5). Some pages are pure prose (p3, p33, p50) with no tables.
- Conflict with syllabus: see cross-cutting.

### pok_l01_machine_model.pdf (112 pages, beamer, Lecture: "Структура та програмна модель комп'ютера")
- Type: lecture. Language: Ukrainian (clean Cyrillic, 58k chars; 21 Latin-1 chars only).
- Layout: beamer, nav strip "Hard Soft Віртуалізація С-машина Appendix" (p1-3, p56-112); footer "Олег Фаренюк Структура та програмна модель комп'ютера". Title left under nav.
- Quirks: p3 epigraphs in English (quoted); p56 is a diagram of a preemptive multitasking state machine (labels are text, arrows lost); p57 virtual memory text with superscript footnotes. p111 has bare URLs and bug-link lists. p112 is an end slide (footer only).
- Overlay: none detected (no consecutive near-duplicates).

### pok_l01_physics_basics.pdf (14 pages, beamer, "Основи електричних процесів: абсолютний мінімум")
- Type: lecture. Language: Ukrainian in moj encoding.
- Quirk: MOJIBAKE throughout (5716 Latin-1 chars, 0 Cyrillic). Example p1: "Îñíîâè åëåêòðè÷íèõ ïðîöåñiâ". Decode with `s.encode('latin-1').decode('cp1251')`; Latin "i" in "процесiв" survives and must be mapped to "і".
- Layout: beamer nav/footer exist but are mojibake too. p3 includes superscripts for units. p7 is a photo-like slide (text mostly intact).

### pok_l02_demoboard.pdf (15 pages, beamer, "Мікроконтролери та демоплати – огляд")
- Type: lecture. Language: Ukrainian in moj encoding (5228 Latin-1 chars, 0 Cyrillic).
- Quirk: MOJIBAKE. Verified on p1 and p2: "Ìiêðîêîíòðîëåð" decodes to "Мікроконтролер" with cp1251, but Latin "i" stays. p3 has a table of MCU specs (rows are readable after decoding). p9 contains a triplet example ("x86_64-unknown-linux-gnu", "arm-none-eabi") with a "<==" arrow.
- Layout: beamer, nav "Мікроконтролер Демоплати Інструменти" (mojibake form).

### pok_l03_bool.pdf (28 pages, beamer, "Трішки булевої алгебри")
- Type: lecture. Language: Ukrainian in moj encoding (5808 Latin-1 chars, 0 Cyrillic).
- Quirks: MOJIBAKE. Truth tables as text columns (p3 binary functions table, p14 2-variable Karnaugh-style tables with merged cells). Formulas use Unicode operators with some superscript/subscript flattening (not checked in detail). Near-duplicate consecutive pages: 15-16 and 17-18 (not clearly builds; not checked visually).

### pok_l04_simple_logic.pdf (114 pages, beamer, "Прості логічні елементи")
- Type: lecture. Language: Ukrainian in moj encoding (20485 Latin-1 chars, 0 Cyrillic), with English terms.
- Layout: beamer. Nav strip "Огляд Мікросхеми Синтез Арифметика Мікросхеми 2 Додатки" (text is moj in extraction). Footer "Олег Фаренюк Прості логічні елементи".
- Quirks: MOJIBAKE. Circuit diagrams as vector art (p40 half-subtractor: schematic with labels A, B, D, B_out; wiring not in text). Chip tables (p77 "74181 4-bit ALU" with IC numbers in a row). Overlay/build slides: 40-41 are real builds (p41 adds the "Таблиця віднімання" lines). Other near-duplicate pairs (14-15, 15-16, 16-17, 18-19, 22-23, 26-27, 42-43, 47-48, 64-65, 74-75, 88-89) mostly differ in table content and are false positives of the metric; check by title before dedupe.
- End slides p113-114: CMOS NOR circuit, mostly image, text only the label "CMOS NOR:".

### pok_l05_sequential_logic.pdf (86 pages, beamer, "Секвенційна логіка")
- Type: lecture. Language: Ukrainian in moj encoding (18796 Latin-1 chars, 0 Cyrillic).
- Layout: beamer, nav "Тригери Лічильники Регістри Пам'ять RAM Інше" (moj), footer "Олег Фаренюк Секвенційна логіка".
- Quirks: MOJIBAKE. p3 RS latch with NOR gates: schematic + truth table (S, R, Q, Q-bar) reads fine after decode. Overlay pairs 26-27 and 68-69 (not checked visually). p45: 74193 synchronous counter diagram (text labels only).

### pok_lab01-03_strings.pdf (99 pages, hyperref report, A4)
- Type: lab/practice (labs 1-3: manual memory management for strings in C++). Language: Ukrainian + C++ code in English.
- Layout: plain article/report (LaTeX + hyperref, A4, title p1 "Ручне керування пам'яттю на прикладі стрічок", date "8 вересня 2024 р.", author line). No header bar. Page numbers in footer. TOC p2-3 with dot leaders ("1 Необхідні знання із С++ 4").
- Quirks: clean Cyrillic (69k chars). Code listings in monospace; p98-99 C header listing with embedded line numbers ("230 //! -1 або..."), which will pollute chunks. p50 CMake listing with generator expressions (`$<$<CXX_COMPILER_ID:MSVC>:/W4 /WX>`). Hyphenation at line ends ("стрі-\nчками"). Bulleted lists with "⋄" and "◇" glyphs.

### os_p01_bash.pdf (23 pages, beamer, "Bash") [pok/ copy]
- Type: lecture/practice (OS course). Language: Ukrainian in moj encoding (4812 Latin-1 chars, 0 Cyrillic).
- Quirk: MOJIBAKE in pok/ copy only. Same page count as `../os/os_p01_bash.pdf` (23) but different bytes; `../os` copy is clean Cyrillic (see cross-cutting). Code: p12 shell session (`[indrekis@west bash]$`), contains user-specific host name (not a parser issue, flag only).
- Overlay: none detected.

### os_pok_syscalls.pdf (38 pages, beamer, "Системні виклики") [pok/ copy]
- Type: lecture (OS course topic in ПОК folder). Language: Ukrainian, clean Cyrillic (11435 chars).
- Layout: beamer, nav "Огляд Реалізація Інше", footer "Олег Фаренюк Системні виклики".
- Quirks: p19 is a long C macro (`internal_syscall3`) with backslash continuations and ~80-char lines; extraction keeps them but ragged. p2 has footnote superscripts glued to words ("коду1").
- Compared with `../os/os_pok_syscalls.pdf` (39 pages, created Nov 2025): newer, same content with typo fixes ("sudoers", "При цьому") and small rewrites. The pok/ copy is the older version (Oct 2023).

### pok_aks_os_l00_intro.pdf (18 pages, beamer, "Базові поняття. Мотивація")
- Type: lecture (intro shared across ПОК, АКС, ОС). Language: Ukrainian, mixed encodings: 7373 Latin-1 (moj) chars vs 661 Cyrillic.
- Layout: beamer, nav "Базові поняття Мотивація ПОК АКС ОС Підсумок", footer "Олег Фаренюк ...". CC BY-SA on p1.
- Quirk: MOJIBAKE on most pages (e.g., p2 "Áàçîâi ïîíÿòòÿ"), but some lines decoded correctly. Parser needs per-page detection.
- Compared with `../aks/pok_aks_os_l00_intro.pdf` (17 pages, created 2021, clean Cyrillic, different md5). The pok/ copy is the 18-page newer version and is mojibake.

### Lek_2_2018.pdf (72 pages, PowerPoint 2013 export, 4:3, "Лекція 2. Класифікація комп'ютерів та принципи організації машини фон Неймана")
- Type: lecture. Language: Ukrainian slides; literature list in Russian (Tanenbaum, "Архитектура компьютера", 2013).
- Layout: PPT, centered red titles (e.g., "Закон Мура (1)" p56, centered), slide number bottom right as a bare integer line.
- Quirks: clean Cyrillic. Image-only slides: p56 (Moore's law chart + photo, text only the title), p72 (number only). Outline page p2 starts "Питання" with numbered list. Historical photos/images not text.

### Lek_3_2018.pdf (51 pages, PowerPoint 2013, "Лекція 3. Представлення даних на машинному рівні")
- Type: lecture. Language: Ukrainian. Clean Cyrillic.
- Quirks: bare slide-number lines (p6 "6", p51 "51"); p6 is near-empty (number only). Titles include counters like "Позиційна система числення (7)" (p25). Number-only page for p6 and p51.

### Lek_4b_2018.pdf (81 pages, PowerPoint 2013, "Лекція 4. Представлення даних на машинному рівні (Ч.2)")
- Type: lecture. Language: Ukrainian slides; literature in Russian (Tanenbaum; Warren "Hacker's Delight", translated, Moscow 2007).
- Quirks: clean Cyrillic. Number-only pages: p81 ("81"); p80 "Алгебра логіки (3)" title-only page with image-only body (not checked). Pages with "(1)/(2)/(3)" counters.

### Lek_6_7_2018.pdf (125 pages, PowerPoint 2013, "Лекція 6_7. Цифрова логіка і цифрові системи")
- Type: lecture. Language: Ukrainian slides. Literature list in Russian (Tokheim; Wilkinson).
- Quirks: IMPORTANT. Most tables and some body text on pages 118-125 are rasterized images (p118 "Суматори": pdftotext returns only the title; pdfimages shows 3 raster images for the truth tables). 14 pages are low-text: 25, 26, 39, 40, 55, 56, 118-125. p125 is number-only.
- Counter pages "функцій (1)" and "(2)" on p12-13 are parallel slides, not overlays. Near-duplicate metric flagged 11 pairs (12-13, 13-14, 16-17, 17-18, 19-20 ...); they are mostly counter continuations.

### Lek_12_2018.pdf (42 pages, PowerPoint 2013, "Лекція 12. Архітектура і організація систем пам'яті")
- Type: lecture. Language: Ukrainian slides; literature mixes Russian (Tanenbaum) and Ukrainian (Karachka & Dudko, 2009).
- Quirks: clean Cyrillic. Number-only pages (p30, p42). p29 "Приклад_3" is image-only (no text beyond title). Outline p2 is a long comma-separated list ("Системи пам'яті та їх технологічні основи; кодування, ущільнення...").

### lapp_qc.pdf (24 pages, beamer, "Нано-огляд квантових комп'ютерів")
- Type: lecture (quantum computing overview). Language: Ukrainian.
- Quirk: Latin "i" substitutes for Ukrainian "і" throughout ("Класична фiзична" p2, "Рiвняння руху" p3). Detected 465 Latin-i-inside-Cyrillic-word hits. Search will miss "фізична" etc. unless normalised.
- Formulas: p3 physics equations in Unicode and Office-math (F~ = m~a, X̂ψ = xψ on p12). Vector symbols lose arrows/hats in text.
- Overlay: none detected. p24 end slide (footer only).
- Course check: quantum-computing topic is not in the ПОК syllabus schedule; likely another course's material.

### lXX_arm_cortex_m_review.pdf (28 pages, beamer, "ARM Cortex M3/M4")
- Type: lecture/review. Language: Ukrainian (clean). Title block p1 "Огляд архітектури ARM Cortex M3/M4".
- Layout: beamer, nav "Огляд Регістри Переривання Пам'ять Програмування", footer "Олег Фаренюк Огляд архітектури ARM Cortex M3/M4".
- Quirks: "Регiстри" Latin i again (minor). p2 refers to STM32F303 "з яким ми працюємо". Register and interrupt tables appear as text in some pages; diagrams not checked. p28 is end slide.
- Course check: ARM Cortex-M is in ПОК syllabus (topic 6 "Архітектура та система команд ARM Cortex M") but file name uses "lXX" (placeholder numbering).

### x86_arch.pdf (186 pages, beamer, "Архітектура системи команд (ISA) x86")
- Type: lecture. Language: Ukrainian; code/ASM in English. Clean Cyrillic (71k chars).
- Layout: beamer, nav "ISA x86 x86-system ABI Лінкування/ELF Інструменти User space Виклики функцій Intrinsic Inline asm Діалекти", footer "Олег Фаренюк Архітектура системи команд x86".
- Quirks: assembler listings and register tables; p90 numbered steps ("1 Що слід зробити – Op code"). Only near-duplicate pair 173-174 (not checked visually). Long nav header repeated on every slide.
- Course check: matches ПОК syllabus topic "Архітектура та система команд x86".

### proc_switching.pdf (1 page, Inkscape vector, 1543x618 pt)
- Type: single figure (scheduler/ISR/dispatcher state diagram). Language: English labels.
- Quirk: text is extracted as diagram labels, no reading order (labels "Scheduler", "ISR xx", "Dispatcher" scattered). Byte-identical to `../os/proc_switching.pdf` (same md5).
- Course: OS topic; fits ОС, not ПОК.

### cpp1_app_autotools.pdf (10 pages, beamer, "C++ — Додаток. Autotools")
- Type: lecture/appendix. Language: Ukrainian, clean Cyrillic (1770 chars). Course: C++ (not ПОК).
- Layout: beamer. Title p1 has a personal social-media link (do not reuse). p6 "Workflow" and p10 near-empty (mostly image).
- Relevance: build tooling appendix; plausible support for ПОК "Роздільна компіляція, системи автоматичної побудови" topic.

### cpp1_app_cmake.pdf (91 pages, beamer, "C++ — Додаток. CMake")
- Type: lecture/appendix. Language: Ukrainian (30k Cyrillic chars). Course: C++ app series.
- Layout: beamer; nav "Hello, CMake Подробиці Пошук конкретних бібліотек VCPKG Посилання"; footer "Олег Фаренюк C++ — Додаток. CMake".
- Quirks: CMake code blocks (`set_target_properties(... SKIP_BUILD_RPATH)`, generator expressions) and bullet glyphs "⋄". Large deck; p91 end slide.

### cpp1_app_libraries.pdf (37 pages, beamer, "C++ — додаток. Бібліотеки")
- Type: lecture/appendix. Language: Ukrainian (11k Cyrillic chars). Course: C++ app series.
- Quirks: symbol/name-mangling examples; code blocks; nav "Статичнi бiблiотеки Динамiчнi бiблiотеки Name mangling" with Latin "i" mixed in ("бiблiотеки").

### cpp1_app_makefile.pdf (33 pages, beamer, "C++ — Додаток. Make і Makefile")
- Type: lecture/appendix. Language: Ukrainian (7k Cyrillic chars). Course: C++ app series.
- Quirks: Makefile examples (tab-indented recipes; not checked whether extraction keeps the tabs); "Програма з багатьох файлiв" nav with Latin i.

### cpp1_app_binutils_n_gcc.pdf (47 pages, beamer, "C++ — Додаток. Binutils та GCC, GDB, FASM")
- Type: lecture/appendix. Language: Ukrainian in moj encoding (10130 Latin-1 chars, 0 Cyrillic). Course: C++ app series.
- Quirk: MOJIBAKE in title and nav: p1 "C++  äîäàòîê. Binutils òà GCC, GDB, FASM". Decode as above. Tool names (nm, ldd, size, objdump, readelf, Bloaty, GDB) are plain Latin.

### PSoC.pptx -> PSoC.pdf (29 slides, 16:9 dark template, "Використання PSoC 4 та PSoC Creator")
- Type: lecture/tutorial (on a PSoC 4 BLE MCU and PSoC Creator IDE). Language: Ukrainian headings with English technical bullets (e.g., p20). Author on title: Озгович Андрій.
- Layout: PowerPoint template, dark background, orange accent bar top right (p13). Title top-left. No footer.
- Quirks: CLEAN text. Image-only slides: p13 (collage of consumer devices, no text), p14-15, p21, p28 (images with near-no text). p29 "References and Links" lists Cypress/Infineon URLs (www.cypress.com/PSoC4BLE and similar).
- Course: MCU/SoC topic ("Робота із мікроконтролерами та SoC" in syllabus).

### BLE.pptx -> BLE.pdf (40 slides, same template, "Cypress PSoC 4 BLE")
- Type: lecture/tutorial (Bluetooth Low Energy on PSoC 4 BLE). Language: Ukrainian bullets with English BLE terms and UI paths ("BLE Customizer -> GAP Settings Tab").
- Quirks: CLEAN text. Typos in source: "Bluetoth" (p2 area), "Sequrity" (p30). Low-text slides p24 (one image) and p38. p40 "Final Thoughts" is the last slide. Overlay/builds not checked.
- Course: fits the ПОК "Робота із мікроконтролерами та SoC" / wireless I/O topics, but the content is an external-tool tutorial rather than ПОК core theory.

### PSoC_Sensors_2023.pptx -> PSoC_Sensors_2023.pdf (36 slides, same template, "Робота з сенсорами в середовищі PSOC Creator 4")
- Type: lecture/tutorial (sensors with PSoC Creator). Language: Ukrainian with English terms. Author on title slide: Тарас Домінюк (contact details present in source; not copied here).
- Quirks: text is clean, but mixed scripts occur (e.g., "Вступ. Cенсори." on the slide where the first "С" appears Latin). p36 is an empty (blank) dark slide. p29 is low-text (image). Bullets with `ADC_SAR_Seq_Start();` code snippets (p24) in plain text.
- Course: matches ПОК syllabus "Робота із зовнішніми сенсорами".

## Cross-cutting findings for the parser

1. Mojibake family (cp1251 bytes read as Latin-1): pok_l01_physics_basics (all pages), pok_l02_demoboard (all pages), pok_l03_bool (all), pok_l04_simple_logic (all, p1-114), pok_l05_sequential_logic (all, p1-86), os_p01_bash (pok/ copy, p1-23), cpp1_app_binutils_n_gcc (p1-47), pok_aks_os_l00_intro (most pages; 7373 vs 661 chars). Fix: `s.encode('latin-1').decode('cp1251')` per text run; verified on demoboard p1-2 (sampled). Latin "i" still appears where "і" was, so map `i`->`і` in Cyrillic context after decoding. Detect per page (e.g., count of U+00C0-U+00FF vs U+0400-U+04FF).
2. Latin "i" homoglyph inside Ukrainian words (not mojibake): lapp_qc (465 hits; p2 "Класична фiзична", p3 "Рiвняння"), lXX_arm_cortex_m_review (p1 nav "Регiстри"), cpp1_app_libraries (p1 "бiблiотеки"), cpp1_app_binutils_n_gcc title line. Normalize before indexing.
3. Repeated running header/footer on every beamer page: nav strip (e.g., pok_l01 p2 "Hard Soft Віртуалізація С-машина Appendix"; pok_l04 p3 "Огляд Мікросхеми Синтез Арифметика Мікросхеми 2 Додатки"; x86_arch p2 "ISA x86 x86-system ABI Лінкування/ELF Інструменти User space Виклики функцій"; requirements p2+ "Пари Уважність Бали Практичні Проект Екзамени Плагіат Інше") and footer "Олег Фаренюк <deck title>" (e.g., pok_l05 p3 footer "Секвенційна логіка", requirements p3 "Олег Фаренюк Вимоги щодо роботи над курсами ''ПОК'', ''АКС'' і ''ОС'' та критерії оцінювання"). Strip by line-frequency across pages. Title is the line directly below the nav strip.
4. Bare slide numbers as text lines: PowerPoint PDFs end pages with the number alone (Lek_2 p72, Lek_3 p6/p51, Lek_4b p81, Lek_6_7 p125, Lek_12 p30/p42). Strip lines that are only digits. Also beamer footer page numbers.
5. Image-only or raster-table pages (text missing): Lek_6_7 p118 (adder truth tables as raster, pdfimages shows 3 images), Lek_6_7 p119-125 (mostly tables/figures; 14 low-text pages total incl. 25, 26, 39, 40, 55, 56), Lek_2 p56 (Moore's law chart + photo), Lek_12 p29 ("Приклад_3"), PSoC p13 (device collage), PSoC p14-15, p21, p28, PSoC_Sensors p29, BLE p24, p38, PSoC_Sensors p36 (blank), pok_l04 p113-114 (CMOS NOR). Needs OCR or vision fallback, or flagged as "no text".
6. Overlay/incremental builds: pok_l04 p40-41 (same title; p41 adds "Таблиця відніманя" and the adder table; real build). Likely builds, not visually verified: pok_l03 p15-16, p17-18; pok_l05 p26-27, p68-69; x86_arch p173-174. Lek_6_7 p12-13 are numbered "функцій (1)/(2)" continuations, not overlays. Near-duplicate metric is noisy (pok_l04 p14-15 are different chip tables), so dedupe on title + text similarity, not similarity alone.
7. Vector circuit diagrams with text-only labels: pok_l04 p40 (half-subtractor), pok_l04 p3 (gate symbols), pok_l05 p3 (RS latch with truth table, table reads fine), pok_l05 p45 (74193 counter), proc_switching.pdf p1 (scheduler diagram; labels in random order). Wiring is lost, so chunk these with their caption text.
8. Code and listings: pok_lab01-03_strings p98-99 (C header with embedded line numbers "230 //! ..."), p50 (CMake); x86_arch (assembly); os_pok_syscalls p19 (long C macro with backslash continuations); cpp1_app_cmake / makefile (CMake, Makefile with tabs). Keep monospace blocks intact and strip leading numbers in the listing.
9. Footnote markers glued to words: requirements p5 "роботу1", p21 "іспит24", p22 "балів25", p40 "балів54", and os_pok_syscalls p2 "коду1". Strip trailing digits from words when they match a footnote number.
10. Duplicates and version conflicts with sibling folders: `os_p01_bash.pdf` (pok/ copy is moj, 23 pages, Sep 2023; `../os` copy is clean, 23 pages, Aug 2020, different md5); `os_pok_syscalls.pdf` (pok/ 38 pages, Oct 2023; `../os` 39 pages, Nov 2025, newer with typo fixes; index the newer one); `pok_aks_os_l00_intro.pdf` (pok/ 18 pages, moj; `../aks` 17 pages, 2021, clean, different md5); `cc_2024_2025_requirements.pdf` and `proc_switching.pdf` are byte-identical to `../os/`. Dedupe by md5 and prefer the clean copy.
11. Logistics conflicts between the syllabus and the requirements document: syllabus grades 40 practicals, 30 project, 10 control works, 10 midterm, 10 exam (= 100); requirements say 40 practicals, 30 project, "Екзамени: 2 x 15 = 30" with up to 2x5 of that from written control tests. Syllabus says materials are on LMS (Moodle); requirements say CMS. Syllabus exam is "усної співбесіди" (oral); requirements allow written colloquium and/or oral. Treat the requirements document as the more detailed authority, and flag the conflict rather than merging numbers.
12. Language mixing: English code and UI strings inside Ukrainian slides (PSoC, BLE, x86, cpp1); Russian literature references in Lek_2, Lek_4b, Lek_12, Lek_6_7. A language detector per chunk will mislabel these as Russian or English.

Not checked: full page reads (sampling only, as specified); whether the PPTX files carry speaker notes; whether the syllabus DOCX has embedded images; visual confirmation of every overlay pair listed above; exact hyperlink targets in the Beamer PDFs (no link annotations inspected).
