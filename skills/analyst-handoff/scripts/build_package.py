"""Сборка пакета на согласование: package.md -> build/<кейс>-v<версия>.docx и .html.

Запуск:
    python scripts/build_package.py <папка-пакета> [--reference-doc шаблон.docx] [--css стиль.css] [--draft]

Заглушка с видимой подписью `*[...]*` без картинки останавливает сборку: заказчик
не должен получить документ с подписями вместо схем. Черновик для себя собирается с --draft.

DOCX и HTML собираются через pandoc. Если pandoc не установлен, HTML собирается
через markdown-it-py, а DOCX пропускается с кодом выхода 2 и подсказкой по установке.
Картинки в HTML встраиваются в файл, поэтому HTML можно отправить одним вложением.
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSS = SKILL_DIR / "assets" / "package.css"
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKER_RE = re.compile(r"<!--\s*([DS]\d+)\b")
VERSION_RE = re.compile(r"\*\*Версия:\*\*\s*([0-9]+(?:\.[0-9]+)?)")
INSTALL_HINT = "Установите pandoc: winget install --id JohnMacFarlane.Pandoc -e (или https://pandoc.org/installing.html)"


def fail(message: str) -> None:
    print(f"ОШИБКА: {message}")
    sys.exit(1)


def read_package(pkg_dir: Path) -> tuple[Path, str, str, str]:
    src = pkg_dir / "package.md"
    if not src.is_file():
        fail(f"нет файла {src}")
    text = src.read_text(encoding="utf-8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), pkg_dir.name)
    match = VERSION_RE.search(text)
    manifest = pkg_dir / "README.md"
    if not match and manifest.is_file():
        match = VERSION_RE.search(manifest.read_text(encoding="utf-8"))
    version = match.group(1) if match else "0"
    return src, text, title, version


def check_images(pkg_dir: Path, text: str) -> list[str]:
    """Проверяет, что все картинки на месте и каждая заглушка D/S заполнена."""
    missing = [p for p in IMAGE_RE.findall(text) if not p.startswith(("http://", "https://", "data:"))
               and not (pkg_dir / p).is_file()]
    if missing:
        fail("нет файлов картинок: " + ", ".join(missing))
    images = IMAGE_RE.findall(text)
    unfilled = []
    for marker in dict.fromkeys(MARKER_RE.findall(text)):
        filled = any(Path(p).name.startswith((f"{marker}-", f"{marker}.")) for p in images)
        captioned = re.search(rf"<!--\s*{marker}\b[^>]*-->\s*\n\s*\*\[", text) is not None
        if not filled and captioned:
            unfilled.append(marker)
    return unfilled


def pandoc_version(pandoc: str) -> tuple[int, ...]:
    out = subprocess.run([pandoc, "--version"], capture_output=True, text=True, encoding="utf-8").stdout
    match = re.search(r"pandoc(?:\.exe)?\s+([0-9.]+)", out)
    return tuple(int(x) for x in match.group(1).split(".")) if match else (0,)


def build_with_pandoc(pandoc: str, pkg_dir: Path, src: Path, title: str, docx: Path, html: Path,
                      css: Path, reference_doc: Path | None) -> None:
    common = [pandoc, src.name, "-f", "gfm", "--resource-path", str(pkg_dir)]
    docx_cmd = common + ["-t", "docx", "-o", str(docx)]
    if reference_doc:
        docx_cmd += ["--reference-doc", str(reference_doc)]
    embed = "--embed-resources" if pandoc_version(pandoc) >= (2, 19) else "--self-contained"
    html_cmd = common + ["-t", "html5", "-s", embed, "--css", str(css),
                         "--metadata", f"pagetitle={title}", "-o", str(html)]
    for cmd in (docx_cmd, html_cmd):
        result = subprocess.run(cmd, cwd=pkg_dir, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            fail(f"pandoc завершился с кодом {result.returncode}: {result.stderr.strip()}")


def build_html_fallback(pkg_dir: Path, text: str, title: str, html: Path, css: Path) -> None:
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        fail("нет ни pandoc, ни markdown-it-py. " + INSTALL_HINT + "; либо pip install markdown-it-py")
    body = MarkdownIt("commonmark", {"html": True}).enable("table").render(text)

    def embed(match: re.Match) -> str:
        path = match.group(1)
        file = pkg_dir / path
        if path.startswith(("http://", "https://", "data:")) or not file.is_file():
            return match.group(0)
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        data = base64.b64encode(file.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{data}"'

    body = re.sub(r'src="([^"]+)"', embed, body)
    style = css.read_text(encoding="utf-8") if css.is_file() else ""
    html.write_text(
        "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title}</title>\n<style>\n{style}\n</style></head>\n<body>\n{body}</body></html>\n",
        encoding="utf-8",
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Сборка пакета на согласование в DOCX и HTML")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--reference-doc", type=Path, help="Word-шаблон стилей для DOCX")
    parser.add_argument("--css", type=Path, default=DEFAULT_CSS, help="Стиль HTML")
    parser.add_argument("--draft", action="store_true",
                        help="собрать черновик с незаполненными заглушками (имя файла с суффиксом -draft)")
    args = parser.parse_args()

    pkg_dir = args.package_dir.resolve()
    src, text, title, version = read_package(pkg_dir)
    unfilled = check_images(pkg_dir, text)
    if unfilled and not args.draft:
        fail("не заполнены заглушки " + ", ".join(unfilled) + ". Заполните их, отметьте проход "
             "«не требуется» и уберите видимые подписи, либо соберите черновик с --draft")

    case = pkg_dir.parent.name if pkg_dir.name == "customer" else pkg_dir.name
    out_dir = pkg_dir / "build"
    out_dir.mkdir(exist_ok=True)
    suffix = "-draft" if args.draft else ""
    docx = out_dir / f"{case}-v{version}{suffix}.docx"
    html = out_dir / f"{case}-v{version}{suffix}.html"

    pandoc = shutil.which("pandoc")
    if pandoc:
        reference = args.reference_doc.resolve() if args.reference_doc else None
        build_with_pandoc(pandoc, pkg_dir, src, title, docx, html, args.css.resolve(), reference)
        built = [docx, html]
    else:
        build_html_fallback(pkg_dir, text, title, html, args.css)
        built = [html]

    for path in built:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"файл не создан или пуст: {path}")
        print(f"Собрано: {path} ({path.stat().st_size} байт)")
    if unfilled:
        print("ВНИМАНИЕ: черновик, не заполнены заглушки " + ", ".join(unfilled))
    if not pandoc:
        print("DOCX не собран: pandoc не найден. " + INSTALL_HINT)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
