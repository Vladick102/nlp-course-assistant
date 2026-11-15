# Data Understanding review: `os/` folder (Operating Systems course)

Scope: `/home/vsydora/projects/nlp/HW1/os/` (29 files: 26 PDFs, 5 PPTX-origin decks as .pptx). Nothing in the folder was modified. Renders and PPTX→PDF conversions are in `/tmp/review_os/`. Sampling: first ~3 pages, 2-3 middle pages, last page per file, plus full-text scans for repeated lines, near-empty pages, and overlay duplicates. Items marked "not checked" were not inspected page by page.

Abbreviations: **B** = Beamer (LaTeX), **PP** = PowerPoint-origin PDF.

## Course-level and logistics files

### `ДВВ_Операційні системи_2025.pdf` (3 pp, Google Docs export, Ukrainian)
- Type: syllabus (Силабус курсу 2025), UCU, Faculty of Applied Sciences.
- Layout: plain document, 2-column label/value blocks, numbered list 1-12, one schedule table, one grading table. Title line "ОПЕРАЦІЙНІ СИСТЕМИ / Силабус курсу 2025".
- Quirks: literal artifact `... (repeated 2 times)` inside the schedule table (between "Огляд операційних систем" and "Інструменти командного рядка" rows); the schedule column "Завдання" reads "Розміщені на LMS" on every row. Contact block (phone, email) present; do not copy into outputs.
- Logistics facts (quote exact):
  - Обсяг: "60 год. аудиторних, 120 год. самостійна робота".
  - Ознаки: "2025 | 5,7 | 122 Комп’ютерні науки | 3 | вибірковий".
  - Grading table: "Практичні завдання | 9 завдань | 40"; "Проект (груповий) | 1 завдання | 30"; "Мідтерм | 3 завдання | 15"; "Іспит | 3 завдання | 15". Sum 100. The "3 завдання" for Мідтерм and Іспит is ambiguous (not checked against requirements).
  - Practicals: bash scripts, xv6, cat clone, ls clone, shell with redirection/pipes/background, networking shell, FAT16/FAT32/ext2 image reading; optional kernel-module tasks; semester project.
  - Prerequisites (p.1, item 9): CPU-RAM-I/O understanding, C machine model, one ISA (assembler), parallel programming basics (threads, mutex, condvar, semaphores), Linux usage.
  - Course order (item 10, 14 topics): Структура комп'ютера → Огляд ОС → Інструменти командного рядка → Файлові API → Процеси та потоки → ФС API → Сигнали → IPC → Файлові системи → Управління пам'яттю → Внутрішня будова GNU/Linux → GUI → xv6 → Драйвери Linux → RTOS.
  - Policies: "Виконання всіх практичних завдань та проекту є обов’язковим." Exam form: "іспит у формі усної співбесіди".

### `cc_2024_2025_requirements.pdf` (52 pp, LaTeX Beamer, Ukrainian)
- Type: course requirements/logistics, shared by three courses: ПОК, АКС, ОС ("Вимоги щодо роботи над курсами ”ПОК”, ”АКС” і ”ОС” та критерії оцінювання"). Filename says 2024_2025; syllabus says 2025 (see duplicates section).
- Layout: B, nav bar at top (`Пари Уважність Бали Практичні Проект Екзамени Плагіат Інше …`), footer `Олег Фаренюк Вимоги щодо роботи над курсами ”ПОК”, ”АКС” і ”ОС”`; section title at top under bar. Footnotes numbered inline (e.g. p.21 "іспит24", p.22 "балів25").
- ОС-specific facts (quote exact):
  - p.2: "Всього аудиторних годин 60 / Самостійна робота 120 / Загальний обсяг 180".
  - p.21: "Семестр складатиметься із двох частин." Each part has an exam (written colloquium and/or oral). "Проект ... демонструється двічі під час семестру, його захист – в кінці." (3 presentations).
  - p.22: "Практичні/лабораторні роботи: 40 балів"; "Контрольний проект: 30 балів разом – три представлення"; "Екзамени: 2 x 15 = 30 балів"; part (up to 2 x 5) may go to written tests.
  - p.27: late work within one week at multiplier "1/2"; unsubmitted work = "подвійній її вартості" negative points; "Фактично, для допуску до іспиту потрібно здати всі роботи."
  - p.23: submission via CMS https://learn.ucu.edu.ua/ ; code via GitHub; "Роботи без вказаного варіанту не перевірятимуться".
  - p.43 (ОС-only): "Програми повинні використовувати POSIX-сумісні API. В сумнівних випадках референтною системою вважатиметься Ubuntu LTS 202x."; "Для курсу ОС перевірка помилкових ситуацій є критичною!"
  - p.44: project 1-3 students, Git required, interim demos (missing one = "мінус 5 балів").
  - p.47: oral theory exam "без фіксованого списку питань та без часу на підготовку" (shared ПОК/АКС/ОС).
