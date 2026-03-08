# planner_plugin.py — Canavar Mod (Agent Zinciri v2)
# ----------------------------------------------------
# Komut ver → planla → uygula → test et → raporla
#
# Yenilikler:
#   - Retry: adım başarısız → max 2 tekrar
#   - Bağlam zinciri: önceki çıktı sonrakine input
#   - Otomatik doğrulama: kritik adımlar test edilir
#   - Markdown rapor: ne yapıldı, başarılı/başarısız
#   - Canavar mod: /plan komutuyla tam agent zinciri

import asyncio
import time
from collections.abc import Callable
from typing import Optional

MAX_ADIM = 7  # Maksimum adım sayısı
MAX_RETRY = 2  # Adım başarısız → kaç kez tekrar
ADIM_TIMEOUT = 90  # Saniye (her adım için) - lokal model yavaş olabilir
OZET_MAX_CHARS = 300  # Bağlam zincirinde önceki adım özeti


class AdimSonucu:
    def __init__(self, adim: str, index: int):
        self.adim = adim
        self.index = index
        self.sonuc = ""
        self.basarili = False
        self.deneme = 0
        self.sure_ms = 0
        self.hata = ""
        self.dogrulama = ""  # doğrulama adımı varsa sonucu


class PlannerExecutor:
    def __init__(self, ask_ai_func: Callable, search_func=None, memory=None, vision=None):
        self.ask_ai = ask_ai_func
        self.search = search_func
        self.memory = memory
        self.vision = vision

    # ------------------------------------------------------------------ #
    # PLAN                                                                 #
    # ------------------------------------------------------------------ #
    async def plan(self, gorev: str) -> list:
        prompt = (
            f"Asagidaki gorevi adim adim planla:\n"
            f"Gorev: {gorev}\n\n"
            f"Kurallar:\n"
            f"- Sadece numaralandirmis adimlar yaz.\n"
            f"- Her adim tek, net bir eylem cumlesi.\n"
            f"- Maksimum {MAX_ADIM} adim.\n"
            f"- Turkce yaz.\n\n"
            f"Format:\n1. ...\n2. ...\n3. ..."
        )
        yanit = await self.ask_ai(prompt, hafiza_destegi=False)
        adimlar = []
        for satir in yanit.split("\n"):
            satir = satir.strip()
            if satir and (satir[0].isdigit() or satir.startswith("-")):
                temiz = satir.lstrip("0123456789.-) ").strip()
                if temiz:
                    adimlar.append(temiz)
        return adimlar[:MAX_ADIM] if adimlar else [gorev]

    # ------------------------------------------------------------------ #
    # ADIM ÇALIŞTIR (retry + bağlam zinciri)                              #
    # ------------------------------------------------------------------ #
    async def _adim_calistir(self, adim: str, onceki_sonuclar: list[AdimSonucu]) -> str:
        # Bağlam: son 2 adımın kısa özeti
        baglam_parcalari = []
        for s in onceki_sonuclar[-2:]:
            ozet = s.sonuc[:OZET_MAX_CHARS].strip()
            if ozet:
                baglam_parcalari.append(f"Adim {s.index+1} ({s.adim[:40]}): {ozet}")
        baglam = "\n".join(baglam_parcalari) if baglam_parcalari else "İlk adım."

        # Vision
        vision_kw = ["ekran", "goruntu", "screenshot", "ne goruyor", "gorsel", "analiz et"]
        if any(k in adim.lower() for k in vision_kw) and self.vision:
            try:
                v = self.vision.analyze_screen(f"Adim: {adim}")
                baglam += f"\n\nVision: {v[:600]}"
            except Exception:
                pass

        # Arama
        arama_kw = ["ara", "bul", "incele", "arastir", "kontrol et", "oku", "araştır"]
        if any(k in adim.lower() for k in arama_kw) and self.search:
            try:
                arama = self.search.search_and_read(adim[:60])
                prompt = (
                    f"Adim: {adim}\n"
                    f"Arama sonuclari:\n{arama[:800]}\n\n"
                    f"Onceki adimlar:\n{baglam}\n\n"
                    f"Bu adimi tamamla. Kisa ve net. Turkce."
                )
            except Exception:
                prompt = self._standart_prompt(adim, baglam)
        else:
            prompt = self._standart_prompt(adim, baglam)

        return await self.ask_ai(prompt, hafiza_destegi=False)

    def _standart_prompt(self, adim: str, baglam: str) -> str:
        return (
            f"Adim: {adim}\n\n"
            f"Onceki adimlar sonuclari:\n{baglam}\n\n"
            f"Bu adimi tamamla. Onceki sonuclari dikkate al. "
            f"Kisa ve net cevap ver. Turkce."
        )

    # ------------------------------------------------------------------ #
    # DOĞRULAMA                                                            #
    # ------------------------------------------------------------------ #
    def _bozuk_cikti_mi(self, text: str) -> bool:
        """Lokal modelden gelen bozuk/anlamsız çıktıyı tespit et."""
        if not text or len(text) < 5:
            return True
        # Anlamlı karakter oranı düşükse bozuk
        anlamli = sum(1 for c in text if c.isalpha())
        if anlamli < 10 or anlamli / max(len(text), 1) < 0.2:
            return True
        # Tekrarlayan sembol kalıpları (örn: _"_"_"_ veya <><><>)
        import re

        if re.search(r"(.{1,3})\1{10,}", text):
            return True
        return False

    async def _dogrula(self, adim: str, sonuc: str) -> str:
        """Adım sonucunun mantıklı/doğru olup olmadığını kontrol et."""
        # Önce bozuk çıktı kontrolü
        if self._bozuk_cikti_mi(sonuc):
            return "BASARISIZ: bozuk veya anlamsiz cikti tespit edildi"

        prompt = (
            f"Asagidaki adim ve sonucunu degerlendır:\n"
            f"Adim: {adim}\n"
            f"Sonuc: {sonuc[:400]}\n\n"
            f"Sadece su formatta cevap ver:\n"
            f"BASARILI: <kisa gerekce>\n"
            f"veya\n"
            f"BASARISIZ: <kisa gerekce>"
        )
        try:
            yanit = await asyncio.wait_for(self.ask_ai(prompt, hafiza_destegi=False), timeout=30)
            return yanit.strip()
        except Exception:
            # Zaman aşımında artık BASARISIZ döndür (önceden BASARILI dönüyordu)
            return "BASARISIZ: dogrulama zaman asimi - sonuc dogrulanamadi"

    # ------------------------------------------------------------------ #
    # ANA ÇALIŞTIRICI                                                      #
    # ------------------------------------------------------------------ #
    async def execute_step(self, adim: str, onceki_sonuclar: list) -> str:
        """Geriye dönük uyumluluk için."""
        return await self._adim_calistir(adim, onceki_sonuclar)

    async def run(self, gorev: str, ilerleme_callback=None) -> dict:
        """
        Tam agent zinciri:
        1. Planla
        2. Her adımı çalıştır (retry + bağlam)
        3. Kritik adımları doğrula
        4. Markdown rapor üret
        """
        baslangic = time.time()
        sonuc = {
            "gorev": gorev,
            "adimlar": [],
            "sonuclar": [],
            "ozet": "",
            "rapor": "",
            "basarili": 0,
            "basarisiz": 0,
            "sure_s": 0,
        }

        async def bildir(mesaj: str):
            if ilerleme_callback:
                try:
                    await ilerleme_callback(mesaj)
                except Exception:
                    pass

        await bildir(f"🧠 Görev planlanıyor: {gorev}")
        adimlar = await self.plan(gorev)
        sonuc["adimlar"] = adimlar
        await bildir(f"📋 {len(adimlar)} adım belirlendi.")

        adim_sonuclari: list[AdimSonucu] = []

        for i, adim in enumerate(adimlar):
            await bildir(f"⚙️ Adım {i+1}/{len(adimlar)}: {adim}")
            as_ = AdimSonucu(adim, i)

            # Retry döngüsü
            for deneme in range(MAX_RETRY + 1):
                as_.deneme = deneme + 1
                t0 = time.perf_counter()
                try:
                    yanit = await asyncio.wait_for(
                        self._adim_calistir(adim, adim_sonuclari), timeout=ADIM_TIMEOUT
                    )
                    # Bozuk çıktı kontrolü → retry
                    if self._bozuk_cikti_mi(yanit):
                        as_.hata = "bozuk/anlamsiz cikti"
                        await bildir(f"⚠️ Adım {i+1} bozuk çıktı, tekrar deneniyor...")
                        continue
                    as_.sonuc = yanit
                    as_.basarili = True
                    as_.sure_ms = int((time.perf_counter() - t0) * 1000)
                    break
                except TimeoutError:
                    as_.hata = f"Zaman aşımı ({ADIM_TIMEOUT}s)"
                    await bildir(f"⏱️ Adım {i+1} zaman aşımı, tekrar deneniyor...")
                except Exception as e:
                    as_.hata = str(e)[:150]
                    await bildir(f"⚠️ Adım {i+1} hata: {as_.hata[:60]}, tekrar...")

            # Doğrulama (başarılı adımlara)
            if as_.basarili and as_.sonuc:
                dogr = await self._dogrula(adim, as_.sonuc)
                as_.dogrulama = dogr
                if "BASARISIZ" in dogr.upper():
                    as_.basarili = False
                    await bildir(f"❌ Adım {i+1} doğrulama başarısız.")
                else:
                    await bildir(f"✅ Adım {i+1} tamamlandı.")
            elif not as_.basarili:
                await bildir(f"❌ Adım {i+1} başarısız: {as_.hata[:60]}")

            adim_sonuclari.append(as_)
            sonuc["sonuclar"].append(
                {
                    "adim": as_.adim,
                    "sonuc": as_.sonuc,
                    "basarili": as_.basarili,
                    "deneme": as_.deneme,
                    "sure_ms": as_.sure_ms,
                    "dogrulama": as_.dogrulama,
                }
            )

        # Sayaçlar
        sonuc["basarili"] = sum(1 for s in adim_sonuclari if s.basarili)
        sonuc["basarisiz"] = sum(1 for s in adim_sonuclari if not s.basarili)
        sonuc["sure_s"] = round(time.time() - baslangic, 1)

        await bildir("📝 Rapor hazırlanıyor...")

        # Özet - tekrar önlemek için max_tokens sınırlı, net format
        ozet_prompt = (
            f"Asagidaki gorev tamamlandi. 2-3 cumlelik KISA ozet yaz. "
            f"Tekrar etme. Turkce.\n\n"
            f"Gorev: {gorev}\n"
            f"Basarili adim: {sonuc['basarili']}/{len(adimlar)}\n"
            f"Adimlar:\n"
            + "\n".join(
                [
                    f"- {s['adim'][:60]}: {'OK' if s['basarili'] else 'HATA'}"
                    for s in sonuc["sonuclar"]
                ]
            )
            + "\n\nOzet (sadece 2-3 cumle, tekrar etme):"
        )
        ozet_ham = await self.ask_ai(ozet_prompt, hafiza_destegi=False)
        # Tekrar eden paragrafları temizle
        sonuc["ozet"] = self._tekrar_temizle(ozet_ham)

        # Markdown rapor
        sonuc["rapor"] = self._rapor_olustur(gorev, adim_sonuclari, sonuc)

        # Hafızaya kaydet
        if self.memory:
            try:
                self.memory.gorev_kaydet(gorev, sonuc["ozet"][:300], "planner")
            except Exception:
                pass

        return sonuc

    def _tekrar_temizle(self, text: str) -> str:
        """Tekrar eden paragrafları ve cümleleri temizle."""
        if not text:
            return text
        # Paragraf bazlı tekilleştir
        paragraflar = [p.strip() for p in text.split("\n\n") if p.strip()]
        goruldu = []
        temiz = []
        for p in paragraflar:
            p_norm = p[:80].lower()  # ilk 80 karakter ile karşılaştır
            if p_norm not in goruldu:
                goruldu.append(p_norm)
                temiz.append(p)
        return "\n\n".join(temiz[:3])  # max 3 paragraf

    # ------------------------------------------------------------------ #
    # RAPOR                                                                #
    # ------------------------------------------------------------------ #
    def _rapor_olustur(self, gorev: str, adim_sonuclari: list, meta: dict) -> str:
        def temizle(s: str) -> str:
            if not s:
                return ""
            s = s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            return s.replace("\ufffd", "").strip()

        baslik = f"# 📋 Agent Raporu\n\n**Görev:** {temizle(gorev)}\n"
        baslik += f"**Süre:** {meta['sure_s']}s | "
        baslik += f"**Başarılı:** {meta['basarili']}/{len(adim_sonuclari)} adım\n\n"
        baslik += "---\n\n"

        adim_bolum = "## Adımlar\n\n"
        for s in adim_sonuclari:
            durum = "✅" if s.basarili else "❌"
            adim_bolum += f"### {durum} Adım {s.index+1}: {temizle(s.adim)}\n"
            if s.sonuc:
                adim_bolum += f"**Sonuç:** {temizle(s.sonuc[:300])}\n"
            if s.hata:
                adim_bolum += f"**Hata:** {temizle(s.hata)}\n"
            if s.dogrulama:
                adim_bolum += f"**Doğrulama:** {temizle(s.dogrulama[:100])}\n"
            adim_bolum += f"*Deneme: {s.deneme} | Süre: {s.sure_ms}ms*\n\n"

        ozet_bolum = f"## Özet\n\n{temizle(meta['ozet'])}\n"

        return baslik + adim_bolum + ozet_bolum
