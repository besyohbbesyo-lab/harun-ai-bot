# memory_plugin.py - AEE Aşama 2: Short-term Memory + Reward + Decay destekli
import math
from collections import deque
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

BASE_DIR = Path(__file__).parent.resolve()

# ─────────────────────────────────────────────────────────────
# SHORT-TERM MEMORY (RAM'de, per-user, son 10 mesaj)
# ─────────────────────────────────────────────────────────────

_short_term: dict[int, deque] = {}  # {user_id: deque([{"role": ..., "content": ...}])}
STM_MAX = 20  # S2-1: 10'dan 20'ye genisletildi


def stm_ekle(user_id: int, rol: str, icerik: str):
    """Short-term memory'e mesaj ekle (max 20)"""
    if user_id not in _short_term:
        _short_term[user_id] = deque(maxlen=STM_MAX)
    _short_term[user_id].append(
        {"role": rol, "content": icerik, "zaman": datetime.now().strftime("%H:%M")}
    )


def stm_al(user_id: int) -> list:
    """Kullanicinin kisa sure hafizasini domdur"""
    if user_id not in _short_term:
        return []
    return list(_short_term[user_id])


def stm_temizle(user_id: int):
    """Kullanicinin kisa sure hafizasini temizle"""
    if user_id in _short_term:
        _short_term[user_id].clear()


def stm_baglam_olustur(user_id: int) -> str:
    """
    Son 10 mesajdan prompt'a eklenecek baglam metni olustur.
    Cok eski veya cok tekrarlayan mesajlari dahil etme.
    """
    mesajlar = stm_al(user_id)
    if not mesajlar:
        return ""

    satirlar = []
    for m in mesajlar:
        rol_adi = "Sen" if m["role"] == "user" else "Asistan"
        icerik = m["content"][:200]  # Cok uzun olmasin
        if icerik:
            satirlar.append(f"{rol_adi} [{m.get('zaman', '')}]: {icerik}")

    if not satirlar:
        return ""

    return "[Onceki Konusma]\n" + "\n".join(satirlar) + "\n[/Onceki Konusma]"


# ─────────────────────────────────────────────────────────────
# S2-1: EPİSODİK GEÇİŞ HAFIZASI (ETM - 24 saatlik ara depo)
# STM (RAM, 20 mesaj) → ETM (JSON, 24 saat) → LTM (ChromaDB, kalici)
# ─────────────────────────────────────────────────────────────
import json as _json

ETM_DOSYA = BASE_DIR / "etm_buffer.json"
ETM_SURE_SAAT = 24  # Maksimum tutma suresi
ETM_CONSOLIDATE_ESIK = 0.6  # Bu skorun uzerindekiler LTM'ye tasinir
ETM_DECAY_YARI_OMUR = 6.0  # 6 saatte skor yarisina duser


