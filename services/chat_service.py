# services/chat_service.py - AI yanit servisleri
# ask_groq, ask_llama_local, ask_ai, reward hesaplama
# S1-3: CircuitBreaker entegrasyonu eklendi

import asyncio
import hashlib
import json
import os
import re

# Reward v2 — noise pattern
import re as _re
import time
from datetime import datetime
from pathlib import Path

import httpx
from groq import Groq

from cache_manager import yanit_cache
from core.ab_testing import Varyant, VaryantSonuc, ab_test_al_veya_olustur
from core.globals import (
    CFG,
    ask_deepseek,
    ask_gemini,
    confidence_hesapla,
    confidence_metni_olustur,
    consistency_hesapla,
    consistency_kaydet,
    hata_siniflandir,
    memory,
    model_mgr,
    policy,
    prompt_evo,
    reward_sys,
    rotator,
    search_engine,
    soru_hash_olustur,
    strategy_mgr,
    supervisor,
)
from core.resilience import CircuitOpenError, cb_gemini, cb_groq, cb_ollama
from core.schemas import ToolResult, yeni_trace_id
from core.utils import _safe_active_provider, log_yaz, normalize_provider
from services.rag_service import (
    _rag_build_context,
    _rag_extract_section,
    _rag_extract_usage,
    _rag_get_source_label,
    _rag_wants_verbatim,
)
from token_budget import budget

_REWARD_V2_NOISE_RE = _re.compile(
    r"^\s*(test|ping|deneme|ok|aa+|\.\.+|merhaba|selam|hi|hey|sa)\s*$", _re.IGNORECASE
)


_AB_PROMPT_TESTI = None


_B_YAPISAL_STRES_TERIMLERI = (
    "madde madde",
    "karsilastir",
    "karşılaştır",
    "fark",
    "örnek",
    "ornek",
    "yaygin hata",
    "yaygın hata",
    "senaryo",
    "özet",
    "ozet",
    "her biri icin",
    "her biri için",
)


def _b_yapisal_stres_prompt_mu(prompt: str) -> bool:
    """Cok kosullu / uzun isteklerde B_yapisal'i devre disi birak."""
    q = (prompt or "").strip().lower()
    if not q:
        return False

    sayisal_istek_sayisi = len(re.findall(r"\b\d+\b", q))
    anahtar_skoru = sum(1 for anahtar in _B_YAPISAL_STRES_TERIMLERI if anahtar in q)
    satir_sayisi = q.count("\n") + 1

    return bool(
        len(q) >= 220
        or (anahtar_skoru >= 4 and sayisal_istek_sayisi >= 2)
        or (anahtar_skoru >= 5)
        or (sayisal_istek_sayisi >= 4 and len(q) >= 140)
        or (satir_sayisi >= 5 and anahtar_skoru >= 3)
    )


def _ab_varyanti_bul(motor, varyant_adi: str):
    """Motor icindeki varyanti adina gore bul; yoksa None don."""
    for varyant in getattr(motor, "_varyantlar", []) or []:
        if getattr(varyant, "ad", None) == varyant_adi and getattr(varyant, "aktif", True):
            return varyant
    return None


def b_yapisal_kalite_kontrolu(prompt: str, response: str, smoothed_reward: float):
    """B_yapisal varyanti icin kalite gecip gecmedigini hesaplar."""
    _, rwd_features = compute_reward_v2(prompt, response, smoothed_reward)
    ab_basari = not (rwd_features["answer_len"] < 60 or rwd_features["reward_v2"] < 0.35)
    return ab_basari, rwd_features


def ab_prompt_testini_hazirla():
    """Sohbet/genel cevap stili A/B test varyantlarini startup'ta hazirla."""
    global _AB_PROMPT_TESTI
    if _AB_PROMPT_TESTI is not None:
        return _AB_PROMPT_TESTI

    motor = ab_test_al_veya_olustur("yanit_stili_v1")
    if not getattr(motor, "_varyantlar", None):
        motor.varyant_ekle(Varyant("A_klasik", agirlik=0.5, konfig={"prompt_prefix": ""}))
        motor.varyant_ekle(
            Varyant(
                "B_yapisal",
                agirlik=0.5,
                konfig={
                    "prompt_prefix": (
                        "Cevabini daha yapisal ver. Once kisa ozet yaz, "
                        "ardindan gerekiyorsa madde madde net adimlar ver.\n\n"
                    )
                },
            )
        )
    _AB_PROMPT_TESTI = motor
    return _AB_PROMPT_TESTI


