from core import ab_testing
from services.chat_service import ab_prompt_testini_hazirla


def test_ab_prompt_testini_hazirla_varyantlari_olusturur():
    ab_testing.testleri_sifirla()
    motor = ab_prompt_testini_hazirla()
    adlar = [v.ad for v in motor._varyantlar]
    assert "A_klasik" in adlar
    assert "B_yapisal" in adlar
