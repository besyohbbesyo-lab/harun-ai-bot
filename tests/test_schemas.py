# tests/test_schemas.py — ToolResult + ProviderConfig testleri
import pytest

from core.schemas import OperationLog, ProviderConfig, ToolResult, yeni_trace_id


class TestToolResult:
    def test_basari_factory(self):
        r = ToolResult.basari("merhaba")
        assert r.ok is True
        assert r.data == "merhaba"
        assert r.error is None
        assert len(r.trace_id) == 8

    def test_hata_factory(self):
        r = ToolResult.hata("bir hata olustu")
        assert r.ok is False
        assert r.error == "bir hata olustu"
        assert r.data is None

    def test_dict_donusum(self):
        r = ToolResult.basari({"x": 1})
        d = r.dict()
        assert d["ok"] is True
        assert d["data"] == {"x": 1}
        assert "trace_id" in d

    def test_trace_id_benzersiz(self):
        ids = {ToolResult.basari().trace_id for _ in range(20)}
        assert len(ids) == 20

    def test_none_data_kabul_edilir(self):
        r = ToolResult.basari(None)
        assert r.ok is True

    def test_repr_ok(self):
        r = ToolResult.basari()
        assert "OK" in repr(r)

    def test_repr_err(self):
        r = ToolResult.hata("kaos")
        assert "ERR" in repr(r)


class TestProviderConfig:
    def test_temel_olusturma(self):
        p = ProviderConfig(name="Groq", model="llama-3.3-70b")
        assert p.name == "Groq"
        assert p.api_key == ""

    def test_dict_isim_uyumu(self):
        p = ProviderConfig(name="Gemini", model="gemini-2.0-flash")
        d = p.dict()
        assert d["name"] == "Gemini"
        assert d["isim"] == "Gemini"

    def test_from_dict_name(self):
        p = ProviderConfig.from_dict({"name": "Groq", "model": "llama", "max_tokens": 2000})
        assert p.name == "Groq"
        assert p.max_tokens == 2000

    def test_from_dict_isim(self):
        p = ProviderConfig.from_dict({"isim": "Gemini", "model": "gemini-flash"})
        assert p.name == "Gemini"

    def test_from_dict_varsayilanlar(self):
        p = ProviderConfig.from_dict({"name": "Test", "model": "test"})
        assert p.max_tokens == 4096
        assert p.temperature == 0.7

    def test_from_dict_bos(self):
        p = ProviderConfig.from_dict({})
        assert p.name == "bilinmiyor"


class TestTraceId:
    def test_uzunluk_8(self):
        assert len(yeni_trace_id()) == 8

    def test_benzersiz(self):
        ids = {yeni_trace_id() for _ in range(50)}
        assert len(ids) == 50

    def test_string_tipi(self):
        assert isinstance(yeni_trace_id(), str)


class TestOperationLog:
    def test_ilk_calisma(self, tmp_path):
        log = OperationLog(db_path=str(tmp_path / "ops.json"))
        sayac = {"n": 0}

        def islem():
            sayac["n"] += 1
            return "tamam"

        log.execute_once("op_001", islem)
        assert sayac["n"] == 1

    def test_ikinci_cagri_atlanir(self, tmp_path):
        log = OperationLog(db_path=str(tmp_path / "ops.json"))
        sayac = {"n": 0}

        def islem():
            sayac["n"] += 1
            return "tamam"

        log.execute_once("op_002", islem)
        log.execute_once("op_002", islem)
        assert sayac["n"] == 1

    def test_farkli_id_iki_kez_calisir(self, tmp_path):
        log = OperationLog(db_path=str(tmp_path / "ops.json"))
        sayac = {"n": 0}

        def islem():
            sayac["n"] += 1
            return "ok"

        log.execute_once("op_A", islem)
        log.execute_once("op_B", islem)
        assert sayac["n"] == 2

    def test_is_done_true(self, tmp_path):
        log = OperationLog(db_path=str(tmp_path / "ops.json"))
        log.execute_once("op_003", lambda: "x")
        assert log.is_done("op_003") is True

    def test_is_done_false(self, tmp_path):
        log = OperationLog(db_path=str(tmp_path / "ops.json"))
        assert log.is_done("op_yok") is False
