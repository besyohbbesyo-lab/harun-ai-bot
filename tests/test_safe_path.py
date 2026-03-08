# tests/test_safe_path.py — safe_path modülü testleri
# pytest -v tests/test_safe_path.py

import os
import sys
from pathlib import Path

import pytest

# Proje kök dizini
PROJE_DIR = Path(__file__).parent.parent.resolve()


class TestSafePath:
    def test_gecerli_dosya_adi(self):
        from safe_path import safe_path

        sonuc = safe_path("rapor.txt")
        assert sonuc == PROJE_DIR / "rapor.txt"

    def test_gecerli_alt_dizin(self):
        from safe_path import safe_path

        sonuc = safe_path("core/utils.py")
        assert sonuc == PROJE_DIR / "core" / "utils.py"

    def test_traversal_nokta_nokta(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("../../etc/passwd")

    def test_traversal_ters_slash(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("..\\..\\windows\\system32")

    def test_tilde_engellenir(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("~/gizli")

    def test_pipe_engellenir(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("dosya|komut")

    def test_semicolon_engellenir(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("dosya;komut")

    def test_null_byte_engellenir(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("dosya\x00.txt")

    def test_dollar_engellenir(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("$HOME/gizli")

    def test_path_traversal_error_tipi(self):
        from safe_path import PathTraversalError, safe_path

        with pytest.raises(PathTraversalError):
            safe_path("../../etc/passwd")

    def test_path_nesnesi_doner(self):
        from safe_path import safe_path

        sonuc = safe_path("rapor.txt")
        assert isinstance(sonuc, Path)

    def test_memory_db_alt_dizini(self):
        from safe_path import safe_path

        sonuc = safe_path("memory_db/veri.json")
        assert "memory_db" in str(sonuc)


class TestDosyaIzinliMi:
    def test_izinli_dosya(self):
        from safe_path import dosya_izinli_mi

        assert dosya_izinli_mi("rapor.txt") is True

    def test_traversal_izinsiz(self):
        from safe_path import dosya_izinli_mi

        assert dosya_izinli_mi("../../etc/passwd") is False

    def test_tehlikeli_karakter_izinsiz(self):
        from safe_path import dosya_izinli_mi

        assert dosya_izinli_mi("dosya;komut") is False

    def test_tilde_izinsiz(self):
        from safe_path import dosya_izinli_mi

        assert dosya_izinli_mi("~/gizli") is False


class TestSafeOpen:
    def test_yazma_ve_okuma(self):
        from safe_path import safe_delete, safe_open

        # Yaz
        with safe_open("_test_gecici.txt", "w") as f:
            f.write("test içerik")
        # Oku
        with safe_open("_test_gecici.txt", "r") as f:
            assert f.read() == "test içerik"
        # Temizle
        safe_delete("_test_gecici.txt")

    def test_traversal_engellenir(self):
        from safe_path import PathTraversalError, safe_open

        with pytest.raises(PathTraversalError):
            safe_open("../../etc/passwd", "r")

    def test_yazma_alt_dizin_olusturur(self):
        import shutil

        from safe_path import safe_delete, safe_open

        # Yaz
        with safe_open("_test_klasor/_test_dosya.txt", "w") as f:
            f.write("alt dizin testi")
        assert (PROJE_DIR / "_test_klasor" / "_test_dosya.txt").exists()
        # Temizle
        shutil.rmtree(PROJE_DIR / "_test_klasor", ignore_errors=True)


class TestSafeDelete:
    def test_var_olan_dosyayi_siler(self):
        from safe_path import safe_delete, safe_open

        # Önce oluştur
        with safe_open("_test_silinecek.txt", "w") as f:
            f.write("silinecek")
        # Sil
        sonuc = safe_delete("_test_silinecek.txt")
        assert sonuc is True
        assert not (PROJE_DIR / "_test_silinecek.txt").exists()

    def test_olmayan_dosya_false(self):
        from safe_path import safe_delete

        sonuc = safe_delete("_olmayan_dosya_xyz.txt")
        assert sonuc is False

    def test_traversal_engellenir(self):
        from safe_path import PathTraversalError, safe_delete

        with pytest.raises(PathTraversalError):
            safe_delete("../../etc/passwd")