def _ab_prompt_testini_hazirla():
    """Geriye donuk uyumluluk icin private alias."""
    return ab_prompt_testini_hazirla()


def _ab_varyanti_uygula(prompt: str, gorev_turu: str, kullanici_id):
    """A/B varyantini sec ve prompta uygula."""
    if gorev_turu not in ("genel", "sohbet"):
        return prompt, None

    try:
        motor = ab_prompt_testini_hazirla()
        bucket_key = (
            kullanici_id
            if kullanici_id is not None
            else hashlib.md5(prompt[:120].encode()).hexdigest()
        )
        varyant = motor.varyant_sec(bucket_key)

        if getattr(varyant, "ad", None) == "B_yapisal" and _b_yapisal_stres_prompt_mu(prompt):
            fallback = _ab_varyanti_bul(motor, "A_klasik")
            if fallback is None:
                fallback = Varyant("A_klasik", agirlik=0.0, konfig={"prompt_prefix": ""})
            log_yaz(
                "[AB] B_yapisal stres promptta A_klasik'e yonlendirildi",
                "INFO",
            )
            varyant = fallback

        prefix = (varyant.konfig or {}).get("prompt_prefix", "")
        if prefix:
            return prefix + prompt, varyant
        return prompt, varyant
    except Exception as e:
        log_yaz(f"[AB] varyant uygulama hatasi: {e}", "WARNING")
        return prompt, None


