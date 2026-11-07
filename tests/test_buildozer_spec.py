"""Регрессионные проверки гигиены рабочего дерева и сборки APK.

Два инцидента, которые закрывают эти тесты:

1. `git rm -r` снял файлы с индекса, но оставил на диске каталоги с
   untracked-содержимым (node_modules) — 18 499 файлов, ~380 МБ. Корень:
   правила игнорирования жили в локальном `.git/info/exclude` и терялись
   при клоне. Теперь они обязаны быть в коммитящемся `.gitignore`.
2. Чистка `buildozer.spec` чуть не выбросила из `source.exclude_dirs`
   живые каталоги (`website-redesign-figma-files` — 2888 файлов). Список
   исключений нельзя править «на глаз» — нужно пересчитывать, что реально
   уезжает в APK по `source.include_exts`.
"""
from __future__ import annotations

import os
import re
from collections import Counter
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

# Живые каталоги, которые НЕ должны попадать в APK.
LIVE_JUNK = (
    "website-redesign-figma-files",
    "visual-redesign-of-tech-project",
    ".slim",
    ".workbuddy-ai",
)

# Каталоги верхнего уровня, из которых файлы осознанно едут в APK.
# '' — файлы в корне проекта (api.py, main.py, иконки, ...).
PACKAGED_TOPLEVEL = {"", "mobile-teacher-app-redesign", "src"}

DIST_BUNDLE = "mobile-teacher-app-redesign/dist/index.html"


def _spec_parts() -> tuple[set[str], set[str], str]:
    text = SPEC.read_text(encoding="utf-8")
    exts = re.search(r"^source\.include_exts\s*=\s*(.+)$", text, re.M)
    excl = re.search(r"^source\.exclude_dirs\s*=\s*(.+)$", text, re.M)
    assert exts, "source.include_exts не найден в buildozer.spec"
    assert excl, "source.exclude_dirs не найден в buildozer.spec"
    extensions = {e.strip().lower() for e in exts.group(1).split(",") if e.strip()}
    excludes = {e.strip() for e in excl.group(1).split(",") if e.strip()}
    assert extensions and excludes
    return extensions, excludes, text


def _included_files(extensions: set[str], excludes: set[str]) -> list[str]:
    """Эмуляция отбора файлов buildozer: exclude_dirs матчится по имени
    каталога на любой глубине, include_exts — по расширению файла."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT)
        if rel.parts and rel.parts[0] == ".git":
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d != ".git" and d not in excludes]
        for name in filenames:
            if Path(name).suffix.lstrip(".").lower() in extensions:
                path = (rel / name) if str(rel) != "." else Path(name)
                found.append(path.as_posix())
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
    """6 проектных скиллов отслеживаются git — весь .workbuddy-ai/ ignорировать нельзя."""
    text = GITIGNORE.read_text(encoding="utf-8")
    assert ".workbuddy-ai/\n" not in text and not re.search(
        r"^\.workbuddy-ai/\s*$", text, re.M
    ), "Весь .workbuddy-ai/ игнорируется — новые скиллы не попадут в репозиторий"


def test_no_prototype_names_in_build_config():
    """Исторические упоминания в docs/ допустимы, в конфиге сборки — нет."""
    _, _, spec_text = _spec_parts()
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
    _, excludes, _ = _spec_parts()
    for name in LIVE_JUNK:
        if (ROOT / name).exists():
            assert name in excludes, (
                f"{name} существует, но отсутствует в source.exclude_dirs — "
                "содержимое уедет в APK"
            )


def test_large_dirs_are_either_excluded_or_known():
    """Любой новый каталог со >100 файлами обязан быть явно исключён."""
    _, excludes, _ = _spec_parts()
    offenders = [
        f"{name} ({count} файлов)"
        for name, count in _top_level_dirs().items()
        if count > 100 and name not in excludes and name not in PACKAGED_TOPLEVEL
    ]
    assert offenders == [], f"Крупные каталоги без исключения: {offenders}"


def test_no_dead_prototype_names_in_exclude_dirs():
    _, excludes, _ = _spec_parts()
    dead = set(DELETED_PROTOTYPES) & excludes
    assert not dead, f"Мёртвые имена в source.exclude_dirs: {sorted(dead)}"


def test_every_packaged_file_comes_from_known_dir():
    """Пересчёт реального payload: ничего лишнего по include_exts не едет."""
    extensions, excludes, _ = _spec_parts()
    files = _included_files(extensions, excludes)
    tops = {p.split("/")[0] if "/" in p else "" for p in files}
    unexpected = tops - PACKAGED_TOPLEVEL
    assert unexpected == set(), (
        f"Файлы едут из неизвестных каталогов: {sorted(unexpected)}"
    )


def test_no_excluded_dir_leaks_into_payload():
    extensions, excludes, _ = _spec_parts()
    for path in _included_files(extensions, excludes):
        parts = Path(path).parts[:-1]
        assert not (set(parts) & excludes), f"{path} попал в APK из исключённого каталога"


def test_frontend_bundle_is_packaged():
    """Канарейка: если исключить frontend целиком, APK станет пустым."""
    extensions, excludes, _ = _spec_parts()
    assert DIST_BUNDLE in _included_files(extensions, excludes), (
        f"{DIST_BUNDLE} не попадает в APK"
    )


def test_no_personal_data_in_payload():
    extensions, excludes, _ = _spec_parts()
    leaked = [p for p in _included_files(extensions, excludes)
              if Path(p).suffix.lower() in {".db", ".db-wal", ".db-shm", ".db-journal"}]
    assert leaked == [], f"Персональные данные уезжают в APK: {leaked}"


def test_payload_size_stays_bounded():
    """Защита от тихого раздувания APK новым мусорным каталогом."""
    extensions, excludes, _ = _spec_parts()
    files = _included_files(extensions, excludes)
    assert len(files) <= 60, f"В APK уезжает {len(files)} файлов (ожидалось <= 60)"
