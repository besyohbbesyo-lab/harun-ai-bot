# finetuning_runner.py - Unsloth tabanlı Fine-Tuning
import json
from datetime import datetime
from pathlib import Path

# Dosya her zaman script ile aynı klasörde
BASE_DIR = Path(__file__).parent.resolve()
EGITIM_DOSYASI = BASE_DIR / "egitim_verisi.jsonl"
TEMIZ_DOSYA = BASE_DIR / "finetuning_data.jsonl"
MODEL_DIR = BASE_DIR / "finetuned_model"
LOG_DOSYASI = BASE_DIR / "finetuning_log.json"
AKTIF_MODEL_KAYIT = BASE_DIR / "aktif_model.json"

# ─────────────────────────────────────────────────────────────
# VERİ DÖNÜŞTÜRME
# ─────────────────────────────────────────────────────────────


def veri_donustur(min_kalite: float = 0.7) -> dict:
    if not EGITIM_DOSYASI.exists():
        return {
            "basari": False,
            "mesaj": f"egitim_verisi.jsonl bulunamadi!\nAranan: {EGITIM_DOSYASI}",
        }

    toplam = 0
    gecen = 0
    elenen = 0
    hatali = 0

    with (
        open(EGITIM_DOSYASI, encoding="utf-8") as f_in,
        open(TEMIZ_DOSYA, "w", encoding="utf-8") as f_out,
    ):
        for satir in f_in:
            satir = satir.strip()
            if not satir:
                continue
            toplam += 1
            try:
                kayit = json.loads(satir)
                kalite = kayit.get("kalite_skoru", kayit.get("reward", 0.5))
                if isinstance(kalite, str):
                    try:
                        kalite = float(kalite)
                    except:
                        kalite = 0.5
                if kalite < min_kalite:
                    elenen += 1
                    continue

                messages = kayit.get("messages", [])
                if not messages or len(messages) < 2:
                    elenen += 1
                    continue

                user_msg = None
                asst_msg = None
                for m in messages:
                    if m.get("role") == "user" and m.get("content"):
                        user_msg = m["content"]
                    elif m.get("role") == "assistant" and m.get("content"):
                        asst_msg = m["content"]

                if not user_msg or not asst_msg:
                    elenen += 1
                    continue
                if len(asst_msg) < 20:
                    elenen += 1
                    continue

                temiz = {
                    "messages": [
                        {
                            "role": "system",
                            "content": "Sen Harun'un kisisel AI asistanisin. Turkce cevap ver.",
                        },
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": asst_msg},
                    ]
                }
                f_out.write(json.dumps(temiz, ensure_ascii=False) + "\n")
                gecen += 1

            except Exception:
                hatali += 1

    return {
        "basari": True,
        "toplam": toplam,
        "gecen": gecen,
        "elenen": elenen,
        "hatali": hatali,
        "dosya": str(TEMIZ_DOSYA),
    }


# ─────────────────────────────────────────────────────────────
# FINE-TUNING (UNSLOTH)
# ─────────────────────────────────────────────────────────────