- Quirks: heavy repeated header/footer (see cross-cutting); many footnotes; Beamer tables on p.2, p.22; some slides are long prose (p.3, p.17-20 ~1,200 chars/page).
- Not checked: pp.4-20 and 28-42 in detail (policy text, not ОС-specific).

## Lecture decks (PowerPoint-origin, Teslyuk course) — Lec_*.pdf

### `Lec_1_OS.pdf` (65 pp, PP, "Microsoft PowerPoint 2010", Ukrainian)
- Type: lecture + course overview (title "Слайд 1"). Course "Операційні системи", author on title slide: Теслюк Василь Миколайович, професор (name on slide, not copied).
- Layout: plain PowerPoint, title in bold at top of slide, slide number bottom-right. No header/footer, no nav bar.
- Quirks: p.10 grading: "1. Лабораторні роботи – 30 балів. 2. Контрольна робота – 20 балів. 3. Поточний контроль – 2*10=20 балів. 4. Екзамен – 30 балів." (**conflicts with the 2025 syllabus**: 40/30/15/15). p.9 lab list includes FreeRTOS on STM32, not xv6.
- Text-as-image: p.65 ("Дякую за увагу!") is rasterized (text layer = only "65"). Section-title slides with a picture: p.13, p.37 (title text plus image; text ~75-80 chars).
- Not checked: whether pp.4-64 contain other rasterized text.

### `Lec_3_OS.pdf` (73 pp, PP, Ukrainian)
- Type: lecture (file systems topic, "Тема 8. Файлові системи" on p.2). Title "Файлова система".
- Layout: plain PowerPoint, title bold colored at top, figures often full-slide.
- Text layer: clean on text pages (e.g. p.2 identical to Lec_7 p.2, md5 match). Picture-only title slides with 1-3 words: p.4 "Комп’ютерна інформація", p.16 "Поняття файлової системи (1)", p.36 "FAT. DOS" (figure + title), p.73 "Дякую за увагу!".
- Near-duplicate consecutive slides: p.29-30 ("Файлова система FAT", identical 21-char text, two picture slides), also 37-38, 40-41.
- Not checked: diagrams' labels (raster).

### `Lec_7.pdf` (88 pp, PP, Ukrainian)
- Type: lecture (file systems, extended). Title "Файлова система". Same title slide and p.2 as Lec_3.
- Layout: as Lec_3. Titles per slide "Структура файлової системи (1-3)", "Файлова система ext2" (p.11, picture + 22 chars), "Дискове планування. (6)" (p.50), "Флешка (ФС, Продуктивність, Менше — краще)" (p.69), closing p.88.
- Overlap with Lec_3: 33 of 73 Lec_3 slide titles also appear as titles in Lec_7 (not checked per slide); Lec_3 looks like an earlier subset of Lec_7.
- Stray or foreign text: none found (grep for "Linux Device" / "Okhrimenko" = 0).

