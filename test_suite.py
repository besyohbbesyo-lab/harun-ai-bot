# test_suite.py
import json
import time
from datetime import datetime
from pathlib import Path


def _run(code_runner, code: str, name: str) -> dict:
    t0 = time.perf_counter()
    res = code_runner.save_and_run(code, name)
    ms = int((time.perf_counter() - t0) * 1000)
    # normalize keys across versions
    ok = bool(res.get("basari") or res.get("success") or res.get("ok"))
    msg = res.get("mesaj") or res.get("message") or ""
    out = res.get("output") or res.get("cikti") or ""
    fp = str(res.get("filepath") or res.get("path") or "")
    return {"ok": ok, "msg": msg, "out": out, "filepath": fp, "ms": ms}


def run_selftests(code_runner) -> dict:
    tests = []

    def expect_pass(name, code):
        r = _run(code_runner, code, f"selftest_{len(tests)+1}_{name.replace(' ','_')}")
        tests.append(
            {
                "name": name,
                "pass": r["ok"],
                "ms": r["ms"],
                "detail": r["out"] if not r["ok"] else r["out"],
            }
        )

    def expect_block(name, code, must_contain=None):
        r = _run(code_runner, code, f"selftest_{len(tests)+1}_{name.replace(' ','_')}")
        blocked = not r["ok"]
        detail = r["msg"] or r["out"] or ""
        if must_contain and must_contain not in detail:
            blocked = False
            detail = f"Beklenen engel metni bulunamadi. Detay: {detail}"
        tests.append(
            {
                "name": name,
                "pass": blocked,
                "ms": r["ms"],
                "detail": detail[:500],
            }
        )

    # 1) basic run
    expect_pass("basic_print", 'print("ok")')

    # 2) open() banned
    expect_block("open_banned", 'open("a.txt","w").write("x")', must_contain="open")

    # 3) os import banned
    expect_block("os_import_banned", "import os\nprint(os.getcwd())", must_contain="os")

    # 4) urllib import banned (network libs)
    expect_block(
        "urllib_import_banned", 'import urllib.request\nprint("net")', must_contain="urllib"
    )

    # 5) subprocess import banned (escape attempts)
    expect_block(
        "subprocess_import_banned", "import subprocess\nprint('x')", must_contain="subprocess"
    )

    report = {
        "stage": 24,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "passed": sum(1 for t in tests if t["pass"]),
            "total": len(tests),
        },
        "tests": tests,
    }
    return report


def write_report(report: dict) -> str:
    out_dir = Path.home() / "Desktop"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"test_report_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
