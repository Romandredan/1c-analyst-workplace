"""Установка навыка агента из репозитория Git или из архива .skill в каталог навыков клиента.

Запуск:
    python scripts/install_skill.py --repo obra/superpowers --ref v7.0.2 --path skills/brainstorming --client zcode
    python scripts/install_skill.py --repo mattpocock/skills --ref v1.3.2 \
        --path skills/productivity/grilling --path skills/engineering/domain-modeling --client zcode
    python scripts/install_skill.py --archive analyst-handoff.skill --client zcode

Из репозитория делается поверхностный clone указанного тега или ветки во временную
папку, затем каждая папка из --path копируется в каталог навыков целиком (со
скриптами и справочниками). Код из скачанного не запускается. Уже установленный
навык не перезаписывается: скрипт останавливается и называет папку, решение
принимает пользователь.
Код выхода: 0 - всё поставлено, 1 - ошибка, 3 - навык уже есть.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_env import CLIENT_SKILL_DIRS  # noqa: E402


def resolve_dest(args: argparse.Namespace) -> Path:
    if args.dest:
        return Path(args.dest).expanduser().resolve()
    return Path(CLIENT_SKILL_DIRS[args.client][0]).expanduser().resolve()


def copy_skill(folder: Path, dest: Path) -> int:
    if not (folder / "SKILL.md").is_file():
        print(f"ОШИБКА: в {folder.name} нет SKILL.md, это не навык")
        return 1
    target = dest / folder.name
    if target.exists():
        print(f"УЖЕ ЕСТЬ: {target}. Обновление или замену согласуйте с пользователем")
        return 3
    shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    print(f"Установлен: {target}")
    return 0


def from_repo(args: argparse.Namespace, dest: Path) -> int:
    url = args.repo if "://" in args.repo or args.repo.startswith("git@") else f"https://github.com/{args.repo}.git"
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "repo"
        result = subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", args.ref, url, str(clone)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            print(f"ОШИБКА: git clone {url} ({args.ref}) не выполнен: {result.stderr.strip()[:300]}")
            print("Если репозиторий приватный, нужен доступ к нему; иначе используйте архив .skill")
            return 1
        commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        print(f"Источник: {url}, {args.ref}, коммит {commit}")
        codes = [copy_skill(clone / p, dest) for p in args.path]
    return max(codes)


def from_archive(args: argparse.Namespace, dest: Path) -> int:
    archive = Path(args.archive).expanduser().resolve()
    if not zipfile.is_zipfile(archive):
        print(f"ОШИБКА: {archive} не является архивом навыка")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        folders = [p.parent for p in Path(tmp).glob("*/SKILL.md")]
        if not folders:
            print(f"ОШИБКА: в {archive.name} нет папки навыка с SKILL.md")
            return 1
        print(f"Источник: {archive}")
        codes = [copy_skill(folder, dest) for folder in folders]
    return max(codes)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Установка навыка агента")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", help="владелец/репозиторий на GitHub или полный адрес Git")
    source.add_argument("--archive", help="архив <имя>.skill")
    parser.add_argument("--ref", default="main", help="тег или ветка; для чужих навыков указывайте тег")
    parser.add_argument("--path", action="append", help="папка навыка внутри репозитория; можно несколько")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--client", choices=sorted(CLIENT_SKILL_DIRS), help="клиент агента")
    target.add_argument("--dest", help="каталог навыков явно")
    args = parser.parse_args()

    dest = resolve_dest(args)
    dest.mkdir(parents=True, exist_ok=True)
    if args.repo:
        if not args.path:
            parser.error("для --repo нужен хотя бы один --path")
        return from_repo(args, dest)
    return from_archive(args, dest)


if __name__ == "__main__":
    sys.exit(main())
