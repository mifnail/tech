/**
 * Platform detection — frontend-only gate for APK updater on iOS.
 * Phase 2: не трогаем бэкенд .py, всё решается фронтом.
 * iOS = iPhone/iPad/iPod или iPadOS 13+ (MacIntel + touch).
 * Также детектим Toga/WKWebView по характерным признакам.
 */

export function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  try {
    const ua = navigator.userAgent || "";
    if (/iPad|iPhone|iPod/.test(ua)) return true;
    // iPadOS 13+ reports as MacIntel but has touch
    const platform = (navigator as any).platform || "";
    const maxTouch = (navigator as any).maxTouchPoints || 0;
    if (platform === "MacIntel" && maxTouch > 1) return true;
    // Standalone WKWebView on iOS sometimes has "AppleWebKit" without the above
    // Fallback: check for iOS-specific touch + webkit
    if (/Mac OS X/.test(ua) && maxTouch > 1) return true;
    return false;
  } catch (_) {
    return false;
  }
}

export function isAndroid(): boolean {
  if (typeof navigator === "undefined") return false;
  try {
    const ua = navigator.userAgent || "";
    return /Android/.test(ua);
  } catch (_) {
    return false;
  }
}

/** APK updater доступен только на Android. На iOS — гейтим (TestFlight/App Store). */
export function isApkUpdaterAvailable(): boolean {
  // Явно выключаем на iOS; на остальных (Android, desktop) — доступен
  // (desktop просто вернет 400 от /api/update/download, но UI покажем для консистентности)
  return !isIOS();
}
