# tests/test_rag_service.py
from unittest.mock import MagicMock, patch

import pytest

from services.rag_service import (
    _rag_build_context,
    _rag_extract_section,
    _rag_extract_usage,
    _rag_get_source_label,
    _rag_wants_verbatim,
)

# --- _rag_wants_verbatim ---


def test_verbatim_aynen_yaz():
    assert _rag_wants_verbatim("bunu aynen yaz") is True


def test_verbatim_kelimesi_kelimesine():
    assert _rag_wants_verbatim("kelimesi kelimesine aktar") is True


def test_verbatim_verbatim():
    assert _rag_wants_verbatim("verbatim yaz") is True


def test_verbatim_tam_metin():
    assert _rag_wants_verbatim("tam metin ver") is True


def test_verbatim_aynen_aktar():
    assert _rag_wants_verbatim("aynen aktar") is True


def test_verbatim_normal_sorgu():
    assert _rag_wants_verbatim("hava nasıl?") is False


def test_verbatim_bos_string():
    assert _rag_wants_verbatim("") is False


def test_verbatim_none():
    assert _rag_wants_verbatim(None) is False


# --- _rag_extract_section ---


def test_extract_section_bulur():
    text = "Başlık:\nKullanim:\nbir iki üç\n\n# Sonraki"
    result = _rag_extract_section(text, "Kullanim")
    assert result is not None
    assert "bir iki üç" in result


def test_extract_section_bulamazsa_none():
    result = _rag_extract_section("hiç eşleşme yok", "Kullanim")
    assert result is None


def test_extract_section_bos_text():
    assert _rag_extract_section("", "Kullanim") is None


def test_extract_section_none_text():
    assert _rag_extract_section(None, "Kullanim") is None


# --- _rag_extract_usage ---


def test_extract_usage_kullanim_bulur():
    text = "Kullanim:\nşöyle kullanılır\n\n# bitti"
    result = _rag_extract_usage(text)
    assert result is not None
    assert "kullanılır" in result


def test_extract_usage_bos():
    assert _rag_extract_usage("") is None


# --- _rag_get_source_label ---


def test_get_source_label_normal():
    hits = [(1.0, {"source": "dosya.txt", "merged": False, "merged_count": 1})]
    result = _rag_get_source_label(hits)
    assert "dosya.txt" in result


def test_get_source_label_merged():
    hits = [(1.0, {"source": "dosya.txt", "merged": True, "merged_count": 3})]
    result = _rag_get_source_label(hits)
    assert "3 bolum" in result


def test_get_source_label_bos_hits():
    assert _rag_get_source_label([]) == ""


def test_get_source_label_source_yok():
    hits = [(1.0, {"source": "", "merged": False})]
    result = _rag_get_source_label(hits)
    assert result == ""


def test_get_source_label_hata_toleransi():
    hits = ["bozuk_veri"]
    result = _rag_get_source_label(hits)
    assert result == ""


# --- _rag_build_context ---


def test_build_context_bos_hits():
    fake_memory = MagicMock()
    fake_memory.benzer_gorev_bul.return_value = []
    import services.rag_service as rs

    with patch("core.globals.memory", fake_memory):
        ctx, hits = rs._rag_build_context("test sorgu")
    assert ctx == ""
    assert hits == []


def test_build_context_hits_var():
    fake_memory = MagicMock()
    fake_memory.benzer_gorev_bul.return_value = ["belge1", "belge2"]
    import services.rag_service as rs

    with patch("core.globals.memory", fake_memory):
        ctx, hits = rs._rag_build_context("test sorgu")
    assert "belge1" in ctx
    assert len(hits) == 2


def test_build_context_memory_exception():
    import services.rag_service as rs

    with patch.dict("sys.modules", {"core.globals": None}):
        ctx, hits = rs._rag_build_context("test")
    assert ctx == ""
    assert hits == []


def test_build_context_merged_ve_chunk():
    fake_memory = MagicMock()
    fake_memory.benzer_gorev_bul.return_value = ["içerik"]
    import services.rag_service as rs

    with patch("core.globals.memory", fake_memory):
        ctx, hits = rs._rag_build_context("sorgu", top_k=3)
    assert isinstance(ctx, str)
    assert isinstance(hits, list)
