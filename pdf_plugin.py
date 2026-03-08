# pdf_plugin.py
from pathlib import Path

import requests
from ddgs import DDGS


class PDFDownloader:
    def __init__(self):
        self.output_dir = Path.home() / "Desktop"

    def search_pdfs(self, query: str, max_results: int = 10) -> list:
        """PDF dosyalarını internette ara"""
        try:
            pdf_links = []
            search_query = f"{query} filetype:pdf"

            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=max_results):
                    url = r.get("href", "")
                    title = r.get("title", "Isimsiz")
                    if url.endswith(".pdf") or "pdf" in url.lower():
                        pdf_links.append({"title": title, "url": url})

            return pdf_links
        except Exception as e:
            print(f"PDF arama hatasi: {e}")
            return []

    def download_pdf(self, url: str, filepath: Path) -> bool:
        """Tek bir PDF indir"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=30, stream=True)

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "pdf" in content_type.lower() or url.endswith(".pdf"):
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return True
            return False
        except Exception:
            return False

    def download_pdfs(self, query: str) -> str:
        """Konuya göre PDF ara ve indir, klasöre kaydet"""
        try:
            klasor_adi = query.replace(" ", "_")[:30]
            klasor_yolu = self.output_dir / f"PDF_{klasor_adi}"
            klasor_yolu.mkdir(exist_ok=True)

            pdf_listesi = self.search_pdfs(query, max_results=15)

            if not pdf_listesi:
                return f"Hata: '{query}' icin PDF bulunamadi."

            indirilen = 0

            for i, pdf in enumerate(pdf_listesi):
                if indirilen >= 5:
                    break

                url = pdf["url"]
                baslik = pdf["title"].replace("/", "_").replace("\\", "_")[:50]
                dosya_adi = f"{i+1}_{baslik}.pdf"
                dosya_yolu = klasor_yolu / dosya_adi

                basari = self.download_pdf(url, dosya_yolu)
                if basari:
                    indirilen += 1

            if indirilen > 0:
                return (
                    f"Tamamlandi!\n"
                    f"Konu: {query}\n"
                    f"Indirilen PDF: {indirilen}\n"
                    f"Konum: {klasor_yolu}\n"
                    f"Klasor adi: PDF_{klasor_adi}"
                )
            else:
                return "PDF'ler bulundu ama indirilemedi. Siteler erisimi engelliyor olabilir."

        except Exception as e:
            return f"Hata: {e}"
