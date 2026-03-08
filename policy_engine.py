# policy_engine.py
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
POLICY_DOSYASI = BASE_DIR / "policy_state.json"


class PolicyEngine:
    def __init__(self):
        self.state = self._yukle()
        self.performance_window = []
        self.WINDOW_SIZE = 50

    def _yukle(self) -> dict:
        """Policy durumunu dosyadan yükle"""
        try:
            if POLICY_DOSYASI.exists():
                with open(POLICY_DOSYASI, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Policy yukle hatasi: {e}")
        return {
            "success_rate": 0.5,
            "avg_cost": 1.0,
            "exploration_rate": 0.3,
            "confidence_score": 0.5,
            "total_tasks": 0,
            "last_updated": str(datetime.now()),
        }

    def _kaydet(self):
        """Policy durumunu dosyaya kaydet"""
        try:
            self.state["last_updated"] = str(datetime.now())
            with open(POLICY_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Policy kayit hatasi: {e}")

    def guncelle(self, basari: bool, maliyet: float = 1.0):
        """Görev sonucuna göre policy güncelle"""
        self.performance_window.append({"basari": 1.0 if basari else 0.0, "maliyet": maliyet})

        if len(self.performance_window) > self.WINDOW_SIZE:
            self.performance_window.pop(0)

        self.state["success_rate"] = sum(r["basari"] for r in self.performance_window) / len(
            self.performance_window
        )

        self.state["avg_cost"] = sum(r["maliyet"] for r in self.performance_window) / len(
            self.performance_window
        )

        self.state["exploration_rate"] = max(0.05, self.state["exploration_rate"] * 0.998)

        stabilite = min(1.0, len(self.performance_window) / 20)
        self.state["confidence_score"] = self.state["success_rate"] * stabilite

        self.state["total_tasks"] += 1
        self._kaydet()

    def runtime_parametreleri_al(self, gorev_turu: str = "genel") -> dict:
        """Göreve göre dinamik parametreler üret"""
        risk = self._risk_hesapla(gorev_turu)
        confidence = self.state["confidence_score"]

        temperature = max(
            0.1, min(1.0, 0.4 - (risk * 0.2) + (self.state["exploration_rate"] * 0.3))
        )

        if risk > 0.7 or confidence < 0.4:
            mod = "derin"
            retrieval_depth = 5
            reasoning_depth = 4
        elif risk < 0.3 and confidence > 0.8:
            mod = "hizli"
            retrieval_depth = 2
            reasoning_depth = 1
        else:
            mod = "dengeli"
            retrieval_depth = 3
            reasoning_depth = 2

        return {
            "temperature": temperature,
            "retrieval_depth": retrieval_depth,
            "reasoning_depth": reasoning_depth,
            "mod": mod,
            "exploration_rate": self.state["exploration_rate"],
            "confidence": confidence,
        }

    def _risk_hesapla(self, gorev_turu: str) -> float:
        """Görev türüne göre risk skoru"""
        risk_haritasi = {
            "kod": 0.6,
            "arastirma": 0.4,
            "sohbet": 0.2,
            "planner": 0.7,
            "pdf": 0.3,
            "sunum": 0.4,
            "word": 0.4,
            "vision": 0.5,
            "genel": 0.5,
        }
        return risk_haritasi.get(gorev_turu, 0.5)

    def ozet(self) -> str:
        params = self.runtime_parametreleri_al()
        return (
            f"Policy Durumu:\n"
            f"Basari orani: %{self.state['success_rate']*100:.1f}\n"
            f"Guven skoru: {self.state['confidence_score']:.2f}\n"
            f"Kesif orani: {self.state['exploration_rate']:.3f}\n"
            f"Aktif mod: {params['mod']}\n"
            f"Toplam gorev: {self.state['total_tasks']}"
        )