## Beamer decks (os_*.pdf, LaTeX Beamer, author "Олег Фаренюк", CC BY-SA)

Common layout for all Beamer decks: top nav bar listing section names (e.g. `Огляд File I/O Дескриптори Locks Filesystem Інше`), title in bold below it, footer `Олег Фаренюк <deck title>` bottom, page number. Title slide (p.1) has `©Олег Фаренюк, Creative Commons - Attribution Share Alike (CC BY-SA)`. Nav bar and footer text must be stripped before chunking.

### `os_l000_intro.pdf` (13 pp, B, lecture; title "Що таке операційна система і навіщо вона")
- Header "Огляд", footer `Олег Фаренюк Що таке операційна система і навіщо вона`. Short deck; p.2-3 bullet lists with ◇ markers. p.13 is a title-only "Поняття операційної системи (2)" style page with nothing else (74 chars).
- Overlay/duplicate: none. Footnotes as superscript digits (p.3: "1" "2" lines at bottom).

### `os_l010_processes.pdf` (72 pp, B, lecture; "Процеси та потоки")
- Header `Процеси Process management Різне` (+ `Linux Windows Потоки POSIX ...` on section pages); footer `Олег Фаренюк Процеси та потоки` (variant without "та" on other pages).
- p.20-21 "Карта пам’яті процесу та її відображення – 1/2" (picture-based, source credit "Взято із: getrobot.net"). p.36 has dense ERRNO text (execve).
- Overlay pairs: p.20-21, p.53-54 (not checked).

### `os_l020_files.pdf` (118 pp, B, lecture; "Файлові API")
- Header `Огляд File I/O Дескриптори Locks Filesystem Інше POSIX LibC WinAPI C++`; footer `Олег Фаренюк Файлові API`. Heavy C code (open(), dup(), dup2()). p.117 link slide ("Linux 6.5 Brings New ”cachestat” Syscall..."), p.118 nearly empty (117 chars).
- Code listings: `int open(const char *pathname, int flags);`. No overlay duplicates found by Jaccard test.

### `os_l025_signals.pdf` (38 pp, B, lecture; "Сигнали POSIX")
- Header `Огляд Список API`; footer `Олег Фаренюк Сигнали POSIX`. Dense list slides; p.22 "Реєнтрантні функції:" with one picture (123 chars); p.38 nearly empty (55 chars). Code via `signalfd(...)` on p.37.

### `os_l030_IPC.pdf` (135 pp, B, lecture; "Взаємодія процесів – IPC")
- Header `Огляд Сокети Pipes/FIFOs POSIX IPC mmap Інше`, sub-header `Принципи UNIX Domain сокети Інтернет Сервери` on p.67; footer `Олег Фаренюк Взаємодія процесів – IPC, Inter-process communication`. Largest Beamer deck; ~600-1000 chars/page. p.134 link list ("Серія статей про IPC…"). One glued Latin/Cyrillic token "ВзаємодіяInterface" (page not located).
- No overlay duplicates. Diagrams (p.2-3 bullet figures) raster.

### `os_l033_async.pdf` (51 pp, B, lecture; "Огляд асинхронного програмування")
- Header `Огляд Низькорівневі API Високорівневі API`; footer `Олег Фаренюк Огляд асинхронного програмування`. Code: `const char hostname[] = ”www.google.com”;` (p.3) — **curly quotes inside code**.
- Near-identical trailing slides p.45-51 (~158 chars each, library overview "Огляд libevent libuv Boost.Asio"); treat as duplicates.

