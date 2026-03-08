# search_plugin.py
import re

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS


class SearchEngine:
    def search(self, query: str, max_results: int = 5) -> list:
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "url": r.get("href", ""),
                        }
                    )
            return results
        except Exception as e:
            return [{"title": "Hata", "body": str(e), "url": ""}]

    def get_page_content(self, url: str, max_chars: int = 2000) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.content, "html.parser")

            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "header",
                    "footer",
                    "aside",
                    "form",
                    "iframe",
                    "noscript",
                    "menu",
                ]
            ):
                tag.decompose()

            icerik = ""
            for selector in ["article", "main", ".content", "#content", ".post", ".article"]:
                alan = soup.select_one(selector)
                if alan:
                    icerik = alan.get_text(separator=" ", strip=True)
                    break

            if not icerik:
                icerik = soup.get_text(separator=" ", strip=True)

            icerik = re.sub(r"\s+", " ", icerik).strip()

            if len(icerik) < 100:
                return ""

            return icerik[:max_chars]

        except Exception:
            return ""

    def search_and_read(self, query: str) -> str:
        try:
            results = self.search(query, max_results=5)
            if not results:
                return f"'{query}' icin sonuc bulunamadi."

            parcalar = []

            for i, result in enumerate(results[:5]):
                baslik = result["title"].strip()
                ozet = result["body"].strip()

                if not baslik and not ozet:
                    continue

                parca = f"Kaynak {i+1}: {baslik}"
                if ozet:
                    parca += f"\n{ozet}"

                if i < 3 and result["url"]:
                    detay = self.get_page_content(result["url"])
                    if detay and len(detay) > 200:
                        parca += f"\nDetay: {detay[:800]}"

                parcalar.append(parca)

            if not parcalar:
                return f"'{query}' icin icerik okunamadi."

            return f"'{query}' hakkinda bilgi:\n\n" + "\n\n".join(parcalar)

        except Exception as e:
            return f"Arama hatasi: {e}"
