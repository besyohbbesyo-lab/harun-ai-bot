# chat_panel.py - Masaustu AI Sohbet Paneli
# Asama 10: Wake word ("Hey Harun") + Surekli dinleme + UI iyilestirmeleri

import json
import os
import re
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext

from dotenv import load_dotenv

load_dotenv()  # .env dosyasindan ortam degiskenlerini yukle

BASE_DIR = Path(__file__).parent.resolve()

# ─────────────────────────────────────────────────────────────
# SHORT-TERM MEMORY
# ─────────────────────────────────────────────────────────────

PANEL_USER_ID = 0
_panel_stm: deque = deque(maxlen=10)


def panel_stm_ekle(rol: str, icerik: str):
    _panel_stm.append({"role": rol, "content": icerik, "zaman": datetime.now().strftime("%H:%M")})


def panel_stm_temizle():
    _panel_stm.clear()


def panel_stm_baglam() -> str:
    if not _panel_stm:
        return ""
    satirlar = []
    for m in list(_panel_stm):
        rol_adi = "Sen" if m["role"] == "user" else "Asistan"
        icerik = m["content"][:200]
        if icerik:
            satirlar.append(f"{rol_adi} [{m.get('zaman','')}]: {icerik}")
    if not satirlar:
        return ""
    return "[Onceki Konusma]\n" + "\n".join(satirlar) + "\n[/Onceki Konusma]"


# ─────────────────────────────────────────────────────────────
# SES MODULLERİ
# ─────────────────────────────────────────────────────────────

try:
    import speech_recognition as sr

    SES_GIRIS_AKTIF = True
except ImportError:
    SES_GIRIS_AKTIF = False

try:
    import pyttsx3

    _tts = pyttsx3.init()
    _tts.setProperty("rate", 160)
    for voice in _tts.getProperty("voices"):
        if "tr" in voice.id.lower() or "turkish" in voice.name.lower():
            _tts.setProperty("voice", voice.id)
            break
    SES_CIKIS_AKTIF = True
except ImportError:
    SES_CIKIS_AKTIF = False


# ─────────────────────────────────────────────────────────────
# ASAMA 10: WAKE WORD MOTORU
# ─────────────────────────────────────────────────────────────

WAKE_WORDS = ["hey harun", "hey, harun", "harun", "heyharun"]


def _wake_word_kontrol(metin: str) -> tuple:
    """
    Metinde wake word var mi kontrol et.
    Doner: (tespit_edildi: bool, komut_kismi: str)
    """
    metin_lower = metin.lower().strip()
    for ww in WAKE_WORDS:
        if metin_lower.startswith(ww):
            komut = metin[len(ww) :].strip(" ,!?")
            return True, komut
        if ww in metin_lower:
            idx = metin_lower.find(ww)
            komut = metin[idx + len(ww) :].strip(" ,!?")
            return True, komut
    return False, metin


# ─────────────────────────────────────────────────────────────
# AI SORGU
# ─────────────────────────────────────────────────────────────


def _groq_key_al() -> str:
    """Groq API key'ini api_rotator'dan al (yeni _keys yapısı ile uyumlu)."""
    import sys

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    # Yontem 1: api_rotator'dan rotator instance uzerinden
    try:
        from api_rotator import rotator

        # Yeni yapi: rotator._keys listesi (_KeyState nesneleri)
        if hasattr(rotator, "_keys") and rotator._keys:
            for ks in rotator._keys:
                key = getattr(ks, "key", "")
                if key:
                    return key
        # Eski yapi (uyumluluk): rotator.providers listesi
        if hasattr(rotator, "providers"):
            for p in rotator.providers:
                if (p.get("isim") == "Groq" or p.get("name") == "Groq") and p.get("api_key"):
                    return p["api_key"]
        # aktif_provider_al() dene
        if hasattr(rotator, "aktif_provider_al"):
            p = rotator.aktif_provider_al()
            if p and p.get("api_key"):
                return p["api_key"]
    except Exception:
        pass
    # Yontem 2: Ortam degiskenlerinden
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key
    keys = os.getenv("GROQ_API_KEYS", "").strip()
    if keys:
        return keys.split(",")[0].strip()
    return ""


def _gemini_key_al() -> str:
    """Groq-only modda Gemini devre disi — stub fonksiyon."""
    return ""


def _profil_talimat_al() -> str:
    try:
        import sys

        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        from user_profile import sistem_prompt_olustur

        return sistem_prompt_olustur(PANEL_USER_ID)
    except Exception:
        return ""