### `os_l040_Linux_internals.pdf` (51 pp, B (pdfTeX/MiKTeX), lecture; title "Linux")
- **Encoding defect on all 51 pages**: text is Cyrillic cp1251 bytes read as Latin-1 (e.g. p.2 "Îãëÿä Ïðîöåñè i ïîòîêè" = "Огляд Процеси i потоки"; p.46 "Îëåã Ôàðåíþê" = "Олег Фаренюк"). Fonts are Type 3 with no ToUnicode.
- Fix verified: per-character remap, `c.encode('latin-1').decode('cp1251') if ord(c)<256 else c` (keeps "⋄" U+22C4 etc.). Whole-page `encode('latin-1')` fails on U+22C4, so do the per-character version. After remap, Cyrillic text reads correctly (p.46 checked).
- Header `Огляд Процеси i потоки Керування пам'ятю I/O Namespaces Завантаження`. Near-duplicate trailing slides p.46-51.
- Footer quirk: `Олег Фаренюк Внутрішня будова та порядок завантаження Linux` (in mojibake form too).

### `os_l0XX_FS.pdf` (44 pp, B, lecture; "Файлові системи")
- Header `Огляд Partitioning Case study Посилання`, plus `Ext2 FS Ext3 FS Ext4 FS Btrfs FAT NTFS HFS+ APFS ISO 9660 UDF` on case-study pages (p.22). Footer `Олег Фаренюк Файлові системи`. Overlay pairs p.36-41 (FAT/NTFS one-word-per-slide). p.44 nearly empty (103 chars).
- Topic overlaps with Lec_3/Lec_7 (ext2, FAT, inode): not checked slide-by-slide.

### `os_l0XX_GUI_1_overview.pdf` (73 pp, B, lecture; "GUI – огляд")
- Header `Intro Iсторiя Будова Controls Огляд Структурнi елементи Controls`, footer `Олег Фаренюк GUI – огляд`. Title slide has 2 images; p.73 near-empty (116 chars, links only).
- **Latin/Cyrillic homoglyphs**: about 1,140 tokens mix Latin "i/I" with Cyrillic letters (e.g. "Iсторiя", "Вiкiпедiї", "Всi присутнi", "Iлюстрацiя" p.36). Affects search/keyword match ("історія" ≠ "Iсторiя").

### `os_l0XX_GUI_2_X_Window.pdf` (55 pp, B, lecture; "GUI – X Window System")
- Header `X Windows Огляд Протокол та компоненти XLib XCB Xt Xaw Motif`, footer `Олег Фаренюк GUI – X Window System`. Diagrams p.2 (2 images), p.27 (2 images), p.54 (8 images: desktop-environment screenshots, text-light, 264 chars).
- Homoglyphs: about 960 mixed tokens ("Пiдсумовуючи", "Лiнукс", "замiну"). Long prose (p.3 ~1,260 chars).

### `os_l0XX_GUI_3_Wayland.pdf` (48 pp, B, lecture draft; "GUI – Wayland (draft)")
- Header `Wayland Огляд Архiтектура Приклади Iнше`, footer `Олег Фаренюк GUI – Wayland (draft)`. Title says "(draft)".
- **Code with substituted characters**: p.30 `redraw(void ∗data, struct wl_callback ∗ callback , uint32_t time)` — `∗` (U+2217) used in place of `*`. Likely also in other code slides (not checked).
- ~830 mixed Latin/Cyrillic tokens. p.9 is a diagram ("Загальна схема") with 2 images, 139 chars. p.48 near-empty (89 chars).

### `os_p01_bash.pdf` (23 pp, B, practice/lab; title "Bash")
- Type: practice/lab. Header none beyond title; footer `Олег Фаренюк Bash`. Terminal transcripts: `[indrekis@west bash]$ bash --version` (example prompt contains a username/hostname from an external example; not user data). p.1 title-only.
- Mixed Latin/Cyrillic: ~210 tokens ("iз", "найбiльш", "варiантом", "акронiм"). p.22-23 further-reading lists with URLs.

### `os_pok_syscalls.pdf` (39 pp, B, lecture; "Системні виклики")
- Header `Огляд Реалізація Інше` (+ `Linux DOS Windows`, `vDSO Захист strace` on later pages); footer `Олег Фаренюк Системні виклики`. Code: C for fopen/glibc; p.38 OpenBSD pinsyscalls; p.39 nearly empty ("Олег Фаренюк Системні виклики" + nav only).
- Clean Ukrainian text; no homoglyph or encoding issues found in sampled pages.

