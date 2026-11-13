# Изменения

## 0.3.0, 2026-11-13

- `analyst-workplace-setup`: code-index проверяется сквозной smoke-пробой
  (CODE_INDEX_HOME, daemon.toml, статус демона, MCP-порт 8011); бинарник
  без живого MCP получает статус «настроить» вместо «есть» и не предлагает
  переустановку.
- SKILL.md: процедура пост-установки code-index - переменная окружения,
  daemon.toml, демон, отсоединённый запуск serve, регистрация MCP в клиенте,
  сквозная проба initialize + get_stats, команды перезапуска в отчёт.
- «Частые ошибки»: HTTP 406 на `/mcp` без заголовков Accept, кириллица
  в JSON-RPC из Git Bash, падение `daemon status` без CODE_INDEX_HOME,
  смерть serve вместе с сессией агента, поиск index.db от текущей папки.
- `check_env.py`: переменные окружения пользователя (CODE_INDEX_HOME)
  перечитываются из реестра, как PATH.

## 0.2.0, 2026-11-12

- Шаблон проекта вынесен в отдельный репозиторий-шаблон
  [1c-analyst-bootstrap](https://github.com/Romandredan/1c-analyst-bootstrap).
- Общие правила агента `global/AGENTS.md`.
- `requirements-elicitation-ru` переписан самостоятельно, добавлены справочники
  `references/`.
- Манифест: источник и способы установки шлюза `odata1c`.
- Манифест: установка `v8-runner` и шлюза `odata1c` автоматизирована (релиз
  GitHub и пакет PyPI), ручной осталась только платформа 1С - она
  лицензионная и не скачивается.
- README: раздел «Одной просьбой к агенту» - установка рабочего места без
  ручных шагов по ссылке на репозиторий.
- Манифест: навыки [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills)
  (Nick Shirokov, MIT) для внешнего отчёта: каркас ERF, СКД из JSON, сборка
  и проверка; ставятся из репозитория автора, копии не хранятся.
- `NOTICE.md`: раздел о происхождении `requirements-elicitation-ru` убран,
  атрибуция сторонних навыков собрана в одном разделе.

## 0.1.0, 2026-11-09

Первая сборка набора: навыки `analyst-workplace-setup`, `requirements-elicitation-ru`,
`analyst-handoff`, `mermaid-diagrams-ru`, установщик навыков из репозиториев и архивов,
проверка и сборка архивов `tools/build_skills.py`.
