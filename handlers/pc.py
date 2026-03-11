# handlers/pc.py - PC kontrol komutlari
# ekran, tikla, yaz, tus, web, guncel, otomasyon

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from core.decorators import gorev_kaydet, otomasyon_gerekli, yetki_gerekli
from core.globals import (
    MASAUSTU,
    OTOMASYON_AKTIF,
    VISION_AKTIF,
    onay_kaydet,
    onay_mesaji_olustur,
    otomasyon,
    search_engine,
    vision,
)
from core.utils import log_yaz
from services.chat_service import ask_ai


@yetki_gerekli
async def ekran_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not VISION_AKTIF:
        await update.message.reply_text(
            "Vision sistemi aktif degil.\n"
            "LLaVA modeli yuklu olmayabilir.\n"
            "CMD'de su komutu calistir: ollama pull llava"
        )
        return

    soru = (
        " ".join(context.args)
        if context.args
        else "Bu ekrani detayli analiz et ve ne gorduğunu anlat."
    )
    await update.message.reply_text(f"Ekran analiz ediliyor...\nSoru: {soru}")

    try:
        loop = asyncio.get_running_loop()
        ekran_dosyasi = str(MASAUSTU / "ekran_goruntusu.png")
        await loop.run_in_executor(None, vision.take_screenshot, ekran_dosyasi)
        sonuc = await loop.run_in_executor(None, vision.analyze_screen, soru)

        ceviri_prompt = f"Asagidaki metni Turkceye cevir. Sadece ceviriyi yaz:\n\n{sonuc}"
        turkce_sonuc = await ask_ai(ceviri_prompt, hafiza_destegi=False)

        if len(turkce_sonuc) > 4000:
            turkce_sonuc = turkce_sonuc[:4000] + "..."

        await update.message.reply_text(f"Ekran Analizi:\n\n{turkce_sonuc}")
        with open(ekran_dosyasi, "rb") as f:
            await update.message.reply_photo(photo=f, caption="Ekran goruntusu")

        gorev_kaydet(f"Ekran analizi: {soru[:50]}", turkce_sonuc[:200], "vision")
    except Exception as e:
        await update.message.reply_text(f"Vision hatasi: {e}")


@otomasyon_gerekli
async def tikla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OTOMASYON_AKTIF:
        await update.message.reply_text("Otomasyon aktif degil. pip install pyautogui")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Kullanim: /tikla <x> <y>")
        return
    try:
        x, y = int(context.args[0]), int(context.args[1])
        user_id = update.message.chat_id
        onay_kaydet(user_id, "tikla", f"{x},{y}")
        await update.message.reply_text(onay_mesaji_olustur("tikla", f"x={x}, y={y}"))
    except ValueError:
        await update.message.reply_text("x ve y tam sayi olmali. Ornek: /tikla 500 300")


@otomasyon_gerekli
async def yaz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OTOMASYON_AKTIF:
        await update.message.reply_text("Otomasyon aktif degil.")
        return
    if context.args:
        metin = " ".join(context.args)
        user_id = update.message.chat_id
        onay_kaydet(user_id, "yaz", metin)
        await update.message.reply_text(onay_mesaji_olustur("yaz", metin))
    else:
        await update.message.reply_text("Kullanim: /yaz <metin>")


@otomasyon_gerekli
async def tus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OTOMASYON_AKTIF:
        await update.message.reply_text("Otomasyon aktif degil.")
        return
    if context.args:
        tus = " ".join(context.args)
        user_id = update.message.chat_id
        onay_kaydet(user_id, "tus", tus)
        await update.message.reply_text(onay_mesaji_olustur("tus", tus))
    else:
        await update.message.reply_text("Kullanim: /tus <tus>\nOrnek: /tus enter")


@otomasyon_gerekli
async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OTOMASYON_AKTIF:
        await update.message.reply_text("Otomasyon aktif degil.")
        return
    if context.args:
        url = context.args[0]
        user_id = update.message.chat_id
        onay_kaydet(user_id, "web", url)
        await update.message.reply_text(onay_mesaji_olustur("web", url))
    else:
        await update.message.reply_text("Kullanim: /web <url>")


@yetki_gerekli
async def guncel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanim: /guncel <konu>")
        return
    konu = " ".join(context.args)
    await update.message.reply_text(f"'{konu}' hakkinda guncel bilgi aranıyor...")
    try:
        web_content = search_engine.search_and_read(konu)
        prompt = (
            f"'{konu}' hakkinda guncel bilgi ver.\n"
            f"Web kaynakları:\n{web_content[:3000]}\n\n"
            f"Bu bilgileri kullanarak Turkce ozet yaz."
        )
        response = await ask_ai(prompt, gorev_turu="arastirma")
        if len(response) > 4000:
            response = response[:4000] + "..."
        await update.message.reply_text(f"Guncel Bilgi - {konu}:\n\n{response}")
        gorev_kaydet(f"Guncel arama: {konu}", response[:200], "guncel")
    except Exception as e:
        await update.message.reply_text(f"Hata: {e}")


@otomasyon_gerekli
async def otomasyon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OTOMASYON_AKTIF:
        await update.message.reply_text("Otomasyon aktif degil. pip install pyautogui")
        return
    if not context.args:
        await update.message.reply_text(
            "Kullanim: /otomasyon <gorev>\n"
            "Ornek: /otomasyon not defterine merhaba yaz\n"
            "Ornek: /otomasyon youtube.com ac"
        )
        return
    gorev = " ".join(context.args)
    await update.message.reply_text(f"Otomasyon basliyor: {gorev}")

    prompt = f"""Asagidaki bilgisayar gorevini pyautogui komutlari olarak planla:
Gorev: {gorev}

Kullanilabilir komutlar:
- tikla(x, y) - mouse tiklama
- yaz(metin) - klavye ile yaz
- tus_bas(tus) - tus bas (enter, escape, tab vb)
- program_ac(program) - program ac
- web_git(url) - web sitesi ac

Sadece JSON liste formatinda komutlar yaz:
[
  {{"komut": "program_ac", "parametre": "notepad"}},
  {{"komut": "yaz", "parametre": "Merhaba Dunya"}}
]
Baska hicbir sey yazma."""

    response = await ask_ai(prompt, gorev_turu="genel")

    try:
        json_match = re.search(r"\[.*?\]", response, re.DOTALL)
        if json_match:
            adimlar = json.loads(json_match.group())
            sonuclar = []
            for adim in adimlar:
                komut = adim.get("komut")
                parametre = adim.get("parametre", "")

                if komut == "tikla" and isinstance(parametre, list):
                    sonuc = otomasyon.tikla(parametre[0], parametre[1])
                elif komut == "yaz":
                    sonuc = otomasyon.tur_yaz(str(parametre))  # type: ignore[attr-defined]
                elif komut == "tus_bas":
                    sonuc = otomasyon.tus_bas(str(parametre))
                elif komut == "program_ac":
                    sonuc = otomasyon.program_ac(str(parametre))
                elif komut == "web_git":
                    sonuc = otomasyon.web_git(str(parametre))
                elif komut == "enter":
                    sonuc = otomasyon.enter_bas()  # type: ignore[attr-defined]
                else:
                    sonuc = f"Bilinmeyen komut: {komut}"

                sonuclar.append(sonuc)
                await asyncio.sleep(1)

            await update.message.reply_text("Tamamlandi!\n" + "\n".join(sonuclar))
        else:
            await update.message.reply_text(f"AI yaniti:\n{response}")
    except Exception as e:
        await update.message.reply_text(f"Otomasyon hatasi: {e}\nAI yaniti: {response[:200]}")
