import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import "./refinements.css";
import App from "./App";

if (
  !(window as Window & { __teachHelperLegacy?: boolean }).__teachHelperLegacy
) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
