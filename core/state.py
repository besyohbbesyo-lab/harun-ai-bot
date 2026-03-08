# core/state.py — S5-3: globals.py refactoring
# Sorumluluk: Calisma zamani durumu (runtime state)

# Fine-tuning onay durumu
finetuning_onay_bekliyor: bool = False

# Kullanici bazli son yanit takibi {user_id: {soru, yanit, gorev_turu}}
_son_yanit: dict = {}


def son_yanit_kaydet(user_id: int, soru: str, yanit: str, gorev_turu: str = "genel"):
    _son_yanit[user_id] = {"soru": soru, "yanit": yanit, "gorev_turu": gorev_turu}


def son_yanit_al(user_id: int) -> dict | None:
    return _son_yanit.get(user_id)


def son_yanit_temizle(user_id: int):
    _son_yanit.pop(user_id, None)
