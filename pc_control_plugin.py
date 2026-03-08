# pc_control_plugin.py
import os
import shutil
import subprocess
from pathlib import Path


class PCControl:
    """PC kontrol özellikleri"""

    @staticmethod
    def create_folder(path):
        """Klasör oluştur"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return f"✓ Klasör oluşturuldu: {path}"
        except Exception as e:
            return f"✗ Hata: {e}"

    @staticmethod
    def create_file(path, content=""):
        """Dosya oluştur"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"✓ Dosya oluşturuldu: {path}"
        except Exception as e:
            return f"✗ Hata: {e}"

    @staticmethod
    def open_program(program_name):
        """Program aç"""
        programs = {
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "explorer": "explorer.exe",
            "calculator": "calc.exe",
        }

        try:
            program = programs.get(program_name.lower())
            if program:
                subprocess.Popen(program)
                return f"✓ {program_name} açıldı"
            else:
                return f"✗ Program bulunamadı: {program_name}"
        except Exception as e:
            return f"✗ Hata: {e}"

    @staticmethod
    def move_file(source, destination):
        """Dosya taşı"""
        try:
            shutil.move(source, destination)
            return f"✓ Dosya taşındı: {source} -> {destination}"
        except Exception as e:
            return f"✗ Hata: {e}"

    @staticmethod
    def list_files(directory):
        """Klasördeki dosyaları listele"""
        try:
            files = os.listdir(directory)
            return files
        except Exception as e:
            return f"✗ Hata: {e}"