class EpisodicTransitionMemory:
    """24 saatlik gecis hafizasi. JSON tabanli, hafif."""

    def __init__(self, dosya_yolu=None):
        self._dosya = dosya_yolu or ETM_DOSYA
        self._kayitlar = []
        self._yukle()

    def _yukle(self):
        try:
            if Path(self._dosya).exists():
                with open(self._dosya, encoding="utf-8") as f:
                    self._kayitlar = _json.load(f)
            else:
                self._kayitlar = []
        except Exception as e:
            print(f"[ETM] Yukleme hatasi: {e}")
            self._kayitlar = []

    def _kaydet(self):
        try:
            with open(self._dosya, "w", encoding="utf-8") as f:
                _json.dump(self._kayitlar, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[ETM] Kaydetme hatasi: {e}")

    def ekle(
        self,
        icerik: str,
        tur: str = "sohbet",
        onem: float = 0.5,
        user_id: int = 0,
        meta: dict = None,
    ):
        """ETM'ye yeni kayit ekle."""
        kayit = {
            "icerik": icerik[:500],
            "tur": tur,
            "onem": round(onem, 3),
            "zaman": datetime.now().isoformat(),
            "user_id": user_id,
            "erisim": 0,
            "meta": meta or {},
        }
        self._kayitlar.append(kayit)
        self._kaydet()

    def ara(self, sorgu: str, n: int = 3) -> list:
        """Basit keyword arama (ETM kucuk oldugu icin embedding gereksiz)."""
        self._suresi_dolanlari_temizle()
        sorgu_lower = sorgu.lower()
        kelimeler = sorgu_lower.split()

        skorlu = []
        now = datetime.now()
        for k in self._kayitlar:
            # Keyword esleme
            icerik_lower = k["icerik"].lower()
            eslesme = sum(1 for kel in kelimeler if kel in icerik_lower)
            if eslesme == 0:
                continue

            # Decay hesapla
            try:
                kayit_zaman = datetime.fromisoformat(k["zaman"])
                saat_farki = (now - kayit_zaman).total_seconds() / 3600
                decay = math.exp(-math.log(2) * saat_farki / ETM_DECAY_YARI_OMUR)
            except Exception:
                decay = 0.5

            skor = (eslesme / max(1, len(kelimeler))) * decay * k.get("onem", 0.5)
            skorlu.append((skor, k))

        skorlu.sort(key=lambda x: x[0], reverse=True)
        # Erisim sayisini guncelle
        for _, k in skorlu[:n]:
            k["erisim"] = k.get("erisim", 0) + 1
        if skorlu:
            self._kaydet()
        return [k for _, k in skorlu[:n]]

    def consolidate(self, memory_system) -> int:
        """Yuksek skorlu ETM kayitlarini LTM'ye tasi.
        Doner: tasilan kayit sayisi."""
        self._suresi_dolanlari_temizle()
        tasinan = 0
        kalan = []
        now = datetime.now()

        for k in self._kayitlar:
            try:
                kayit_zaman = datetime.fromisoformat(k["zaman"])
                saat_farki = (now - kayit_zaman).total_seconds() / 3600
                decay = math.exp(-math.log(2) * saat_farki / ETM_DECAY_YARI_OMUR)
            except Exception:
                decay = 0.5
                saat_farki = 12

            guncel_skor = k.get("onem", 0.5) * decay
            erisim_bonus = min(0.2, k.get("erisim", 0) * 0.05)
            final_skor = guncel_skor + erisim_bonus

            # Yuksek skorlular LTM'ye
            if final_skor >= ETM_CONSOLIDATE_ESIK:
                try:
                    memory_system.gorev_kaydet(
                        gorev=k["icerik"][:100],
                        sonuc=k["icerik"],
                        tur=k.get("tur", "etm_consolidate"),
                        reward=final_skor,
                        basari=True,
                    )
                    tasinan += 1
                except Exception as e:
                    print(f"[ETM] LTM tasima hatasi: {e}")
                    kalan.append(k)  # Basarisiz olursa tut
            else:
                kalan.append(k)

        self._kayitlar = kalan
        self._kaydet()
        if tasinan > 0:
            print(f"[ETM] {tasinan} kayit LTM'ye konsolide edildi")
        return tasinan

    def _suresi_dolanlari_temizle(self):
        """24 saati gecen kayitlari sil."""
        now = datetime.now()
        onceki = len(self._kayitlar)
        temiz = []
        for k in self._kayitlar:
            try:
                kayit_zaman = datetime.fromisoformat(k["zaman"])
                saat_farki = (now - kayit_zaman).total_seconds() / 3600
                if saat_farki <= ETM_SURE_SAAT:
                    temiz.append(k)
            except Exception:
                temiz.append(k)  # Parse edilemiyorsa tut
        self._kayitlar = temiz
        silinen = onceki - len(temiz)
        if silinen > 0:
            self._kaydet()
            print(f"[ETM] {silinen} suresi dolan kayit temizlendi")

    def durum(self) -> dict:
        """ETM durumu."""
        self._suresi_dolanlari_temizle()
        return {
            "kayit_sayisi": len(self._kayitlar),
            "sure_limit_saat": ETM_SURE_SAAT,
            "consolidate_esik": ETM_CONSOLIDATE_ESIK,
        }

    def ozet(self) -> str:
        self._suresi_dolanlari_temizle()
        return f"ETM (gecis hafizasi): {len(self._kayitlar)} kayit (24s pencere)"


# Global ETM instance
etm = EpisodicTransitionMemory()


# ─────────────────────────────────────────────────────────────
# UZUN VADELI HAFIZA (ChromaDB)
# ─────────────────────────────────────────────────────────────


class MemorySystem:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(BASE_DIR / "memory_db"))
        self.ef = embedding_functions.DefaultEmbeddingFunction()

        self.gorevler = self.client.get_or_create_collection(
            name="gorevler", embedding_function=self.ef
        )
        self.bilgiler = self.client.get_or_create_collection(
            name="bilgiler", embedding_function=self.ef
        )
        self.tercihler = self.client.get_or_create_collection(
            name="tercihler", embedding_function=self.ef
        )

        # ASAMA 9: Episodik ve Prosedürel hafıza
        self.episodik = EpisodicMemory(self.client, self.ef)
        self.prosedur = ProceduralMemory(self.client, self.ef)

    def gorev_kaydet(
        self, gorev: str, sonuc: str, tur: str = "genel", reward: float = 0.5, basari: bool = True
    ):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.gorevler.add(
                documents=[f"Gorev: {gorev}\nSonuc: {sonuc}"],
                metadatas=[
                    {
                        "tur": tur,
                        "zaman": timestamp,
                        "reward_contribution": round(reward, 4),
                        "basari": 1 if basari else 0,
                        "decay_factor": 0.001,
                        "reinforcement_boost": round(reward * 0.2, 4),
                        "failure_penalty": 0.0 if basari else 0.3,
                        "onem_skoru": round(0.5 + reward * 0.5, 4),
                        "erisim_sayisi": 0,  # ASAMA 17: re-ranking icin
                        "korunuyor": 0,  # ASAMA 17: 1 ise decay uygulanmaz
                    }
                ],
                ids=[f"gorev_{timestamp}"],
            )
            return True
        except Exception as e:
            print(f"Gorev kayit hatasi: {e}")
            return False

    def bilgi_kaydet(self, konu: str, bilgi: str):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.bilgiler.add(
                documents=[bilgi],
                metadatas=[
                    {
                        "konu": konu,
                        "zaman": timestamp,
                        "reward_contribution": 0.5,
                        "decay_factor": 0.0005,
                        "onem_skoru": 0.7,
                    }
                ],
                ids=[f"bilgi_{timestamp}"],
            )
            return True
        except Exception as e:
            print(f"Bilgi kayit hatasi: {e}")
            return False

    def tercih_kaydet(self, tercih_turu: str, deger: str):
        try:
            try:
                self.tercihler.delete(ids=[tercih_turu])
            except Exception:
                pass
            self.tercihler.add(
                documents=[deger], metadatas=[{"tur": tercih_turu}], ids=[tercih_turu]
            )
            return True
        except Exception as e:
            print(f"Tercih kayit hatasi: {e}")
            return False

    def benzer_gorev_bul(self, sorgu: str, n: int = 3) -> list:
        """S2-2: Hybrid RAG — Dense (ChromaDB) + BM25 + RRF Fusion."""
        try:
            count = self.gorevler.count()
            if count == 0:
                return []

            # ChromaDB'den daha fazla aday cek (hybrid icin)
            fetch_n = min(n * 4, count, 20)
            sonuclar = self.gorevler.query(
                query_texts=[sorgu],
                n_results=fetch_n,
                include=["documents", "metadatas", "distances"],
            )
            if not sonuclar or not sonuclar["documents"][0]:
                return []

            # Hybrid RAG: Dense + BM25 + RRF
            try:
                from hybrid_rag import hybrid_search

                dense_sonuclar = []
                for i, (doc, meta, dist) in enumerate(
                    zip(
                        sonuclar["documents"][0],
                        sonuclar["metadatas"][0],
                        sonuclar["distances"][0],
                        strict=False,
                    )
                ):
                    doc_id = sonuclar["ids"][0][i] if sonuclar.get("ids") else f"doc_{i}"
                    dense_sonuclar.append((doc_id, doc, dist, meta))

                hybrid_sonuc = hybrid_search(sorgu, dense_sonuclar, n=n)

                # Recency ve onem ile zenginlestir
                final = []
                for doc_id, doc, rrf_skor in hybrid_sonuc:
                    # Metadata bul
                    meta = {}
                    for j, did in enumerate(sonuclar.get("ids", [[]])[0]):
                        if did == doc_id:
                            meta = sonuclar["metadatas"][0][j]
                            break
                    onem = meta.get("onem_skoru", 0.5)
                    recency = self._recency_hesapla(meta.get("zaman", "20240101_000000"))
                    final_skor = rrf_skor * onem * (0.5 + 0.5 * recency)
                    final.append((final_skor, doc))

                final.sort(key=lambda x: x[0], reverse=True)
                return [doc for _, doc in final[:n]]

            except ImportError:
                # hybrid_rag yuklenemezse eski yonteme geri don
                pass

            # Fallback: Eski yontem (sadece dense)
            skorlu = []
            for doc, meta, dist in zip(
                sonuclar["documents"][0],
                sonuclar["metadatas"][0],
                sonuclar["distances"][0],
                strict=False,
            ):
                similarity = 1.0 / (1.0 + dist)
                onem = meta.get("onem_skoru", 0.5)
                failure = meta.get("failure_penalty", 0.0)
                recency = self._recency_hesapla(meta.get("zaman", "20240101_000000"))
                erisim = meta.get("erisim_sayisi", 0)
                erisim_skoru = min(1.0, erisim / 10.0)
                final_skor = (
                    ((similarity * 0.60) + (recency * 0.25) + (erisim_skoru * 0.15))
                    * onem
                    * (1 - failure * 0.3)
                )
                skorlu.append((final_skor, doc))

            skorlu.sort(key=lambda x: x[0], reverse=True)
            return [doc for _, doc in skorlu[:n]]
        except Exception as e:
            print(f"Benzer gorev bul hatasi: {e}")
            return []

    def bilgi_ara(self, sorgu: str, n: int = 3) -> list:
        try:
            count = self.bilgiler.count()
            if count == 0:
                return []
            sonuclar = self.bilgiler.query(query_texts=[sorgu], n_results=min(n, count))
            if sonuclar and sonuclar["documents"][0]:
                return sonuclar["documents"][0]
            return []
        except Exception as e:
            print(f"Bilgi ara hatasi: {e}")
            return []

    def hafizayi_guclendir(self, sorgu: str, reward: float):
        try:
            count = self.gorevler.count()
            if count == 0:
                return
            sonuclar = self.gorevler.query(
                query_texts=[sorgu], n_results=min(3, count), include=["metadatas", "documents"]
            )
            if not sonuclar or not sonuclar["ids"][0]:
                return
            for id_, meta in zip(sonuclar["ids"][0], sonuclar["metadatas"][0], strict=False):
                yeni_reward = min(1.0, meta.get("reward_contribution", 0.5) + 0.2 * reward)
                yeni_onem = min(1.0, meta.get("onem_skoru", 0.5) + 0.1 * reward)
                # ASAMA 17: Erisim sayisini artir (re-ranking icin)
                yeni_erisim = meta.get("erisim_sayisi", 0) + 1
                self.gorevler.update(
                    ids=[id_],
                    metadatas=[
                        {
                            **meta,
                            "reward_contribution": round(yeni_reward, 4),
                            "onem_skoru": round(yeni_onem, 4),
                            "reinforcement_boost": round(0.2 * reward, 4),
                            "erisim_sayisi": yeni_erisim,
                        }
                    ],
                )
        except Exception as e:
            print(f"Guclendir hatasi: {e}")

    def decay_uygula(self, esik: float = 0.05):
        """
        Reward'u dusuk olan kayitlari zayiflat.
        Esigin altina dusenleri sil (ChromaDB sisinmesin).
        """
        try:
            count = self.gorevler.count()
            if count == 0:
                return
            sonuclar = self.gorevler.get(include=["metadatas"])
            if not sonuclar or not sonuclar["ids"]:
                return

            silinecekler = []
            for id_, meta in zip(sonuclar["ids"], sonuclar["metadatas"], strict=False):
                # ASAMA 17: Korumali kayitlara decay uygulanmaz
                if meta.get("korunuyor", 0) == 1:
                    continue
                # ASAMA 17: Cok erisilen kayitlar silinmez (erisim_sayisi > 5)
                if meta.get("erisim_sayisi", 0) > 5:
                    continue

                decay = meta.get("decay_factor", 0.001)
                yeni_reward = max(0.0, meta.get("reward_contribution", 0.5) * (1 - decay))
                yeni_failure = max(0.0, meta.get("failure_penalty", 0.0) * (1 - decay))

                # Cok dusuk reward + dusuk onem → silinecekler listesine al
                if yeni_reward < esik and meta.get("onem_skoru", 0.5) < 0.2:
                    silinecekler.append(id_)
                else:
                    self.gorevler.update(
                        ids=[id_],
                        metadatas=[
                            {
                                **meta,
                                "reward_contribution": round(yeni_reward, 4),
                                "failure_penalty": round(yeni_failure, 4),
                            }
                        ],
                    )

            if silinecekler:
                self.gorevler.delete(ids=silinecekler)
                print(f"Decay temizligi: {len(silinecekler)} dusuk onemli kayit silindi.")

        except Exception as e:
            print(f"Decay hatasi: {e}")

    def _recency_hesapla(self, zaman_str: str) -> float:
        try:
            for fmt in ("%Y%m%d_%H%M%S_%f", "%Y%m%d_%H%M%S"):
                try:
                    zaman = datetime.strptime(zaman_str, fmt)
                    saat_farki = (datetime.now() - zaman).total_seconds() / 3600
                    return math.exp(-math.log(2) * saat_farki / (7 * 24))
                except ValueError:
                    continue
            return 0.5
        except Exception:
            return 0.5

    def tum_tercihleri_al(self) -> dict:
        try:
            sonuclar = self.tercihler.get()
            tercihler = {}
            if sonuclar and sonuclar["ids"]:
                for i, id_ in enumerate(sonuclar["ids"]):
                    tercihler[id_] = sonuclar["documents"][i]
            return tercihler
        except Exception as e:
            print(f"Tercih al hatasi: {e}")
            return {}

    def hafiza_ozeti(self) -> str:
        try:
            gorev_sayisi = self.gorevler.count()
            bilgi_sayisi = self.bilgiler.count()
            tercih_sayisi = self.tercihler.count()
            stm_kullanici_sayisi = len(_short_term)
            return (
                f"Hafiza Durumu:\n"
                f"Uzun vadeli gorev: {gorev_sayisi}\n"
                f"Kayitli bilgi: {bilgi_sayisi}\n"
                f"Kayitli tercih: {tercih_sayisi}\n"
                f"Aktif kisa sure hafizasi: {stm_kullanici_sayisi} kullanici\n"
                f"{etm.ozet()}\n"
                f"{self.episodik.ozet()}\n"
                f"{self.prosedur.ozet()}"
            )
        except Exception as e:
            return f"Hafiza ozeti hatasi: {e}"

    def gorev_korumaya_al(self, sorgu: str) -> bool:
        """
        ASAMA 17: Belirli bir sorguya en yakin kaydi decay'den koru.
        /hatirlat komutu ile tetiklenir.
        Doner: True = koruma uygulandı, False = kayit bulunamadi
        """
        try:
            count = self.gorevler.count()
            if count == 0:
                return False
            sonuclar = self.gorevler.query(
                query_texts=[sorgu], n_results=min(1, count), include=["metadatas"]
            )
            if not sonuclar or not sonuclar["ids"][0]:
                return False
            id_ = sonuclar["ids"][0][0]
            meta = sonuclar["metadatas"][0][0]
            self.gorevler.update(ids=[id_], metadatas=[{**meta, "korunuyor": 1}])
            return True
        except Exception as e:
            print(f"Koruma hatasi: {e}")
            return False

    def hafizayi_temizle(self, kategori: str = "hepsi") -> str:
        try:
            if kategori in ("gorevler", "hepsi"):
                self.client.delete_collection("gorevler")
                self.gorevler = self.client.get_or_create_collection(
                    name="gorevler", embedding_function=self.ef
                )
            if kategori in ("bilgiler", "hepsi"):
                self.client.delete_collection("bilgiler")
                self.bilgiler = self.client.get_or_create_collection(
                    name="bilgiler", embedding_function=self.ef
                )
            return f"{kategori} hafizasi temizlendi!"
        except Exception as e:
            return f"Temizleme hatasi: {e}"


