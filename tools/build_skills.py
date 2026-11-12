"""Проверка навыков репозитория и сборка архивов .skill.

Запуск:
    python tools/build_skills.py            # проверить все навыки и собрать dist/<имя>.skill
    python tools/build_skills.py --check    # только проверить

Проверки: frontmatter (name совпадает с папкой, есть description, не длиннее
1024 символов), относительные ссылки из SKILL.md ведут на существующие файлы,
нет длинного тире и меток TODO/TBD, скрипты Python компилируются, манифест
analyst-workplace-setup согласован (поля, ступени, зависимости), собственные
тесты навыков tests/test_skill.py проходят. Папки examples/ и tests/ в архив
.skill не входят.
Код выхода: 0 - всё в порядке, 1 - есть ошибки.
"""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
DIST = ROOT / "dist"
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
TEXT_SUFFIXES = {".md", ".py", ".json", ".css", ".yaml", ".yml"}
# Папки навыка, которые нужны в репозитории, но не агенту: в архив .skill не входят
NOT_PACKAGED = {"examples", "tests", "__pycache__"}


def check_skill(folder: Path) -> list[str]:
    errors: list[str] = []
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        return [f"{folder.name}: нет SKILL.md"]
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return [f"{folder.name}: нет frontmatter"]
    frontmatter = text.split("---", 2)[1]
    name = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    if not name or name.group(1) != folder.name:
        errors.append(f"{folder.name}: name во frontmatter не совпадает с папкой")
    if not re.search(r"^description:\s*\S+", frontmatter, re.MULTILINE):
        errors.append(f"{folder.name}: нет description")
    if len(frontmatter) > 1024:
        errors.append(f"{folder.name}: frontmatter {len(frontmatter)} символов, больше 1024")
    for target in LINK_RE.findall(text):
        if "://" in target or target.startswith("mailto:"):
            continue
        if not (folder / target).exists():
            errors.append(f"{folder.name}: ссылка на отсутствующий файл {target}")
    for path in folder.rglob("*"):
        if path.suffix not in TEXT_SUFFIXES or "__pycache__" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        rel = path.relative_to(SKILLS)
        if "—" in body:
            errors.append(f"{rel}: длинное тире")
        if re.search(r"\b(TODO|TBD)\b", body):
            errors.append(f"{rel}: метка TODO или TBD")
        if path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True, cfile=str(DIST / "_pyc" / rel.with_suffix(".pyc")))
            except py_compile.PyCompileError as error:
                errors.append(f"{rel}: не компилируется: {error.msg}")
    return errors


def check_manifest(folder: Path) -> list[str]:
    manifest_path = folder / "components.json"
    if not manifest_path.is_file():
        return []
    errors: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for comp in manifest["components"]:
        cid = comp.get("id", "?")
        for key in ("id", "name", "stage", "required", "purpose", "used_by", "check", "source", "install"):
            if key not in comp:
                errors.append(f"components.json {cid}: нет поля {key}")
        if cid in ids:
            errors.append(f"components.json: повтор id {cid}")
        ids.add(cid)
        if str(comp.get("stage")) not in manifest["stages"]:
            errors.append(f"components.json {cid}: неизвестная ступень")
        for method in comp.get("install", []):
            if not {"method", "command", "admin"} <= set(method):
                errors.append(f"components.json {cid}: неполный способ установки")
    for comp in manifest["components"]:
        for dep in comp.get("requires", []):
            if dep not in ids:
                errors.append(f"components.json {comp['id']}: неизвестная зависимость {dep}")
    return errors


def package(folder: Path) -> Path:
    DIST.mkdir(exist_ok=True)
    archive_path = DIST / f"{folder.name}.skill"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            rel = path.relative_to(folder)
            if path.is_file() and not NOT_PACKAGED.intersection(rel.parts):
                archive.write(path, path.relative_to(SKILLS))
    return archive_path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Проверка и сборка навыков")
    parser.add_argument("--check", action="store_true", help="только проверить, архивы не собирать")
    args = parser.parse_args()

    folders = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    errors = [e for f in folders for e in check_skill(f) + check_manifest(f)]
    for folder in folders:
        test = folder / "tests" / "test_skill.py"
        if test.is_file():
            result = subprocess.run([sys.executable, str(test)], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
            if result.returncode != 0:
                tail = (result.stdout + result.stderr).strip().splitlines()[-5:]
                errors.append(f"{folder.name}: tests/test_skill.py код {result.returncode}: " + " | ".join(tail))
    if errors:
        print("Ошибки:")
        print("\n".join(f"  {e}" for e in errors))
        return 1
    print(f"Проверено навыков: {len(folders)}")
    if not args.check:
        for folder in folders:
            archive = package(folder)
            print(f"  {archive.relative_to(ROOT)} ({archive.stat().st_size} байт)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
