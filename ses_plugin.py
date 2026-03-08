"""
ses_plugin.py — Harun AI Sesli Mesaj Desteği
Aşama 11: Telegram'dan gelen OGG sesli mesajları metne çevirir.
Motor: Google Speech Recognition (ücretsiz, internet gerekli)
Gereksinimler: pip install SpeechRecognition pydub
Sistem: ffmpeg kurulu olmalı (ses dönüşümü için)
"""

import logging
import os
from pathlib import Path

import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
TEMP_DIR = BASE_DIR / "temp_ses"
TEMP_DIR.mkdir(exist_ok=True)


class SesPlugin:
    """
    Telegram'dan gelen sesli mesajları (OGG/OPUS) alır,
    WAV formatına çevirir ve Google STT ile metne dönüştürür.
    """

    def __init__(self, dil: str = "tr-TR"):
        self.dil = dil
        self.recognizer = sr.Recognizer()
        # Gürültüye karşı hassasiyet ayarları
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        logger.info(f"[SES] SesPlugin baslatildi. Dil: {self.dil}")

    def ogg_wav_cevir(self, ogg_yolu: Path) -> Path:
        """OGG/OPUS dosyasını WAV formatına çevirir."""
        wav_yolu = TEMP_DIR / (ogg_yolu.stem + ".wav")
        try:
            ses = AudioSegment.from_ogg(str(ogg_yolu))
            # Mono, 16kHz — Google STT için optimal
            ses = ses.set_channels(1).set_frame_rate(16000)
            ses.export(str(wav_yolu), format="wav")
            logger.info(f"[SES] OGG -> WAV donusum basarili: {wav_yolu.name}")
            return wav_yolu
        except Exception as e:
            logger.error(f"[SES] OGG->WAV donusum hatasi: {e}")
            raise

    def metne_cevir(self, wav_yolu: Path) -> dict:
        """
        WAV dosyasını Google STT ile metne çevirir.
        Döner: {"basarili": bool, "metin": str, "hata": str}
        """
        try:
            with sr.AudioFile(str(wav_yolu)) as kaynak:
                # Arka plan gürültüsüne adaptasyon (0.5 saniye)
                self.recognizer.adjust_for_ambient_noise(kaynak, duration=0.5)
                ses_verisi = self.recognizer.record(kaynak)

            metin = self.recognizer.recognize_google(ses_verisi, language=self.dil)
            logger.info(
                f"[SES] Metne cevirme basarili: '{metin[:50]}...' "
                if len(metin) > 50
                else f"[SES] Metne cevirme basarili: '{metin}'"
            )
            return {"basarili": True, "metin": metin, "hata": ""}

        except sr.UnknownValueError:
            logger.warning("[SES] Ses anlasilamadi (UnknownValueError)")
            return {"basarili": False, "metin": "", "hata": "anlasilamadi"}

        except sr.RequestError as e:
            logger.error(f"[SES] Google STT API hatasi: {e}")
            return {"basarili": False, "metin": "", "hata": f"api_hatasi: {e}"}

        except Exception as e:
            logger.error(f"[SES] Beklenmeyen hata: {e}")
            return {"basarili": False, "metin": "", "hata": str(e)}

    def isleme_pipeline(self, ogg_yolu: Path) -> dict:
        """
        Tam pipeline: OGG al → WAV'a çevir → metne çevir → temp dosyaları temizle.
        Döner: {"basarili": bool, "metin": str, "hata": str}
        """
        wav_yolu = None
        try:
            wav_yolu = self.ogg_wav_cevir(ogg_yolu)
            sonuc = self.metne_cevir(wav_yolu)
            return sonuc

        except Exception as e:
            logger.error(f"[SES] Pipeline hatasi: {e}")
            return {"basarili": False, "metin": "", "hata": str(e)}

        finally:
            # Geçici dosyaları temizle
            try:
                if ogg_yolu and ogg_yolu.exists():
                    ogg_yolu.unlink()
                if wav_yolu and wav_yolu.exists():
                    wav_yolu.unlink()
            except Exception as temizlik_hatasi:
                logger.warning(f"[SES] Gecici dosya temizleme hatasi: {temizlik_hatasi}")