## Single figure

### `proc_switching.pdf` (1 p, Inkscape 1.3 vector figure, English)
- Type: single figure (process-switching diagram: "Scheduler / Dispatcher / Syscall / IRQ / Timer IRQ / OS (kernel mode) code"). No title or footer. Text layer is clean English, Verdana embedded (TrueType WinAnsi). No raster images. Not checked which lecture uses it.

## PowerPoint decks (`.pptx` in folder; converted to PDF in `/tmp/review_os/pptx/` only)

### `Presentation1.pptx` (20 slides; PDF 20 pp)
- Type: lecture, English. Title "Linux Device Drivers / Lection 1 / Roman Okhrimenko 2019" (author credit on title slide). Layout: PowerPoint, slide number + "Wireless Solutions IoT - SGUP" footer ("1 Wireless Solutions IoT - SGUP"). Text layer clean; p.10 "Monolithic vs Microkernel" with 9 images. Not Ukrainian; not the same as the Lec_* PDFs.

### `Presentation2.pptx` (20 slides; PDF 20 pp)
- Lection 2, same author/footer ("Wireless Solutions IoT - SGUP"), topic: kobject/kset/uevent. p.1 title, p.4 near-empty (52 chars). Text clean.

### `Presentation3.pptx` (16 slides; PDF 16 pp)
- Lection 3: Device Tree, I2C/SPI/USB drivers. Footer as above. p.8 "I2C, SPI and USB bus based drivers" with 7 images (82 chars). p.14 and p.6 near-empty.

### `Presentation4.pptx` (25 slides; PDF 25 pp)
- "Real Time Operating Systems / Lection 4 / 2019". Topics: RTOS vs regular OS, priority inversion (p.12 "Priority ceiling"). Text clean, p.25 references. Overlaps topic-wise with the Realtime deck (not checked page by page).

### `Realtime_OS__QNX_vxWorks_FreeRTOS.pptx` (21 slides; PDF 21 pp)
- Type: lecture/talk, English, "Realtime Operating Systems / QNX, vxWorks, FreeRTOS", prepared by an external engineer, © 2020 GlobalLogic (copyright line, contact block: do not copy). Header repeated on 16 slides: `Realtime Operating Systems - QNX, vxWorks, FreeRTOS`. p.1 is logo only (24 chars, 10 images); p.11, 14, 17, 19 are image-heavy (20-80 chars). Last page "Thank you" with contact block.

## Cross-cutting findings for the parser

