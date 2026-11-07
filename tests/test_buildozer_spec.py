"""Регрессионные проверки гигиены рабочего дерева и сборки APK.

Три инцидента, которые закрывают эти тесты:

1. `git rm -r` снял файлы с индекса, но оставил на диске каталоги с
   untracked-содержимым (node_modules) — 18 499 файлов, ~380 МБ. Корень:
   правила игнорирования жили в локальном `.git/info/exclude` и терялись
   при клоне. Теперь они обязаны быть в коммитящемся `.gitignore`.
2. Чистка `buildozer.spec` чуть не выбросила из `source.exclude_dirs`
   живые каталоги (`website-redesign-figma-files` — 2888 файлов). Список
   исключений нельзя править «на глаз» — нужно пересчитывать, что реально
   уезжает в APK по `source.include_exts`.
3. Эмуляция считала `exclude_dirs` по имени каталога на любой глубине,
   тогда как buildozer 1.6.0 сравнивает **префикс относительного пути**
   (`filtered_root.startswith(exclude_dir + '/')`). Из-за этого
   `mobile-teacher-app-redesign/node_modules` в APK не исключался, а тест
   этого не видел. Теперь эмуляция повторяет `_copy_application_sources`
   из buildozer 1.6.0, включая `source.exclude_patterns` (fnmatch по
   полному относительному пути файла).
"""
from __future__ import annotations

import os
import re
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "buildozer.spec"
GITIGNORE = ROOT / ".gitignore"

# Каталоги дизайн-итераций, удалённые в 65e1891. Имена намеренно остаются
# в .gitignore: если архив распакуют обратно, мусор не попадёт в индекс.
DELETED_PROTOTYPES = (
    "code-and-design-review",
    "refactor-and-lightweight-redesign",
    "refactor-and-redesign-mobile-app",
    "refactoring-and-redesign-prompt",
)

# Живые каталоги первого уровня, которые НЕ должны попадать в APK.
LIVE_JUNK = (
    "website-redesign-figma-files",
    "visual-redesign-of-tech-project",
    ".slim",
    ".workbuddy-ai",
)

# Dev-инструменты, которые остаются в репозитории, но не нужны в APK.
DEV_ONLY_FILES = (
    "stand.py",
    "stand_seed.py",
    "seed_db.py",
    "generate_icon.py",
    "mobile-teacher-app-redesign/e2e_server.py",
    "mobile-teacher-app-redesign/index.html",
    "mobile-teacher-app-redesign/src/index.css",
    "mobile-teacher-app-redesign/src/restore.css",
    "src/teachhelper/app.py",
    "src/teachhelper/__init__.py",
)

# Каталоги верхнего уровня, из которых файлы осознанно едут в APK.
# '' — файлы в корне проекта (api.py, main.py, иконки, ...).
PACKAGED_TOPLEVEL = {"", "mobile-teacher-app-redesign"}

DIST_BUNDLE = "mobile-teacher-app-redesign/dist/index.html"


def _spec_parts() -> tuple[set[str], set[str], set[str], str]:
    text = SPEC.read_text(encoding="utf-8")

    def get(key: str) -> set[str]:
        match = re.search(r"^" + re.escape(key) + r"\s*=\s*(.*)$", text, re.M)
        assert match, f"{key} не найден в buildozer.spec"
        return {part.strip().lower() for part in match.group(1).split(",") if part.strip()}

    extensions = get("source.include_exts")
    exclude_dirs = get("source.exclude_dirs")
    exclude_patterns = get("source.exclude_patterns")
    assert extensions and exclude_dirs
    return extensions, exclude_dirs, exclude_patterns, text


def _included_files(extensions: set[str], exclude_dirs: set[str],
                    exclude_patterns: set[str]) -> list[str]:
    """Точная эмуляция `_copy_application_sources` из buildozer 1.6.0.

    Отличия от бывшей здесь упрощённой модели:
    - `exclude_dirs` — префикс относительного пути каталога, а не имя
      каталога на любой глубине;
    - `exclude_patterns` — fnmatch по полному относительному пути;
    - скрытые файлы и каталоги пропускаются (`x.startswith('.')`).
    """
    dir_prefixes = [d.rstrip("/") + "/" for d in exclude_dirs]
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT).as_posix()
        parts = [] if rel == "." else rel.split("/")
        if any(part.startswith(".") for part in parts):
            continue
        filtered_root = (rel.lower() + "/") if rel != "." else ""
        if filtered_root:
            if any(filtered_root.startswith(prefix) for prefix in dir_prefixes):
                continue
            if any(fnmatch(filtered_root, pattern) for pattern in exclude_patterns):
                continue
        for name in filenames:
            if name.startswith("."):
                continue
            dfn = (filtered_root + name).lower()
            if any(fnmatch(dfn, pattern) for pattern in exclude_patterns):
                continue
            if Path(name).suffix.lstrip(".").lower() in extensions:
                found.append(dfn)
    return sorted(found)


def _top_level_dirs() -> dict[str, int]:
    counts: Counter[str] = Counter()
    for child in ROOT.iterdir():
        if not child.is_dir() or child.name == ".git":
            continue
        counts[child.name] = sum(1 for _ in child.rglob("*") if _.is_file())
    return dict(counts)


# ── Инцидент 1: удаление и игнорирование мусора ────────────────────────────

def test_deleted_prototype_dirs_are_really_gone():
    """git rm снимает файлы с индекса, но не гарантирует чистоту диска."""
    leftovers = [n for n in DELETED_PROTOTYPES if (ROOT / n).exists()]
    assert leftovers == [], f"Каталоги остались на диске: {leftovers}"


