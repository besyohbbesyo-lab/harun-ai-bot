# code_plugin.py
import ast
import re
import subprocess
from datetime import datetime
from pathlib import Path


class CodeRunner:
    """Runs user-provided Python code inside a locked-down Docker sandbox.

    Security goals (Aşama 20 + S0-3):
      - Strict input limits (chars/lines)
      - AST-based denylist for risky imports and dangerous calls (open/eval/exec/etc.)
      - Docker resource limits + no network + read-only rootfs + no-new-privileges
      - Bounded runtime (timeout) and bounded output size
      - nonroot user inside container
      - tmpfs for /tmp (Python'un geçici dosyaları için)

    S0-3 Eklenen güvenlik katmanları:
      - --security-opt=no-new-privileges   (privilege escalation engeli)
      - --tmpfs /tmp:rw,noexec,size=16m    (read-only rootfs'de Python çalışsın)
      - --user 2000:2000                   (container içi nonroot)
      - --cap-drop=ALL                     (tüm Linux capabilities düşür)
      - --pids-limit=32                    (fork bomb koruması sıkılaştırıldı)
      - --memory-swap=128m                 (swap ile bellek aşımı engeli)
      - SANDBOX_IMAGE config ile ayarlanabilir
    """

    # Hard limits
    MAX_CHARS = 5000
    MAX_LINES = 200
    MAX_OUTPUT_CHARS = 4000
    DOCKER_TIMEOUT_SEC = 10

    # Docker sandbox ayarları
    SANDBOX_IMAGE = "harun-ai-sandbox:1"
    MEMORY_LIMIT = "128m"
    MEMORY_SWAP = "128m"  # swap yok (memory ile aynı = swap kapalı)
    CPU_LIMIT = "0.5"
    PIDS_LIMIT = "32"
    TMPFS_SIZE = "16m"

    # Denylist (modules)
    BANNED_IMPORTS = {
        "os",
        "subprocess",
        "sys",
        "socket",
        "shutil",
        "pathlib",
        "multiprocessing",
        "threading",
        "signal",
        "ctypes",
        "resource",
        "importlib",
        "builtins",
        "urllib",
        "requests",
        "http",
        "ftplib",
        "telnetlib",
        "ssl",
        "pickle",
        "marshal",
        "dill",
    }

    # Denylist (functions / builtins)
    BANNED_CALLS = {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "vars",
        "input",
        "breakpoint",
    }

    # Denylist (dunder attrs often used for sandbox escapes)
    BANNED_DUNDER_ATTRS = {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__globals__",
        "__code__",
        "__getattribute__",
        "__getattr__",
        "__dict__",
        "__dir__",
        "__reduce__",
        "__reduce_ex__",
        "__init_subclass__",
        "__setattr__",
        "__delattr__",
        "__new__",
        "__import__",
    }

    def __init__(self):
        self.output_dir = Path.home() / "Desktop"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_code(self, code: str) -> str:
        if not code:
            return ""
        c = str(code).strip()

        # Remove fenced blocks
        c = c.replace("```python", "").replace("```py", "").replace("```", "").strip()

        # Remove safety-analysis injected lines
        lines = []
        for line in c.splitlines():
            s = line.strip()
            if s.startswith("[OK]"):
                continue
            if "Guven:" in line or "Tutarlilik:" in line:
                continue
            lines.append(line)
        c = "\n".join(lines).strip()

        # If whole payload quoted
        if len(c) >= 2 and c[0] == c[-1] and c[0] in ("'", '"'):
            c = c[1:-1].strip()

        # Normalize newlines
        c = c.replace("\r\n", "\n").replace("\r", "\n")
        return c

    def _safe_filename(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"program_{timestamp}.py"

    def _fail(self, filepath: str, msg: str) -> dict:
        return {"basari": False, "filepath": filepath or "", "mesaj": msg}

    def _validate_limits(self, code: str):
        if not code.strip():
            raise ValueError("Kod bos olamaz.")
        if len(code) > self.MAX_CHARS:
            raise ValueError(f"Kod cok uzun. Maks {self.MAX_CHARS} karakter.")
        lines = code.splitlines()
        if len(lines) > self.MAX_LINES:
            raise ValueError(f"Kod cok satirli. Maks {self.MAX_LINES} satir.")
        # Prevent null bytes / weird control chars
        if "\x00" in code:
            raise ValueError("Gecersiz karakter (NUL) bulundu.")

    def _validate_ast(self, code: str):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"AST analiz hatasi: {e.msg} (line {e.lineno})")

        for node in ast.walk(tree):
            # Block imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = (alias.name or "").split(".")[0]
                    if mod in self.BANNED_IMPORTS:
                        raise ValueError(f"Güvenlik engeli: '{mod}' import yasak.")
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in self.BANNED_IMPORTS:
                    raise ValueError(f"Güvenlik engeli: '{mod}' import yasak.")

            # Block dangerous calls (open/eval/exec/...)
            if isinstance(node, ast.Call):
                # Name(...)
                if isinstance(node.func, ast.Name):
                    fn = node.func.id
                    if fn in self.BANNED_CALLS:
                        raise ValueError(f"Güvenlik engeli: '{fn}()' yasak.")
                # something.attr(...)
                if isinstance(node.func, ast.Attribute):
                    attr = node.func.attr
                    if attr in self.BANNED_CALLS:
                        raise ValueError(f"Güvenlik engeli: '{attr}()' yasak.")
                    if attr in self.BANNED_DUNDER_ATTRS:
                        raise ValueError(f"Güvenlik engeli: '{attr}' kullanimi yasak.")

            # Block direct access to risky dunder attrs (even without call)
            if isinstance(node, ast.Attribute):
                attr = node.attr
                if attr in self.BANNED_DUNDER_ATTRS:
                    raise ValueError(f"Güvenlik engeli: '{attr}' kullanimi yasak.")

            # Block explicit dunder names
            if isinstance(node, ast.Name):
                if node.id.startswith("__") and node.id.endswith("__"):
                    # allow a tiny set of harmless dunders
                    if node.id not in {"__name__", "__file__"}:
                        raise ValueError(f"Güvenlik engeli: '{node.id}' kullanimi yasak.")

    def _docker_mevcut_mu(self) -> bool:
        """Docker'ın kurulu ve çalışır durumda olup olmadığını kontrol et."""
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _sandbox_imaj_mevcut_mu(self) -> bool:
        """Sandbox Docker imajının mevcut olup olmadığını kontrol et."""
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.SANDBOX_IMAGE],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def save_and_run(self, kod: str, dosya_adi: str = None) -> dict:
        filepath = ""
        try:
            kod = self._sanitize_code(kod)

            # Limits + AST security
            self._validate_limits(kod)
            self._validate_ast(kod)

            # Docker kontrolleri
            if not self._docker_mevcut_mu():
                return self._fail(
                    "", "Docker kurulu degil veya calismıyor. Kod sandbox'i icin Docker gerekli."
                )
            if not self._sandbox_imaj_mevcut_mu():
                return self._fail(
                    "",
                    f"Sandbox imaji bulunamadi: {self.SANDBOX_IMAGE}\n"
                    f"Olusturmak icin: docker build -f Dockerfile.sandbox -t {self.SANDBOX_IMAGE} .",
                )

            dosya_adi = self._safe_filename()
            filepath = str(self.output_dir / dosya_adi)
            p = Path(filepath)

            # Save (host-side only; user code runs in container)
            with open(p, "w", encoding="utf-8") as f:
                f.write(kod)

            # ====================================================
            # DOCKER KOMUTLARI — S0-3 TAM İZOLASYON
            # ====================================================
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                # --- Kaynak limitleri ---
                f"--memory={self.MEMORY_LIMIT}",  # RAM limiti
                f"--memory-swap={self.MEMORY_SWAP}",  # swap kapalı (aynı değer = swap yok)
                f"--cpus={self.CPU_LIMIT}",  # CPU limiti
                f"--pids-limit={self.PIDS_LIMIT}",  # fork bomb koruması
                # --- Ağ izolasyonu ---
                "--network=none",  # ağ erişimi tamamen kapalı
                # --- Dosya sistemi ---
                "--read-only",  # rootfs salt okunur
                f"--tmpfs=/tmp:rw,noexec,nosuid,size={self.TMPFS_SIZE}",  # Python geçici dosyalar
                # --- Güvenlik ---
                "--security-opt=no-new-privileges",  # privilege escalation engeli
                "--cap-drop=ALL",  # tüm Linux capabilities düşür
                "--user=2000:2000",  # container içi nonroot
                # --- Sandbox mount ---
                "-v",
                f"{self.output_dir}:/sandbox:ro",  # kod dosyası salt okunur
                # --- İmaj ve komut ---
                self.SANDBOX_IMAGE,
                f"/sandbox/{p.name}",
            ]

            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=self.DOCKER_TIMEOUT_SEC
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            # Output cap
            if len(stdout) > self.MAX_OUTPUT_CHARS:
                stdout = stdout[: self.MAX_OUTPUT_CHARS] + "\n... (cikti kisaltildi)"
            if len(stderr) > self.MAX_OUTPUT_CHARS:
                stderr = stderr[: self.MAX_OUTPUT_CHARS] + "\n... (hata kisaltildi)"

            if result.returncode != 0:
                return self._fail(str(p), f"Docker hatasi:\n{stderr}")

            return {"basari": True, "filepath": str(p), "mesaj": f"Basarili!\nCikti:\n{stdout}"}

        except subprocess.TimeoutExpired:
            return self._fail(filepath, f"Timeout ({self.DOCKER_TIMEOUT_SEC}s)")
        except Exception as e:
            return self._fail(filepath, str(e))
