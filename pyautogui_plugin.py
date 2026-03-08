# pyautogui_plugin.py  (SECURE VERSION — S0-4: OTP + RISK CLASSES)

import re
import secrets
import shutil
import subprocess
import time

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

# ============================================================
# İZİN LİSTELERİ
# ============================================================

ALLOWED_PROGRAMS = {
    "notepad",
    "notepad.exe",
    "calc",
    "calc.exe",
    "chrome",
    "chrome.exe",
    "msedge",
    "msedge.exe",
}

FORBIDDEN_COMBOS = {
    "alt+f4",
    "ctrl+alt+del",
    "ctrl+shift+esc",
    "win",
    "shutdown",
    "taskkill",
    "powershell",
    "regedit",
}

# ============================================================
# RISK SINIFLARI (S0-4)
# ============================================================
# low      → Onay gerekmez, doğrudan çalışır
# medium   → Kullanıcıya bilgi verilir, doğrudan çalışır
# high     → OTP onayı gerekir (6 hex karakter, 30sn timeout)
# critical → OTP onayı gerekir + ekstra uyarı mesajı
# ============================================================

RISK_CLASSES = {
    "tikla": "low",
    "yaz": "medium",
    "tus_bas": "medium",
    "program_ac": "high",
    "web_git": "high",
    "otomasyon": "critical",  # çoklu adım otomasyonu
}

# OTP ayarları
OTP_TIMEOUT_SN = 30
OTP_UZUNLUK = 6  # secrets.token_hex(3) → 6 hex karakter

# ============================================================
# RATE LIMIT
# ============================================================

MAX_ACTIONS = 15
WINDOW_SECONDS = 30
_action_log = []


def rate_limit_ok():
    global _action_log
    now = time.time()
    _action_log = [t for t in _action_log if now - t < WINDOW_SECONDS]
    if len(_action_log) >= MAX_ACTIONS:
        return False
    _action_log.append(now)
    return True


def safe_coord(x, y):
    w, h = pyautogui.size()
    if x < 5 or y < 5 or x > w - 5 or y > h - 5:
        return False
    return True


# ============================================================
# URL & PROGRAM GÜVENLİK DOĞRULAMASI (shell=True düzeltmesi)
# ============================================================

# URL whitelist pattern — sadece http/https, tehlikeli karakterler yok
_URL_PATTERN = re.compile(
    r"^https?://"  # http:// veya https://
    r"[a-zA-Z0-9]"  # domain harfle/rakamla başlamalı
    r"[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=%-]*$"  # izin verilen URL karakterleri
)

# Shell injection'a yol açabilecek tehlikeli karakterler
_SHELL_TEHLIKELI = set(";&|`$(){}[]<>!'\"\\")


def _guvenli_url_mi(url: str) -> bool:
    """URL'nin güvenli olduğunu doğrula — injection riski olan karakterler engellenir."""
    if not url or len(url) > 2048:
        return False
    # Tehlikeli shell karakteri kontrolü
    if any(c in _SHELL_TEHLIKELI for c in url):
        return False
    if not _URL_PATTERN.match(url):
        return False
    return True


def _guvenli_program_mi(program: str) -> bool:
    """Program adının whitelist'te ve temiz olduğunu doğrula."""
    p = program.strip().lower()
    if p not in ALLOWED_PROGRAMS:
        return False
    # Ek güvenlik: sadece alfanumerik + nokta (path injection engeli)
    if not re.match(r"^[a-zA-Z0-9_.]+$", program.strip()):
        return False
    return True


# ============================================================
# OTP YÖNETİCİSİ (S0-4)
# ============================================================