# ---------------------------------------------------------------------------
# telegram_bot.py'ye eklenecek handler — buraya yapıştır
# ---------------------------------------------------------------------------
TELEGRAM_BOT_EK_KOD = '''
# ============================================================
# AŞAMA 11: SESLİ MESAJ HANDLER — telegram_bot.py'ye ekle
# ============================================================
# 1) Dosyanın üstüne import ekle:
#    from ses_plugin import SesPlugin
#    from pathlib import Path
#    import os

# 2) Bot init bloğuna ekle (diğer plugin'lerin yanına):
#    ses_plugin = SesPlugin(dil="tr-TR")

# 3) Bu handler fonksiyonunu ekle:

async def sesli_mesaj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram'dan gelen sesli mesajları metne çevirir ve AI'a iletir."""
    kullanici_id = str(update.effective_user.id)

    # Yetki kontrolü (varsa mevcut sistemine göre ayarla)
    # if kullanici_id not in IZINLI_KULLANICILAR: return

    await update.message.reply_text("Sesli mesajin isleniyor, bekle...")

    try:
        # Sesi Telegram'dan indir
        voice = update.message.voice
        dosya = await context.bot.get_file(voice.file_id)

        ogg_yolu = Path("temp_ses") / f"ses_{kullanici_id}_{voice.file_id}.ogg"
        ogg_yolu.parent.mkdir(exist_ok=True)
        await dosya.download_to_drive(str(ogg_yolu))

        # STT pipeline'ı çalıştır
        sonuc = ses_plugin.isleme_pipeline(ogg_yolu)

        if not sonuc["basarili"]:
            if sonuc["hata"] == "anlasilamadi":
                await update.message.reply_text(
                    "Sesi anlayamadim. Lutfen daha yakin veya net konusarak tekrar dene."
                )
            else:
                await update.message.reply_text(
                    f"Ses isleme hatasi: {sonuc['hata']}"
                )
            return

        algilanan_metin = sonuc["metin"]

        # Kullanıcıya ne anladığını göster
        await update.message.reply_text(
            f"Duyduklarim: \\"{algilanan_metin}\\""
        )

        # Metni normal mesaj gibi AI'a gönder — mevcut ask_ai fonksiyonunu kullan
        ai_yanit = await ask_ai(kullanici_id, algilanan_metin)
        await update.message.reply_text(ai_yanit)

        # Eğitim toplayıcısına kaydet (mevcut sisteme entegre)
        egitim_toplayici.basarili_kaydet(algilanan_metin, ai_yanit, "sesli_mesaj")

    except Exception as e:
        logger.error(f"[BOT] Sesli mesaj handler hatasi: {e}")
        await update.message.reply_text("Sesli mesaj islenirken bir hata olustu.")


# 4) Handler'ı application'a kaydet (diğer handler'ların yanına):
#    application.add_handler(MessageHandler(filters.VOICE, sesli_mesaj_handler))
'''


if __name__ == "__main__":
    # Hızlı test: örnek bir OGG dosyanız varsa buradan test edin
    print("SesPlugin test modu")
    print("Kullanim: plugin = SesPlugin(); sonuc = plugin.isleme_pipeline(Path('ses.ogg'))")
    print()
    print("telegram_bot.py entegrasyon kodunu gormek icin TELEGRAM_BOT_EK_KOD degiskenini yazdir.")
    print()

    # Kurulum kontrolü
    try:
        import speech_recognition

        print("SpeechRecognition: KURULU")
    except ImportError:
        print("SpeechRecognition: EKSIK — pip install SpeechRecognition")

    try:
        from pydub import AudioSegment

        print("pydub: KURULU")
    except ImportError:
        print("pydub: EKSIK — pip install pydub")

    import shutil

    ffmpeg_var = shutil.which("ffmpeg")
    if ffmpeg_var:
        print(f"ffmpeg: KURULU ({ffmpeg_var})")
    else:
        print("ffmpeg: EKSIK — https://ffmpeg.org/download.html adresinden indir, PATH'e ekle")
