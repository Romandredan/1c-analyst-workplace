"""Проверка навыка analyst-handoff: структура, тексты, скрипты и регрессия на примере.

Запуск из любой папки:
    python tests/test_skill.py

Нужен только Python 3.10+. Если установлены openspec и pandoc, проверяются и они;
без них соответствующие шаги пропускаются с пометкой.
Код выхода 0: все проверки пройдены. Код 1: есть ошибки.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
EXAMPLE = SKILL / "examples" / "vip"
SCRIPTS = SKILL / "scripts"
REFERENCES = ("customer-package.md", "dev-package.md", "review-checklist.md",
              "scripts/build_package.py", "scripts/check_package.py")
REQUIRED = REFERENCES + ("SKILL.md", "README.md", "assets/package.css")
failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("OK   " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8")


def test_structure() -> None:
    for name in REQUIRED:
        check((SKILL / name).is_file(), f"файл {name} на месте")
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    check(text.startswith("---\n"), "SKILL.md начинается с YAML-шапки")
    front = text.split("---", 2)[1]
    check(re.search(r"^name:\s*analyst-handoff\s*$", front, re.M) is not None, "name: analyst-handoff")
    check(re.search(r"^description:\s*\S+", front, re.M) is not None, "description заполнен")
    check(len(front) <= 1024, f"шапка не длиннее 1024 символов ({len(front)})")
    check(len(text.splitlines()) < 500, "SKILL.md короче 500 строк")
    for name in REFERENCES:
        check(name in text, f"SKILL.md ссылается на {name}")


def test_texts() -> None:
    em_dash = chr(0x2014)
    placeholder = re.compile(r"\b(" + "TO" + "DO|T" + "BD)\b")
    bad = []
    for path in SKILL.rglob("*"):
        if path.suffix in (".md", ".py", ".css", ".mmd") and "__pycache__" not in path.parts:
            body = path.read_text(encoding="utf-8")
            if em_dash in body or placeholder.search(body):
                bad.append(str(path.relative_to(SKILL)))
    check(not bad, "тексты без длинных тире и заглушек" + (f": {', '.join(bad)}" if bad else ""))


def test_scripts() -> None:
    for script in ("build_package.py", "check_package.py"):
        source = SCRIPTS / script
        compile(source.read_text(encoding="utf-8"), str(source), "exec")
        check(run([str(source), "--help"], SKILL).returncode == 0, f"{script} --help")


def test_example() -> None:
    if not EXAMPLE.is_dir():
        check(False, "пример examples/vip на месте")
        return
    customer = run([str(SCRIPTS / "check_package.py"), "customer", "deliverables/vip/customer"], EXAMPLE)
    check(customer.returncode == 0 and "ошибок 0" in customer.stdout,
          "пример: пакет для заказчика проходит проверку")

    if shutil.which("openspec"):
        dev = run([str(SCRIPTS / "check_package.py"), "dev", "deliverables/vip/dev",
                   "--change", "add-vip-fitting-sales", "--customer", "deliverables/vip/customer"], EXAMPLE)
        check(dev.returncode == 1 and "design.md: нет таблицы интеграций" in dev.stdout
              and "openspec validate --strict пройден" in dev.stdout,
              "пример: пакет для разработки ловит блокер по design.md (ожидаемый код 1)")
    else:
        print("SKIP пример: режим «разработка» (openspec не установлен)")

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "vip" / "customer"
        shutil.copytree(EXAMPLE / "deliverables" / "vip" / "customer", copy,
                        ignore=shutil.ignore_patterns("build"))
        build = run([str(SCRIPTS / "build_package.py"), str(copy)], SKILL)
        expected = 0 if shutil.which("pandoc") else 2
        html = copy / "build" / "vip-v2.html"
        check(build.returncode == expected and html.is_file() and html.stat().st_size > 0,
              f"пример: сборка (код {expected}, HTML не пуст)")
        if expected == 0:
            check((copy / "build" / "vip-v2.docx").is_file(), "пример: DOCX собран")

        package = copy / "package.md"
        package.write_text(package.read_text(encoding="utf-8").replace(
            "<!-- D1", "<!-- D9: проверка -->\n*[Схема D9]*\n\n<!-- D1", 1), encoding="utf-8")
        blocked = run([str(SCRIPTS / "build_package.py"), str(copy)], SKILL)
        check(blocked.returncode == 1 and "D9" in blocked.stdout,
              "сборка останавливается на незаполненной заглушке")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for test in (test_structure, test_texts, test_scripts, test_example):
        test()
    print(f"\nИтог: ошибок {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
