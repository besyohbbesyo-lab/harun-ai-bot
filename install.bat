@echo off
chcp 65001 >nul
echo ============================================
echo  Harun AI Bot - Kurulum Basliyor
echo ============================================
echo.

REM Python kontrolu
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo Lutfen https://python.org adresinden Python 3.11 kurun.
    pause
    exit /b 1
)
echo [OK] Python bulundu.

REM pip guncelle
echo.
echo [1/4] pip guncelleniyor...
python -m pip install --upgrade pip --quiet

REM Bagimliliklar
echo [2/4] Bagimliliklar yukleniyor...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [HATA] Bagimlilik yuklemesi basarisiz!
    pause
    exit /b 1
)
echo [OK] Bagimliliklar yuklendi.

REM .env dosyasi
echo [3/4] .env dosyasi kontrol ediliyor...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [OK] .env.example kopyalandi → .env
        echo [!!] Lutfen .env dosyasini duzenleyip API anahtarlarini girin!
    ) else (
        echo [UYARI] .env.example bulunamadi, .env elle olusturulacak.
        echo TELEGRAM_TOKEN=buraya_yaz> .env
        echo GROQ_API_KEY=buraya_yaz>> .env
        echo [!!] .env dosyasini duzenleyin!
    )
) else (
    echo [OK] .env mevcut, atlanıyor.
)

REM Testler
echo [4/4] Testler calistiriliyor...
pytest tests/ -q --tb=short
if errorlevel 1 (
    echo [UYARI] Bazi testler basarisiz. Yukaridaki hatalari inceleyin.
) else (
    echo [OK] Tum testler gecti.
)

echo.
echo ============================================
echo  Kurulum tamamlandi!
echo  Baslatmak icin: python telegram_bot.py
echo ============================================
pause
