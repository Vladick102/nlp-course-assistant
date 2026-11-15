from app.ingest.textnorm import clean, fix_latin_i, fix_mojibake, is_toc_line


def test_latin_i_inside_words():
    assert fix_latin_i("Практичнi роботи") == "Практичні роботи"
    assert fix_latin_i("iнiцiалiзацiя") == "ініціалізація"
    assert fix_latin_i("Iнше") == "Інше"


def test_latin_i_conjunction_between_cyrillic_words():
    assert fix_latin_i("процеси i потоки") == "процеси і потоки"


def test_latin_i_untouched_in_english():
    for t in ("integer i = 0;", "Linux kernel", "for i in range", "I/O і DMA"):
        assert fix_latin_i(t) == t


def test_mojibake_repaired():
    assert fix_mojibake("Ïðîöåñè i ïîòîêè") == "Процеси i потоки"
    assert clean("Ïðîöåñè i ïîòîêè") == "Процеси і потоки"
    assert fix_mojibake("Ðiâíi îðãàíiçàöi¨ Linux").endswith("Linux") and "організації" in clean("Ðiâíi îðãàíiçàöi¨")


def test_mojibake_not_triggered_on_clean_text():
    for t in ("Café déjà vu — naïve", "Ñandú", "Операційні системи"):
        assert fix_mojibake(t) == t


def test_clean_invisible_and_ligatures():
    assert clean("a​b­c") == "abc"
    assert clean("ﬁle ﬂow") == "file flow"
    assert clean("пам’ять памʼять") == "пам'ять пам'ять"


def test_control_glyphs():
    assert clean("так \x15 ні") == "так – ні"
    assert clean("\x15 пауза") == '" пауза'  # not between spaces → quote glyph
    assert clean("слово \x12цитата\x13") == 'слово "цитата"'


def test_toc_line():
    assert is_toc_line("1.2 Ціль роботи . . . . . . 3")
    assert not is_toc_line("Ціль роботи")


def test_partial_mojibake_word_level():
    assert clean("Iëþñòðàöiÿ ç Andrew S. Tanenbaum") == "Ілюстрація з Andrew S. Tanenbaum"
    assert clean("Iäåÿ ðåàëiçàöi¨ iç òðàíçèñòîðiâ") == "Ідея реалізації із транзисторів"
    assert clean("живлення 3.3Â!") == "живлення 3.3В!"


def test_partial_mojibake_keeps_real_latin1():
    for t in ("Un café très chic à Paris", "naïve Ñandú über Straße", "Café Müller"):
        assert clean(t) == t


def test_num_sign_artifact():
    assert clean("мина№") == "минає"
    assert clean("назива№ться напругою") == "називається напругою"
    assert clean("Його характеристикою № сила струму") == "Його характеристикою є сила струму"
    assert clean("Лабораторна робота № 5") == "Лабораторна робота № 5"
    assert clean("№ з/п") == "№ з/п"


def test_fl_fi_ligature_glyphs():
    assert clean("(\x1dip-\x1dop)") == "(flip-flop)"
    assert clean("signi\x1ccant di\x1berent e\x1ecient of\x1dine") == "significant different efficient offline"
    assert clean("зни\x1fженн") == "зниженн"


def test_num_sign_after_latin_i_and_apostrophe():
    assert clean("технологi№ю") == "технологією"
    assert clean("під'№днати") == "під'єднати"


def test_num_sign_word_start_and_comma():
    assert clean("з №диною адресою") == "з єдиною адресою"
    assert clean("Decoder №, фактично") == "Decoder №, фактично"
    assert clean("там є, i № зовсім просто") == "там є, і є зовсім просто"
