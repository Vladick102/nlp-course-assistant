from app.text import lemmas


def test_inflected_forms_share_lemma():
    a, b, c = lemmas("ядра"), lemmas("ядром"), lemmas("ядрі")
    assert a and a == b == c


def test_technical_tokens_kept():
    toks = lemmas("fork() та x86, C++ і MPI_Send; пам'ять")
    for t in ("fork", "x86", "c++", "mpi_send"):
        assert t in toks
    assert "та" not in toks and "і" not in toks
    assert any(t.startswith("пам'ят") for t in toks)


def test_empty():
    assert lemmas("") == []