def test_deleted_prototype_dirs_stay_in_gitignore():
    """Повторная распаковка архива не должна вернуть мусор в индекс."""
    text = GITIGNORE.read_text(encoding="utf-8")
    for name in DELETED_PROTOTYPES:
        assert f"{name}/" in text, f"{name}/ отсутствует в .gitignore"


def test_ignore_rules_are_committed_not_local():
    """Раньше это жило только в .git/info/exclude и терялось при клоне."""
    text = GITIGNORE.read_text(encoding="utf-8")
    for rule in ("node_modules/", "*/node_modules/", ".slim/",
                 ".workbuddy-ai/memory/", "*.log", "*.db", "*.pyc"):
        assert rule in text, f"Правило {rule!r} не закоммичено в .gitignore"


def test_project_skills_are_not_hidden_by_gitignore():
    """6 проектных скиллов отслеживаются git — весь .workbuddy-ai/ игнорировать нельзя."""
    text = GITIGNORE.read_text(encoding="utf-8")
    assert not re.search(r"^\.workbuddy-ai/\s*$", text, re.M), (
        "Весь .workbuddy-ai/ игнорируется — новые скиллы не попадут в репозиторий"
    )


def test_no_prototype_names_in_build_config():
    """Исторические упоминания в docs/ допустимы, в конфиге сборки — нет."""
    *_, spec_text = _spec_parts()
    configs = [spec_text]
    wf_dir = ROOT / ".github" / "workflows"
    for wf in sorted(wf_dir.glob("*.yml")):
        configs.append(wf.read_text(encoding="utf-8"))
    for text in configs:
        for name in DELETED_PROTOTYPES:
            assert name not in text, f"Удалённый каталог {name} всё ещё в конфиге сборки"


# ── Инцидент 2: полнота source.exclude_dirs ────────────────────────────────

def test_live_junk_dirs_are_excluded():
    """Тот самый near-miss: живой каталог выкинули из исключений."""
    _, excludes, _, _ = _spec_parts()
    for name in LIVE_JUNK:
        if (ROOT / name).exists():
            assert name in excludes, (
                f"{name} существует, но отсутствует в source.exclude_dirs — "
                "содержимое уедет в APK"
            )


def test_large_dirs_are_either_excluded_or_known():
    """Любой новый каталог со >100 файлами обязан быть явно исключён."""
    _, excludes, _, _ = _spec_parts()
    offenders = [
        f"{name} ({count} файлов)"
        for name, count in _top_level_dirs().items()
        if count > 100 and name not in excludes and name not in PACKAGED_TOPLEVEL
    ]
    assert offenders == [], f"Крупные каталоги без исключения: {offenders}"


def test_no_dead_prototype_names_in_exclude_dirs():
    _, excludes, _, _ = _spec_parts()
    dead = set(DELETED_PROTOTYPES) & excludes
    assert not dead, f"Мёртвые имена в source.exclude_dirs: {sorted(dead)}"


def test_nested_node_modules_is_excluded_by_full_path():
    """exclude_dirs — префикс пути: basename вложенный каталог не исключает."""
    _, excludes, _, _ = _spec_parts()
    assert "mobile-teacher-app-redesign/node_modules" in excludes, (
        "Нужен полный путь: buildozer 1.6.0 сравнивает префикс относительного пути"
    )


# ── Инцидент 3: dev-инструменты и точный payload ───────────────────────────

def test_dev_only_files_are_not_packaged():
    for name in DEV_ONLY_FILES:
        assert name not in _included_files(*_spec_parts()[:3]), (
            f"{name} всё ещё уезжает в APK"
        )


def test_every_packaged_file_comes_from_known_dir():
    """Пересчёт реального payload: ничего лишнего по include_exts не едет."""
    files = _included_files(*_spec_parts()[:3])
    tops = {p.split("/")[0] if "/" in p else "" for p in files}
    unexpected = tops - PACKAGED_TOPLEVEL
    assert unexpected == set(), (
        f"Файлы едут из неизвестных каталогов: {sorted(unexpected)}"
    )


def test_no_excluded_dir_leaks_into_payload():
    _, excludes, _, _ = _spec_parts()
    prefixes = [d.rstrip("/") + "/" for d in excludes]
    for path in _included_files(*_spec_parts()[:3]):
        assert not any(path.startswith(prefix) for prefix in prefixes), (
            f"{path} попал в APK из исключённого каталога"
        )


def test_no_node_modules_in_payload():
    """Главный риск: зависимости фронта не должны раздувать APK."""
    leaked = [p for p in _included_files(*_spec_parts()[:3])
              if "node_modules" in p]
    assert leaked == [], f"node_modules уезжает в APK: {leaked[:5]}"


def test_frontend_bundle_is_packaged():
    """Канарейка: если исключить frontend целиком, APK станет пустым."""
    assert DIST_BUNDLE in _included_files(*_spec_parts()[:3]), (
        f"{DIST_BUNDLE} не попадает в APK"
    )


def test_no_personal_data_in_payload():
    leaked = [p for p in _included_files(*_spec_parts()[:3])
              if Path(p).suffix.lower() in {".db", ".db-wal", ".db-shm", ".db-journal"}]
    assert leaked == [], f"Персональные данные уезжают в APK: {leaked}"


def test_payload_size_stays_bounded():
    """Защита от тихого раздувания APK новым мусорным каталогом."""
    files = _included_files(*_spec_parts()[:3])
    assert len(files) <= 40, f"В APK уезжает {len(files)} файлов (ожидалось <= 40)"
