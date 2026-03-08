# vision_plugin.py
import base64
import io

import mss
import mss.tools
from ollama import chat
from PIL import Image


class VisionTool:
    def __init__(self, model="llava"):
        self.model = model

    def take_screenshot(self, save_as=None):
        """Ekranin tamamini ceker ve bytes doner"""
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            if save_as:
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=save_as)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

    def analyze_screen(
        self, query: str = "Bu ekrani detayli analiz et ve ne gordugunü anlat."
    ) -> str:
        try:
            image_bytes = self.take_screenshot()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            response = chat(
                model=self.model,
                messages=[{"role": "user", "content": query, "images": [image_base64]}],
            )
            return response["message"]["content"]
        except Exception as e:
            return f"Vision hatasi: {str(e)}"

    def analyze_image(self, image_path: str, query: str = "Bu resmi detayli analiz et.") -> str:
        """Dosyadaki resmi analiz et"""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            response = chat(
                model=self.model,
                messages=[{"role": "user", "content": query, "images": [image_base64]}],
            )
            return response["message"]["content"]
        except Exception as e:
            return f"Vision hatasi: {str(e)}"


vision_tool = VisionTool(model="llava")
