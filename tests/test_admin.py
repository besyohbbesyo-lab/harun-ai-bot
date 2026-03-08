import types

import pytest

from handlers import admin as admin_mod


class DummyMessage:
    def __init__(self, user_id=123):
        self.from_user = types.SimpleNamespace(id=user_id, username="tester")
        self.sent = []

    async def reply_text(self, text, *args, **kwargs):
        self.sent.append(text)


class DummyUpdate:
    def __init__(self, user_id=123):
        self.message = DummyMessage(user_id=user_id)


@pytest.mark.asyncio
async def test_abtest_command_bos_durum(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
    monkeypatch.setattr(admin_mod, "tum_testler_istatistik", lambda: {})

    update = DummyUpdate()
    context = types.SimpleNamespace(args=[])
    await admin_mod.abtest_command(update, context)

    assert update.message.sent
    assert "A/B test kaydi yok." in update.message.sent[-1]


@pytest.mark.asyncio
async def test_abtest_command_istatistik_gosterir(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
    monkeypatch.setattr(
        admin_mod,
        "tum_testler_istatistik",
        lambda: {
            "yanit_stili_v1": {
                "toplam_sonuc": 3,
                "varyantlar": {
                    "A_klasik": {
                        "toplam": 3,
                        "basari_orani": 1.0,
                        "ort_sure_ms": 123.4,
                    }
                },
            }
        },
    )

    update = DummyUpdate()
    context = types.SimpleNamespace(args=[])
    await admin_mod.abtest_command(update, context)

    assert update.message.sent
    metin = update.message.sent[-1]
    assert "A/B Test Ozeti:" in metin
    assert "yanit_stili_v1" in metin
    assert "A_klasik" in metin


@pytest.mark.asyncio
async def test_ab_force_command_mevcut_kullaniciyi_zorlar(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
    cagri = {}

    def fake_force(test_adi, user_id, varyant_adi):
        cagri["test_adi"] = test_adi
        cagri["user_id"] = user_id
        cagri["varyant_adi"] = varyant_adi

    monkeypatch.setattr(admin_mod, "kullaniciyi_varyanta_zorla", fake_force)

    update = DummyUpdate(user_id=555)
    context = types.SimpleNamespace(args=["yanit_stili_v1", "B_yapisal"])
    await admin_mod.ab_force_command(update, context)

    assert cagri == {
        "test_adi": "yanit_stili_v1",
        "user_id": "555",
        "varyant_adi": "B_yapisal",
    }
    assert "Varyant: B_yapisal" in update.message.sent[-1]


@pytest.mark.asyncio
async def test_ab_force_command_hedef_user_id_alir(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
    cagri = {}

    def fake_force(test_adi, user_id, varyant_adi):
        cagri["test_adi"] = test_adi
        cagri["user_id"] = user_id
        cagri["varyant_adi"] = varyant_adi

    monkeypatch.setattr(admin_mod, "kullaniciyi_varyanta_zorla", fake_force)

    update = DummyUpdate(user_id=555)
    context = types.SimpleNamespace(args=["yanit_stili_v1", "B_yapisal", "999"])
    await admin_mod.ab_force_command(update, context)

    assert cagri["user_id"] == "999"


@pytest.mark.asyncio
async def test_ab_force_command_hata_doner(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)

    def fake_force(test_adi, user_id, varyant_adi):
        raise ValueError("varyant yok")

    monkeypatch.setattr(admin_mod, "kullaniciyi_varyanta_zorla", fake_force)

    update = DummyUpdate(user_id=555)
    context = types.SimpleNamespace(args=["yanit_stili_v1", "B_yapisal"])
    await admin_mod.ab_force_command(update, context)

    assert "A/B force hatasi" in update.message.sent[-1]


async def _async_true():
    return True


@pytest.mark.asyncio
async def test_ab_force_command_yanit_stili_testini_once_hazirlar(monkeypatch):
    monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
    monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
    hazir = {"ok": False}
    cagri = {}

    def fake_hazirla():
        hazir["ok"] = True

    def fake_force(test_adi, user_id, varyant_adi):
        cagri["test_adi"] = test_adi
        cagri["user_id"] = user_id
        cagri["varyant_adi"] = varyant_adi

    monkeypatch.setattr(admin_mod, "ab_prompt_testini_hazirla", fake_hazirla)
    monkeypatch.setattr(admin_mod, "kullaniciyi_varyanta_zorla", fake_force)

    update = DummyUpdate(user_id=555)
    context = types.SimpleNamespace(args=["yanit_stili_v1", "B_yapisal"])
    await admin_mod.ab_force_command(update, context)

    assert hazir["ok"] is True
    assert cagri == {
        "test_adi": "yanit_stili_v1",
        "user_id": "555",
        "varyant_adi": "B_yapisal",
    }


# ── YENİ TESTLER ──────────────────────────────────────────────────────────────


class TestStartCommand:
    @pytest.mark.asyncio
    async def test_start_mesaj_gonderir(self):
        """start() her kullanıcıya karşılama mesajı gönderir."""
        from handlers import admin as admin_mod

        update = DummyUpdate()
        await admin_mod.start(update, None)
        assert update.message.sent
        assert "Harun AI Bot" in update.message.sent[0]

    @pytest.mark.asyncio
    async def test_start_yetki_kontrolu_yok(self):
        """start() yetki kontrolü yapmaz — herkes erişebilir."""
        from handlers import admin as admin_mod

        update = DummyUpdate(user_id=999)  # yetkisiz kullanıcı
        await admin_mod.start(update, None)
        assert update.message.sent  # mesaj gönderildi


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_yetkili_kullanici_help_alir(self, monkeypatch):
        """Yetkili kullanıcı /help çağırınca komut listesi gelir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "VISION_AKTIF", True)

        update = DummyUpdate()
        await admin_mod.help_command(update, None)
        assert update.message.sent
        metin = update.message.sent[-1]
        assert "/status" in metin
        assert "/chat" in metin

    @pytest.mark.asyncio
    async def test_yetkisiz_kullanici_help_almaz(self, monkeypatch):
        """Yetkisiz kullanıcı /help çağırınca mesaj gönderilmez."""
        from handlers import admin as admin_mod

        async def _async_false():
            return False

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_false())

        update = DummyUpdate(user_id=999)
        await admin_mod.help_command(update, None)
        assert not update.message.sent

    @pytest.mark.asyncio
    async def test_vision_devre_disi_help_gosterir(self, monkeypatch):
        """VISION_AKTIF=False iken help mesajında 'Devre disi' yazar."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "VISION_AKTIF", False)

        update = DummyUpdate()
        await admin_mod.help_command(update, None)
        assert "Devre disi" in update.message.sent[-1]


class TestAbtestOzetMetni:
    """_abtest_ozet_metni() doğrudan test eder."""

    def test_ab_aktif_degil_mesaji(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_AB_AKTIF", False)
        sonuc = admin_mod._abtest_ozet_metni()
        assert "aktif degil" in sonuc

    def test_istatistik_bos_kayit_yok(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
        monkeypatch.setattr(admin_mod, "tum_testler_istatistik", lambda: {})
        sonuc = admin_mod._abtest_ozet_metni()
        assert "kaydi yok" in sonuc

    def test_istatistik_exception_hatasi(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
        monkeypatch.setattr(
            admin_mod,
            "tum_testler_istatistik",
            lambda: (_ for _ in ()).throw(RuntimeError("db hatasi")),
        )
        sonuc = admin_mod._abtest_ozet_metni()
        assert "hata" in sonuc.lower()

    def test_varyant_yok_satiri_eklenir(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
        monkeypatch.setattr(
            admin_mod,
            "tum_testler_istatistik",
            lambda: {"test_v1": {"toplam_sonuc": 0, "varyantlar": {}}},
        )
        sonuc = admin_mod._abtest_ozet_metni()
        assert "varyant yok" in sonuc

    def test_varyant_detaylari_gosterilir(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)
        monkeypatch.setattr(
            admin_mod,
            "tum_testler_istatistik",
            lambda: {
                "test_v1": {
                    "toplam_sonuc": 5,
                    "varyantlar": {
                        "A_klasik": {"toplam": 5, "basari_orani": 0.8, "ort_sure_ms": 200.0}
                    },
                }
            },
        )
        sonuc = admin_mod._abtest_ozet_metni()
        assert "A_klasik" in sonuc
        assert "80.0" in sonuc


class TestAbForceCommandEksDallar:
    @pytest.mark.asyncio
    async def test_ab_aktif_degil_mesaj_gonderir(self, monkeypatch):
        """_AB_AKTIF=False iken uyarı mesajı gönderilir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "_AB_AKTIF", False)

        update = DummyUpdate()
        context = types.SimpleNamespace(args=["test", "varyant"])
        await admin_mod.ab_force_command(update, context)
        assert "aktif degil" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_args_eksik_kullanim_mesaji(self, monkeypatch):
        """args < 2 iken kullanım açıklaması gönderilir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "_AB_AKTIF", True)

        update = DummyUpdate()
        context = types.SimpleNamespace(args=["sadece_bir_arg"])
        await admin_mod.ab_force_command(update, context)
        assert "Kullanim" in update.message.sent[-1]


class TestFinetuningBaslat:
    @pytest.mark.asyncio
    async def test_yetkili_baslatma_mesaji(self, monkeypatch):
        """Yetkili kullanıcı fine-tuning başlatır."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())

        update = DummyUpdate()
        await admin_mod.finetuning_baslat(update, None)
        assert update.message.sent
        assert "Fine-tuning" in update.message.sent[-1]


class TestMetricsCommand:
    @pytest.mark.asyncio
    async def test_metrics_aktif_ozet_gonderir(self, monkeypatch):
        """_METRICS_AKTIF=True iken metrik özeti gönderilir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "_METRICS_AKTIF", True)

        class FakeMetrics:
            def ozet_metni(self):
                return "CPU: %5, RAM: %30"

        monkeypatch.setattr(admin_mod, "_metrics", FakeMetrics())

        update = DummyUpdate()
        await admin_mod.metrics_command(update, None)
        assert update.message.sent
        assert "CPU" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_metrics_devre_disi_mesaj(self, monkeypatch):
        """_METRICS_AKTIF=False iken devre dışı mesajı gönderilir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "_METRICS_AKTIF", False)

        update = DummyUpdate()
        await admin_mod.metrics_command(update, None)
        assert "aktif" in update.message.sent[-1].lower()

    @pytest.mark.asyncio
    async def test_metrics_exception_hata_mesaji(self, monkeypatch):
        """metrics exception atarsa hata mesajı gönderilir."""
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda update: _async_true())
        monkeypatch.setattr(admin_mod, "_METRICS_AKTIF", True)

        class PatlayenMetrics:
            def ozet_metni(self):
                raise RuntimeError("metrics patladı")

        monkeypatch.setattr(admin_mod, "_metrics", PatlayenMetrics())

        update = DummyUpdate()
        await admin_mod.metrics_command(update, None)
        assert "hata" in update.message.sent[-1].lower()


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_yetkisiz_erisim_engellenir(self, monkeypatch):
        from handlers import admin as admin_mod

        async def _false():
            return False

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _false())
        update = DummyUpdate()
        await admin_mod.status_command(update, None)
        assert not update.message.sent

    @pytest.mark.asyncio
    async def test_yetkili_durum_mesaji_gonderir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        monkeypatch.setattr(admin_mod, "VISION_AKTIF", False)
        monkeypatch.setattr(admin_mod, "_METRICS_AKTIF", False)
        monkeypatch.setattr(admin_mod, "_AB_AKTIF", False)

        fake_memory = _types.SimpleNamespace(hafiza_ozeti=lambda: "Hafiza OK")
        fake_rotator = _types.SimpleNamespace(durum_ozeti=lambda: "Rotator OK")
        fake_budget = _types.SimpleNamespace(durum_ozeti=lambda: "Budget OK")
        fake_policy = _types.SimpleNamespace(ozet=lambda: "Policy OK")

        import core.globals as _g

        monkeypatch.setattr(_g, "uptime_hesapla", lambda: "1s")
        monkeypatch.setattr(admin_mod, "memory", fake_memory)
        monkeypatch.setattr(admin_mod, "rotator", fake_rotator)
        monkeypatch.setattr(admin_mod, "budget", fake_budget)
        monkeypatch.setattr(admin_mod, "policy", fake_policy)

        update = DummyUpdate()
        await admin_mod.status_command(update, None)
        assert update.message.sent
        assert "Groq" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_metrics_aktifse_ozet_eklenir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        monkeypatch.setattr(admin_mod, "VISION_AKTIF", True)
        monkeypatch.setattr(admin_mod, "_METRICS_AKTIF", True)
        monkeypatch.setattr(admin_mod, "_AB_AKTIF", False)

        fake_memory = _types.SimpleNamespace(hafiza_ozeti=lambda: "")
        fake_rotator = _types.SimpleNamespace(durum_ozeti=lambda: "")
        fake_budget = _types.SimpleNamespace(durum_ozeti=lambda: "")
        fake_policy = _types.SimpleNamespace(ozet=lambda: "")

        class FakeMetrics:
            def ozet_metni(self):
                return "METRICS_DATA"

        import core.globals as _g

        monkeypatch.setattr(_g, "uptime_hesapla", lambda: "5m")
        monkeypatch.setattr(admin_mod, "memory", fake_memory)
        monkeypatch.setattr(admin_mod, "rotator", fake_rotator)
        monkeypatch.setattr(admin_mod, "budget", fake_budget)
        monkeypatch.setattr(admin_mod, "policy", fake_policy)
        monkeypatch.setattr(admin_mod, "_metrics", FakeMetrics())

        update = DummyUpdate()
        await admin_mod.status_command(update, None)
        assert "METRICS_DATA" in update.message.sent[-1]


class TestGuvenlikCommand:
    @pytest.mark.asyncio
    async def test_yetkili_guvenlik_ozeti_gonderir(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        monkeypatch.setattr(admin_mod, "guvenlik_ozeti", lambda: "Guvenlik: OK")

        update = DummyUpdate()
        await admin_mod.guvenlik_command(update, None)
        assert update.message.sent
        assert "Guvenlik" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_yetkisiz_engellenir(self, monkeypatch):
        from handlers import admin as admin_mod

        async def _false():
            return False

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _false())
        update = DummyUpdate()
        await admin_mod.guvenlik_command(update, None)
        assert not update.message.sent


class TestApiCommand:
    @pytest.mark.asyncio
    async def test_yetkili_rotator_durumu_gonderir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        monkeypatch.setattr(
            admin_mod, "rotator", _types.SimpleNamespace(durum_ozeti=lambda: "API Durum: OK")
        )

        update = DummyUpdate()
        await admin_mod.api_command(update, None)
        assert "API Durum" in update.message.sent[-1]


class TestAeeCommand:
    @pytest.mark.asyncio
    async def test_yetkili_aee_mesaji_gonderir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        ns = lambda txt: _types.SimpleNamespace(ozet=lambda: txt, durum_ozeti=lambda: txt)
        monkeypatch.setattr(admin_mod, "policy", ns("POLICY"))
        monkeypatch.setattr(admin_mod, "reward_sys", ns("REWARD"))
        monkeypatch.setattr(admin_mod, "strategy_mgr", ns("STRATEGY"))
        monkeypatch.setattr(admin_mod, "supervisor", ns("SUPERVISOR"))
        monkeypatch.setattr(admin_mod, "prompt_evo", ns("PROMPT"))
        monkeypatch.setattr(admin_mod, "rotator", ns("ROTATOR"))
        monkeypatch.setattr(admin_mod, "model_mgr", ns("MODEL"))

        class FakeEgitim:
            def hata_istatistigi(self):
                return {}

        monkeypatch.setattr(admin_mod, "egitim", FakeEgitim())

        update = DummyUpdate()
        await admin_mod.aee_command(update, None)
        assert update.message.sent
        assert "AEE" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_hata_istatistigi_varsa_eklenir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        ns = lambda txt: _types.SimpleNamespace(ozet=lambda: txt, durum_ozeti=lambda: txt)
        monkeypatch.setattr(admin_mod, "policy", ns(""))
        monkeypatch.setattr(admin_mod, "reward_sys", ns(""))
        monkeypatch.setattr(admin_mod, "strategy_mgr", ns(""))
        monkeypatch.setattr(admin_mod, "supervisor", ns(""))
        monkeypatch.setattr(admin_mod, "prompt_evo", ns(""))
        monkeypatch.setattr(admin_mod, "rotator", ns(""))
        monkeypatch.setattr(admin_mod, "model_mgr", ns(""))

        class FakeEgitim:
            def hata_istatistigi(self):
                return {"timeout": 3, "api_error": 1}

        monkeypatch.setattr(admin_mod, "egitim", FakeEgitim())

        update = DummyUpdate()
        await admin_mod.aee_command(update, None)
        assert "Basarisiz" in update.message.sent[-1]


class TestEgitimInceleCommand:
    @pytest.mark.asyncio
    async def test_bekleyen_kayit_yok_stats_gosterir(self, monkeypatch):
        import types as _types

        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def listele_reward(self, status, limit):
                return []

            def stats(self):
                return {"NEW": 5}

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        await admin_mod.egitim_incele_command(update, None)
        assert "bekleyen" in update.message.sent[-1].lower()

    @pytest.mark.asyncio
    async def test_bekleyen_kayitlar_listelenir(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def listele_reward(self, status, limit):
                return [
                    {
                        "id": "abc123",
                        "smoothed_reward": 0.8,
                        "gorev_turu": "genel",
                        "prompt_preview": "test sorusu",
                    }
                ]

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        await admin_mod.egitim_incele_command(update, None)
        assert "abc123" in update.message.sent[-1]


class TestEgitimOnaylaCommand:
    @pytest.mark.asyncio
    async def test_args_yok_kullanim_mesaji(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        update = DummyUpdate()
        context = types.SimpleNamespace(args=[])
        await admin_mod.egitim_onayla_command(update, context)
        assert "Kullanim" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_tekil_onay_basarili(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def status_degistir(self, rid, status, actor):
                return {"ok": True}

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        context = types.SimpleNamespace(args=["kayit-id-123"])
        await admin_mod.egitim_onayla_command(update, context)
        assert "onaylandi" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_toplu_onay(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def onayla_toplu(self, n, actor):
                return {"count": n}

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        context = types.SimpleNamespace(args=["toplu", "5"])
        await admin_mod.egitim_onayla_command(update, context)
        assert "Toplu Onay" in update.message.sent[-1]


class TestEgitimReddetCommand:
    @pytest.mark.asyncio
    async def test_args_yok_kullanim_mesaji(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())
        update = DummyUpdate()
        context = types.SimpleNamespace(args=[])
        await admin_mod.egitim_reddet_command(update, context)
        assert "Kullanim" in update.message.sent[-1]

    @pytest.mark.asyncio
    async def test_reddet_basarili(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def status_degistir(self, rid, status, actor):
                return {"ok": True}

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        context = types.SimpleNamespace(args=["kayit-id-456"])
        await admin_mod.egitim_reddet_command(update, context)
        assert "reddedildi" in update.message.sent[-1]


class TestEgitimStatsCommand:
    @pytest.mark.asyncio
    async def test_stats_gosterilir(self, monkeypatch):
        from handlers import admin as admin_mod

        monkeypatch.setattr(admin_mod, "_yetki_kontrol", lambda u: _async_true())

        class FakeStore:
            def stats(self):
                return {"NEW": 10, "PENDING_REVIEW": 3, "APPROVED": 5, "REJECTED": 1, "TOTAL": 19}

            def rapor(self):
                return {"avg_reward": {"NEW": 0.7}, "avg_reward_v1": {}, "avg_reward_v2": {}}

        monkeypatch.setattr(admin_mod, "egitim_store", FakeStore())

        update = DummyUpdate()
        await admin_mod.egitim_stats_command(update, None)
        assert update.message.sent
        assert "TOPLAM" in update.message.sent[-1]
