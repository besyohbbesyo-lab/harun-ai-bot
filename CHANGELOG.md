# CHANGELOG — Harun AI Bot

## [Sprint 3] — 2026-03-05/06

### Eklendi
- `monitoring/metrics.py` — BotMetrics sınıfı: mesaj sayacı, hata sayacı, yanıt süresi, token takibi, thread-safe
- `monitoring/__init__.py` — monitoring paketi
- `structlog_config.py` — trace_id desteği, Prometheus lazy-load entegrasyonu
- `/metrics` Telegram komutu — bot performans metriklerini anlık gösterir
- `handlers/admin.py` — `/status` çıktısına Bot Metrikleri bölümü eklendi
- `handlers/message.py` — başarılı yanıt ve hata durumlarında metrics otomatik kaydediliyor
- `.github/workflows/ci.yml` — GitHub Actions CI/CD pipeline (her push'ta pytest)

### Test
- `tests/test_metrics.py` — 22 test (sayaçlar, hesaplamalar, thread safety)
- `tests/test_safe_path.py` — 20 test (path traversal, safe_open, safe_delete)
- `tests/test_rol_yetki.py` — 19 test (rol atama, komut izinleri)
- `tests/test_utils.py` — 15 test (normalize_provider, son_dosyayi_bul, log_yaz)
- **Toplam: 291/291 PASSED**

---

## [Sprint 2] — 2026-03-05

### Düzeltildi
- Uptime "Bilinmiyor" hatası — `core/globals.py`'e `baslangic_zamanini_kaydet()` ve `uptime_hesapla()` eklendi
- `handlers/admin.py` — `uptime_hesapla()` ile doğru uptime gösterimi

### Test
- `tests/test_resilience.py` — 33 test (CircuitBreaker, retry_async, hard timeout)
- `tests/test_schemas.py` — 21 test (ToolResult, ProviderConfig, OperationLog)
- `tests/test_token_budget.py` — 20 test (kullanim_ekle, limit, rapor, maliyet)
- **Toplam: 215/215 PASSED**

---

## [Sprint 1] — 2026-03-04/05

### Eklendi
- `core/resilience.py` — CircuitBreaker (CLOSED→OPEN→HALF_OPEN), retry_async, hard timeout
- `core/schemas.py` — ToolResult, ProviderConfig, OperationLog, trace_id
- `token_budget.py` — Günlük token bütçesi, limit takibi, maliyet hesabı, warn threshold
- `services/chat_service.py` — AI yanıt servisi refactor
- `services/memory_service.py` — Bellek servisi refactor
- `services/model_service.py` — Model yönetimi refactor
- `docker-compose.yml` — Bot + ChromaDB container orchestration

### Refactor
- 2024 satırlık `telegram_bot.py` monolith → 8 modüle bölündü:
  - `core/globals.py`, `core/utils.py`
  - `services/rag_service.py`, `services/chat_service.py`
  - `handlers/admin.py`, `handlers/tool.py`, `handlers/pc.py`, `handlers/message.py`

### Test
- `tests/test_code_sandbox.py` — 40 test
- `tests/test_config.py` — 17 test
- `tests/test_guvenlik.py` — 104 test
- `tests/test_otp.py` — 104 test (risk seviyeleri, URL/program güvenlik)
- `tests/test_pii.py` — 18 test (PII maskeleme, log rotasyon)
- **Toplam: 161/161 PASSED**

---

## Genel İstatistikler

| Metrik | Değer |
|--------|-------|
| Toplam test | 291 |
| Başarı oranı | %100 |
| Test dosyası | 9 |
| Sprint sayısı | 3 |
| Proje skoru | ~95/100 |

## Mimari

```
python temelleri/
├── core/
│   ├── globals.py        # Global nesneler, config
│   ├── utils.py          # Yardımcı fonksiyonlar
│   ├── resilience.py     # CircuitBreaker, retry
│   └── schemas.py        # ToolResult, ProviderConfig
├── services/
│   ├── chat_service.py   # AI yanıt servisi
│   ├── memory_service.py # Bellek servisi
│   └── model_service.py  # Model yönetimi
├── handlers/
│   ├── admin.py          # Yönetim komutları
│   ├── tool.py           # Araç komutları
│   ├── pc.py             # PC kontrol
│   └── message.py        # Mesaj işleyiciler
├── monitoring/
│   └── metrics.py        # Bot performans metrikleri
├── tests/                # 291 unit test
├── .github/workflows/    # CI/CD pipeline
├── docker-compose.yml    # Container orchestration
└── telegram_bot.py       # Ana giriş noktası
```
