content = """# Harun AI Bot
.env
*.log
bot_log.txt
guvenlik_log.json
cikti.txt
api_rotator_state.json
policy_state.json
strategy_data.json
reward_history.json
prompt_data.json
model_performans.json
proaktif_ayar.json
proaktif_oneri_log.json
privacy_mode.json
etm_buffer.json
token_budget_log.json
token_budget_log.jsonl
kullanici_soru_log.jsonl
egitim_audit.jsonl
egitim_verisi.jsonl
hata_verisi.jsonl
finetuning_data.jsonl
backups/
memory_db/
data/
temp_ses/
sandbox/
exports/
dataset/
dataset_clean/
finetuning_approved_*.jsonl
*.exe
*.bin
*.zip
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.vscode/
.idea/
*.swp
*.swo
Thumbs.db
.DS_Store
desktop.ini
.pytest_cache/
"""

with open(".gitignore", "w", encoding="utf-8") as f:
    f.write(content)

print("Tamam! .gitignore guncellendi.")
