# egitim_plugin.py - Otomatik Fine-Tuning Sistemi
import asyncio
import json
import threading
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

BASE_DIR = Path(__file__).parent.resolve()
EGITIM_DOSYASI = BASE_DIR / "egitim_verisi.jsonl"
OTOMATIK_AYAR = BASE_DIR / "otomatik_egitim.json"

# Global durum
_egitim_aktif = False
_bot_app = None  # telegram application referansi

# Kac ornekte bir egitim tetiklensin
OTOMATIK_ESIK = 500  # Asama 7: 200'den 500'e ciktirildi (overfitting onlemek icin)


def bot_app_kaydet(app):
    """telegram_bot.py baslangicta bunu cagirarak app referansini verir"""
    global _bot_app
    _bot_app = app


def _ayar_yukle() -> dict:
    try:
        if OTOMATIK_AYAR.exists():
            with open(OTOMATIK_AYAR, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"son_egitim_ornegi": 0, "toplam_egitim": 0}


def _ayar_kaydet(ayar: dict):
    try:
        with open(OTOMATIK_AYAR, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _ornek_sayisi() -> int:
    try:
        if not EGITIM_DOSYASI.exists():
            return 0
        return sum(1 for _ in open(EGITIM_DOSYASI, encoding="utf-8"))
    except Exception:
        return 0


async def otomatik_egitim_kontrol(chat_id: int):
    """
    Her gorev sonrasi cagrilir.
    Esige ulasilinca kullaniciya Telegram bildirimi gonder.
    """
    global _egitim_aktif, _bot_app

    if _egitim_aktif:
        return
    if _bot_app is None:
        return

    ayar = _ayar_yukle()
    toplam = _ornek_sayisi()
    son_egitim = ayar.get("son_egitim_ornegi", 0)
    yeni_ornek = toplam - son_egitim

    if yeni_ornek >= OTOMATIK_ESIK:
        try:
            await _bot_app.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"Otomatik Egitim Bildirimi!\n\n"
                    f"Son egitimden bu yana {yeni_ornek} yeni ornek birikte.\n"
                    f"Toplam: {toplam} kayit\n\n"
                    f"Fine-tuning baslatmak istiyor musun?\n"
                    f"Evet icin: evet\n"
                    f"Hayir icin: hayir\n\n"
                    f"(Hayir dersen bir sonraki {OTOMATIK_ESIK} ornekte tekrar soracagim)"
                ),
            )
            # Onay bekleme modunu kaydet
            ayar["onay_bekliyor"] = True
            ayar["onay_chat_id"] = chat_id
            ayar["bildirim_ornegi"] = toplam
            _ayar_kaydet(ayar)
        except Exception as e:
            print(f"Otomatik egitim bildirimi hatasi: {e}")


# ─────────────────────────────────────────────────────────────
# KOMUT: /egitim
# ─────────────────────────────────────────────────────────────


async def egitim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _egitim_aktif

    if _egitim_aktif:
        await update.message.reply_text("Zaten bir egitim sureci aktif!\n" "Tamamlanmasini bekle.")
        return

    await update.message.reply_text("Egitim verisi analiz ediliyor...")

    try:
        from finetuning_runner import durum_ozeti, veri_donustur

        durum = durum_ozeti()
        await update.message.reply_text(durum)

        await update.message.reply_text("Veri kalite filtresi uygulanıyor (min 0.7 skor)...")
        sonuc = veri_donustur(min_kalite=0.7)

        if not sonuc["basari"]:
            await update.message.reply_text(f"Hata: {sonuc['mesaj']}")
            return

        gecen = sonuc["gecen"]

        if gecen < 50:
            await update.message.reply_text(
                f"Uyari: Sadece {gecen} kaliteli ornek var.\n"
                f"Fine-tuning icin en az 50 ornek onerilir.\n"
                f"Bot kullanilmaya devam edildikce veri birikecek."
            )
            return

        await update.message.reply_text(
            f"Fine-Tuning Hazir!\n\n"
            f"Toplam ham veri: {sonuc['toplam']}\n"
            f"Kaliteli ornek: {gecen}\n"
            f"Elenen: {sonuc['elenen']}\n\n"
            f"Model: Llama-3.2-3B-Instruct\n"
            f"Epoch: 3\n"
            f"Tahmini sure: 30-60 dakika\n\n"
            f"Baslatmak istiyor musun?\n"
            f"Evet icin: evet\n"
            f"Hayir icin: hayir"
        )

        ayar = _ayar_yukle()
        ayar["onay_bekliyor"] = True
        ayar["onay_chat_id"] = update.message.chat_id
        ayar["bildirim_ornegi"] = _ornek_sayisi()
        _ayar_kaydet(ayar)

    except Exception as e:
        await update.message.reply_text(f"Egitim hazırlık hatasi: {e}")