1. **Beamer nav bar and footer repeat on every page (all 13 Beamer decks, and the requirements doc).** Strip the first 1-2 lines (`Огляд ... Інше`) and the last footer line (`Олег Фаренюк <title>`). Examples: `os_l010_processes.pdf` p.2 (header `Процеси Process management Різне`, footer `Олег Фаренюк Процеси та потоки`), `cc_2024_2025_requirements.pdf` p.3 (`Пари Уважність Бали ...`). Counts: nav line 17-120 times per deck.
2. **Mojibake in `os_l040_Linux_internals.pdf`, all 51 pages.** cp1251 bytes read as Latin-1, Type 3 fonts, no ToUnicode. Remap per character (see entry). Example p.2 and p.46. Verify after remap before indexing.
3. **Latin/Cyrillic homoglyphs in Beamer Ukrainian text.** `os_l0XX_GUI_1_overview.pdf` (~1,140 mixed tokens, p.3 "Iсторiя"), `GUI_2` (~960, p.2 "Лiнукс"), `GUI_3` (~830), `os_p01_bash.pdf` (~210, p.2 "акронiм"). Normalize Latin i/I to Cyrillic і/І (and other lookalikes) before tokenizing, or the same word will not match its Cyrillic variant in questions.
4. **Code listings contain substituted characters.** `os_l0XX_GUI_3_Wayland.pdf` p.30 uses `∗` (U+2217) for `*`; `os_l033_async.pdf` p.3 uses curly quotes `”www.google.com”` in C. Normalize (`∗`→`*`, `”`/`“`→`"`) inside code blocks only. Not checked on other C-heavy pages (os_l020 p.3, os_pok_syscalls p.20).
5. **Near-duplicate / overlay slides.** Clear clusters: `os_l033_async.pdf` p.45-51, `os_l040_Linux_internals.pdf` p.46-51 (library/overview tail), `os_l0XX_FS.pdf` p.36-41 (one-word FAT/NTFS slides), `Lec_3_OS.pdf` p.29-30, 37-38, 40-41. Dedupe by text hash or keep one per cluster.
6. **Picture-only and near-empty slides.** Lec_1 p.65 ("Дякую за увагу!" is rasterized; text layer = "65"); Lec_3 p.4, 16, 36 (title + picture); Lec_7 p.11, 50, 69; os_l0XX_GUI_1 p.73, os_l0XX_FS p.44, os_pok_syscalls p.39, os_l025 p.38 (title/nav only). Title-only chunks should be merged with the next content page or dropped.
7. **Footnote markers glued to words.** `cc_2024_2025_requirements.pdf` p.21 "іспит24", p.22 "балів25 " and "40 балів25", p.27 "поновилися37"; `os_l025_signals.pdf` "SIGxxxx2" (p.2). Strip trailing digit footnotes before parsing numbers (e.g. "40 балів25" → "40 балів"). Critical for the grading numbers.
8. **Two conflicting grading schemes for the same course.** `ДВВ_Операційні системи_2025.pdf` item 11 (grading table): 40/30/15/15. `Lec_1_OS.pdf` p.10: 30/20/20/30 (lab/control/current/exam). `cc_2024_2025_requirements.pdf` p.22: 40/30/2x15. Tag each chunk with its source year/version. Logistics answers should cite the syllabus and requirements file, not Lec_1.
9. **Mixed course versions and languages in the folder.** Lec_1/Lec_3/Lec_7 are a different author's (Teslyuk) PowerPoint course; Presentation1-4 and Realtime_OS are English third-party decks (2019-2020). None matches `os_*` content. Tag `lang` and `source_course` in metadata to avoid mixing.
10. **Syllabus table artifact.** `ДВВ_Операційні системи_2025.pdf` item 10 (course schedule, p.2-3) contains the literal `... (repeated 2 times)` and "Розміщені на LMS" on every row. Drop those rows from retrieval. Contact fields should be excluded from indexed text.

## Duplicate / older-version candidates
- `Lec_3_OS.pdf` vs `Lec_7.pdf`: same title slide and identical p.2 (md5 match), 33 of 73 Lec_3 titles reappear in Lec_7. Lec_7 looks like the extended version; treat Lec_3 as superseded (not confirmed by the author).
- `Lec_1_OS.pdf` vs `os_l000_intro.pdf`: both introduce OS concepts, different authors (Teslyuk vs Фаренюк). Not duplicates; different course versions.
- `os_l0XX_FS.pdf` vs `Lec_3`/`Lec_7`: overlapping file-system topics (ext2, FAT). Not checked page by page.
- `Presentation4.pptx` vs `Realtime_OS__QNX_vxWorks_FreeRTOS.pptx`: both RTOS (topic overlap). Not checked.
- `cc_2024_2025_requirements.pdf` (2024/2025) vs `ДВВ_Операційні системи_2025.pdf` (2025): the requirements file may be superseded; not verified.
- `os_l0XX_GUI_3_Wayland.pdf` is marked "(draft)".

## Not checked
- Full-text correctness of every page (sampled only). Diagram labels inside raster images. Whether `proc_switching.pdf` is used in a particular lecture. Requirements pp.4-20, 28-42 in detail. Presentation1-4 and Realtime slide contents beyond sampled pages.