def finetuning_baslat(
    model_adi: str = "unsloth/Llama-3.2-3B-Instruct",
    epoch: int = 3,
    batch_size: int = 2,
    ilerleme_callback=None,
) -> dict:
    try:
        if ilerleme_callback:
            ilerleme_callback("Unsloth yukleniyor...")

        import torch
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import get_chat_template

        if not torch.cuda.is_available():
            return {"basari": False, "mesaj": "GPU bulunamadi!"}

        gpu_adi = torch.cuda.get_device_name(0)
        if ilerleme_callback:
            ilerleme_callback(f"GPU: {gpu_adi}")

        if not TEMIZ_DOSYA.exists():
            return {"basari": False, "mesaj": "finetuning_data.jsonl bulunamadi!"}

        if ilerleme_callback:
            ilerleme_callback("Model indiriliyor/yukleniyor... (ilk seferde 5-10 dk surebilir)")

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_adi,
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=42,
        )

        tokenizer = get_chat_template(tokenizer, chat_template="llama-3.1")

        def format_chat(ornekler):
            metinler = []
            for msgs in ornekler["messages"]:
                metin = tokenizer.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=False
                )
                metinler.append(metin)
            return {"text": metinler}

        if ilerleme_callback:
            ilerleme_callback("Veri seti yukleniyor...")

        dataset = load_dataset("json", data_files=str(TEMIZ_DOSYA), split="train")
        dataset = dataset.map(format_chat, batched=True)

        if ilerleme_callback:
            ilerleme_callback(f"Egitim baslıyor... {len(dataset)} ornek, {epoch} epoch")

        MODEL_DIR.mkdir(exist_ok=True)

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            dataset_text_field="text",
            max_seq_length=2048,
            dataset_num_proc=2,
            args=SFTConfig(
                per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=4,
                warmup_steps=5,
                num_train_epochs=epoch,
                learning_rate=2e-4,
                fp16=not torch.cuda.is_bf16_supported(),
                bf16=torch.cuda.is_bf16_supported(),
                logging_steps=10,
                optim="adamw_8bit",
                weight_decay=0.01,
                lr_scheduler_type="linear",
                output_dir=str(MODEL_DIR),
                report_to="none",
            ),
        )

        trainer.train()

        if ilerleme_callback:
            ilerleme_callback("Model kaydediliyor...")

        model.save_pretrained(str(MODEL_DIR))
        tokenizer.save_pretrained(str(MODEL_DIR))

        # ─────────────────────────────────────────────
        # GGUF kaydet + botu otomatik güncelle
        # ─────────────────────────────────────────────
        gguf_dir = MODEL_DIR / "gguf"
        gguf_dir.mkdir(exist_ok=True)

        if ilerleme_callback:
            ilerleme_callback("GGUF formatina donusturuluyor...")

        model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method="q4_k_m")

        # Aktif model kaydını güncelle
        # telegram_bot.py bunu okuyarak lokal modeli otomatik değiştirir
        aktif = {
            "zaman": str(datetime.now()),
            "model_adi": "finetuned_model",
            "ollama_model": None,
            "gguf_yol": str(gguf_dir),
            "lora_yol": str(MODEL_DIR),
            "aktif": True,
        }
        with open(AKTIF_MODEL_KAYIT, "w", encoding="utf-8") as f:
            json.dump(aktif, f, ensure_ascii=False, indent=2)

        log = {
            "zaman": str(datetime.now()),
            "model": model_adi,
            "epoch": epoch,
            "veri_sayisi": len(dataset),
            "gpu": gpu_adi,
            "konum": str(MODEL_DIR),
            "gguf_konum": str(gguf_dir),
        }
        with open(LOG_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        return {
            "basari": True,
            "mesaj": (
                f"Fine-tuning tamamlandi!\n"
                f"Veri: {len(dataset)} ornek\n"
                f"Model klasoru: {MODEL_DIR}\n"
                f"Bot yeniden baslatildiginda yeni modeli kullanacak!"
            ),
            "model_konum": str(MODEL_DIR),
            "gguf_konum": str(gguf_dir),
        }

    except ImportError as e:
        return {"basari": False, "mesaj": f"Eksik paket: {e}"}
    except Exception as e:
        return {"basari": False, "mesaj": f"Fine-tuning hatasi: {e}"}


# ─────────────────────────────────────────────────────────────
# AKTİF MODEL KONTROLÜ
# telegram_bot.py bu fonksiyonu çağırarak lokal modeli belirler
# ─────────────────────────────────────────────────────────────


def aktif_model_al() -> dict:
    """Fine-tuned model varsa onu döndür, yoksa varsayılanı"""
    if AKTIF_MODEL_KAYIT.exists():
        try:
            with open(AKTIF_MODEL_KAYIT, encoding="utf-8") as f:
                kayit = json.load(f)
            if kayit.get("aktif") and Path(kayit.get("gguf_yol", "")).exists():
                return kayit
        except Exception:
            pass
    return {"aktif": False}


# ─────────────────────────────────────────────────────────────
# DURUM
# ─────────────────────────────────────────────────────────────


def durum_ozeti() -> str:
    mesaj = "Fine-Tuning Sistemi:\n"

    if EGITIM_DOSYASI.exists():
        boyut = EGITIM_DOSYASI.stat().st_size / 1024 / 1024
        satir = sum(1 for _ in open(EGITIM_DOSYASI, encoding="utf-8"))
        mesaj += f"Ham veri: {boyut:.2f} MB ({satir} kayit)\n"
    else:
        mesaj += "Ham veri: Bulunamadi\n"

    if TEMIZ_DOSYA.exists():
        satir_sayisi = sum(1 for _ in open(TEMIZ_DOSYA, encoding="utf-8"))
        mesaj += f"Hazir ornek: {satir_sayisi}\n"
    else:
        mesaj += "Hazir ornek: Henuz donusturulmedi\n"

    if LOG_DOSYASI.exists():
        with open(LOG_DOSYASI, encoding="utf-8") as f:
            log = json.load(f)
        mesaj += f"Son egitim: {log.get('zaman', '?')[:16]}\n"
        mesaj += f"Veri sayisi: {log.get('veri_sayisi', '?')}\n"
    else:
        mesaj += "Henuz egitim yapilmadi\n"

    aktif = aktif_model_al()
    if aktif.get("aktif"):
        mesaj += f"Aktif model: Fine-tuned ({aktif.get('zaman', '')[:16]})\n"
    else:
        mesaj += "Aktif model: Varsayilan (GLM lokal)\n"

    return mesaj
