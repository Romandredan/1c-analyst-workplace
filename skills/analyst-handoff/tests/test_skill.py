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
import struct
import subprocess
import sys
import tempfile
import zlib
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


def test_images() -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    signature = b"\x89PNG\r\n\x1a\n"
    header = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    pixels = zlib.compress(b"\x00\x00\x00\x00\xff")
    ending = chunk(b"IEND", b"")
    valid = signature + header + chunk(b"IDAT", pixels) + ending
    bad_crc = bytearray(valid)
    bad_crc[29] ^= 1
    zero_header = chunk(b"IHDR", struct.pack(">IIBBBBB", 0, 1, 8, 6, 0, 0, 0))
    cases = [
        ("корректный PNG", "D1-process.png", valid, ""),
        ("PNG с несколькими IDAT", "D1-process.PNG", signature + header
         + chunk(b"IDAT", pixels[:4]) + chunk(b"IDAT", pixels[4:]) + ending, ""),
        ("пустая картинка", "D1-process.png", b"", "пустой файл картинки"),
        ("чужое содержимое PNG", "D1-process.png", b"plain text", "неверная подпись"),
        ("обрезанный блок PNG", "D1-process.png", valid[:-2], "обрезан блок"),
        ("обрезанные данные PNG", "D1-process.png", valid[:-18], "обрезаны данные блока"),
        ("PNG с неверной CRC", "D1-process.png", bytes(bad_crc), "неверная CRC"),
        ("PNG с нулевым размером", "D1-process.png", signature + zero_header
         + chunk(b"IDAT", pixels) + ending, "нулевые размеры"),
        ("PNG без IDAT", "D1-process.png", signature + header + ending, "нет данных изображения"),
        ("PNG без IEND", "D1-process.png", valid[:-12], "нет завершающего блока"),
        ("отсутствующая картинка", "D1-process.png", None, "нет файла картинки"),
        ("другой формат", "D1-process.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', ""),
        ("внешняя ссылка", "https://example.invalid/D1-process.png", None, ""),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for index, (name, reference, content, error) in enumerate(cases):
            pkg = Path(tmp) / f"case-{index}"
            pkg.mkdir()
            (pkg / "README.md").write_text(
                "**Профиль:** краткий\n\n| Проход | Состояние | Результат |\n"
                "|---|---|---|\n| 2. Диаграммы | готов | D1 |\n", encoding="utf-8")
            (pkg / "package.md").write_text(
                "# Проверка заявки\n\n**Версия:** 1\n\n## 0. Назначение\nПроверить заявку.\n"
                "\n## 2. Решения\n**Р-1. Заявку проверяет оператор.** Статус: Предложено.\n"
                f"\n## 3. Процесс\n<!-- D1: проверка заявки -->\n![D1. Проверка заявки]({reference})\n"
                "\n## 7. Риски\nОткрытых рисков нет.\n\n## 11. Открытые вопросы\nОткрытых вопросов нет.\n",
                encoding="utf-8")
            if content is not None:
                (pkg / reference).write_bytes(content)
            result = run([str(SCRIPTS / "check_package.py"), "customer", str(pkg)], SKILL)
            expected = 1 if error else 0
            check(result.returncode == expected and error in result.stdout,
                  f"картинки: {name}, проверка пакета (код {expected})")
            if error:
                check("заглушки D заполнены" not in result.stdout,
                      f"картинки: {name}, нет подтверждения заполненности")
                for draft in (False, True):
                    options = ["--draft"] if draft else []
                    build = run([str(SCRIPTS / "build_package.py"), str(pkg), *options], SKILL)
                    check(build.returncode == 1 and error in build.stdout
                          and not (pkg / "build").exists(),
                          f"картинки: {name}, сборка {'черновика' if draft else 'пакета'} остановлена")
            elif reference.lower().endswith(".png") and not reference.startswith("https://"):
                build = run([str(SCRIPTS / "build_package.py"), str(pkg)], SKILL)
                expected_build = 0 if shutil.which("pandoc") else 2
                check(build.returncode == expected_build, f"картинки: {name}, сборка (код {expected_build})")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for test in (test_structure, test_texts, test_scripts, test_example, test_images):
        test()
    print(f"\nИтог: ошибок {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
