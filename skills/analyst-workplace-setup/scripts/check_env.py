"""Проверка рабочего места аналитика по манифесту components.json.

Запуск:
    python scripts/check_env.py [--stage 2] [--skills-dir ПАПКА ...] [--markdown] [--write-versions setup/versions.md]

Для каждого компонента ступени (и ниже) печатает: статус, найденную версию,
назначение и что делать, если компонента нет. PATH перечитывается из реестра
Windows, поэтому только что установленные программы видны без перезапуска.
Код выхода: 0 - всё обязательное на месте, 1 - чего-то обязательного нет.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
MANIFEST = SKILL_DIR / "components.json"
CLIENT_SKILL_DIRS = {
    "zcode": ["~/.zcode/skills"],
    "claude": ["~/.claude/skills", ".claude/skills"],
    "agents": ["~/.agents/skills", ".agents/skills"],
}
DEFAULT_SKILL_DIRS = [d for dirs in CLIENT_SKILL_DIRS.values() for d in dirs]
VERSION_RE = re.compile(r"(\d+(?:\.\d+){1,3})")
OK, OLD, MISSING, MANUAL = "есть", "старая версия", "нет", "проверить вручную"


def refresh_path() -> None:
    """Добавляет к PATH процесса значения PATH из реестра (пользователь и система)."""
    if os.name != "nt":
        return
    import winreg
    parts = os.environ.get("PATH", "").split(os.pathsep)
    for root, key in ((winreg.HKEY_CURRENT_USER, r"Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(root, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
        except OSError:
            continue
        for item in os.path.expandvars(value).split(os.pathsep):
            if item and item not in parts:
                parts.append(item)
    os.environ["PATH"] = os.pathsep.join(parts)


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


def check_command(spec: dict) -> tuple[str, str]:
    exe = shutil.which(spec["cmd"][0])
    if not exe:
        exe = next((str(Path(os.path.expandvars(p)).expanduser()) for p in spec.get("paths", [])
                    if Path(os.path.expandvars(p)).expanduser().is_file()), None)
    if not exe:
        return MISSING, ""
    try:
        result = subprocess.run([exe] + spec["cmd"][1:], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return MISSING, f"не запускается: {error}"
    match = VERSION_RE.search(result.stdout + result.stderr)
    version = match.group(1) if match else "?"
    minimum = spec.get("min_version")
    if minimum and match and as_tuple(version) < as_tuple(minimum):
        return OLD, version
    if spec.get("smoke") == "mermaid":
        smoke = mermaid_smoke(exe)
        if smoke:
            return MISSING, f"{version}, рендер не работает: {smoke}"
    return OK, version


def mermaid_smoke(exe: str) -> str:
    """Рисует маленькую схему с кириллицей; возвращает текст ошибки или пустую строку."""
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "smoke.mmd", Path(tmp) / "smoke.png"
        src.write_text('flowchart TD\n  A["Заказ"] --> B["Оплата"]\n', encoding="utf-8")
        result = subprocess.run([exe, "-i", str(src), "-o", str(out), "-b", "white"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            return (result.stderr or result.stdout).strip()[:200] or "PNG не создан"
    return ""


def check_path(spec: dict) -> tuple[str, str]:
    for raw in spec["paths"]:
        path = Path(raw).expanduser()
        if path.exists():
            return OK, str(path)
    return MISSING, ""


def check_skill(spec: dict, skill_dirs: list[Path]) -> tuple[str, str]:
    found = {}
    for name in spec["names"]:
        for root in skill_dirs:
            if (root / name / "SKILL.md").is_file():
                found[name] = root
                break
    need_all = spec.get("all", False)
    if (need_all and len(found) == len(spec["names"])) or (not need_all and found):
        return OK, "; ".join(f"{n} в {r}" for n, r in found.items())
    disabled = [str(r.parent / "skills-disabled" / n) for n in spec["names"] for r in skill_dirs
                if (r.parent / "skills-disabled" / n).is_dir()]
    hint = f"лежит в отключённых: {disabled[0]}" if disabled else ""
    return MISSING, hint


def evaluate(component: dict, skill_dirs: list[Path]) -> tuple[str, str]:
    kind = component["check"]["type"]
    if kind == "command":
        return check_command(component["check"])
    if kind == "path":
        return check_path(component["check"])
    if kind == "skill":
        return check_skill(component["check"], skill_dirs)
    return MANUAL, ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Проверка рабочего места аналитика")
    parser.add_argument("--stage", type=int, default=2, help="Ступень: 2 или 3 (включает нижние)")
    parser.add_argument("--client", choices=sorted(CLIENT_SKILL_DIRS),
                        help="Клиент агента: навыки ищутся только в его каталогах")
    parser.add_argument("--skills-dir", action="append", help="Каталог навыков клиента; можно несколько")
    parser.add_argument("--markdown", action="store_true", help="Вывод таблицей Markdown")
    parser.add_argument("--write-versions", type=Path, help="Записать найденные версии в файл")
    args = parser.parse_args()

    refresh_path()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    chosen = args.skills_dir or (CLIENT_SKILL_DIRS[args.client] if args.client else DEFAULT_SKILL_DIRS)
    skill_dirs = [Path(p).expanduser().resolve() for p in chosen]
    if not args.client and not args.skills_dir:
        print("Клиент не указан: навыки ищутся во всех известных каталогах; для проверки профиля укажите --client")
    by_id = {c["id"]: c for c in manifest["components"]}
    selected = {c["id"] for c in manifest["components"] if c["stage"] <= args.stage}
    for comp_id in list(selected):
        selected.update(dep for dep in by_id[comp_id].get("requires", []) if dep in by_id)
    rows = []
    for comp in manifest["components"]:
        if comp["id"] not in selected:
            continue
        status, detail = evaluate(comp, skill_dirs)
        action = ""
        if status in (MISSING, OLD, MANUAL):
            first = comp["install"][0]
            action = f"{first['method']}: {first['command']}"
        rows.append((comp, status, detail, action))

    if args.markdown:
        print("| Компонент | Ступень | Статус | Версия или место | Назначение | Что делать |")
        print("|---|---|---|---|---|---|")
        for comp, status, detail, action in rows:
            print(f"| {comp['name']} | {comp['stage']} | {status} | {detail} | {comp['purpose']} | {action} |")
    else:
        for comp, status, detail, action in rows:
            mark = {OK: "[+]", OLD: "[~]", MISSING: "[-]", MANUAL: "[?]"}[status]
            need = "обязательный" if comp["required"] else "по необходимости"
            print(f"{mark} {comp['name']} ({need}, ступень {comp['stage']}): {status} {detail}".rstrip())
            if action:
                print(f"    зачем: {comp['purpose']}")
                print(f"    как:   {action}")

    if args.write_versions:
        args.write_versions.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Версии рабочего места", "", f"Проверено: {dt.date.today().isoformat()}, ступень {args.stage}.", "",
                 "| Компонент | Статус | Версия или место | Источник |", "|---|---|---|---|"]
        lines += [f"| {c['name']} | {s} | {d} | {c['source'] or 'уточнить'} |" for c, s, d, _ in rows]
        args.write_versions.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Версии записаны: {args.write_versions}")

    missing_required = [c["name"] for c, s, _, _ in rows if c["required"] and s in (MISSING, OLD)]
    if missing_required:
        print("Не хватает обязательного: " + ", ".join(missing_required))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
