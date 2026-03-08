import telegram_bot


def test_komut_listesinde_abtest_ve_ab_force_var():
    komutlar = dict(telegram_bot.komut_listesini_olustur())
    assert "abtest" in komutlar
    assert "ab_force" in komutlar


def test_komut_listesinde_komutlar_benzersiz():
    isimler = [isim for isim, _ in telegram_bot.komut_listesini_olustur()]
    assert len(isimler) == len(set(isimler))