# ─────────────────────────────────────────────────────────────
# ASAMA 9: EPİSODİK HAFIZA
# Oturum bazlı onemli olaylari kalici olarak saklar.
# Normal gorev hafizasindan farki: sadece yuksek reward veya
# kullanici tarafindan "onemli" isaretlenen anlari tutar.
# ─────────────────────────────────────────────────────────────


class EpisodicMemory:
    """
    Onemli ani (episode) kayitlarini ChromaDB'de kalici saklar.
    Sorgu geldiginde en alakali ve en yeni anilari dondurur.
    """

    def __init__(self, client, ef):
        self.koleksiyon = client.get_or_create_collection(name="episodik", embedding_function=ef)

    def ani_kaydet(self, baslik: str, icerik: str, onem: float = 0.7, etiketler: list = None):
        """
        Onemli bir ani kaydet.
        baslik   : Kisa tanim (ornek: 'Python kodu calistirma')
        icerik   : Tam olay metni
        onem     : 0.0-1.0, yuksek = daha uzun sure tutuluyor
        etiketler: ['kod', 'basarili'] gibi liste
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.koleksiyon.add(
                documents=[f"{baslik}\n{icerik}"],
                metadatas=[
                    {
                        "baslik": baslik[:100],
                        "zaman": timestamp,
                        "tarih_okunabilir": datetime.now().strftime("%d %B %Y, %H:%M"),  # ASAMA 17
                        "onem": round(onem, 3),
                        "etiketler": ",".join(etiketler or []),
                        "erisim_sayisi": 0,
                        "korunuyor": 1,  # Episodik aniler daima korunur
                    }
                ],
                ids=[f"ani_{timestamp}"],
            )
            return True
        except Exception as e:
            print(f"Ani kayit hatasi: {e}")
            return False

    def ani_bul(self, sorgu: str, n: int = 2) -> list:
        """
        Sorguya en yakin anilari dondur.
        Doner: [{"baslik": str, "icerik": str, "onem": float}]
        """
        try:
            count = self.koleksiyon.count()
            if count == 0:
                return []
            sonuclar = self.koleksiyon.query(
                query_texts=[sorgu],
                n_results=min(n, count),
                include=["documents", "metadatas", "distances"],
            )
            if not sonuclar or not sonuclar["documents"][0]:
                return []

            aniler = []
            for doc, meta, dist in zip(
                sonuclar["documents"][0],
                sonuclar["metadatas"][0],
                sonuclar["distances"][0],
                strict=False,
            ):
                benzerlik = 1.0 / (1.0 + dist)
                # Sadece yeterince benzer anilari al
                if benzerlik > 0.3:
                    aniler.append(
                        {
                            "baslik": meta.get("baslik", ""),
                            "icerik": doc,
                            "onem": meta.get("onem", 0.5),
                            "benzerlik": round(benzerlik, 2),
                            # ASAMA 17: Zaman baglami — prompt'a eklenebilir
                            "tarih": meta.get("tarih_okunabilir", ""),
                        }
                    )

                    # Erisim sayisini artir
                    try:
                        yeni_meta = {**meta, "erisim_sayisi": meta.get("erisim_sayisi", 0) + 1}
                        self.koleksiyon.update(
                            ids=[sonuclar["ids"][0][len(aniler) - 1]], metadatas=[yeni_meta]
                        )
                    except Exception:
                        pass

            return aniler
        except Exception as e:
            print(f"Ani bul hatasi: {e}")
            return []

    def ozet(self) -> str:
        try:
            return f"Episodik hafiza: {self.koleksiyon.count()} ani kayitli"
        except Exception:
            return "Episodik hafiza: veri yok"


# ─────────────────────────────────────────────────────────────
# ASAMA 9: PROSEDÜREL HAFIZA
# "Nasil yapilir" bilgisini saklar.
# Basarili bir gorev tamamlandiginda adimlari kaydeder.
# Benzer bir gorev geldiginde bu adimlari referans olarak sunar.
# ─────────────────────────────────────────────────────────────


class ProceduralMemory:
    """
    Basarili gorev adimlarini prosedur olarak saklar.
    Ornek: 'Python kod yazma' gorevi basarili tamamlaninca
           hangi adimlar izlendigi kaydedilir.
    """

    def __init__(self, client, ef):
        self.koleksiyon = client.get_or_create_collection(name="prosedur", embedding_function=ef)

    def prosedur_kaydet(
        self, gorev_tanimi: str, adimlar: list, basari_orani: float = 1.0, gorev_turu: str = "genel"
    ):
        """
        Basarili bir goreve ait adimlari kaydet.
        adimlar: ['1. Prompt olustur', '2. API cagir', '3. Sonucu isle']
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            adim_metni = "\n".join(f"{i+1}. {a}" for i, a in enumerate(adimlar))
            belge = f"Gorev: {gorev_tanimi}\nAdimlar:\n{adim_metni}"

            self.koleksiyon.add(
                documents=[belge],
                metadatas=[
                    {
                        "gorev_tanimi": gorev_tanimi[:100],
                        "gorev_turu": gorev_turu,
                        "adim_sayisi": len(adimlar),
                        "basari_orani": round(basari_orani, 3),
                        "zaman": timestamp,
                        "kullanim_sayisi": 0,
                    }
                ],
                ids=[f"prosedur_{timestamp}"],
            )
            return True
        except Exception as e:
            print(f"Prosedur kayit hatasi: {e}")
            return False

    def prosedur_bul(self, gorev: str, gorev_turu: str = "") -> str:
        """
        Benzer bir goreve ait proseduru bul ve metin olarak dondur.
        Doner: str (prompt'a eklenecek bağlam) veya ""
        """
        try:
            count = self.koleksiyon.count()
            if count == 0:
                return ""

            # Gorev turune gore filtrele
            where = {"gorev_turu": gorev_turu} if gorev_turu else None
            try:
                sonuclar = self.koleksiyon.query(
                    query_texts=[gorev],
                    n_results=min(2, count),
                    include=["documents", "metadatas", "distances"],
                    where=where,
                )
            except Exception:
                # Filtre calismazsa filtresiz dene
                sonuclar = self.koleksiyon.query(
                    query_texts=[gorev],
                    n_results=min(2, count),
                    include=["documents", "metadatas", "distances"],
                )

            if not sonuclar or not sonuclar["documents"][0]:
                return ""

            doc = sonuclar["documents"][0][0]
            meta = sonuclar["metadatas"][0][0]
            dist = sonuclar["distances"][0][0]
            benzerlik = 1.0 / (1.0 + dist)

            # Cok dusuk benzerlikte kullanma
            if benzerlik < 0.35:
                return ""

            # Kullanim sayisini artir
            try:
                self.koleksiyon.update(
                    ids=[sonuclar["ids"][0][0]],
                    metadatas=[{**meta, "kullanim_sayisi": meta.get("kullanim_sayisi", 0) + 1}],
                )
            except Exception:
                pass

            return f"[Prosedur Referansi - {meta.get('gorev_tanimi', '')}]\n{doc}"

        except Exception as e:
            print(f"Prosedur bul hatasi: {e}")
            return ""

    def ozet(self) -> str:
        try:
            return f"Prosedürel hafiza: {self.koleksiyon.count()} prosedur kayitli"
        except Exception:
            return "Prosedürel hafiza: veri yok"
