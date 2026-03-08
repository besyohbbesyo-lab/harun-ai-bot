# ============================================================
# Harun AI Bot — Multi-Stage Dockerfile
# ============================================================
# Stage 1: Builder  — bağımlılıkları derle
# Stage 2: Runtime  — minimal, nonroot, güvenli
# ============================================================

# -------------------- STAGE 1: BUILDER --------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Sistem derleme bağımlılıkları (bazı pip paketleri için gerekli)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt'yi önce kopyala (Docker cache optimizasyonu)
COPY requirements.txt .

# Bağımlılıkları /install dizinine kur (runtime'a taşımak için)
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# -------------------- STAGE 2: RUNTIME --------------------
FROM python:3.11-slim AS runtime

# Metadata
LABEL maintainer="Harun" \
      description="Harun AI - Kişisel Telegram AI Asistanı" \
      version="1.0"

# Runtime sistem bağımlılıkları
# ffmpeg: ses_plugin.py (OGG→WAV dönüşümü) için gerekli
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Builder'dan Python paketlerini kopyala
COPY --from=builder /install /usr/local

# --- GÜVENLİK: nonroot kullanıcı ---
RUN groupadd --gid 1000 harunbot && \
    useradd --uid 1000 --gid harunbot --shell /bin/bash --create-home harunbot

# Çalışma dizini
WORKDIR /app

# Proje dosyalarını kopyala
COPY --chown=harunbot:harunbot . .

# Log ve data dizinlerini oluştur (nonroot yazabilsin)
RUN mkdir -p /app/logs /app/data /app/exports /app/dataset && \
    chown -R harunbot:harunbot /app/logs /app/data /app/exports /app/dataset

# nonroot kullanıcıya geç
USER harunbot

# Ortam değişkenleri
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# --- HEALTHCHECK ---
# Bot'un çalışıp çalışmadığını kontrol et
# telegram_bot.py'nin process olarak ayakta olduğunu doğrular
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Port (dashboard.py Flask için)
EXPOSE 5000

# Başlatma komutu
CMD ["python", "telegram_bot.py"]
