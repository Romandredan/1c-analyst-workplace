"""Установка программы из официального релиза GitHub в папку пользователя, без прав администратора.

Запуск:
    python scripts/install_release.py --repo jgm/pandoc --asset "windows-x86_64\\.zip$" --exe pandoc.exe --name pandoc
        [--tag v3.13] [--sha256 ХЕШ] [--no-path]

Скачивает архив релиза (последнего или указанного) с github.com, проверяет SHA-256,
если он передан, распаковывает в %LOCALAPPDATA%\\Programs\\<name>, копирует туда
папку с исполняемым файлом и добавляет её в PATH пользователя.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/{repo}/releases/{ref}"
HEADERS = {"User-Agent": "analyst-workplace-setup", "Accept": "application/vnd.github+json"}


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return json.load(response)


def add_to_user_path(folder: Path) -> bool:
    current = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "[Environment]::GetEnvironmentVariable('Path','User')"],
                             capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if str(folder).lower() in (p.lower() for p in current.split(";")):
        return False
    new_value = (current.rstrip(";") + ";" + str(folder)).lstrip(";")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"[Environment]::SetEnvironmentVariable('Path', '{new_value}', 'User')"], check=True)
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Установка из релиза GitHub в папку пользователя")
    parser.add_argument("--repo", required=True, help="владелец/репозиторий")
    parser.add_argument("--asset", required=True, help="регулярное выражение имени файла релиза (.zip)")
    parser.add_argument("--exe", required=True, help="имя исполняемого файла внутри архива")
    parser.add_argument("--name", required=True, help="имя папки установки")
    parser.add_argument("--tag", help="тег релиза; по умолчанию последний")
    parser.add_argument("--sha256", help="ожидаемый SHA-256 архива")
    parser.add_argument("--no-path", action="store_true", help="не добавлять в PATH пользователя")
    args = parser.parse_args()

    ref = f"tags/{args.tag}" if args.tag else "latest"
    release = fetch_json(API.format(repo=args.repo, ref=ref))
    assets = [a for a in release["assets"] if re.search(args.asset, a["name"])]
    if not assets:
        print(f"ОШИБКА: в релизе {release['tag_name']} нет файла по шаблону {args.asset}")
        return 1
    asset = assets[0]
    print(f"Релиз {args.repo} {release['tag_name']}: {asset['name']} ({asset['size'] // 1024 // 1024} МБ)")

    target = Path(os.environ["LOCALAPPDATA"]) / "Programs" / args.name
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / asset["name"]
        with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers=HEADERS),
                                    timeout=600) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        print(f"SHA-256: {digest}")
        if args.sha256 and digest.lower() != args.sha256.lower():
            print("ОШИБКА: SHA-256 не совпадает, установка остановлена")
            return 1
        unpacked = Path(tmp) / "unpacked"
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(unpacked)
        exe = next(unpacked.rglob(args.exe), None)
        if exe is None:
            print(f"ОШИБКА: в архиве нет {args.exe}")
            return 1
        target.mkdir(parents=True, exist_ok=True)
        for item in exe.parent.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    installed = target / args.exe
    version = subprocess.run([str(installed), "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.splitlines()[:1]
    print(f"Установлено: {installed} ({version[0] if version else 'версия не прочитана'})")
    if not args.no_path:
        print("PATH пользователя дополнен" if add_to_user_path(target) else "Папка уже в PATH пользователя")
        print("Новые терминалы и клиент агента увидят программу после перезапуска")
    return 0


if __name__ == "__main__":
    sys.exit(main())