class OTPYonetici:
    """Tek kullanımlık onay kodu üretir ve doğrular.

    Akış:
      1. Telegram handler, risk seviyesi high/critical olan komutu algılar
      2. otp_uret() çağrılır → kullanıcıya 6 haneli hex kod gönderilir
      3. Kullanıcı kodu geri gönderir
      4. otp_dogrula() çağrılır → kod + süre kontrolü
      5. Geçerliyse komut çalışır, değilse reddedilir

    Kullanım (telegram_bot.py'de):
        otp = otomasyon.otp_yonetici.otp_uret("program_ac notepad")
        await bot.send_message(chat_id, f"⚠️ Onay kodu: {otp['kod']}\n30 saniye içinde girin.")
        # ... kullanıcı cevabı gelince:
        if otomasyon.otp_yonetici.otp_dogrula(kullanici_girisi):
            sonuc = otomasyon.program_ac("notepad")
    """

    def __init__(self):
        self._bekleyen_otp = None  # {"kod": str, "zaman": float, "islem": str}

    def otp_uret(self, islem_aciklama: str) -> dict:
        """Yeni OTP kodu üret.

        Args:
            islem_aciklama: Hangi işlem için onay istendiği (log için)

        Returns:
            {"kod": "a3f1b2", "islem": "program_ac notepad", "timeout": 30}
        """
        kod = secrets.token_hex(OTP_UZUNLUK // 2)  # 3 byte → 6 hex karakter
        self._bekleyen_otp = {
            "kod": kod,
            "zaman": time.time(),
            "islem": islem_aciklama,
        }
        return {
            "kod": kod,
            "islem": islem_aciklama,
            "timeout": OTP_TIMEOUT_SN,
        }

    def otp_dogrula(self, girilen_kod: str) -> dict:
        """Kullanıcının girdiği OTP kodunu doğrula.

        Args:
            girilen_kod: Kullanıcının gönderdiği kod

        Returns:
            {"gecerli": True/False, "sebep": str}
        """
        if self._bekleyen_otp is None:
            return {"gecerli": False, "sebep": "Bekleyen onay kodu yok."}

        otp = self._bekleyen_otp
        gecen_sure = time.time() - otp["zaman"]

        # Timeout kontrolü
        if gecen_sure > OTP_TIMEOUT_SN:
            self._bekleyen_otp = None
            return {"gecerli": False, "sebep": f"Onay suresi doldu ({OTP_TIMEOUT_SN}sn)."}

        # Kod eşleşme kontrolü (constant-time comparison)
        if not secrets.compare_digest(girilen_kod.strip().lower(), otp["kod"]):
            self._bekleyen_otp = None  # Tek deneme hakkı
            return {"gecerli": False, "sebep": "Yanlis onay kodu."}

        # Başarılı — OTP'yi temizle (tek kullanımlık)
        islem = otp["islem"]
        self._bekleyen_otp = None
        return {"gecerli": True, "sebep": f"Onaylandi: {islem}"}

    def bekleyen_var_mi(self) -> bool:
        """Bekleyen OTP var mı? (timeout kontrolü dahil)"""
        if self._bekleyen_otp is None:
            return False
        gecen_sure = time.time() - self._bekleyen_otp["zaman"]
        if gecen_sure > OTP_TIMEOUT_SN:
            self._bekleyen_otp = None
            return False
        return True

    def iptal(self):
        """Bekleyen OTP'yi iptal et."""
        self._bekleyen_otp = None


# ============================================================
# RISK SEVİYESİ YARDIMCI FONKSİYONLARI
# ============================================================


def risk_seviyesi_al(komut: str) -> str:
    """Komut için risk seviyesini döndür."""
    return RISK_CLASSES.get(komut, "high")  # Bilinmeyen komutlar high kabul edilir


def otp_gerekli_mi(komut: str) -> bool:
    """Bu komut OTP onayı gerektiriyor mu?"""
    seviye = risk_seviyesi_al(komut)
    return seviye in ("high", "critical")


def risk_uyari_mesaji(komut: str, detay: str = "") -> str:
    """Risk seviyesine göre kullanıcıya gösterilecek uyarı mesajı."""
    seviye = risk_seviyesi_al(komut)

    if seviye == "critical":
        return (
            f"🔴 KRİTİK İŞLEM: {komut}\n"
            f"{detay}\n"
            f"Bu işlem sisteminizi doğrudan etkiler.\n"
            f"Onay kodu girin ({OTP_TIMEOUT_SN}sn süreniz var):"
        )
    elif seviye == "high":
        return (
            f"🟠 Yüksek riskli işlem: {komut}\n"
            f"{detay}\n"
            f"Onay kodu girin ({OTP_TIMEOUT_SN}sn süreniz var):"
        )
    elif seviye == "medium":
        return f"🟡 {komut} çalıştırılıyor... {detay}"
    else:
        return ""


# ============================================================
# ANA OTOMASYON SINIFI
# ============================================================


class OtomasyonPlugin:
    def __init__(self):
        self.otp_yonetici = OTPYonetici()

    def tikla(self, x, y, tur="sol"):
        if not rate_limit_ok():
            return "Rate limit asildi."
        if not safe_coord(x, y):
            return "Guvenli koordinat disi."
        try:
            if tur == "sag":
                pyautogui.rightClick(x, y)
            elif tur == "cift":
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y)
            return f"Tiklandi: {x},{y}"
        except Exception as e:
            return f"Hata: {e}"

    def yaz(self, metin):
        if not rate_limit_ok():
            return "Rate limit asildi."
        if len(metin) > 2000:
            return "Metin cok uzun."
        try:
            pyautogui.write(metin, interval=0.05)
            return "Yazildi."
        except Exception as e:
            return f"Hata: {e}"

    def tus_bas(self, *tuslar):
        if not rate_limit_ok():
            return "Rate limit asildi."
        combo = "+".join(tuslar).lower()
        if combo in FORBIDDEN_COMBOS:
            return "Bu tus kombinasyonu yasakli."
        try:
            if len(tuslar) == 1:
                pyautogui.press(tuslar[0])
            else:
                pyautogui.hotkey(*tuslar)
            return f"Tus basildi: {combo}"
        except Exception as e:
            return f"Hata: {e}"

    def program_ac(self, program):
        """Program aç — shell=True KALDIRILDI, güvenli versiyon."""
        if not rate_limit_ok():
            return "Rate limit asildi."
        if not _guvenli_program_mi(program):
            return f"Program izinli degil veya gecersiz: {program}"
        try:
            # --- GÜVENLİK DÜZELTMESİ ---
            # Eski: subprocess.Popen(program, shell=True)  ← command injection riski!
            # Yeni: shutil.which() ile tam yol bul, shell=False ile çalıştır
            tam_yol = shutil.which(program.strip())
            if tam_yol is None:
                return f"Program bulunamadi: {program}"
            subprocess.Popen([tam_yol])
            time.sleep(1)
            return f"Program acildi: {program}"
        except Exception as e:
            return f"Hata: {e}"

    def web_git(self, url):
        """URL aç — shell=True KALDIRILDI, güvenli versiyon."""
        if not rate_limit_ok():
            return "Rate limit asildi."
        if not _guvenli_url_mi(url):
            return "Gecersiz veya guvenli olmayan URL."
        try:
            # --- GÜVENLİK DÜZELTMESİ ---
            # Eski: subprocess.Popen(f'start {url}', shell=True)  ← URL injection riski!
            # Yeni: webbrowser modülü veya os.startfile (shell=True olmadan)
            import webbrowser

            webbrowser.open(url)
            return f"URL acildi: {url}"
        except Exception as e:
            return f"Hata: {e}"


otomasyon = OtomasyonPlugin()
