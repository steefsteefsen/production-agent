import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import Presentation from "./presentation/Presentation.tsx";
import "./index.css";

// Eine App, zwei Einstiege: /presentation (geführter Interview-Walkthrough, auch per iframe im
// Ops-Cockpit) vs. das interne Tab-Cockpit. Vite-SPA-Fallback liefert für beide Pfade index.html.
const isPresentation = window.location.pathname.replace(/\/+$/, "").endsWith("/presentation");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isPresentation ? <Presentation /> : <App />}
  </React.StrictMode>
);
