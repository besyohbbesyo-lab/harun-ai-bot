# tests/test_secrets.py — S7-3: Secret Management testleri
# ============================================================

import os
from unittest.mock import patch

import pytest


class TestSecretAl:
    def setup_method(self):
        import core.secrets as s

        s._cache.clear()
        s._kaynak = s.SecretKaynagi.NONE

    def test_env_fallback(self):
        from core.secrets import secret_al

        with patch.dict(os.environ, {"TEST_SECRET": "test_deger"}):
            assert secret_al("TEST_SECRET") == "test_deger"

    def test_varsayilan_deger(self):
        from core.secrets import secret_al

        assert secret_al("OLMAYAN_SECRET_XYZ", "varsayilan") == "varsayilan"

    def test_bos_varsayilan(self):
        from core.secrets import secret_al

        assert secret_al("OLMAYAN_SECRET_XYZ") == ""

    def test_cache_onceligi(self):
        import core.secrets as s

        s._cache["CACHE_TEST"] = "cache_deger"
        assert s.secret_al("CACHE_TEST") == "cache_deger"

    def test_secret_var_mi_true(self):
        import core.secrets as s

        s._cache["VAR_MI_TEST"] = "deger"
        assert s.secret_var_mi("VAR_MI_TEST") is True

    def test_secret_var_mi_false(self):
        from core.secrets import secret_var_mi

        assert secret_var_mi("KESINLIKLE_YOK_XYZ123") is False

    def test_secret_ozeti_yapisi(self):
        from core.secrets import secret_ozeti

        ozet = secret_ozeti()
        assert "kaynak" in ozet
        assert "toplam_secret" in ozet
        assert "kritik_secretler" in ozet

    def test_secret_ozeti_kritikler(self):
        from core.secrets import secret_ozeti

        ozet = secret_ozeti()
        kritikler = ozet["kritik_secretler"]
        assert "TELEGRAM_TOKEN" in kritikler
        assert "GROQ_API_KEY" in kritikler

    def test_ozet_deger_gostermez(self):
        import core.secrets as s

        s._cache["TELEGRAM_TOKEN"] = "gizli_token_123"
        ozet = s.secret_ozeti()
        # Ozet deger gostermemeli, sadece var/yok
        ozet_str = str(ozet)
        assert "gizli_token_123" not in ozet_str

    def test_secrets_yukle_env(self):
        from core.secrets import SecretKaynagi, secrets_yukle

        kaynak = secrets_yukle(zorla=True)
        assert kaynak in [
            SecretKaynagi.ENV,
            SecretKaynagi.DOPPLER,
            SecretKaynagi.VAULT,
        ]

    def test_secrets_yukle_tekrar(self):
        """Cache doluyken tekrar yuklemez."""
        import core.secrets as s
        from core.secrets import SecretKaynagi

        s._cache["test"] = "deger"
        s._kaynak = SecretKaynagi.ENV
        kaynak = s.secrets_yukle(zorla=False)
        assert kaynak == SecretKaynagi.ENV

    def test_doppler_yoksa_env_fallback(self):
        """Doppler yoksa ENV'e dusmeli."""
        from core.secrets import SecretKaynagi, secrets_yukle

        with patch("subprocess.run", side_effect=FileNotFoundError):
            kaynak = secrets_yukle(zorla=True)
            assert kaynak in [SecretKaynagi.ENV, SecretKaynagi.VAULT]

    def test_secret_kaynagi_sabitleri(self):
        from core.secrets import SecretKaynagi

        assert SecretKaynagi.DOPPLER == "doppler"
        assert SecretKaynagi.VAULT == "vault"
        assert SecretKaynagi.ENV == "env"
        assert SecretKaynagi.NONE == "none"

    def test_coklu_secret_cache(self):
        import core.secrets as s

        s._cache.update(
            {
                "KEY1": "val1",
                "KEY2": "val2",
                "KEY3": "val3",
            }
        )
        assert s.secret_al("KEY1") == "val1"
        assert s.secret_al("KEY2") == "val2"
        assert s.secret_al("KEY3") == "val3"
