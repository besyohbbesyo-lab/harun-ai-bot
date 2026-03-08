# Harun AI Telegram Bot — Roadmap & Checklist (2026-02-28)

## A) Şu ana kadar yapılmış/var olanlar (koddaki gerçek durum)
- Telegram bot iskeleti + komut handler’lar var.
- Groq üzerinden cloud cevap üretme fonksiyonu var.
- Ollama local fallback fonksiyonu var.
- Model seçimi, policy/reward/strategy supervisor entegrasyonu var.
- Hafıza (MemorySystem) entegrasyonu var.
- Web araması ile prompt zenginleştirme var.
- Güvenlik katmanı: injection kontrol + rate-limit + kritik komut onay akışı var.
- Doküman üretimi: Word + Sunum komutları var.
- PDF indirici / Kod üretme-çalıştırma / Eğitim store komutları var.
- Opsiyonel: Vision (LLaVA) ve Otomasyon (pyautogui) modülleri try/except ile açılıyor.

## B) ÇALIŞTIRMA ÖNCESİ “tek seferlik” kontrol listesi
1) TOKEN/GROQ key ayarla (telegram_bot.py veya .env)
2) `python -m py_compile telegram_bot.py`
3) `pip install -r requirements.txt` (yoksa oluştur)
4) `python telegram_bot.py` ile botu başlat
5) Telegram: /start → /help → /status

## C) Kritik hatalar / yüksek riskli alanlar
1) Provider dict key uyumsuzluğu (isim/name) — FIX şart
2) Rotator’ın gerçekten key üretiyor mu? (aktif_provider_al/get_active_provider)
3) Plugin dosyaları yoksa import hatası (telegram_bot.py çok fazla plugin import ediyor)
4) Vision/Otomasyon opsiyonel ama komutlar çağrılınca iyi hata mesajı dönmeli
5) /egitim_* komutlarında dosya yazma/okuma path’leri ve izinler

## D) Hemen yapılacaklar (P0 — bugün)
- [ ] Provider şemasını standardize et (name/isim alanları tek tip)
- [ ] requirements.txt oluştur ve sürüm aralıkları ekle
- [ ] .env okuma ekle (TOKEN, GROQ_API_KEY, OLLAMA_URL vs)
- [ ] `__main__` çalıştırma bloğunu kontrol et (Application builder / polling)
- [ ] Basit smoke test: /status, /help, /chat

## E) Yakın dönem (P1 — bu hafta)
- [ ] Logging’i standardize et (bot_log.txt + console)
- [ ] Plugin interface dokümantasyonu (her plugin ne sağlar)
- [ ] Güvenlik testleri (injection örnekleri + rate-limit)
- [ ] Selftest kapsamını genişlet (import test + provider test)

## F) Orta vadeli (P2)
- [ ] CI (GitHub Actions): lint + unit tests
- [ ] PromptEvolution / AEE metriklerini kalıcı store’a bağla
- [ ] Telemetry: latency histogram + error budget
- [ ] Config yönetimi: pydantic settings

## G) “Sık karşılaşılan sorunlar” hızlı teşhis
- Bot açılmıyor → önce `python -m py_compile telegram_bot.py`
- ImportError → eksik plugin dosyaları veya pip paketleri
- Lokal model cevap vermiyor → Ollama çalışıyor mu? `http://localhost:11434`
- Cloud cevap vermiyor → Groq key/rotator cooldown, /api_test çalıştır
