"""Проверка пакета аналитика: для заказчика или для разработки.

Запуск:
    python scripts/check_package.py customer <папка-пакета>
    python scripts/check_package.py dev <папка-пакета> --change <change-id>
        [--root <корень-проекта>] [--customer <папка-пакета-для-заказчика>]

Код выхода 0: ошибок нет (предупреждения возможны). Код 1: есть ошибки.
Скрипт проверяет форму и связи. Смысл решений и полноту требований проверяет человек.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE_SECTIONS = {"краткий": {0, 2, 3, 7, 11}, "полный": {0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11}}
CUSTOMER_LANGUAGE_SECTIONS = {0, 1, 2, 3, 4, 5, 6, 7, 10, 11}
METADATA_RE = re.compile(r"\b(Документ|Справочник|РегистрСведений|РегистрНакопления|Перечисление|ПланОбмена)\.[A-Za-zА-Яа-яЁё_]+")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
MARKER_RE = re.compile(r"<!--\s*([DS]\d+)\b")
DECISION_RE = re.compile(r"\*\*Р-(\d+)\.")
TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(\d+(?:\.\d+)+)", re.MULTILINE)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.ok: list[str] = []

    def error(self, text: str) -> None:
        self.errors.append(text)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def passed(self, text: str) -> None:
        self.ok.append(text)

    def print(self) -> int:
        for text in self.ok:
            print(f"OK: {text}")
        for text in self.warnings:
            print(f"ВНИМАНИЕ: {text}")
        for text in self.errors:
            print(f"ОШИБКА: {text}")
        print(f"Итог: ошибок {len(self.errors)}, предупреждений {len(self.warnings)}")
        return 1 if self.errors else 0


def sections(text: str) -> dict[int, str]:
    """Разделы `## N. Название` -> текст раздела."""
    parts = re.split(r"^## (\d+)\.[^\n]*$", text, flags=re.MULTILINE)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def column(rows: list[list[str]], name: str) -> int | None:
    if not rows:
        return None
    for index, cell in enumerate(rows[0]):
        if name.lower() in cell.lower():
            return index
    return None


PASS_STATES = ("не начат", "готов", "требует правки", "не требуется")
RISK_STATUSES = ("на решении", "принят", "не принят", "не может быть принят")


def pass_state(manifest: str, number: int) -> str:
    """Состояние прохода из таблицы манифеста: одно из PASS_STATES или ''."""
    match = re.search(rf"^\|\s*{number}\.[^|]*\|\s*([^|]+?)\s*\|", manifest, re.MULTILINE)
    state = match.group(1).strip().strip("`").lower() if match else ""
    return state if state in PASS_STATES else ""


def has_caption(text: str, marker: str) -> bool:
    """Незаполненная заглушка с видимой подписью `*[...]*` под комментарием."""
    return re.search(rf"<!--\s*{marker}\b[^>]*-->\s*\n\s*\*\[", text) is not None


def check_customer(pkg: Path, report: Report) -> dict[str, str]:
    """Возвращает статусы решений {'Р-1': 'Подтверждено', ...}."""
    package_md, manifest_md = pkg / "package.md", pkg / "README.md"
    for path in (package_md, manifest_md):
        if not path.is_file():
            report.error(f"нет файла {path}")
    if report.errors:
        return {}
    text = package_md.read_text(encoding="utf-8")
    manifest = manifest_md.read_text(encoding="utf-8")

    profile_match = re.search(r"\*\*Профиль:\*\*\s*(краткий|полный)", manifest)
    profile = profile_match.group(1) if profile_match else "краткий"
    if not profile_match:
        report.warn("в манифесте не указан профиль, проверяю как краткий")
    found = sections(text)
    missing = sorted(PROFILE_SECTIONS[profile] - found.keys())
    if missing:
        report.error(f"профиль «{profile}»: нет разделов {missing}")
    else:
        report.passed(f"все разделы профиля «{profile}» на месте")

    statuses: dict[str, str] = {}
    decisions = found.get(2, "")
    chunks = DECISION_RE.split(decisions)
    for i in range(1, len(chunks) - 1, 2):
        key, body = f"Р-{chunks[i]}", chunks[i + 1]
        status = re.search(r"Статус:\**\s*(Подтверждено|Предложено)(\s*\([^)]+\))?", body)
        if not status:
            report.error(f"{key}: нет статуса «Предложено» или «Подтверждено»")
            continue
        statuses[key] = status.group(1)
        if status.group(1) == "Подтверждено" and not status.group(2):
            report.error(f"{key}: «Подтверждено» без источника в скобках (кто и когда подтвердил)")
    if statuses:
        report.passed(f"решений со статусом: {len(statuses)}")
    confirmed = [k for k, v in statuses.items() if v == "Подтверждено"]
    if confirmed:
        report.passed(f"подтверждены с указанием источника: {', '.join(confirmed)}")

    risk_rows = table_rows(found.get(7, ""))
    plan_b = column(risk_rows, "вариант б")
    owner = column(risk_rows, "владелец")
    risk_status = column(risk_rows, "статус")
    for row in risk_rows[1:]:
        value = row[risk_status].strip("`").lower() if risk_status is not None and risk_status < len(row) else ""
        if value and not value.startswith(RISK_STATUSES):
            report.warn(f"раздел 7: статус риска «{row[risk_status]}» не из словаря {', '.join(RISK_STATUSES)}")
    if risk_rows and (plan_b is None or owner is None):
        report.error("раздел 7: в таблице рисков нет колонок «Владелец» и «Вариант Б»")
    for row in risk_rows[1:]:
        for idx, name in ((owner, "владельца"), (plan_b, "варианта Б")):
            if idx is not None and (idx >= len(row) or not row[idx]):
                report.error(f"раздел 7: у риска «{row[0]}» нет {name}")

    questions = found.get(11, "")
    question_rows = table_rows(questions)[1:]
    if "открытых вопросов нет" not in questions.lower() and not question_rows:
        report.error("раздел 11 пуст: нужна таблица вопросов или строка «Открытых вопросов нет»")
    elif len(question_rows) > 5:
        report.warn(f"вопросов к заказчику {len(question_rows)}: стоит вернуться к извлечению требований до отправки")

    for number in CUSTOMER_LANGUAGE_SECTIONS & found.keys():
        names = sorted(set(m.group(0) for m in METADATA_RE.finditer(found[number])))
        if names:
            report.warn(f"раздел {number} для заказчика содержит имена метаданных: {', '.join(names)}")

    for path in IMAGE_RE.findall(text):
        if not path.startswith(("http://", "https://", "data:")) and not (pkg / path).is_file():
            report.error(f"нет файла картинки {path}")
    images = [Path(p).name for p in IMAGE_RE.findall(text)]
    for kind, number in (("D", 2), ("S", 3)):
        markers = [m for m in dict.fromkeys(MARKER_RE.findall(text)) if m.startswith(kind)]
        empty = [m for m in markers if not any(name.startswith(f"{m}-") or name.startswith(f"{m}.") for name in images)]
        state = pass_state(manifest, number)
        captioned = [m for m in empty if has_caption(text, m)]
        if empty and state == "готов":
            report.error(f"проход {number} отмечен готовым, но заглушки не заполнены: {', '.join(empty)}")
        elif state == "не требуется" and captioned:
            report.error(f"проход {number} не требуется, но остались видимые подписи заглушек: {', '.join(captioned)}")
        elif state == "не требуется":
            report.passed(f"проход {number} отмечен как не требуется")
        elif empty:
            report.warn(f"не заполнены заглушки {', '.join(empty)} (проход {number}: {state or 'состояние не указано'})")
        elif markers:
            report.passed(f"заглушки {kind} заполнены: {len(markers)}")
    return statuses


def run_openspec(args: list[str], root: Path) -> tuple[int, str]:
    exe = shutil.which("openspec")
    if not exe:
        return 127, "openspec не найден"
    result = subprocess.run([exe, *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout or result.stderr


INTEGRATION_COLUMNS = ("поток", "триггер", "данные", "ошибки", "повторы", "владелец")
EMPTY_VALUES = ("", "-", "?")
UNDECIDED_PREFIXES = ("не определ", "не спроектир", "не описан", "уточнить", "[проверь]")


def is_empty_cell(value: str) -> bool:
    value = value.strip("`* ").lower()
    return value in EMPTY_VALUES or value.startswith(UNDECIDED_PREFIXES)


def check_integrations(design: str, report: Report) -> None:
    """Таблица интеграций в design.md: колонки INTEGRATION_COLUMNS, значения заполнены."""
    if "внешних интеграций нет" in design.lower():
        report.passed("design.md: внешних интеграций нет")
        return
    candidates = [block for block in re.split(r"\n\s*\n", design) if block.lstrip().startswith("|")]
    for block in candidates:
        rows = table_rows(block)
        header = [cell.lower() for cell in rows[0]] if rows else []
        if not any("триггер" in cell for cell in header):
            continue
        indexes = {}
        for name in INTEGRATION_COLUMNS:
            indexes[name] = next((i for i, cell in enumerate(header) if name in cell), None)
        missing = [name for name, i in indexes.items() if i is None]
        if missing:
            report.error(f"design.md: в таблице интеграций нет колонок {', '.join(missing)}")
            return
        for row in rows[1:]:
            empty = [name for name, i in indexes.items() if i >= len(row) or is_empty_cell(row[i])]
            if empty:
                report.error(f"design.md: у потока «{row[indexes['поток']]}» не заполнено: {', '.join(empty)}")
        report.passed(f"design.md: таблица интеграций найдена, потоков {len(rows) - 1}")
        return
    report.error("design.md: нет таблицы интеграций с колонками " + ", ".join(INTEGRATION_COLUMNS)
                 + " (если интеграций нет, напишите «Внешних интеграций нет»)")


def check_dev(pkg: Path, change: str, root: Path, customer: Path | None, report: Report) -> None:
    for name in ("README.md", "traceability.md", "handoff.md"):
        if not (pkg / name).is_file():
            report.error(f"нет файла {pkg / name}")
    change_dir = root / "openspec" / "changes" / change
    if not change_dir.is_dir():
        report.error(f"нет изменения OpenSpec {change_dir}")
        return

    code, out = run_openspec(["validate", change, "--strict", "--json", "--no-interactive"], root)
    if code != 0:
        report.error(f"openspec validate --strict не пройден: {out.strip()[:500]}")
    else:
        report.passed("openspec validate --strict пройден")

    code, out = run_openspec(["show", change, "--json", "--deltas-only"], root)
    requirements: dict[str, int] = {}
    if code == 0:
        for delta in json.loads(out).get("deltas", []):
            for req in delta.get("requirements") or [delta.get("requirement") or {}]:
                if req.get("name"):
                    requirements[req["name"]] = len(req.get("scenarios", []))
    else:
        report.error(f"openspec show не выполнен: {out.strip()[:300]}")
    for name, count in requirements.items():
        if count < 2:
            report.warn(f"требование «{name}»: сценариев {count}, нужен основной и отказный")
    if requirements and all(count >= 2 for count in requirements.values()):
        report.passed("у каждого требования не меньше двух сценариев; что один из них отказный, проверяет человек")

    tasks_md = change_dir / "tasks.md"
    tasks = set(TASK_RE.findall(tasks_md.read_text(encoding="utf-8"))) if tasks_md.is_file() else set()
    if not tasks:
        report.error("в tasks.md нет задач вида «- [ ] 1.1 ...»")

    design = change_dir / "design.md"
    if not design.is_file():
        report.warn("нет design.md: интеграции, состояния и данные не описаны")
    else:
        check_integrations(design.read_text(encoding="utf-8"), report)

    trace_md = pkg / "traceability.md"
    if not trace_md.is_file():
        return
    rows = table_rows(trace_md.read_text(encoding="utf-8"))
    req_col, task_col, dec_col = column(rows, "требование"), column(rows, "задач"), column(rows, "решение")
    if req_col is None or task_col is None or dec_col is None:
        report.error("traceability.md: нужны колонки «Решение», «Требование», «Задачи»")
        return
    traced_reqs, traced_tasks, traced_decisions = set(), set(), set()
    for row in rows[1:]:
        req = row[req_col] if req_col < len(row) else ""
        is_gap = not req or req.lower() == "пробел"
        if not is_gap:
            if req not in requirements:
                report.error(f"traceability.md: требования «{req}» нет в OpenSpec")
            traced_reqs.add(req)
        for task in re.findall(r"\d+(?:\.\d+)+", row[task_col] if task_col < len(row) else ""):
            if task not in tasks:
                report.error(f"traceability.md: задачи {task} нет в tasks.md")
            if not is_gap:
                traced_tasks.add(task)
        traced_decisions.update(re.findall(r"Р-\d+", row[dec_col] if dec_col < len(row) else ""))
    untraced = sorted(set(requirements) - traced_reqs)
    if untraced:
        report.error(f"требования без строки трассировки: {', '.join(untraced)}")
    elif requirements:
        report.passed(f"все требования OpenSpec в трассировке: {len(requirements)}")
    loose = sorted(tasks - traced_tasks)
    if loose:
        report.warn(f"задачи без связи с требованием: {', '.join(loose)}")

    if customer:
        sub = Report()
        statuses = check_customer(customer, sub)
        for text in sub.errors:
            report.error(f"пакет для заказчика: {text}")
        for text in sub.warnings:
            report.warn(f"пакет для заказчика: {text}")
        for key, status in statuses.items():
            if status == "Подтверждено" and key not in traced_decisions:
                report.error(f"подтверждённое решение {key} не покрыто ни одним требованием")
            if status == "Предложено":
                report.warn(f"решение {key} не подтверждено заказчиком")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Проверка пакета аналитика")
    sub = parser.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("customer", help="пакет для заказчика")
    c.add_argument("package_dir", type=Path)
    d = sub.add_parser("dev", help="пакет для разработки")
    d.add_argument("package_dir", type=Path)
    d.add_argument("--change", required=True, help="идентификатор изменения OpenSpec")
    d.add_argument("--root", type=Path, default=Path.cwd(), help="корень проекта с папкой openspec")
    d.add_argument("--customer", type=Path, help="папка пакета для заказчика")
    args = parser.parse_args()

    report = Report()
    if args.mode == "customer":
        check_customer(args.package_dir.resolve(), report)
    else:
        customer = args.customer.resolve() if args.customer else None
        check_dev(args.package_dir.resolve(), args.change, args.root.resolve(), customer, report)
    return report.print()


if __name__ == "__main__":
    sys.exit(main())
