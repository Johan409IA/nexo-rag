from adapters.chunking.page_chunker import PageChunker


def test_cada_pagina_produce_un_fragmento_con_chunk_index_cero() -> None:
    chunker = PageChunker()

    fragmentos = chunker.crear_fragmentos([(1, "cohesión"), (2, "acoplamiento"), (5, "diseño")])

    assert [(f.pagina, f.chunk_index, f.texto) for f in fragmentos] == [
        (1, 0, "cohesión"),
        (2, 0, "acoplamiento"),
        (5, 0, "diseño"),
    ]
    assert all(f.id is None and f.documento_id is None for f in fragmentos)


def test_no_filtra_paginas_por_longitud() -> None:
    chunker = PageChunker()

    fragmentos = chunker.crear_fragmentos([(1, "corta"), (2, "")])

    assert len(fragmentos) == 2


def test_sin_paginas_no_produce_fragmentos() -> None:
    chunker = PageChunker()

    assert chunker.crear_fragmentos([]) == []
