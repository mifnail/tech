"""Phase 2 — иконки, версия сборки, гейт APK-апдейта на iOS (только фронт/конфиги/CI)."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_icons_exist_and_sizes():
    p512 = ROOT / "icon-512.png"
    p1024 = ROOT / "icon-1024.png"
    assert p512.exists(), "icon-512.png missing"
    assert p1024.exists(), "icon-1024.png missing (Phase 2)"
    pytest.importorskip("PIL", reason="Pillow required for icon size checks")
    from PIL import Image

    im512 = Image.open(p512)
    im1024 = Image.open(p1024)
    assert im512.size == (512, 512), f"512 size {im512.size}"
    assert im1024.size == (1024, 1024), f"1024 App Store {im1024.size}"
    assert im512.mode in ("RGBA", "RGB")
    assert im1024.mode in ("RGBA", "RGB")


def test_pyproject_icon_and_ats():
    t = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'icon = "icon-1024.png"' in t or "icon = 'icon-1024.png'" in t, "icon config missing"
    assert "NSAllowsLocalNetworking" in t, "ATS NSAllowsLocalNetworking missing"
    assert 'bundle = "com.teachhelper4"' in t
    assert 'project_name = "TeachHelper"' in t


def test_pyproject_version_sync():
    t = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Both [project] and [tool.briefcase] version must exist
    assert re.search(r'^\[project\][^\[]*?^version\s*=\s*"', t, re.M | re.S)
    assert re.search(r'^\[tool\.briefcase\][^\[]*?^version\s*=\s*"', t, re.M | re.S)
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.match(r"^\d+\.\d+", ver), f"VERSION bad {ver!r}"


def test_build_ios_workflow_phase2():
    yml = (ROOT / ".github" / "workflows" / "build-ios.yml").read_text(encoding="utf-8")
    assert "Phase 2" in yml, "workflow not updated to Phase 2"
    assert "Set version from run number" in yml
    assert "Validate icons" in yml
    assert "Validate iOS gate in frontend" in yml
    assert "icon-1024.png" in yml
    assert "platform.ts" in yml
    assert "TestFlight" in yml or "isIOS" in yml
    assert "TeachHelper-${VER}-unsigned.ipa" in yml or "TeachHelper-" in yml
    # Phase 2 workflow must be iOS-only (macos), not touching Android buildozer
    assert "runs-on: macos" in yml
    assert "briefcase" in yml.lower()


def test_platform_helper_exists():
    p = ROOT / "mobile-teacher-app-redesign" / "src" / "lib" / "platform.ts"
    assert p.exists(), "platform.ts missing"
    t = p.read_text(encoding="utf-8")
    assert "function isIOS" in t
    assert "isApkUpdaterAvailable" in t
    assert "iPad|iPhone|iPod" in t
    assert "MacIntel" in t


def test_update_banner_gated():
    p = ROOT / "mobile-teacher-app-redesign" / "src" / "components" / "UpdateBanner.tsx"
    t = p.read_text(encoding="utf-8")
    assert "isIOS" in t, "UpdateBanner iOS gate missing"
    assert "isApkUpdaterAvailable" in t
    # Must not have early return before hooks (hooks must be unconditional)
    # Check that useState is before isIOS gate return
    assert t.index("useState") < t.index("if (isIOS()") or t.index("useEffect") < t.index("if (isIOS()")


def test_settings_gated():
    p = ROOT / "mobile-teacher-app-redesign" / "src" / "screens" / "Settings.tsx"
    t = p.read_text(encoding="utf-8")
    assert "isIOS" in t
    assert "TestFlight" in t, "Settings must show TestFlight on iOS"
    assert "isApkUpdaterAvailable" in t


def test_legacy_gate():
    p = ROOT / "static" / "app.js"
    t = p.read_text(encoding="utf-8", errors="ignore")
    assert "_isIOS" in t, "legacy _isIOS missing"
    assert "TestFlight" in t, "legacy must notify TestFlight on iOS"


def test_update_lib_gated():
    p = ROOT / "mobile-teacher-app-redesign" / "src" / "lib" / "update.ts"
    t = p.read_text(encoding="utf-8")
    assert "isIOS" in t
    assert "APK not available on iOS" in t


def test_dist_contains_gate():
    dist = ROOT / "mobile-teacher-app-redesign" / "dist" / "index.html"
    assert dist.exists(), "dist missing — run npm run build"
    t = dist.read_text(encoding="utf-8", errors="ignore")
    # After Phase 2, dist must contain gate string (TestFlight or isIOS) — vite singlefile inlines it
    assert ("TestFlight" in t) or ("isIOS" in t) or ("iPad" in t), "dist gate not found (rebuild dist?)"
    assert len(t) > 100000, "dist suspiciously small"


def test_android_pipeline_not_touched():
    # Loose check: build-apk.yml and buildozer.spec must not contain iOS Phase 2 markers
    apk_yml = (ROOT / ".github" / "workflows" / "build-apk.yml").read_text(encoding="utf-8")
    assert "TestFlight" not in apk_yml
    assert "icon-1024" not in apk_yml
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "icon-1024" not in spec
    assert "TestFlight" not in spec
