// A classic bundle for Android 7's original Chromium WebView.
// Build: node scripts/build-legacy.mjs
import "core-js/es/global-this";
import "core-js/es/object/assign";
import "core-js/es/object/entries";
import "core-js/es/object/values";
import "core-js/es/object/from-entries";
import "core-js/es/array/includes";
import "core-js/es/array/flat";
import "core-js/es/string/pad-start";
import "core-js/es/promise/finally";
import "core-js/web/queue-microtask";
import { createRoot } from "react-dom/client";
import App from "./App";
createRoot(document.getElementById("root")!).render(<App />);
