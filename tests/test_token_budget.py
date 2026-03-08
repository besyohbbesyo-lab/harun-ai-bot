# tests/test_token_budget.py — TokenBudget unit testleri
# pytest -v tests/test_token_budget.py

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def budget(tmp_path):
    """Her test için temiz TokenBudget instance'i."""
    with patch.dict("sys.modules", {"bot_config": type(sys)("bot_config")}):
        sys.modules["bot_config"].CFG = {}
        from token_budget import TokenBudget

        b = TokenBudget()
        b.LOG_DOSYASI = tmp_path / "test_budget.jsonl"
        b._kullanim = 0
        b._maliyet = 0.0
        b._gecmis = []
        return b


class TestTokenBudgetTemel:
    def test_baslangicta_limit_asilmamis(self, budget):
        assert budget.limit_asildimi() is False

    def test_kullanim_ekle_artirir(self, budget):
        budget.kullanim_ekle("llama-3.1-8b-instant", prompt_tokens=100, completion_tokens=200)
        assert budget._kullanim == 300

    def test_coklu_kullanim(self, budget):
        budget.kullanim_ekle("model-a", 100, 200)
        budget.kullanim_ekle("model-b", 50, 150)
        assert budget._kullanim == 500

    def test_limit_asimi(self, budget):
        from token_budget import DAILY_LIMIT

        budget._kullanim = DAILY_LIMIT
        assert budget.limit_asildimi() is True

    def test_rapor_dict(self, budget):
        r = budget.rapor()
        assert isinstance(r, dict)
        assert "kullanim" in r
        assert "limit" in r
        assert "kalan" in r
        assert "yuzde" in r

    def test_rapor_metni_str(self, budget):
        s = budget.rapor_metni()
        assert isinstance(s, str)
        assert "Token" in s

    def test_durum_ozeti_alias(self, budget):
        """durum_ozeti() == rapor_metni()"""
        assert budget.durum_ozeti() == budget.rapor_metni()

    def test_reset(self, budget):
        budget.kullanim_ekle("model-a", 1000, 1000)
        budget.reset()
        assert budget._kullanim == 0
        assert budget._maliyet == 0.0

    def test_consume_true(self, budget):
        assert budget.consume(100) is True
        assert budget._kullanim == 100

    def test_consume_limit_asimi_false(self, budget):
        from token_budget import DAILY_LIMIT

        budget._kullanim = DAILY_LIMIT - 50
        assert budget.consume(100) is False  # 50 kalan ama 100 istendi

    def test_son_kayitlar(self, budget):
        budget.kullanim_ekle("model-a", 10, 20)
        budget.kullanim_ekle("model-b", 30, 40)
        kayitlar = budget.son_kayitlar(n=5)
        assert len(kayitlar) == 2

    def test_maliyet_hesaplaniyor(self, budget):
        budget.kullanim_ekle("llama-3.1-8b-instant", 10000, 10000)
        assert budget._maliyet > 0


class TestTokenBudgetUyari:
    def test_uyari_esigi_raporunda(self, budget):
        from token_budget import DAILY_LIMIT, WARN_THRESHOLD

        budget._kullanim = int(DAILY_LIMIT * WARN_THRESHOLD)
        r = budget.rapor()
        assert r["yuzde"] >= WARN_THRESHOLD * 100


class TestTokenBudgetDurumMetni:
    def test_normal_durum(self, budget):
        r = budget.rapor()
        assert "Normal" in r["durum"]

    def test_limit_asildi_durum(self, budget):
        from token_budget import DAILY_LIMIT

        budget._kullanim = DAILY_LIMIT + 1
        r = budget.rapor()
        assert "LIMIT" in r["durum"]