def ask_groq(prompt: str, gorev_turu: str = "genel") -> str:
    """Groq ile yanit uret.
    - gorev_turu'na gore model sec (70b / 8b / gemma2)
    - Rate limit → ayni key, daha ucuz modele duş
    - Tum modeller cooldown → hata mesaji
    - S1-3: CircuitBreaker ile sarili
    """
    # S2-4: Token budget kontrolu
    if budget.limit_asildimi():
        print("[TokenBudget] Gunluk limit asildi, Ollama'ya yonlendiriliyor...")
        return None  # ask_ai bunu yakalar ve Ollama'ya yonlendirir

    # CircuitBreaker OPEN mu kontrol et
    if cb_groq.state == cb_groq.OPEN:
        cb_groq._gecis_kontrol()
        if cb_groq.state == cb_groq.OPEN:
            print("[CB:Groq] Devre acik, Ollama'ya yonlendiriliyor...")
            return None  # ask_ai Ollama'ya yonlendirir

    try:
        detay = model_mgr.model_sec_detayli(prompt, gorev_turu)
        tercih_idx = detay.get("groq_idx", 1)
    except Exception:
        tercih_idx = 1

    # Tarih hazırla (bir kez)
    simdi = datetime.now()
    gunler = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = [
        "",
        "Ocak",
        "Subat",
        "Mart",
        "Nisan",
        "Mayis",
        "Haziran",
        "Temmuz",
        "Agustos",
        "Eylul",
        "Ekim",
        "Kasim",
        "Aralik",
    ]
    tarih_str = (
        f"{simdi.day} {aylar[simdi.month]} {simdi.year} "
        f"{gunler[simdi.weekday()]} saat {simdi.strftime('%H:%M')}"
    )

    from api_rotator import GROQ_MODELS

    deneme = 0
    son_hata = ""

    while deneme < len(GROQ_MODELS):
        try:
            provider = rotator.aktif_provider_al(gorev_turu=gorev_turu, tercih_model_idx=tercih_idx)
        except TypeError:
            provider = _safe_active_provider(rotator)

        api_key = (provider or {}).get("api_key") if provider else None
        if not api_key:
            return "Groq Hata: aktif API key bulunamadi (tum key'ler cooldown'da)"

        model_id = (provider or {}).get("model", "llama-3.1-8b-instant")
        max_tokens = (provider or {}).get("max_tokens", 2000)

        def _groq_cagri():
            """CircuitBreaker'a sarılacak senkron Groq çağrısı."""
            client = Groq(api_key=api_key)
            t0 = time.perf_counter()
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {
                        "role": "system",
                        "content": "Sen Harun'un kisisel AI asistanisin. Turkce cevap ver. Asla parantez icinde aciklayici not ekleme.",
                    },
                    {"role": "user", "content": "Bugunun tarihi nedir?"},
                    {"role": "assistant", "content": f"Bugun {tarih_str}."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return response, latency_ms

        try:
            # CircuitBreaker state kontrolü (senkron — lock olmadan)
            cb_groq._gecis_kontrol()
            if cb_groq.state == cb_groq.OPEN:
                raise Exception("CircuitBreaker OPEN")
            # Doğrudan senkron çağrı yap
            response, latency_ms = _groq_cagri()

            yanit = response.choices[0].message.content
            yanit = re.sub(r"\(Aciklayici.*?\)", "", yanit, flags=re.DOTALL).strip()
            yanit = re.sub(r"\(Not:.*?\)", "", yanit, flags=re.DOTALL).strip()

            # Başarı kaydet
            try:
                rotator.basari_kaydet("Groq", latency_ms=latency_ms)
            except Exception:
                pass

            # CircuitBreaker başarı bildir
            with cb_groq._lock if hasattr(cb_groq._lock, "__enter__") else open(os.devnull):
                pass
            cb_groq.failures = 0
            cb_groq.state = cb_groq.CLOSED

            # S2-4: Token kullanimi kaydet
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    budget.kullanim_ekle(
                        model_id,
                        prompt_tokens=getattr(usage, "prompt_tokens", 0),
                        completion_tokens=getattr(usage, "completion_tokens", 0),
                    )
            except Exception:
                pass

            if deneme > 0:
                print(f"[Groq] Fallback basarili: {model_id} (deneme {deneme+1})")

            return yanit

        except CircuitOpenError as e:
            print(f"[CB:Groq] {e}")
            return None  # ask_ai Ollama'ya yonlendirir

        except Exception as e:
            son_hata = str(e)
            print(f"[Groq] {model_id} hata: {son_hata[:80]}")

            # CircuitBreaker hata bildir (senkron)
            cb_groq.failures += 1
            if cb_groq.failures >= cb_groq.threshold:
                cb_groq.state = cb_groq.OPEN
                cb_groq.opened_at = time.time()
                print(f"[CB:Groq] → OPEN ({cb_groq.failures} hata)")

            try:
                rotator.hata_kaydet("Groq", son_hata, cooldown_s=60, model_id=model_id)
            except Exception:
                try:
                    rotator.hata_kaydet("Groq", son_hata, cooldown_s=60)
                except Exception:
                    pass

            tercih_idx = (tercih_idx + 1) % len(GROQ_MODELS)
            deneme += 1

    return f"Groq Hata: tum modeller basarisiz. Son hata: {son_hata}"


async def ask_llama_local(prompt: str) -> str:
    """Yerel model ile yanıt üret - fine-tuned model varsa onu kullan."""
    try:
        _ollama = CFG.get("ollama", {})
        ollama_url = _ollama.get("url", "http://localhost:11434/api/generate")
        ollama_timeout = _ollama.get("timeout", 120)

        model_adi = _ollama.get("default_model", "haervwe/GLM-4.6V-Flash-9B")
        try:
            from finetuning_runner import aktif_model_al

            aktif = aktif_model_al()
            if aktif.get("aktif") and aktif.get("ollama_model"):
                model_adi = aktif["ollama_model"]
                print(f"[Fine-tuned model kullaniliyor: {model_adi}]")
        except Exception:
            pass

        async def _ollama_cagri():
            async with httpx.AsyncClient(timeout=ollama_timeout) as client:
                response = await client.post(
                    ollama_url, json={"model": model_adi, "prompt": prompt, "stream": False}
                )
                return response.json()

        # S1-3: CircuitBreaker ile Ollama çağrısı
        try:
            data = await cb_ollama.call(_ollama_cagri, hard_timeout=ollama_timeout + 5)
        except CircuitOpenError as e:
            return f"Lokal Hata: {e}"

        yanit = data.get("response", "")
        yanit = yanit.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        yanit = yanit.replace("\ufffd", "").strip()
        anlamli = sum(1 for c in yanit if c.isalpha())
        if not yanit or anlamli < 10:
            return "Lokal Hata: bozuk veya bos cevap"
        return yanit

    except Exception as e:
        return f"Lokal Hata: {e}"


GUNCEL_KONULAR = [
    "haber",
    "guncel",
    "bugun",
    "dun",
    "bu hafta",
    "son dakika",
    "son",
    "yeni",
    "2024",
    "2025",
    "2026",
    "fiyat",
    "dolar",
    "euro",
    "borsa",
    "kripto",
    "bitcoin",
    "secim",
    "mac",
    "skor",
    "sampiyonluk",
    "deprem",
    "hava durumu",
    "hava",
    "yasadi",
    "oldu",
    "acikladi",
    "transfer",
    "piyasa",
    "faiz",
    "enflasyon",
    "doviz",
    "altin",
]


def guncel_bilgi_gerekli_mi(soru: str) -> bool:
    return any(k in soru.lower() for k in GUNCEL_KONULAR)


def web_aramasiyla_zenginlestir(soru: str) -> str:
    try:
        sonuc = search_engine.search_and_read(soru)
        if sonuc and len(sonuc) > 100:
            return sonuc[:2000]
        return ""
    except Exception:
        return ""


def compute_reward_v2(prompt_text: str, answer_text: str, base_reward: float) -> tuple[float, dict]:
    """Reward v2: base_reward (v1) + kalite bonusu - ceza skorları."""
    p = (prompt_text or "").strip()
    a = (answer_text or "").strip()

    noise_flag = bool(_REWARD_V2_NOISE_RE.match(p)) or (len(p) < 6)
    command_flag = p.startswith("/") or bool(
        re.match(r"^\s*(mkdir|mkfile|open|rm|del|copy|move)\b", p, re.IGNORECASE)
    )

    a_len = len(a)
    p_len = len(p)
    long_enough = 1.0 if a_len >= 220 else (0.6 if a_len >= 120 else (0.3 if a_len >= 60 else 0.0))
    has_steps = 1.0 if re.search(r"(^|\n)\s*(\d+\)|\d+\.|-\s)", a) else 0.0
    has_sections = 1.0 if re.search(r"\n\s*#|\n\s*##", a) else 0.0

    words = re.findall(r"\w+", a.lower())
    uniq_ratio = (len(set(words)) / len(words)) if words else 1.0
    rep_score = 1.0 - min(1.0, max(0.0, uniq_ratio))
    repetition_penalty = 0.25 * rep_score

    noise_penalty = 0.45 if noise_flag else 0.0
    command_penalty = 0.25 if command_flag else 0.0

    errorish = bool(re.search(r"\b(hata|alinamadi|error|exception)\b", a, re.IGNORECASE))
    error_penalty = 0.20 if errorish else 0.0

    quality_bonus = 0.0
    quality_bonus += 0.10 * long_enough
    quality_bonus += 0.07 * has_steps
    quality_bonus += 0.05 * has_sections

    v2 = (
        float(base_reward)
        + quality_bonus
        - (noise_penalty + command_penalty + repetition_penalty + error_penalty)
    )
    v2 = max(0.0, min(1.0, v2))

    features = {
        "reward_v1": round(float(base_reward), 4),
        "reward_v2": round(float(v2), 4),
        "quality_bonus": round(float(quality_bonus), 4),
        "noise_flag": int(noise_flag),
        "command_flag": int(command_flag),
        "rep_score": round(float(rep_score), 4),
        "noise_penalty": round(float(noise_penalty), 4),
        "command_penalty": round(float(command_penalty), 4),
        "repetition_penalty": round(float(repetition_penalty), 4),
        "error_penalty": round(float(error_penalty), 4),
        "prompt_len": int(p_len),
        "answer_len": int(a_len),
    }
    return v2, features


def auto_moderation_suggest(reward_v2: float) -> str:
    """Dry-run öneri: AUTO_APPROVE / AUTO_REJECT / MANUAL"""
    try:
        t_high = float(os.getenv("EGITIM_T_HIGH", "0.82"))
        t_low = float(os.getenv("EGITIM_T_LOW", "0.35"))
    except Exception:
        t_high, t_low = 0.82, 0.35

    if reward_v2 >= t_high:
        return "AUTO_APPROVE"
    if reward_v2 <= t_low:
        return "AUTO_REJECT"
    return "MANUAL"


async def ask_ai(
    prompt: str, hafiza_destegi: bool = True, gorev_turu: str = "genel", kullanici_id=None
) -> str:
    baslangic = time.time()
    trace_id = yeni_trace_id()  # S1-5: Her islem icin trace_id

    # S3-5: Cache kontrolu
    cache_key = yanit_cache._key_olustur(prompt, gorev_turu)
    cached = yanit_cache.al(cache_key)
    if cached:
        print(f"[Cache:{trace_id}] Hit — cache'den donduruluyor")
        return cached

    try:
        # Supervisor + policy parametreleri
        sup_params = supervisor.mod_belirle(gorev_turu, prompt[:100])
        params = policy.runtime_parametreleri_al(gorev_turu)
        params["retrieval_depth"] = sup_params["retrieval_depth"]
        params["mod"] = sup_params["mod"]
        hafiza_destegi = sup_params["hafiza_destegi"] and hafiza_destegi

        # Prompt Evolution
        prompt_id, prompt_sablon = prompt_evo.prompt_sec(gorev_turu)
        if prompt_sablon and "{prompt}" in prompt_sablon:
            prompt = prompt_sablon.format(prompt=prompt)
        elif prompt_sablon and "{soru}" in prompt_sablon:
            prompt = prompt_sablon.format(soru=prompt)

        # Güncel bilgi gerekiyor mu?
        if guncel_bilgi_gerekli_mi(prompt) and gorev_turu in ("sohbet", "genel"):
            web_bilgi = web_aramasiyla_zenginlestir(prompt[:100])
            if web_bilgi:
                prompt = (
                    f"{prompt}\n\n"
                    f"[Guncel Web Bilgisi]\n{web_bilgi}\n[/Guncel Web Bilgisi]\n"
                    f"Lutfen bu guncel bilgileri kullanarak cevap ver."
                )

        # Hafıza desteği
        if hafiza_destegi:
            n = params["retrieval_depth"]
            gecmis = memory.benzer_gorev_bul(prompt[:100], n=min(n, 3))
            bilgiler = memory.bilgi_ara(prompt[:100], n=min(n, 3))
            ek_bilgi = ""
            if gecmis:
                ek_bilgi += f"\nGecmis deneyimler: {' | '.join(gecmis[:2])}"
            if bilgiler:
                ek_bilgi += f"\nIlgili bilgiler: {' | '.join(bilgiler[:2])}"

            try:
                prosedur_ref = memory.prosedur.prosedur_bul(prompt[:100], gorev_turu)
                if prosedur_ref:
                    ek_bilgi += f"\n{prosedur_ref}"
            except Exception:
                pass

            try:
                aniler = memory.episodik.ani_bul(prompt[:100], n=1)
                if aniler:
                    ani = aniler[0]
                    ek_bilgi += f"\n[Ilgili Ani: {ani['baslik']}] {ani['icerik'][:150]}"
            except Exception:
                pass

            if ek_bilgi:
                prompt = prompt + f"\n\n[Hafiza]{ek_bilgi}[/Hafiza]"

        # RAG v5: KB injection
        try:
            rag_enabled = (os.getenv("RAG_ENABLED", "1") or "1").strip() != "0"
            if rag_enabled and gorev_turu in ("sohbet", "genel", "kod", "word", "sunum"):
                ctx, hits = _rag_build_context(prompt, top_k=6)
                if ctx and hits:
                    if _rag_wants_verbatim(prompt):
                        _, best_row = hits[0]
                        best_text = (best_row or {}).get("text", "").strip()
                        ql = (prompt or "").lower()
                        if ("kullanim" in ql) or ("kullanım" in ql):
                            sec = _rag_extract_usage(best_text) or _rag_extract_usage(ctx)
                            if sec:
                                return sec + _rag_get_source_label(hits)
                        if best_text:
                            return best_text + _rag_get_source_label(hits)

                    src_label = _rag_get_source_label(hits).strip()
                    prompt = (
                        "[PROJE_KB]\n" + ctx + "\n[/PROJE_KB]\n\n"
                        "KURALLAR:\n"
                        "- Cevabi PROJE_KB icindeki bilgilere dayandir.\n"
                        "- KB'de yoksa uydurma; emin degilsen soyle.\n"
                        "- Cevabinin sonuna su kaynak etiketini ekle: " + src_label + "\n\n"
                        "SORU:\n" + prompt
                    )
        except Exception:
            pass

        prompt, secilen_varyant = _ab_varyanti_uygula(prompt, gorev_turu, kullanici_id)

        # Model seçimi
        secilen_model = model_mgr.model_sec(prompt, gorev_turu)
        basari = False
        response = ""
        provider = None

        if secilen_model == "lokal":
            print(f"[GLM-Lokal:{trace_id}] basit gorev, lokale gonderiliyor...")
            response = await ask_llama_local(prompt)
            basari = "Lokal Hata" not in response
            if not basari:
                secilen_model = "cloud"

        if secilen_model == "cloud":
            provider = _safe_active_provider(rotator)

            if provider:
                prov_adi = provider.get("name") or provider.get("isim", "Groq")
                print(f"[{prov_adi}:{trace_id}] cloud'a gonderiliyor...")

                try:
                    # S1-3: Provider'a gore dogru CircuitBreaker sec
                    if prov_adi == "Gemini":
                        response = await cb_gemini.call(
                            ask_gemini,
                            prompt,
                            provider["api_key"],
                            provider["model"],
                            hard_timeout=30,
                        )
                    elif prov_adi == "DeepSeek":
                        response = await cb_gemini.call(  # DeepSeek icin gemini CB kullan
                            ask_deepseek,
                            prompt,
                            provider["api_key"],
                            provider["model"],
                            hard_timeout=30,
                        )
                    else:  # Groq
                        loop = asyncio.get_running_loop()
                        response = await loop.run_in_executor(
                            None, lambda: ask_groq(prompt, gorev_turu)
                        )

                    if response:
                        basari = True
                        rotator.basari_kaydet(prov_adi)
                        print(f"[{prov_adi}:{trace_id}] basarili")

                except CircuitOpenError as e:
                    print(f"[CB:{trace_id}] {e} — yedek deneniyor")

                except Exception as e:
                    hata = str(e)
                    print(f"[{prov_adi}:{trace_id}] hata: {hata[:80]}")
                    rotator.hata_kaydet(prov_adi, hata)

                # Yedek provider dene (ilk basarisizsa)
                if not basari:
                    provider2 = _safe_active_provider(rotator)
                    if provider2:
                        p2_adi = provider2.get("name") or provider2.get("isim", "Groq")
                        if p2_adi != prov_adi:
                            try:
                                if p2_adi == "Gemini":
                                    response = await cb_gemini.call(
                                        ask_gemini,
                                        prompt,
                                        provider2["api_key"],
                                        provider2["model"],
                                        hard_timeout=30,
                                    )
                                elif p2_adi == "DeepSeek":
                                    response = await cb_gemini.call(
                                        ask_deepseek,
                                        prompt,
                                        provider2["api_key"],
                                        provider2["model"],
                                        hard_timeout=30,
                                    )
                                else:
                                    loop = asyncio.get_running_loop()
                                    response = await loop.run_in_executor(
                                        None, lambda: ask_groq(prompt, gorev_turu)
                                    )
                                if response:
                                    basari = True
                                    provider = provider2
                                    rotator.basari_kaydet(p2_adi)
                                    print(f"[{p2_adi}:{trace_id}] yedek basarili")
                            except Exception as e2:
                                p2_adi2 = provider2.get("name") or provider2.get("isim", "?")
                                rotator.hata_kaydet(p2_adi2, str(e2))

            # Tum cloud basarisizsa → Ollama
            if not basari or not response:
                print(f"[{trace_id}] Tum cloud basarisiz → Ollama")
                response = await ask_llama_local(prompt)
                basari = "Lokal Hata" not in response

        # AEE güncelle
        sure = time.time() - baslangic
        smoothed_reward = reward_sys.hesapla(basari, sure, len(prompt) // 4)
        policy.guncelle(basari, sure / 10.0)

        imza = strategy_mgr.imza_olustur(
            gorev_turu, params["mod"], ["groq", "llama"], params["retrieval_depth"]
        )
        strategy_mgr.sonuc_kaydet(imza, gorev_turu, basari, sure, smoothed_reward)
        supervisor.guclendir(basari)

        if prompt_id:
            prompt_evo.sonuc_kaydet(prompt_id, basari)
        if basari and smoothed_reward > 0.6:
            memory.hafizayi_guclendir(prompt[:100], smoothed_reward)

        # Episodik + Prosedürel hafıza
        try:
            if basari and smoothed_reward > 0.75:
                orijinal_prompt = prompt.split("\n\n[Hafiza]")[0]
                baslik = f"{gorev_turu}: {orijinal_prompt[:60]}"
                memory.episodik.ani_kaydet(
                    baslik=baslik,
                    icerik=f"Soru: {orijinal_prompt[:200]}\nYanit: {response[:300]}",
                    onem=smoothed_reward,
                    etiketler=[gorev_turu, "basarili"],
                )
                adimlar = []
                for satir in [s.strip() for s in response.split("\n") if s.strip()][:5]:
                    if len(satir) > 15:
                        adimlar.append(satir[:100])
                if len(adimlar) >= 2:
                    memory.prosedur.prosedur_kaydet(
                        gorev_tanimi=orijinal_prompt[:80],
                        adimlar=adimlar,
                        basari_orani=smoothed_reward,
                        gorev_turu=gorev_turu,
                    )
        except Exception:
            pass

        # Self-Consistency
        c_skoru = 0.5
        try:
            s_hash = soru_hash_olustur(prompt[:100])
            consistency_kaydet(s_hash, response, "dusuk")

            if smoothed_reward < 0.5 or len(response) < 80:
                try:
                    aktif_provider = _safe_active_provider(rotator)
                    if aktif_provider:
                        ap_adi = aktif_provider.get("name") or aktif_provider.get("isim", "Groq")
                        if ap_adi == "Gemini":
                            yanit2 = await ask_gemini(
                                prompt, aktif_provider["api_key"], aktif_provider["model"]
                            )
                        else:
                            loop2 = asyncio.get_running_loop()
                            yanit2 = await loop2.run_in_executor(
                                None, lambda: ask_groq(prompt, gorev_turu)
                            )
                        consistency_kaydet(s_hash, yanit2, "yuksek")
                        c_skoru = consistency_hesapla(s_hash)
                        print(f"[Consistency:{trace_id}] skor={c_skoru}")
                except Exception:
                    pass
        except Exception:
            pass

        # Confidence hesapla
        try:
            hata_tipi = hata_siniflandir(response)
            confidence = confidence_hesapla(
                response, sure, basari, smoothed_reward, hata_tipi, c_skoru
            )
            model_adi = (
                (provider.get("name") or provider.get("isim", "Lokal"))
                if (secilen_model == "cloud" and provider)
                else "Lokal"
            )
            guven_satiri = confidence_metni_olustur(confidence, hata_tipi, model_adi, c_skoru)
            response = response + guven_satiri
        except Exception:
            pass

        try:
            if secilen_varyant is not None:
                motor = ab_prompt_testini_hazirla()

                # B_yapisal kalite kontrolü: kısa veya düşük kaliteli yanıtlar başarısız sayılır
                ab_basari = basari
                if basari and secilen_varyant.ad == "B_yapisal":
                    try:
                        ab_basari, rwd_features = b_yapisal_kalite_kontrolu(
                            prompt, response, smoothed_reward
                        )
                        if not ab_basari:
                            log_yaz(
                                f"[AB] B_yapisal kalite reddedildi: "
                                f"len={rwd_features['answer_len']} "
                                f"r2={rwd_features['reward_v2']:.3f}",
                                "WARNING",
                            )
                    except Exception as qe:
                        log_yaz(f"[AB] B_yapisal kalite kontrol hatasi: {qe}", "WARNING")

                motor.sonuc_kaydet(
                    VaryantSonuc(
                        varyant_adi=secilen_varyant.ad,
                        kullanici_id=str(kullanici_id)
                        if kullanici_id is not None
                        else hashlib.md5(prompt[:120].encode()).hexdigest(),
                        basarili=ab_basari,
                        sure_ms=sure * 1000.0,
                        metadata={"gorev_turu": gorev_turu},
                    )
                )
        except Exception as e:
            log_yaz(f"[AB] sonuc kayit hatasi: {e}", "WARNING")

        # S3-5: Basarili yaniti cache'e kaydet
        if response:
            yanit_cache.koy(cache_key, response)

        print(f"[ask_ai:{trace_id}] tamamlandi — {sure:.2f}s, basari={basari}")
        return response if response else "Yanit alinamadi."

    except Exception as e:
        print(f"[ask_ai:{trace_id}] genel hata: {e}")
        return await ask_llama_local(prompt)
