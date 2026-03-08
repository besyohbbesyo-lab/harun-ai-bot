# gemini_provider.py - Google Gemini API entegrasyonu
import httpx


async def ask_gemini(prompt: str, api_key: str, model: str = "gemini-2.0-flash") -> str:
    """Gemini API ile cevap al"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, params=params, json=body)
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 429:
                raise Exception("429 rate limit")
            else:
                raise Exception(f"{response.status_code} {response.text[:100]}")
    except Exception as e:
        raise e


async def ask_deepseek(prompt: str, api_key: str, model: str = "deepseek-chat") -> str:
    """DeepSeek API ile cevap al"""
    try:
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.7,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            elif response.status_code == 429:
                raise Exception("429 rate limit")
            elif response.status_code == 402:
                raise Exception("402 quota")
            else:
                raise Exception(f"{response.status_code} {response.text[:100]}")
    except Exception as e:
        raise e
