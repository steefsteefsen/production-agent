import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import Presentation from "./presentation/Presentation.tsx";
import ApprovalPage from "./components/ApprovalPage.tsx";
import "./index.css";

// Eine App, drei Einstiege über den Pfad (Vite-SPA-Fallback liefert für alle index.html):
//   /presentation → geführter Interview-Walkthrough (auch per iframe im Ops-Cockpit)
//   /freigabe     → eigenständige Freigabe-Seite (Konfidenzbalken, Policy-Badges, Belegtext)
//   sonst         → internes Tab-Cockpit
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
      <App />
    )}
  </React.StrictMode>
);