def _sanitize(text: str) -> str:
    """Model kontrol tokenlarini temizle."""
    import re as _re

    if not text:
        return text
    text = _re.sub(r"<begin_of_box>.*?<end_of_box>", "", text, flags=_re.DOTALL)
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    text = _re.sub(r"<analysis>.*?</analysis>", "", text, flags=_re.DOTALL)
    text = _re.sub(r"<\|[^|]*\|>", "", text)
    text = _re.sub(r"<(begin_of_box|end_of_box|think|analysis)[^>]*>", "", text)
    text = _re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def ai_soru_sor(mesaj: str) -> str:
    import sys

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    stm_baglam = panel_stm_baglam()
    profil_talimat = _profil_talimat_al()

    onbilgi = ""
    if stm_baglam:
        onbilgi += stm_baglam + "\n\n"
    if profil_talimat:
        onbilgi += f"[Kullanici Tercihi] {profil_talimat} [/Kullanici Tercihi]\n\n"

    tam_prompt = onbilgi + mesaj if onbilgi else mesaj

    sistem_mesaji = (
        "Sen Harun'un kisisel AI asistanisin. Turkce cevap ver. "
        "Asla parantez icinde aciklayici not ekleme."
    )

    # GROQ-ONLY: Sadece Groq kullan
    try:
        import httpx

        key = _groq_key_al()
        if key:
            r = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": sistem_mesaji},
                        {"role": "user", "content": tam_prompt},
                    ],
                    "max_tokens": 1024,
                },
                timeout=30,
            )
            data = r.json()
            if "choices" in data:
                return _sanitize(data["choices"][0]["message"]["content"])
            else:
                err = data.get("error", {}).get("message", str(data))
                return f"API hatasi: {err}"
        else:
            return "API key bulunamadi. .env dosyasina GROQ_API_KEY=gsk_... satirini ekleyin."
    except Exception as e:
        return f"Baglanti hatasi: {e}"


def sesi_oku(metin: str):
    if not SES_CIKIS_AKTIF:
        return

    def _oku():
        try:
            _tts.say(metin)
            _tts.runAndWait()
        except Exception:
            pass

    threading.Thread(target=_oku, daemon=True).start()


# ─────────────────────────────────────────────────────────────
# ANA PENCERE
# ─────────────────────────────────────────────────────────────