# ─────────────────────────────────────────────────────────────
# ONAY KONTROLU - handle_message'dan cagirilir
# ─────────────────────────────────────────────────────────────


async def egitim_onay_kontrol(
    mesaj: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    ayar = _ayar_yukle()

    if not ayar.get("onay_bekliyor"):
        return False

    # Sadece dogru chat'ten gelen onay
    if ayar.get("onay_chat_id") and ayar["onay_chat_id"] != update.message.chat_id:
        return False

    if any(k in mesaj.lower() for k in ["evet", "basla", "tamam", "olur", "yes"]):
        ayar["onay_bekliyor"] = False
        _ayar_kaydet(ayar)
        await _finetuning_baslat(update)
        return True

    elif any(k in mesaj.lower() for k in ["hayir", "sonra", "dur", "no", "iptal"]):
        ayar["onay_bekliyor"] = False
        # Esigi ilerlet - bir sonraki 500 ornekte tekrar soracak
        ayar["son_egitim_ornegi"] = _ornek_sayisi()
        _ayar_kaydet(ayar)
        await update.message.reply_text(
            "Tamam, ertelendi.\n" f"Bir sonraki {OTOMATIK_ESIK} ornekte tekrar soracagim."
        )
        return True

    return False


# ─────────────────────────────────────────────────────────────
# FINE-TUNING BASLAT
# ─────────────────────────────────────────────────────────────


async def _finetuning_baslat(update: Update):
    global _egitim_aktif

    _egitim_aktif = True
    chat_id = update.message.chat_id

    await update.message.reply_text(
        "Fine-tuning baslatildi!\n\n"
        "30-60 dakika surebilir.\n"
        "Bilgisayarin kapanmamasi onemli.\n"
        "Ilerlemeyi buradan takip edebilirsin..."
    )

    async def bildir(mesaj: str):
        try:
            await _bot_app.bot.send_message(chat_id=chat_id, text=f"Egitim: {mesaj}")
        except Exception:
            pass

    def egitim_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def calistir():
            global _egitim_aktif
            try:
                from finetuning_runner import finetuning_baslat, veri_donustur

                await bildir("Veri hazırlanıyor...")
                veri_donustur(min_kalite=0.7)

                sonuc = await loop.run_in_executor(
                    None,
                    lambda: finetuning_baslat(
                        model_adi="unsloth/Llama-3.2-3B-Instruct",
                        epoch=3,
                        batch_size=2,
                        ilerleme_callback=lambda m: asyncio.run_coroutine_threadsafe(
                            bildir(m), loop
                        ).result(),
                    ),
                )

                if sonuc["basari"]:
                    # Sayaci guncelle
                    ayar = _ayar_yukle()
                    ayar["son_egitim_ornegi"] = _ornek_sayisi()
                    ayar["toplam_egitim"] = ayar.get("toplam_egitim", 0) + 1
                    ayar["onay_bekliyor"] = False
                    _ayar_kaydet(ayar)

                    await _bot_app.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"Fine-tuning tamamlandi!\n\n"
                            f"{sonuc['mesaj']}\n\n"
                            f"Toplam egitim sayisi: {ayar['toplam_egitim']}\n"
                            f"Botu yeniden baslat: Ctrl+C, sonra python telegram_bot.py"
                        ),
                    )
                else:
                    await _bot_app.bot.send_message(
                        chat_id=chat_id, text=f"Fine-tuning basarisiz:\n{sonuc['mesaj']}"
                    )

            except Exception as e:
                await _bot_app.bot.send_message(chat_id=chat_id, text=f"Egitim hatasi: {e}")
            finally:
                _egitim_aktif = False

        loop.run_until_complete(calistir())
        loop.close()

    t = threading.Thread(target=egitim_thread, daemon=True)
    t.start()
