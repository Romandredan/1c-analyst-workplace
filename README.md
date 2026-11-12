# 1c-analyst-workplace

Рабочее место аналитика 1С для работы с ИИ-агентом. Репозиторий даёт:

- **навыки**, которые ведут задачу от транскрипта встречи до пакета на
  согласование заказчику и пакета для разработки;
- **навык установки**, который проверяет и ставит всё нужное для этой работы;
- **общие правила агента** для всех проектов.

Рабочее место ставится один раз на компьютер. Проекты создаются из шаблона
[1c-analyst-bootstrap](https://github.com/Romandredan/1c-analyst-bootstrap): в нём
у сырья, знаний, решений, спецификаций и пакетов есть свои места, а агент знает
правила работы с ними.

## Состав

| Путь | Что это |
|---|---|
| [`skills/requirements-elicitation-ru`](skills/requirements-elicitation-ru/) | Разбор встречи или постановки: факты, гипотезы, пробелы, вопросы к заказчику и к реализации, риски |
| [`skills/analyst-handoff`](skills/analyst-handoff/) | Пакет на согласование заказчику (текст, схемы, экраны, сборка в DOCX и HTML) в итерационном или полном режиме и пакет передачи в разработку |
| [`skills/mermaid-diagrams-ru`](skills/mermaid-diagrams-ru/) | Схемы процессов, интеграций и статусов в Mermaid с отрисовкой в PNG |
| [`skills/analyst-workplace-setup`](skills/analyst-workplace-setup/) | Проверка и установка рабочего места по ступеням; манифест компонентов [`components.json`](skills/analyst-workplace-setup/components.json) |
| [`global/AGENTS.md`](global/AGENTS.md) | Общие правила агента для всех проектов: кладутся в каталог настроек клиента |
| [`tools/build_skills.py`](tools/build_skills.py) | Проверка навыков и сборка архивов `dist/<имя>.skill` |

## Ступени рабочего места

| Ступень | Что даёт |
|---|---|
| 1 | Чат с пространствами: ничего не устанавливается |
| 2 | Агентская среда: клиент агента, Git, Python, Node.js, Mermaid CLI, pandoc, OpenSpec, навыки аналитика |
| 3 | Контур 1С: платформа, индекс кода конфигурации, шлюз к данным базы, сборка и тесты |

## Как начать

### 0. Одной просьбой к агенту

Если ставить будет агент, ручные шаги не нужны. Отправьте ему текст:

> Установи мне рабочее место аналитика 1С из этого репозитория:
> https://github.com/Romandredan/1c-analyst-workplace
> Там есть навык установки — найди его и следуй ему до конца. Если что-то
> нужно подтвердить или доустановить, спроси меня простыми словами и подожди
> моего ответа.

Агент сам скачает репозиторий, поставит навык установки
(`skills/analyst-workplace-setup`, установщик — `scripts/install_skill.py`),
скопирует общие правила `global/AGENTS.md` в настройки клиента и выполнит
установку по манифесту. Требование одно: Python на машине; если его нет,
агент подскажет, что сделать.

### 1. Рабочее место

Первым ставится навык установки, дальше он работает сам: проверяет окружение,
показывает план недостающего и после подтверждения ставит компоненты из
официальных источников.

1. Скачайте архив `analyst-workplace-setup.skill` из раздела Releases.
2. Распакуйте его в каталог навыков своего клиента агента:

   ```powershell
   python -m zipfile -e analyst-workplace-setup.skill "$env:USERPROFILE\.zcode\skills"
   ```

   Для Claude Code каталог `%USERPROFILE%\.claude\skills`. Команда
   `Expand-Archive` расширение `.skill` не принимает.
3. Попросите агента: «Подготовь рабочее место аналитика, ступень 2».

Проверить окружение без агента:

```powershell
python skills/analyst-workplace-setup/scripts/check_env.py --stage 2 --client zcode
```

В Claude Code репозиторий подключается как плагин:

```text
/plugin marketplace add Romandredan/1c-analyst-workplace
/plugin install 1c-analyst-workplace@1c-analyst-workplace
```

### 2. Общие правила агента

Скопируйте [`global/AGENTS.md`](global/AGENTS.md) в каталог настроек клиента:
`%USERPROFILE%\.zcode\AGENTS.md` для ZCode, `%USERPROFILE%\.claude\CLAUDE.md`
для Claude Code. Правила конкретного проекта лежат в `AGENTS.md` проекта.

### 3. Проект

Проект создаётся из шаблона
[1c-analyst-bootstrap](https://github.com/Romandredan/1c-analyst-bootstrap)
кнопкой «Use this template» или командой `git clone`, затем места шаблона
заполняются скриптом `tools/init_project.py`. Тот же скрипт накладывает
структуру на существующий репозиторий команды разработки. Порядок описан в
README шаблона.

## Навыки по ходу задачи

```text
сырьё и встречи → извлечение требований → ответы заказчика → ADR и прожарка
  → пакет для заказчика (подпись) → изменение OpenSpec → пакет для разработки
```

| Шаг | Навык |
|---|---|
| Разбор встречи или постановки | `requirements-elicitation-ru` |
| Варианты решения, запись и прожарка ADR | `brainstorming`, `domain-modeling`, `grilling` |
| Пакет на согласование: текст, схемы, экраны, сборка | `analyst-handoff`, `mermaid-diagrams-ru`, `md-design-prototype` |
| Спецификация изменения | `openspec-propose` (ставится в проект командой `openspec init`) |
| Пакет для разработки | `analyst-handoff` |

## Сторонние навыки

Навык установки ставит их из репозиториев авторов; в этом
репозитории их копий нет.

| Навык | Источник | Лицензия |
|---|---|---|
| `brainstorming` | [obra/superpowers](https://github.com/obra/superpowers) `v7.0.2` | MIT |
| `grilling`, `domain-modeling` | [mattpocock/skills](https://github.com/mattpocock/skills) `v1.3.2` | MIT |
| `md-design-prototype` и исполнители отрисовки | [Romandredan/md-design-skills](https://github.com/Romandredan/md-design-skills) | MIT |
| `erf-*`, `epf-build`, `epf-validate`, `skd-*`, `meta-info` (и необязательные `db-*`, `template-add`, `mxl-*`) | [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills), ветка `main` | MIT |

`brainstorming` в конце работы передаёт управление навыку `writing-plans` своего
набора. Аналитику этот шаг не нужен: его работа заканчивается дизайном и записью
решения (ADR).

Для контура 1С манифест описывает также индекс кода
[code-index](https://github.com/Regsorm/code-index-mcp), шлюз к данным
[odata1c-gate](https://github.com/Romandredan/odata1c-gate) и
[v8-runner](https://github.com/alkoleft/v8-runner-rust).

## Сборка

```powershell
python tools/build_skills.py
```

Скрипт проверяет навыки (frontmatter, ссылки, скрипты, манифест), запускает
собственные тесты навыков `tests/test_skill.py` и собирает архивы
`dist/<имя>.skill` для раздела Releases. Папки `examples/` и `tests/` остаются
в репозитории, но в архивы не входят: агенту они не нужны.

## Происхождение и лицензия

Код и тексты репозитория распространяются по лицензии [MIT](LICENSE), кроме
случаев, перечисленных в [NOTICE.md](NOTICE.md).