class ChatPanel:
    def __init__(self):
        self.pencere = tk.Tk()
        self.pencere.title("Harun AI - Masaustu Asistan")
        self.pencere.geometry("900x700")
        self.pencere.configure(bg="#0a0a0a")
        self.pencere.resizable(True, True)

        try:
            self.pencere.iconbitmap(str(BASE_DIR / "icon.ico"))
        except Exception:
            pass

        self.ses_aktif = tk.BooleanVar(value=False)
        self.dinliyor = False

        # ASAMA 10: Surekli dinleme state
        self.surekli_dinleme = False
        self._surekli_dinleme_durdur = threading.Event()

        self._arayuz_kur()
        self._mesaj_ekle(
            "Asistan",
            "Merhaba! Ben Harun'un AI asistaniyim. Sana nasil yardimci olabilirim?\n"
            "Ipucu: 'Hey Harun' diyerek sesle de konusabilirsin.",
        )

    def _arayuz_kur(self):
        # ── Baslik ──
        baslik = tk.Frame(self.pencere, bg="#111111", height=60)
        baslik.pack(fill=tk.X)
        baslik.pack_propagate(False)

        tk.Label(
            baslik,
            text="  HARUN AI   MASAUSTU ASISTAN",
            bg="#111111",
            fg="#00ff88",
            font=("Courier New", 14, "bold"),
        ).pack(side=tk.LEFT, padx=15, pady=15)

        self.durum_lbl = tk.Label(
            baslik, text="Hazir", bg="#111111", fg="#555555", font=("Courier New", 10)
        )
        self.durum_lbl.pack(side=tk.RIGHT, padx=15)

        # Ses cikis toggle
        ses_cikis_btn = tk.Checkbutton(
            baslik,
            text="Sesli Cevap",
            variable=self.ses_aktif,
            bg="#111111",
            fg="#888888",
            selectcolor="#111111",
            activebackground="#111111",
            activeforeground="#00ff88",
            font=("Courier New", 10),
            cursor="hand2",
        )
        ses_cikis_btn.pack(side=tk.RIGHT, padx=10)

        # ASAMA 10: Surekli dinleme butonu
        if SES_GIRIS_AKTIF:
            self.surekli_btn = tk.Button(
                baslik,
                text="[ DINLEME: KAPALI ]",
                bg="#111111",
                fg="#444444",
                font=("Courier New", 9, "bold"),
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=4,
                cursor="hand2",
                command=self._surekli_dinleme_toggle,
            )
            self.surekli_btn.pack(side=tk.RIGHT, padx=5)

        # ── Alt bilgi (ONCE pack et) ──
        alt = tk.Frame(self.pencere, bg="#0a0a0a")
        alt.pack(fill=tk.X, padx=15, pady=(0, 5), side=tk.BOTTOM)

        self.alt_lbl = tk.Label(
            alt,
            text="Enter: Gonder  |  Shift+Enter: Satir atla  |  MIC: Sesle konuş  |  Hey Harun: Wake word",
            bg="#0a0a0a",
            fg="#444444",
            font=("Courier New", 9),
        )
        self.alt_lbl.pack(side=tk.LEFT)

        tk.Button(
            alt,
            text="Yeni Sohbet",
            bg="#0a0a0a",
            fg="#555555",
            font=("Courier New", 9),
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._yeni_sohbet,
        ).pack(side=tk.RIGHT)

        # ── Giris alani (ONCE pack et, sohbet alanindan önce) ──
        giris_frame = tk.Frame(self.pencere, bg="#2d2d2d", pady=8, height=80)
        giris_frame.pack(fill=tk.X, side=tk.BOTTOM)
        giris_frame.pack_propagate(False)

        self.ses_btn = tk.Button(
            giris_frame,
            text="MIC",
            bg="#2d2d2d",
            fg="#555555",
            font=("Courier New", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._ses_kaydet,
        )
        if SES_GIRIS_AKTIF:
            self.ses_btn.configure(fg="#00aa55")
        self.ses_btn.pack(side=tk.LEFT, padx=(10, 8))

        self.giris = tk.Text(
            giris_frame,
            bg="#3a3a3a",
            fg="#d4d4aa",
            font=("Courier New", 13),
            height=3,
            wrap=tk.WORD,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=6,
            insertbackground="#00ff88",
        )
        self.giris.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.giris.bind("<Return>", self._enter_gonder)
        self.giris.bind("<Shift-Return>", lambda e: None)

        self.gonder_btn = tk.Button(
            giris_frame,
            text="GONDER",
            bg="#00ff88",
            fg="#000000",
            font=("Courier New", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._gonder,
        )
        self.gonder_btn.pack(side=tk.LEFT, padx=(0, 10))

        # ── Sohbet alani (EN SON pack et, expand=True ile kalan alani doldursun) ──
        sohbet_frame = tk.Frame(self.pencere, bg="#0a0a0a")
        sohbet_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 5))

        self.sohbet = scrolledtext.ScrolledText(
            sohbet_frame,
            bg="#141414",
            fg="#c8c8c8",
            font=("Courier New", 13),
            wrap=tk.WORD,
            state=tk.DISABLED,
            bd=0,
            relief=tk.FLAT,
            padx=15,
            pady=12,
            insertbackground="#00ff88",
            spacing1=3,
            spacing3=3,
        )
        self.sohbet.pack(fill=tk.BOTH, expand=True)

        self.sohbet.tag_config(
            "asistan_isim", foreground="#00ff88", font=("Courier New", 13, "bold")
        )
        self.sohbet.tag_config(
            "kullanici_isim", foreground="#4db8ff", font=("Courier New", 13, "bold")
        )
        self.sohbet.tag_config("kullanici_metin", foreground="#ffffff", font=("Courier New", 13))
        self.sohbet.tag_config("asistan_metin", foreground="#c8c8c8", font=("Courier New", 13))
        self.sohbet.tag_config("sistem", foreground="#555555", font=("Courier New", 11, "italic"))
        self.sohbet.tag_config("zaman", foreground="#3a3a3a", font=("Courier New", 10))
        self.sohbet.tag_config("wake", foreground="#ffaa00", font=("Courier New", 11, "italic"))

    # ─────────────────────────────────────────────────────────
    # MESAJ EKLEME
    # ─────────────────────────────────────────────────────────

    def _mesaj_ekle(self, kimden: str, metin: str, renk: str = None):
        self.sohbet.configure(state=tk.NORMAL)
        zaman = datetime.now().strftime("%H:%M")

        if kimden == "Sen":
            self.sohbet.insert(tk.END, f"\n[{zaman}] ", "zaman")
            self.sohbet.insert(tk.END, "Sen\n", "kullanici_isim")
            self.sohbet.insert(tk.END, metin + "\n", "kullanici_metin")
        elif kimden == "Asistan":
            self.sohbet.insert(tk.END, f"\n[{zaman}] ", "zaman")
            self.sohbet.insert(tk.END, "Asistan\n", "asistan_isim")
            self.sohbet.insert(tk.END, metin + "\n", "asistan_metin")
        elif kimden == "Wake":
            self.sohbet.insert(tk.END, f"\n{metin}\n", "wake")
        else:
            self.sohbet.insert(tk.END, f"\n{kimden}: {metin}\n", "sistem")

        self.sohbet.configure(state=tk.DISABLED)
        self.sohbet.see(tk.END)

    def _durum_guncelle(self, metin: str, renk: str = "#555555"):
        self.durum_lbl.configure(text=metin, fg=renk)
        self.pencere.update_idletasks()

    def _enter_gonder(self, event):
        if not (event.state & 0x1):
            self._gonder()
            return "break"

    def _gonder(self):
        metin = self.giris.get("1.0", tk.END).strip()
        if not metin:
            return
        self.giris.delete("1.0", tk.END)
        self._mesaj_ekle("Sen", metin)
        panel_stm_ekle("user", metin)
        self._ai_cevap_al(metin)

    def _ai_cevap_al(self, metin: str):
        self.gonder_btn.configure(state=tk.DISABLED, bg="#333333")
        self._durum_guncelle("Dusunuyor...", "#ff8800")

        def _thread():
            try:
                cevap = ai_soru_sor(metin)
                panel_stm_ekle("assistant", cevap)
                self.pencere.after(0, lambda: self._cevap_goster(cevap))
            except Exception:
                self.pencere.after(0, lambda: self._cevap_goster(f"Hata: {e}"))

        threading.Thread(target=_thread, daemon=True).start()

    def _cevap_goster(self, cevap: str):
        self._mesaj_ekle("Asistan", cevap)
        self.gonder_btn.configure(state=tk.NORMAL, bg="#00ff88")

        # Surekli dinleme aktifse durumu geri al
        if self.surekli_dinleme:
            self._durum_guncelle("Wake word bekleniyor...", "#ffaa00")
        else:
            self._durum_guncelle("Hazir", "#555555")

        if self.ses_aktif.get() and SES_CIKIS_AKTIF:
            temiz = re.sub(r"[*#`\[\]()]", "", cevap)
            temiz = temiz[:500]
            sesi_oku(temiz)

    # ─────────────────────────────────────────────────────────
    # MIC BUTONU (Tek seferlik)
    # ─────────────────────────────────────────────────────────

    def _ses_kaydet(self):
        if not SES_GIRIS_AKTIF:
            self._mesaj_ekle(
                "Sistem", "Ses modulu kurulu degil. pip install SpeechRecognition pyaudio"
            )
            return
        if self.dinliyor:
            return

        self.dinliyor = True
        self.ses_btn.configure(bg="#ff3300", fg="#ffffff", text="...")
        self._durum_guncelle("Dinliyor...", "#ff3300")

        def _dinle():
            try:
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=8, phrase_time_limit=15)
                try:
                    metin = r.recognize_google(audio, language="tr-TR")
                    self.pencere.after(0, lambda: self._ses_tamamlandi(metin))
                except sr.UnknownValueError:
                    self.pencere.after(0, lambda: self._ses_tamamlandi(None, "Anlasilamadi"))
                except sr.RequestError:
                    self.pencere.after(0, lambda: self._ses_tamamlandi(None, f"Servis hatasi: {e}"))
            except Exception:
                self.pencere.after(0, lambda: self._ses_tamamlandi(None, str(e)))

        threading.Thread(target=_dinle, daemon=True).start()

    def _ses_tamamlandi(self, metin, hata=None):
        self.dinliyor = False
        self.ses_btn.configure(bg="#1a1a1a", fg="#00aa55", text="MIC")
        self._durum_guncelle("Hazir", "#555555")

        if hata:
            self._mesaj_ekle("Sistem", f"Ses hatasi: {hata}")
            return

        if metin:
            wake_var, komut = _wake_word_kontrol(metin)
            gidecek = komut if (wake_var and komut) else metin
            self.giris.delete("1.0", tk.END)
            self.giris.insert("1.0", gidecek)
            self._mesaj_ekle("Sen", f"[Ses] {gidecek}")
            panel_stm_ekle("user", gidecek)
            self._ai_cevap_al(gidecek)

    # ─────────────────────────────────────────────────────────
    # ASAMA 10: SUREKLI DİNLEME MODU
    # ─────────────────────────────────────────────────────────

    def _surekli_dinleme_toggle(self):
        if not SES_GIRIS_AKTIF:
            self._mesaj_ekle("Sistem", "Ses modulu kurulu degil.")
            return

        if self.surekli_dinleme:
            self.surekli_dinleme = False
            self._surekli_dinleme_durdur.set()
            self.surekli_btn.configure(text="[ DINLEME: KAPALI ]", fg="#444444")
            self._durum_guncelle("Hazir", "#555555")
            self._mesaj_ekle("Wake", "Surekli dinleme modu kapatildi.")
        else:
            self.surekli_dinleme = True
            self._surekli_dinleme_durdur.clear()
            self.surekli_btn.configure(text="[ DINLEME: AKTIF ]", fg="#00ff88")
            self._durum_guncelle("Wake word bekleniyor...", "#ffaa00")
            self._mesaj_ekle("Wake", "Surekli dinleme aktif. 'Hey Harun' diyerek baslayabilirsin.")
            threading.Thread(target=self._surekli_dinleme_dongusu, daemon=True).start()

    def _surekli_dinleme_dongusu(self):
        """Arka planda calisir, wake word duyunca komutu isle."""
        if not SES_GIRIS_AKTIF:
            return

        rec = sr.Recognizer()
        rec.energy_threshold = 300
        rec.dynamic_energy_threshold = True
        rec.pause_threshold = 0.8

        while self.surekli_dinleme and not self._surekli_dinleme_durdur.is_set():
            try:
                with sr.Microphone() as source:
                    rec.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = rec.listen(source, timeout=3, phrase_time_limit=5)
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        metin = rec.recognize_google(audio, language="tr-TR")
                    except (sr.UnknownValueError, sr.RequestError):
                        continue

                    if not metin:
                        continue

                    wake_var, komut = _wake_word_kontrol(metin)

                    if not wake_var:
                        continue

                    # Wake word tespit edildi
                    self.pencere.after(
                        0,
                        lambda: (
                            self._durum_guncelle("Hey Harun tespit edildi...", "#ff3300"),
                            self._mesaj_ekle("Wake", "Hey Harun! Dinliyorum..."),
                        ),
                    )

                    if komut and len(komut) > 2:
                        # Komut wake word'un hemen ardindan geldi
                        k = komut
                        self.pencere.after(0, lambda k=k: self._wake_komutu_isle(k))
                    else:
                        # Komut bekle
                        self.pencere.after(
                            0, lambda: self._durum_guncelle("Komut bekleniyor...", "#ff8800")
                        )
                        try:
                            with sr.Microphone() as src2:
                                rec.adjust_for_ambient_noise(src2, duration=0.2)
                                audio2 = rec.listen(src2, timeout=6, phrase_time_limit=15)
                                komut2 = rec.recognize_google(audio2, language="tr-TR")
                                if komut2:
                                    k2 = komut2
                                    self.pencere.after(0, lambda k2=k2: self._wake_komutu_isle(k2))
                        except Exception:
                            self.pencere.after(
                                0,
                                lambda: self._durum_guncelle("Wake word bekleniyor...", "#ffaa00"),
                            )

            except Exception:
                time.sleep(1)
                continue

    def _wake_komutu_isle(self, komut: str):
        self._mesaj_ekle("Sen", f"[Hey Harun] {komut}")
        panel_stm_ekle("user", komut)
        self._ai_cevap_al(komut)

    # ─────────────────────────────────────────────────────────
    # YENI SOHBET / KAPAT
    # ─────────────────────────────────────────────────────────

    def _yeni_sohbet(self):
        panel_stm_temizle()
        self.sohbet.configure(state=tk.NORMAL)
        self.sohbet.delete("1.0", tk.END)
        self.sohbet.configure(state=tk.DISABLED)
        self._mesaj_ekle("Asistan", "Yeni sohbet basladi! Nasil yardimci olabilirim?")

    def calistir(self):
        self.pencere.protocol("WM_DELETE_WINDOW", self._kapat)
        self.pencere.mainloop()

    def _kapat(self):
        self.surekli_dinleme = False
        self._surekli_dinleme_durdur.set()
        self.pencere.destroy()


# ─────────────────────────────────────────────────────────────
# BASLAT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Kurulum kontrol ediliyor...")

    eksik = []
    if not SES_GIRIS_AKTIF:
        eksik.append("SpeechRecognition + pyaudio (ses giris + wake word)")
    if not SES_CIKIS_AKTIF:
        eksik.append("pyttsx3 (ses cikis)")

    if eksik:
        print("Opsiyonel eksik paketler:")
        for e in eksik:
            print(f"  - {e}")
        print("Sadece yazi modu aktif.\n")

    print("Panel aciliyor...")
    panel = ChatPanel()
    panel.calistir()
