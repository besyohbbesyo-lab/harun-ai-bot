# tests/test_chat_service.py — chat_service saf fonksiyon testleri
# API çağrısı gerektirmeyen fonksiyonlar test edilir.
# pytest -v tests/test_chat_service.py

import os

import pytest


class TestGuncelBilgiGerekliMi:
    def test_haber_iceren_soru(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("bugünkü haberler neler?") is True

    def test_dolar_kuru(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("dolar kaç lira?") is True

    def test_hava_durumu(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("İstanbul hava durumu") is True

    def test_bitcoin(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("bitcoin fiyatı ne kadar?") is True

    def test_deprem(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("son deprem nerede oldu?") is True

    def test_enflasyon(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("enflasyon oranı kaç?") is True

    def test_yil_2026(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("2026 seçim sonuçları") is True

    def test_guncel_olmayan_soru(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("Python'da for döngüsü nasıl yazılır?") is False

    def test_matematik_sorusu(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("2 + 2 kaç eder?") is False

    def test_tarih_sorusu(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("Osmanlı ne zaman kuruldu?") is False

    def test_bos_soru(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("") is False

    def test_buyuk_kucuk_harf(self):
        from services.chat_service import guncel_bilgi_gerekli_mi

        assert guncel_bilgi_gerekli_mi("BUGUN ne var?") is True


class TestComputeRewardV2:
    def test_temel_reward_korunur(self):
        from services.chat_service import compute_reward_v2

        v2, _ = compute_reward_v2("Merhaba nasılsın?", "İyiyim, teşekkür ederim.", 0.7)
        assert 0.0 <= v2 <= 1.0

    def test_uzun_cevap_bonus_alir(self):
        from services.chat_service import compute_reward_v2

        kisa_cevap = "Evet."
        uzun_cevap = (
            "Python programlama dili, Guido van Rossum tarafından 1991 yılında geliştirilmiştir. "
            * 5
        )
        _, feat_kisa = compute_reward_v2("Python nedir?", kisa_cevap, 0.5)
        _, feat_uzun = compute_reward_v2("Python nedir?", uzun_cevap, 0.5)
        assert feat_uzun["quality_bonus"] > feat_kisa["quality_bonus"]

    def test_noise_prompt_ceza_alir(self):
        from services.chat_service import compute_reward_v2

        _, feat = compute_reward_v2("test", "Bu bir test cevabıdır.", 0.5)
        assert feat["noise_flag"] == 1
        assert feat["noise_penalty"] > 0

    def test_komut_ceza_alir(self):
        from services.chat_service import compute_reward_v2

        _, feat = compute_reward_v2("/status", "Bot aktif.", 0.5)
        assert feat["command_flag"] == 1
        assert feat["command_penalty"] > 0

    def test_hata_iceren_cevap_ceza_alir(self):
        from services.chat_service import compute_reward_v2

        v2, feat = compute_reward_v2("Bunu yap", "Hata: işlem tamamlanamadı.", 0.5)
        assert feat["error_penalty"] > 0

    def test_adimli_cevap_bonus(self):
        from services.chat_service import compute_reward_v2

        adimli = "İşte adımlar:\n1. Önce şunu yap\n2. Sonra bunu yap\n3. Bitir"
        _, feat = compute_reward_v2("Nasıl yapılır?", adimli, 0.5)
        assert feat["quality_bonus"] > 0

    def test_v2_sifir_ile_bir_arasinda(self):
        from services.chat_service import compute_reward_v2

        for base in [0.0, 0.3, 0.5, 0.8, 1.0]:
            v2, _ = compute_reward_v2("soru", "cevap", base)
            assert 0.0 <= v2 <= 1.0, f"base={base} için v2={v2} sınır dışı"

    def test_features_dict_anahtarlari(self):
        from services.chat_service import compute_reward_v2

        _, feat = compute_reward_v2("soru", "cevap", 0.5)
        for anahtar in [
            "reward_v1",
            "reward_v2",
            "quality_bonus",
            "noise_flag",
            "command_flag",
            "rep_score",
            "noise_penalty",
            "command_penalty",
            "repetition_penalty",
            "error_penalty",
            "prompt_len",
            "answer_len",
        ]:
            assert anahtar in feat, f"'{anahtar}' features dict'te yok"

    def test_bos_prompt_ve_cevap(self):
        from services.chat_service import compute_reward_v2

        v2, feat = compute_reward_v2("", "", 0.5)
        assert 0.0 <= v2 <= 1.0
        assert feat["prompt_len"] == 0
        assert feat["answer_len"] == 0

    def test_tekrar_iceren_cevap_ceza(self):
        from services.chat_service import compute_reward_v2

        tekrar = "evet evet evet evet evet evet evet evet evet evet evet evet"
        _, feat = compute_reward_v2("soru", tekrar, 0.5)
        assert feat["repetition_penalty"] > 0


class TestAutoModerationSuggest:
    def test_yuksek_reward_auto_approve(self):
        from services.chat_service import auto_moderation_suggest

        assert auto_moderation_suggest(0.90) == "AUTO_APPROVE"
        assert auto_moderation_suggest(0.85) == "AUTO_APPROVE"
        assert auto_moderation_suggest(1.0) == "AUTO_APPROVE"

    def test_dusuk_reward_auto_reject(self):
        from services.chat_service import auto_moderation_suggest

        assert auto_moderation_suggest(0.10) == "AUTO_REJECT"
        assert auto_moderation_suggest(0.30) == "AUTO_REJECT"
        assert auto_moderation_suggest(0.0) == "AUTO_REJECT"

    def test_orta_reward_manual(self):
        from services.chat_service import auto_moderation_suggest

        assert auto_moderation_suggest(0.5) == "MANUAL"
        assert auto_moderation_suggest(0.6) == "MANUAL"
        assert auto_moderation_suggest(0.7) == "MANUAL"

    def test_sinir_degerleri(self):
        from services.chat_service import auto_moderation_suggest

        # t_high=0.82, t_low=0.35 (default)
        assert auto_moderation_suggest(0.82) == "AUTO_APPROVE"
        assert auto_moderation_suggest(0.35) == "AUTO_REJECT"
        assert auto_moderation_suggest(0.36) == "MANUAL"
        assert auto_moderation_suggest(0.81) == "MANUAL"

    def test_env_threshold_override(self, monkeypatch):
        from services.chat_service import auto_moderation_suggest

        monkeypatch.setenv("EGITIM_T_HIGH", "0.9")
        monkeypatch.setenv("EGITIM_T_LOW", "0.2")
        assert auto_moderation_suggest(0.95) == "AUTO_APPROVE"
        assert auto_moderation_suggest(0.15) == "AUTO_REJECT"
        assert auto_moderation_suggest(0.5) == "MANUAL"


class TestBYapisalKaliteKontrolu:
    """B_yapisal varyantında kalite reddi mantığını test eder."""

    def test_kisa_yanit_ab_basarisiz_sayilir(self):
        """60 karakterden kısa yanıt → ab_basari=False olmalı."""
        from services.chat_service import compute_reward_v2

        _, feat = compute_reward_v2("Merhaba", "Kısa.", 0.8)
        assert feat["answer_len"] < 60
        # Bu yanıt B_yapisal için kalite reddine düşmeli

    def test_uzun_yanit_kalite_gecti(self):
        """Yeterince uzun yanıt → answer_len >= 60."""
        from services.chat_service import compute_reward_v2

        uzun = "Bu yanıt yeterince uzundur ve kalite kontrolünden geçmelidir. " * 3
        _, feat = compute_reward_v2("Soru?", uzun, 0.8)
        assert feat["answer_len"] >= 60

    def test_dusuk_reward_v2_kalite_reddedilir(self):
        """reward_v2 < 0.35 olan yanıt → B_yapisal başarısız sayılmalı."""
        from services.chat_service import compute_reward_v2

        # Hata içeren + kısa = düşük reward_v2
        v2, feat = compute_reward_v2("test", "Hata alinamadi.", 0.0)
        assert feat["reward_v2"] < 0.35

    def test_yuksek_reward_v2_basarili(self):
        """Kaliteli uzun yanıt → reward_v2 >= 0.35."""
        from services.chat_service import compute_reward_v2

        iyi_yanit = (
            "Python programlama dilinde döngüler şu şekilde kullanılır:\n"
            "1. for döngüsü bir koleksiyon üzerinde iterate eder.\n"
            "2. while döngüsü koşul doğru olduğu sürece çalışır.\n"
            "Her iki döngü de break ve continue ile kontrol edilebilir."
        )
        v2, feat = compute_reward_v2("Python döngüleri?", iyi_yanit, 0.7)
        assert feat["reward_v2"] >= 0.35
        assert feat["answer_len"] >= 60


class TestBYapisalRouting:
    """Stres promptlarda B_yapisal'in A_klasik'e yonlendirilmesini test eder."""

    def test_stres_prompt_algilanir(self):
        from services.chat_service import _b_yapisal_stres_prompt_mu

        prompt = (
            "Python'da for ve while döngülerini karşılaştır. Aralarındaki 5 farkı "
            "madde madde ver; her biri için birer kod örneği, 2 yaygın hata, "
            "2 gerçek kullanım senaryosu ve en sonda 4 maddelik kısa özet ekle."
        )
        assert _b_yapisal_stres_prompt_mu(prompt) is True

    def test_normal_prompt_stres_sayilmaz(self):
        from services.chat_service import _b_yapisal_stres_prompt_mu

        prompt = "Python'da for ve while döngülerini kısa özet + madde madde örneklerle açıkla."
        assert _b_yapisal_stres_prompt_mu(prompt) is False

    def test_b_yapisal_stres_promptta_a_klasike_yonlenir(self, monkeypatch):
        from services import chat_service

        class DummyVaryant:
            def __init__(self, ad, prompt_prefix):
                self.ad = ad
                self.konfig = {"prompt_prefix": prompt_prefix}
                self.aktif = True

        class DummyMotor:
            def __init__(self):
                self._varyantlar = [
                    DummyVaryant("A_klasik", ""),
                    DummyVaryant("B_yapisal", "YAPISAL_PREFIX\n"),
                ]

            def varyant_sec(self, _bucket_key):
                return self._varyantlar[1]

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: DummyMotor())

        prompt = (
            "Python'da for ve while döngülerini karşılaştır. Aralarındaki 5 farkı "
            "madde madde ver; her biri için birer kod örneği, 2 yaygın hata, "
            "2 gerçek kullanım senaryosu ve en sonda 4 maddelik kısa özet ekle."
        )
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(prompt, "genel", 6481156818)

        assert varyant.ad == "A_klasik"
        assert yeni_prompt == prompt

    def test_b_yapisal_normal_promptta_korunur(self, monkeypatch):
        from services import chat_service

        class DummyVaryant:
            def __init__(self, ad, prompt_prefix):
                self.ad = ad
                self.konfig = {"prompt_prefix": prompt_prefix}
                self.aktif = True

        class DummyMotor:
            def __init__(self):
                self._varyantlar = [
                    DummyVaryant("A_klasik", ""),
                    DummyVaryant("B_yapisal", "YAPISAL_PREFIX\n"),
                ]

            def varyant_sec(self, _bucket_key):
                return self._varyantlar[1]

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: DummyMotor())

        prompt = "Python'da for ve while döngülerini kısa özet + madde madde örneklerle açıkla."
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(prompt, "genel", 6481156818)

        assert varyant.ad == "B_yapisal"
        assert yeni_prompt.startswith("YAPISAL_PREFIX")
        assert yeni_prompt.endswith(prompt)


class TestBYapisalKaliteKontroluDirekt:
    """b_yapisal_kalite_kontrolu() fonksiyonunu doğrudan test eder."""

    def test_kisa_yanit_basarisiz_sayilir(self):
        """60 karakterden kısa yanıt → ab_basari=False."""
        from services.chat_service import b_yapisal_kalite_kontrolu

        ab_basari, feat = b_yapisal_kalite_kontrolu("soru", "Kısa.", 0.8)
        assert ab_basari is False
        assert feat["answer_len"] < 60

    def test_dusuk_reward_basarisiz_sayilir(self):
        """reward_v2 < 0.35 → ab_basari=False."""
        from services.chat_service import b_yapisal_kalite_kontrolu

        # Hata içeren + çok kısa yanıt → reward_v2 düşük olacak
        ab_basari, feat = b_yapisal_kalite_kontrolu("test", "Hata alinamadi.", 0.0)
        assert ab_basari is False
        assert feat["reward_v2"] < 0.35

    def test_kaliteli_uzun_yanit_basarili(self):
        """Uzun + kaliteli yanıt → ab_basari=True."""
        from services.chat_service import b_yapisal_kalite_kontrolu

        iyi_yanit = (
            "Python'da döngüler şu şekilde kullanılır:\n"
            "1. for döngüsü: bir koleksiyon üzerinde iterate eder.\n"
            "2. while döngüsü: koşul True olduğu sürece çalışır.\n"
            "Her iki döngü de break ve continue ile kontrol edilebilir. "
            "Performans açısından for döngüsü genellikle tercih edilir."
        )
        ab_basari, feat = b_yapisal_kalite_kontrolu("Python döngüleri?", iyi_yanit, 0.7)
        assert ab_basari is True
        assert feat["answer_len"] >= 60
        assert feat["reward_v2"] >= 0.35


class TestAbVaryantiBul:
    """_ab_varyanti_bul() fonksiyonunu test eder."""

    def test_mevcut_varyant_bulunur(self):
        from services.chat_service import _ab_varyanti_bul

        class DummyVaryant:
            def __init__(self, ad):
                self.ad = ad
                self.aktif = True

        class DummyMotor:
            _varyantlar = [DummyVaryant("A_klasik"), DummyVaryant("B_yapisal")]

        sonuc = _ab_varyanti_bul(DummyMotor(), "A_klasik")
        assert sonuc is not None
        assert sonuc.ad == "A_klasik"

    def test_olmayan_varyant_none_doner(self):
        from services.chat_service import _ab_varyanti_bul

        class DummyMotor:
            _varyantlar = []

        assert _ab_varyanti_bul(DummyMotor(), "A_klasik") is None

    def test_aktif_false_varyant_atlanir(self):
        from services.chat_service import _ab_varyanti_bul

        class DummyVaryant:
            def __init__(self, ad, aktif):
                self.ad = ad
                self.aktif = aktif

        class DummyMotor:
            _varyantlar = [DummyVaryant("A_klasik", False)]

        assert _ab_varyanti_bul(DummyMotor(), "A_klasik") is None

    def test_varyantlar_alani_olmayan_motor(self):
        from services.chat_service import _ab_varyanti_bul

        class BosMotor:
            pass

        assert _ab_varyanti_bul(BosMotor(), "A_klasik") is None


class TestAbVaryantiUygulaEkDallar:
    """_ab_varyanti_uygula() eksik dallarını test eder."""

    def test_genel_olmayan_gorev_turu_direkt_döner(self):
        """gorev_turu 'kod' ise AB uygulanmaz, prompt değişmeden döner."""
        from services.chat_service import _ab_varyanti_uygula

        prompt = "Bu bir kod görevi."
        yeni_prompt, varyant = _ab_varyanti_uygula(prompt, "kod", 12345)
        assert yeni_prompt == prompt
        assert varyant is None

    def test_kullanici_id_none_ise_hash_kullanilir(self, monkeypatch):
        """kullanici_id=None olunca prompt hash'i bucket_key olarak kullanılır."""
        from services import chat_service

        class DummyVaryant:
            ad = "A_klasik"
            aktif = True
            konfig = {"prompt_prefix": ""}

        class DummyMotor:
            def varyant_sec(self, bucket_key):
                # hash string geldiğini doğrula
                assert isinstance(bucket_key, str)
                return DummyVaryant()

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: DummyMotor())

        prompt = "Kullanıcı id yok."
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(prompt, "genel", None)
        assert yeni_prompt == prompt

    def test_exception_durumunda_orijinal_prompt_doner(self, monkeypatch):
        """ab_prompt_testini_hazirla exception atarsa prompt değişmeden döner, varyant=None."""
        from services import chat_service

        def patlayan_hazirla():
            raise RuntimeError("test hatasi")

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", patlayan_hazirla)

        prompt = "Hata senaryosu."
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(prompt, "genel", 999)
        assert yeni_prompt == prompt
        assert varyant is None

    def test_sohbet_gorev_turu_da_ab_uygulanir(self, monkeypatch):
        """gorev_turu 'sohbet' de geçerli — AB uygulanmalı."""
        from services import chat_service

        class DummyVaryant:
            ad = "A_klasik"
            aktif = True
            konfig = {"prompt_prefix": ""}

        class DummyMotor:
            def varyant_sec(self, _):
                return DummyVaryant()

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: DummyMotor())

        prompt = "Merhaba, nasılsın?"
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(prompt, "sohbet", 42)
        assert yeni_prompt == prompt
        assert varyant is not None
        assert varyant.ad == "A_klasik"


class TestAskGroqErkenCikis:
    """ask_groq() erken çıkış dallarını mock ile test eder (API çağrısı yapılmaz)."""

    def test_token_budget_asilinca_none_doner(self, monkeypatch):
        """budget.limit_asildimi() True dönünce ask_groq None döndürmeli."""
        from services import chat_service

        class DummyBudget:
            def limit_asildimi(self):
                return True

        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        sonuc = chat_service.ask_groq("test prompt")
        assert sonuc is None

    def test_circuit_breaker_open_iken_none_doner(self, monkeypatch):
        """cb_groq.state == OPEN ve _gecis_kontrol sonrası hâlâ OPEN → None döner."""
        from services import chat_service

        class DummyBudget:
            def limit_asildimi(self):
                return False

        class DummyCB:
            OPEN = "open"
            CLOSED = "closed"
            state = "open"

            def _gecis_kontrol(self):
                pass  # state değişmiyor → hâlâ OPEN

        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        monkeypatch.setattr(chat_service, "cb_groq", DummyCB())
        sonuc = chat_service.ask_groq("test prompt")
        assert sonuc is None

    def test_api_key_yoksa_hata_mesaji_doner(self, monkeypatch):
        """Aktif provider bulunamazsa hata mesajı döner."""
        from services import chat_service

        class DummyBudget:
            def limit_asildimi(self):
                return False

        class DummyCB:
            OPEN = "open"
            CLOSED = "closed"
            state = "closed"

            def _gecis_kontrol(self):
                pass

        class DummyModelMgr:
            def model_sec_detayli(self, prompt, gorev_turu):
                return {"groq_idx": 0}

        class DummyRotator:
            def aktif_provider_al(self, **kwargs):
                return {"api_key": None, "model": "test-model", "max_tokens": 100}

        # GROQ_MODELS mock
        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        monkeypatch.setattr(chat_service, "cb_groq", DummyCB())
        monkeypatch.setattr(chat_service, "model_mgr", DummyModelMgr())
        monkeypatch.setattr(chat_service, "rotator", DummyRotator())

        import sys
        import types

        fake_api_rotator = types.ModuleType("api_rotator")
        fake_api_rotator.GROQ_MODELS = ["model-a"]
        monkeypatch.setitem(sys.modules, "api_rotator", fake_api_rotator)

        sonuc = chat_service.ask_groq("test prompt")
        assert sonuc is not None
        assert "Hata" in sonuc or "hata" in sonuc or "key" in sonuc.lower() or sonuc is None


class TestWebAramasiZenginlestir:
    """web_aramasiyla_zenginlestir() dallarını test eder."""

    def test_search_engine_exception_bos_string_doner(self, monkeypatch):
        """search_engine.search_and_read exception atarsa '' döner."""
        from services import chat_service

        class DummySearch:
            def search_and_read(self, soru):
                raise RuntimeError("ağ hatası")

        monkeypatch.setattr(chat_service, "search_engine", DummySearch())
        sonuc = chat_service.web_aramasiyla_zenginlestir("bitcoin fiyatı")
        assert sonuc == ""

    def test_kisa_sonuc_bos_doner(self, monkeypatch):
        """100 karakterden kısa sonuç → '' döner."""
        from services import chat_service

        class DummySearch:
            def search_and_read(self, soru):
                return "kısa"

        monkeypatch.setattr(chat_service, "search_engine", DummySearch())
        sonuc = chat_service.web_aramasiyla_zenginlestir("test")
        assert sonuc == ""

    def test_uzun_sonuc_2000_ile_kisaltilir(self, monkeypatch):
        """2000 karakterden uzun sonuç 2000'e kısaltılır."""
        from services import chat_service

        class DummySearch:
            def search_and_read(self, soru):
                return "x" * 3000

        monkeypatch.setattr(chat_service, "search_engine", DummySearch())
        sonuc = chat_service.web_aramasiyla_zenginlestir("test")
        assert len(sonuc) == 2000

    def test_yeterli_uzunlukta_sonuc_doner(self, monkeypatch):
        """100-2000 karakter arası sonuç olduğu gibi döner."""
        from services import chat_service

        class DummySearch:
            def search_and_read(self, soru):
                return "a" * 500

        monkeypatch.setattr(chat_service, "search_engine", DummySearch())
        sonuc = chat_service.web_aramasiyla_zenginlestir("test")
        assert len(sonuc) == 500


class TestAskLlamaLocal:
    """ask_llama_local() mock'lu dallarını test eder."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_lokal_hata_doner(self, monkeypatch):
        """cb_ollama.call CircuitOpenError atarsa 'Lokal Hata' döner."""
        from core.resilience import CircuitOpenError
        from services import chat_service

        class DummyCBOllama:
            async def call(self, fn, hard_timeout=None):
                raise CircuitOpenError("devre açık")

        monkeypatch.setattr(chat_service, "cb_ollama", DummyCBOllama())
        sonuc = await chat_service.ask_llama_local("test prompt")
        assert "Lokal Hata" in sonuc

    @pytest.mark.asyncio
    async def test_bos_yanit_lokal_hata_doner(self, monkeypatch):
        """Ollama boş yanıt dönünce 'Lokal Hata: bozuk' döner."""
        from services import chat_service

        class DummyCBOllama:
            async def call(self, fn, hard_timeout=None):
                return {"response": ""}

        monkeypatch.setattr(chat_service, "cb_ollama", DummyCBOllama())
        sonuc = await chat_service.ask_llama_local("test prompt")
        assert "Lokal Hata" in sonuc

    @pytest.mark.asyncio
    async def test_anlamli_yanit_doner(self, monkeypatch):
        """Yeterli alfabetik içerikli yanıt olduğu gibi döner."""
        from services import chat_service

        class DummyCBOllama:
            async def call(self, fn, hard_timeout=None):
                return {"response": "Bu bir test yanıtıdır ve yeterince uzundur."}

        monkeypatch.setattr(chat_service, "cb_ollama", DummyCBOllama())
        sonuc = await chat_service.ask_llama_local("test prompt")
        assert "Lokal Hata" not in sonuc
        assert len(sonuc) > 0


class TestBYapisalStresPromptEkDallar:
    """_b_yapisal_stres_prompt_mu() eksik dalları — satır 63."""

    def test_bos_string_false_doner(self):
        """Boş string → erken False (satır 63)."""
        from services.chat_service import _b_yapisal_stres_prompt_mu

        assert _b_yapisal_stres_prompt_mu("") is False

    def test_sadece_bosluk_false_doner(self):
        """Sadece boşluk → strip sonrası boş → False."""
        from services.chat_service import _b_yapisal_stres_prompt_mu

        assert _b_yapisal_stres_prompt_mu("   ") is False

    def test_cok_satirli_ve_anahtar_stres_sayilir(self):
        """5+ satır ve 3+ anahtar → stres prompt."""
        from services.chat_service import _b_yapisal_stres_prompt_mu

        prompt = "madde madde açıkla\nkarşılaştır\nörnek ver\nsenaryo yaz\nözet ekle\ndetay ver"
        assert _b_yapisal_stres_prompt_mu(prompt) is True

    def test_cok_sayisal_ve_uzun_stres_sayilir(self):
        """4+ sayı ve 140+ karakter → stres prompt."""
        from services.chat_service import _b_yapisal_stres_prompt_mu

        prompt = "1 2 3 4 rakamı olan bu prompt yeterince uzundur " + "x" * 100
        assert _b_yapisal_stres_prompt_mu(prompt) is True


class TestAbPromptTestiniHazirla:
    """ab_prompt_testini_hazirla() ve private alias dalları — satır 98-117, 122."""

    def test_ilk_cagri_motor_olusturur(self, monkeypatch):
        """_AB_PROMPT_TESTI None iken çağrılınca motor oluşturulur."""
        from services import chat_service

        # Global'i sıfırla
        monkeypatch.setattr(chat_service, "_AB_PROMPT_TESTI", None)

        class DummyMotor:
            _varyantlar = []

            def varyant_ekle(self, v):
                self._varyantlar.append(v)

        monkeypatch.setattr(chat_service, "ab_test_al_veya_olustur", lambda ad: DummyMotor())

        motor = chat_service.ab_prompt_testini_hazirla()
        assert motor is not None
        assert len(motor._varyantlar) == 2  # A_klasik + B_yapisal eklendi

    def test_ikinci_cagri_ayni_motoru_doner(self, monkeypatch):
        """_AB_PROMPT_TESTI dolu iken tekrar çağrılınca cache'den döner."""
        from services import chat_service

        class DummyMotor:
            pass

        sentinel = DummyMotor()
        monkeypatch.setattr(chat_service, "_AB_PROMPT_TESTI", sentinel)

        sonuc = chat_service.ab_prompt_testini_hazirla()
        assert sonuc is sentinel  # aynı nesne

    def test_private_alias_ayni_sonucu_doner(self, monkeypatch):
        """_ab_prompt_testini_hazirla() public fonksiyonla aynı sonucu döner (satır 122)."""
        from services import chat_service

        class DummyMotor:
            pass

        sentinel = DummyMotor()
        monkeypatch.setattr(chat_service, "_AB_PROMPT_TESTI", sentinel)

        assert chat_service._ab_prompt_testini_hazirla() is sentinel


class TestAbVaryantiUygulaFallbackYaratma:
    """_ab_varyanti_uygula içinde A_klasik bulunamayınca yeni Varyant yaratma — satır 142."""

    def test_a_klasik_bulunamazsa_yeni_varyant_olusturulur(self, monkeypatch):
        """Motor'da A_klasik yoksa fallback Varyant('A_klasik') yaratılır."""
        from services import chat_service

        class DummyVaryant:
            def __init__(self, ad, prompt_prefix):
                self.ad = ad
                self.konfig = {"prompt_prefix": prompt_prefix}
                self.aktif = True

        class DummyMotor:
            def __init__(self):
                # Sadece B_yapisal var, A_klasik YOK
                self._varyantlar = [DummyVaryant("B_yapisal", "PREFIX\n")]

            def varyant_sec(self, _):
                return self._varyantlar[0]  # B_yapisal döner

        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: DummyMotor())

        # Stres prompt → B_yapisal'den A_klasik'e fallback, ama A_klasik bulunamaz → yeni yaratılır
        stres_prompt = (
            "Python'da for ve while döngülerini karşılaştır. Aralarındaki 5 farkı "
            "madde madde ver; her biri için birer kod örneği, 2 yaygın hata, "
            "2 gerçek kullanım senaryosu ve en sonda 4 maddelik kısa özet ekle."
        )
        yeni_prompt, varyant = chat_service._ab_varyanti_uygula(stres_prompt, "genel", 42)

        assert varyant.ad == "A_klasik"
        assert yeni_prompt == stres_prompt  # prefix yok


class TestAskGroqModelMgrVeRotatorDallari:
    """ask_groq satır 180-181 (model_mgr exception) ve 214-215 (rotator TypeError)."""

    def test_model_mgr_exception_tercih_idx_1_olur(self, monkeypatch):
        """model_mgr.model_sec_detayli exception atarsa tercih_idx=1 ile devam eder."""
        from services import chat_service

        class DummyBudget:
            def limit_asildimi(self):
                return False

        class DummyCB:
            OPEN = "open"
            CLOSED = "closed"
            state = "closed"
            failures = 0
            threshold = 5

            def _gecis_kontrol(self):
                pass

        class DummyModelMgr:
            def model_sec_detayli(self, prompt, gorev_turu):
                raise RuntimeError("model mgr patladı")

        class DummyRotator:
            def aktif_provider_al(self, **kwargs):
                # api_key yok → erken çıkış "Groq Hata:" mesajı
                return {"api_key": None, "model": "test", "max_tokens": 100}

        import sys
        import types

        fake_api_rotator = types.ModuleType("api_rotator")
        fake_api_rotator.GROQ_MODELS = ["model-a"]
        monkeypatch.setitem(sys.modules, "api_rotator", fake_api_rotator)

        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        monkeypatch.setattr(chat_service, "cb_groq", DummyCB())
        monkeypatch.setattr(chat_service, "model_mgr", DummyModelMgr())
        monkeypatch.setattr(chat_service, "rotator", DummyRotator())

        sonuc = chat_service.ask_groq("test prompt")
        # api_key=None → "Groq Hata: aktif API key bulunamadi"
        assert "Hata" in sonuc or sonuc is None

    def test_rotator_typeerror_safe_provider_fallback(self, monkeypatch):
        """rotator.aktif_provider_al TypeError atarsa _safe_active_provider çağrılır (214-215)."""
        from services import chat_service

        class DummyBudget:
            def limit_asildimi(self):
                return False

        class DummyCB:
            OPEN = "open"
            CLOSED = "closed"
            state = "closed"
            failures = 0
            threshold = 5

            def _gecis_kontrol(self):
                pass

        class DummyModelMgr:
            def model_sec_detayli(self, prompt, gorev_turu):
                return {"groq_idx": 0}

        class DummyRotator:
            def aktif_provider_al(self, **kwargs):
                raise TypeError("beklenmeyen argüman")

        import sys
        import types

        fake_api_rotator = types.ModuleType("api_rotator")
        fake_api_rotator.GROQ_MODELS = ["model-a"]
        monkeypatch.setitem(sys.modules, "api_rotator", fake_api_rotator)

        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        monkeypatch.setattr(chat_service, "cb_groq", DummyCB())
        monkeypatch.setattr(chat_service, "model_mgr", DummyModelMgr())
        monkeypatch.setattr(chat_service, "rotator", DummyRotator())
        # _safe_active_provider da None dönsün → "Groq Hata:" mesajı
        monkeypatch.setattr(chat_service, "_safe_active_provider", lambda r: None)

        sonuc = chat_service.ask_groq("test prompt")
        assert "Hata" in sonuc or sonuc is None


class TestAskGroqBasariliYanit:
    """ask_groq() başarılı yanıt dalını mock Groq client ile test eder (221-284)."""

    def _ortak_monkeypatch(self, monkeypatch, chat_service, mock_yanit="Test yanıtı."):
        import sys
        import types

        class DummyBudget:
            def limit_asildimi(self):
                return False

        class DummyLock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        class DummyCB:
            OPEN = "open"
            CLOSED = "closed"
            state = "closed"
            failures = 0
            threshold = 5
            opened_at = 0
            _lock = DummyLock()

            def _gecis_kontrol(self):
                pass

        class DummyModelMgr:
            def model_sec_detayli(self, prompt, gorev_turu):
                return {"groq_idx": 0}

        class DummyRotator:
            def aktif_provider_al(self, **kwargs):
                return {"api_key": "test-key", "model": "test-model", "max_tokens": 100}

            def basari_kaydet(self, *args, **kwargs):
                pass

            def hata_kaydet(self, *args, **kwargs):
                pass

        yanit_ref = [mock_yanit]

        class FakeMessage:
            @property
            def content(self):
                return yanit_ref[0]

        class FakeChoice:
            message = FakeMessage()

        class FakeUsage:
            prompt_tokens = 10
            completion_tokens = 20

        class FakeResponse:
            choices = [FakeChoice()]
            usage = FakeUsage()

        class FakeGroqClient:
            def __init__(self, api_key):
                pass

            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        return FakeResponse()

        fake_api_rotator = types.ModuleType("api_rotator")
        fake_api_rotator.GROQ_MODELS = ["test-model"]
        monkeypatch.setitem(sys.modules, "api_rotator", fake_api_rotator)

        monkeypatch.setattr(chat_service, "budget", DummyBudget())
        monkeypatch.setattr(chat_service, "cb_groq", DummyCB())
        monkeypatch.setattr(chat_service, "model_mgr", DummyModelMgr())
        monkeypatch.setattr(chat_service, "rotator", DummyRotator())
        monkeypatch.setattr(chat_service, "Groq", FakeGroqClient)

    def test_basarili_yanit_doner(self, monkeypatch):
        """Mock Groq client ile başarılı yanıt senaryosu."""
        from services import chat_service

        self._ortak_monkeypatch(monkeypatch, chat_service, "Merhaba bu bir test yaniti.")
        sonuc = chat_service.ask_groq("test sorusu")
        assert sonuc == "Merhaba bu bir test yaniti."

    def test_aciklayici_not_temizlenir(self, monkeypatch):
        """(Aciklayici ...) parantezi yanıttan temizlenir."""
        from services import chat_service

        self._ortak_monkeypatch(
            monkeypatch, chat_service, "Yanit metni (Aciklayici not buraya) devam ediyor."
        )
        sonuc = chat_service.ask_groq("test sorusu")
        assert "(Aciklayici" not in sonuc
        assert "Yanit metni" in sonuc

    def test_not_parantezi_temizlenir(self, monkeypatch):
        """(Not: ...) parantezi yanıttan temizlenir."""
        from services import chat_service

        self._ortak_monkeypatch(
            monkeypatch, chat_service, "Cevap burada. (Not: bu kisim silinmeli)"
        )
        sonuc = chat_service.ask_groq("test sorusu")
        assert "(Not:" not in sonuc
        assert "Cevap burada" in sonuc


class TestAskLlamaLocalFineTuned:
    """ask_llama_local fine-tuned model dalını test eder (328-331)."""

    @pytest.mark.asyncio
    async def test_finetuned_model_aktifse_kullanilir(self, monkeypatch):
        """finetuning_runner aktif model döndürünce o model kullanılır."""
        import sys
        import types

        from services import chat_service

        fake_ft = types.ModuleType("finetuning_runner")
        fake_ft.aktif_model_al = lambda: {"aktif": True, "ollama_model": "fine-tuned-model-v1"}
        monkeypatch.setitem(sys.modules, "finetuning_runner", fake_ft)

        class DummyCBOllama:
            async def call(self, fn, hard_timeout=None):
                return {"response": "Fine-tuned model yaniti geldi buraya basariyla."}

        monkeypatch.setattr(chat_service, "cb_ollama", DummyCBOllama())
        sonuc = await chat_service.ask_llama_local("test prompt")
        assert "Lokal Hata" not in sonuc

    @pytest.mark.asyncio
    async def test_finetuned_aktif_degil_default_kullanilir(self, monkeypatch):
        """finetuning_runner aktif=False ise default model kullanılır."""
        import sys
        import types

        from services import chat_service

        fake_ft = types.ModuleType("finetuning_runner")
        fake_ft.aktif_model_al = lambda: {"aktif": False, "ollama_model": None}
        monkeypatch.setitem(sys.modules, "finetuning_runner", fake_ft)

        class DummyCBOllama:
            async def call(self, fn, hard_timeout=None):
                return {"response": "Default model yaniti yeterince uzun ve anlamlidir."}

        monkeypatch.setattr(chat_service, "cb_ollama", DummyCBOllama())
        sonuc = await chat_service.ask_llama_local("test prompt")
        assert "Lokal Hata" not in sonuc


class TestAskAiAnaDallar:
    """ask_ai() fonksiyonunun ana dallarini test eder (satir 498-825)."""

    def _mock_tumu(self, monkeypatch, cs, **kw):
        """ask_ai bagimliklarini toplu mock'la."""
        cache_hit = kw.get("cache_hit")
        secilen_model = kw.get("secilen_model", "lokal")
        provider = kw.get("provider")
        reward_val = kw.get("reward_val", 0.8)
        varyant = kw.get("varyant")
        memory_data = kw.get("memory_data", False)

        class DummyCache:
            def _key_olustur(self, prompt, gorev_turu):
                return f"{prompt}:{gorev_turu}"

            def al(self, key):
                return cache_hit

            def koy(self, key, value):
                pass

        class DummySupervisor:
            def mod_belirle(self, gorev_turu, prompt_text):
                return {"retrieval_depth": 2, "mod": "normal", "hafiza_destegi": True}

            def guclendir(self, basari):
                pass

        class DummyPolicy:
            def runtime_parametreleri_al(self, gorev_turu):
                return {"retrieval_depth": 2, "mod": "normal"}

            def guncelle(self, basari, sure):
                pass

        class DummyPromptEvo:
            def prompt_sec(self, gorev_turu):
                return None, None

            def sonuc_kaydet(self, prompt_id, basari):
                pass

        class DummyEpisodik:
            def ani_kaydet(self, **kwargs):
                pass

            def ani_bul(self, prompt, n=1):
                if memory_data:
                    return [{"baslik": "test_ani", "icerik": "ani icerik detay buraya"}]
                return []

        class DummyProsedur:
            def prosedur_kaydet(self, **kwargs):
                pass

            def prosedur_bul(self, prompt, gorev_turu):
                return "[Prosedur: test ref]" if memory_data else None

        class DummyMemory:
            episodik = DummyEpisodik()
            prosedur = DummyProsedur()

            def benzer_gorev_bul(self, prompt, n=3):
                return ["gecmis deneyim 1"] if memory_data else []

            def bilgi_ara(self, prompt, n=3):
                return ["ilgili bilgi 1"] if memory_data else []

            def hafizayi_guclendir(self, prompt, rwd):
                pass

        class DummyModelMgr:
            def model_sec(self, prompt, gorev_turu):
                return secilen_model

        class DummyRotator:
            def basari_kaydet(self, *a, **k):
                pass

            def hata_kaydet(self, *a, **k):
                pass

        class DummyRewardSys:
            def hesapla(self, basari, sure, token):
                return reward_val

        class DummyStrategyMgr:
            def imza_olustur(self, *a):
                return "imza"

            def sonuc_kaydet(self, *a):
                pass

        monkeypatch.setattr(cs, "yanit_cache", DummyCache())
        monkeypatch.setattr(cs, "supervisor", DummySupervisor())
        monkeypatch.setattr(cs, "policy", DummyPolicy())
        monkeypatch.setattr(cs, "prompt_evo", DummyPromptEvo())
        monkeypatch.setattr(cs, "memory", DummyMemory())
        monkeypatch.setattr(cs, "model_mgr", DummyModelMgr())
        monkeypatch.setattr(cs, "rotator", DummyRotator())
        monkeypatch.setattr(cs, "reward_sys", DummyRewardSys())
        monkeypatch.setattr(cs, "strategy_mgr", DummyStrategyMgr())
        monkeypatch.setattr(cs, "yeni_trace_id", lambda: "t-trace")
        monkeypatch.setattr(cs, "guncel_bilgi_gerekli_mi", lambda s: False)
        monkeypatch.setattr(cs, "_ab_varyanti_uygula", lambda p, g, k: (p, varyant))
        monkeypatch.setattr(cs, "_rag_build_context", lambda p, top_k=6: ("", []))
        monkeypatch.setattr(cs, "soru_hash_olustur", lambda s: "h123")
        monkeypatch.setattr(cs, "consistency_kaydet", lambda *a: None)
        monkeypatch.setattr(cs, "consistency_hesapla", lambda s: 0.5)
        monkeypatch.setattr(cs, "hata_siniflandir", lambda r: "yok")
        monkeypatch.setattr(cs, "confidence_hesapla", lambda *a: 0.85)
        monkeypatch.setattr(cs, "confidence_metni_olustur", lambda *a: "\n[Guven: 0.85]")
        monkeypatch.setattr(cs, "_safe_active_provider", lambda r: provider)
        monkeypatch.setenv("RAG_ENABLED", "0")

    # ------------------------------------------------------------------
    # Test 1: Cache hit — satir 507-509
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_cache_hit_dogrudan_doner(self, monkeypatch):
        """Cache'de yanit varsa dogrudan doner, hicbir islem yapilmaz."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, cache_hit="Cached yanit")
        sonuc = await chat_service.ask_ai("test sorusu")
        assert sonuc == "Cached yanit"

    # ------------------------------------------------------------------
    # Test 2: Lokal model basarili + hafiza + episodik + prosedur
    # Satir 511-563, 594-605, 697-735, 765-779, 816-821
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_lokal_basarili_hafiza_ve_episodik(self, monkeypatch):
        """Lokal model basarili, hafiza verileri var, episodik+prosedur kaydedilir."""
        from services import chat_service

        self._mock_tumu(
            monkeypatch,
            chat_service,
            secilen_model="lokal",
            reward_val=0.85,
            memory_data=True,
        )

        async def fake_llama(prompt):
            return (
                "Bu basarili bir yanittir ve yeterince uzundur.\n"
                "Adim 1: Ilk olarak bu islemi yapin detayli.\n"
                "Adim 2: Sonra bu adimi tamamlayin dikkatle.\n"
                "Adim 3: Son olarak kontrol edin ve bitirin."
            )

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu", hafiza_destegi=True)
        assert "basarili bir yanittir" in sonuc
        assert "[Guven:" in sonuc

    # ------------------------------------------------------------------
    # Test 3: Cloud Groq basarili — satir 609-643
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_cloud_groq_basarili(self, monkeypatch):
        """Cloud Groq provider basarili yanit doner."""
        from services import chat_service

        provider = {"name": "Groq", "api_key": "k", "model": "m", "max_tokens": 100}
        self._mock_tumu(
            monkeypatch, chat_service, secilen_model="cloud", provider=provider
        )
        monkeypatch.setattr(
            chat_service,
            "ask_groq",
            lambda p, g="genel": "Cloud Groq basarili yanit yeterince uzun olmali.",
        )
        sonuc = await chat_service.ask_ai("test sorusu")
        assert "Cloud Groq basarili" in sonuc

    # ------------------------------------------------------------------
    # Test 4: Tum cloud basarisiz → Ollama fallback — satir 691-694
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_cloud_basarisiz_ollama_fallback(self, monkeypatch):
        """Cloud ask_groq None doner, yedek ayni isim → Ollama fallback."""
        from services import chat_service

        provider = {"name": "Groq", "api_key": "k", "model": "m", "max_tokens": 100}
        self._mock_tumu(
            monkeypatch, chat_service, secilen_model="cloud", provider=provider
        )
        monkeypatch.setattr(chat_service, "ask_groq", lambda p, g="genel": None)

        async def fake_llama(prompt):
            return "Ollama fallback yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu")
        assert "Ollama fallback" in sonuc

    # ------------------------------------------------------------------
    # Test 5: Genel exception → ask_llama_local fallback — satir 823-825
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_genel_exception_llama_fallback(self, monkeypatch):
        """ask_ai icinde genel exception → ask_llama_local ile fallback."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service)

        class FailSupervisor:
            def mod_belirle(self, gorev_turu, prompt_text):
                raise RuntimeError("supervisor patladi")

        monkeypatch.setattr(chat_service, "supervisor", FailSupervisor())

        async def fake_llama(prompt):
            return "Exception fallback yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu")
        assert "Exception fallback" in sonuc

    # ------------------------------------------------------------------
    # Test 6: AB varyant B_yapisal sonuc kaydi — satir 781-814
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ab_varyant_b_yapisal_sonuc_kaydedilir(self, monkeypatch):
        """B_yapisal varyant secilmisse kalite kontrol + sonuc kaydedilir."""
        from services import chat_service

        class FakeVaryant:
            ad = "B_yapisal"
            konfig = {"prompt_prefix": ""}

        class FakeMotor:
            kayitlar = []

            def sonuc_kaydet(self, sonuc):
                self.kayitlar.append(sonuc)

        motor = FakeMotor()
        self._mock_tumu(
            monkeypatch,
            chat_service,
            secilen_model="lokal",
            varyant=FakeVaryant(),
            reward_val=0.8,
        )
        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: motor)

        async def fake_llama(prompt):
            return (
                "Bu yeterince uzun kaliteli bir yanittir ve B_yapisal "
                "kalite kontrolunden gecmelidir. Detayli bilgi icermektedir. "
                "Adim 1: Ilk adimdaki islem.\nAdim 2: Ikinci adim detay."
            )

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu")
        assert "yeterince uzun" in sonuc
        assert len(motor.kayitlar) == 1

    # ------------------------------------------------------------------
    # Test 7: Dusuk reward → consistency re-check — satir 743-761
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_dusuk_reward_consistency_recheck(self, monkeypatch):
        """smoothed_reward < 0.5 ise ikinci yanit alinip consistency hesaplanir."""
        from services import chat_service

        provider = {"name": "Groq", "api_key": "k", "model": "m", "max_tokens": 100}
        self._mock_tumu(
            monkeypatch,
            chat_service,
            secilen_model="lokal",
            reward_val=0.3,
            provider=provider,
        )

        async def fake_llama(prompt):
            return "Lokal yanit biraz kisa ama anlamli on karakter."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        monkeypatch.setattr(
            chat_service, "ask_groq", lambda p, g="genel": "ikinci yanit consistency icin"
        )
        sonuc = await chat_service.ask_ai("test sorusu")
        assert sonuc  # Yanit donmeli

    # ------------------------------------------------------------------
    # Test 8: prompt_sablon {soru} dali — satir 522-524
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_prompt_sablon_soru_uygulanir(self, monkeypatch):
        """prompt_evo {soru} sablonu varsa prompt'a uygulanir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8)

        class SablonluEvo:
            def prompt_sec(self, gorev_turu):
                return ("pid-1", "Su soruyu yanitla: {soru}")

            def sonuc_kaydet(self, pid, basari):
                pass

        monkeypatch.setattr(chat_service, "prompt_evo", SablonluEvo())

        async def fake_llama(prompt):
            return "Sablon uygulandi yanit yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu")
        assert sonuc

    # ------------------------------------------------------------------
    # Test 9: guncel_bilgi web zenginlestirme — satir 527-534
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_guncel_bilgi_web_zenginlestirme(self, monkeypatch):
        """guncel_bilgi_gerekli_mi True ise web_aramasiyla_zenginlestir cagirilir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8)
        monkeypatch.setattr(chat_service, "guncel_bilgi_gerekli_mi", lambda s: True)
        monkeypatch.setattr(
            chat_service,
            "web_aramasiyla_zenginlestir",
            lambda s: "Web bilgisi burada yeterince uzun ve detayli.",
        )

        async def fake_llama(prompt):
            return "Guncel bilgi yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("dolar kac lira?", gorev_turu="genel")
        assert sonuc

    # ------------------------------------------------------------------
    # Test 10: hafiza prosedur + episodik sonuc var — satir 548-560
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_hafiza_prosedur_ve_episodik_sonuc(self, monkeypatch):
        """Hafiza destegi acikken prosedur_bul ve ani_bul sonuclari prompt'a eklenir."""
        from services import chat_service

        self._mock_tumu(
            monkeypatch, chat_service, reward_val=0.8, memory_data=True
        )

        async def fake_llama(prompt):
            return "Hafiza destekli yanit yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test", hafiza_destegi=True)
        assert sonuc

    # ------------------------------------------------------------------
    # Test 11: prompt_id varsa sonuc_kaydet cagirilir — satir 707-708
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_prompt_id_varsa_sonuc_kaydedilir(self, monkeypatch):
        """prompt_evo bir prompt_id dondururse sonuc_kaydet cagirilir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8)

        kaydedilenler = []

        class TrackingEvo:
            def prompt_sec(self, gorev_turu):
                return ("pid-42", None)

            def sonuc_kaydet(self, pid, basari):
                kaydedilenler.append(pid)

        monkeypatch.setattr(chat_service, "prompt_evo", TrackingEvo())

        async def fake_llama(prompt):
            return "Prompt evo yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test")
        assert "pid-42" in kaydedilenler

    # ------------------------------------------------------------------
    # Test 12: AB sonuc kayit exception — satir 813-814
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ab_sonuc_kayit_exception_sessizce_gecilir(self, monkeypatch):
        """AB motor.sonuc_kaydet exception atarsa sessizce gecilir."""
        from services import chat_service

        class FakeVaryant:
            ad = "A_klasik"
            konfig = {"prompt_prefix": ""}

        class FailMotor:
            def sonuc_kaydet(self, sonuc):
                raise RuntimeError("kayit patladi")

        self._mock_tumu(
            monkeypatch, chat_service, secilen_model="lokal", varyant=FakeVaryant()
        )
        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: FailMotor())

        async def fake_llama(prompt):
            return "AB exception yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test")
        assert sonuc  # Exception yutulur, yanit doner

    # ------------------------------------------------------------------
    # Test 13: B_yapisal kalite reddedildi — satir 787-800
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_b_yapisal_kalite_reddedildi(self, monkeypatch):
        """B_yapisal kisa yanit → kalite reddi log'lanir."""
        from services import chat_service

        class FakeVaryant:
            ad = "B_yapisal"
            konfig = {"prompt_prefix": ""}

        class FakeMotor:
            kayitlar = []

            def sonuc_kaydet(self, sonuc):
                self.kayitlar.append(sonuc)

        motor = FakeMotor()
        self._mock_tumu(
            monkeypatch, chat_service, secilen_model="lokal", varyant=FakeVaryant(), reward_val=0.8
        )
        monkeypatch.setattr(chat_service, "ab_prompt_testini_hazirla", lambda: motor)

        async def fake_llama(prompt):
            # Kisa yanit — B_yapisal kalite kontrolunden gecemez
            return "Cok kisa."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test")
        assert sonuc
        assert len(motor.kayitlar) == 1

    # ------------------------------------------------------------------
    # Test 14: prompt_sablon {prompt} dali — satir 522
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_prompt_sablon_prompt_uygulanir(self, monkeypatch):
        """prompt_evo {prompt} sablonu varsa prompt'a uygulanir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8)

        class SablonluEvo:
            def prompt_sec(self, gorev_turu):
                return ("pid-2", "Detayli yanit ver: {prompt}")

            def sonuc_kaydet(self, pid, basari):
                pass

        monkeypatch.setattr(chat_service, "prompt_evo", SablonluEvo())

        async def fake_llama(prompt):
            return "Prompt sablon yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test sorusu")
        assert sonuc

    # ------------------------------------------------------------------
    # Test 15: prosedur_bul exception → except dali — satir 551-552
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_prosedur_bul_exception_sessizce_gecilir(self, monkeypatch):
        """memory.prosedur.prosedur_bul exception atarsa sessizce gecilir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8, memory_data=True)

        class FailProsedur:
            def prosedur_kaydet(self, **kw):
                pass

            def prosedur_bul(self, prompt, gorev_turu):
                raise RuntimeError("prosedur patladi")

        chat_service.memory.prosedur = FailProsedur()

        async def fake_llama(prompt):
            return "Prosedur exception yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test", hafiza_destegi=True)
        assert sonuc

    # ------------------------------------------------------------------
    # Test 16: ani_bul exception → except dali — satir 559-560
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ani_bul_exception_sessizce_gecilir(self, monkeypatch):
        """memory.episodik.ani_bul exception atarsa sessizce gecilir."""
        from services import chat_service

        self._mock_tumu(monkeypatch, chat_service, reward_val=0.8, memory_data=True)

        class FailEpisodik:
            def ani_kaydet(self, **kw):
                pass

            def ani_bul(self, prompt, n=1):
                raise RuntimeError("episodik patladi")

        chat_service.memory.episodik = FailEpisodik()

        async def fake_llama(prompt):
            return "Episodik exception yaniti yeterince uzun ve anlamli."

        monkeypatch.setattr(chat_service, "ask_llama_local", fake_llama)
        sonuc = await chat_service.ask_ai("test", hafiza_destegi=True)
        assert sonuc
