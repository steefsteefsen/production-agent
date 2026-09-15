import React from "react";
import ReactDOM from "react-dom/client";
import Presentation from "./presentation/Presentation.tsx";
import ApprovalPage from "./components/ApprovalPage.tsx";
import Cockpit from "./Cockpit.tsx";
import "./index.css";

// Eine App, mehrere Einstiege über den Pfad (Vite-SPA-Fallback liefert für alle index.html):
//   /presentation → geführter Interview-Walkthrough (auch per iframe im Ops-Cockpit)
//   /freigabe     → eigenständige Freigabe-Seite (Konfidenzbalken, Policy-Badges, Belegtext)
//   sonst         → Sechs-Tab-Cockpit (Bediener, Live-Daten, MCP, RAG, Sicherheit, Konfiguration)
const path = window.location.pathname.replace(/\/+$/, "");
const route = path.endsWith("/presentation")
  ? "presentation"
  : path.endsWith("/freigabe")
    ? "freigabe"
    : "cockpit";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {route === "presentation" ? (
      <Presentation />
    ) : route === "freigabe" ? (
      <ApprovalPage />
    ) : (
      <Cockpit />
    )}
  </React.StrictMode>
);
