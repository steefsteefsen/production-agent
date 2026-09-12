import { useState } from "react";
import LiveMES from "./components/LiveMES.tsx";
import Medallion from "./components/Medallion.tsx";
import Agent from "./components/Agent.tsx";
import Status from "./components/Status.tsx";

type Tab = "Live-MES" | "Medallion" | "Agent" | "Status";
const TABS: Tab[] = ["Live-MES", "Medallion", "Agent", "Status"];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Live-MES");

  return (
    <div className="min-h-screen flex flex-col">
      {/* Kopfzeile */}
      <header className="bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center gap-6">
        <span className="text-teal-600 font-bold text-base tracking-wide">
          Production Agent
        </span>
        <span className="text-gray-400 text-xs">Verpackungslinie L1 · Werk Nord</span>
      </header>

      {/* Tab-Leiste */}
      <nav className="bg-gray-900 border-b border-gray-700 px-6 flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={[
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              activeTab === tab
                ? "border-teal-600 text-teal-500"
                : "border-transparent text-gray-400 hover:text-gray-200",
            ].join(" ")}
          >
            {tab}
          </button>
        ))}
      </nav>

      {/* Inhalt */}
      <main className="flex-1 p-6">
        {activeTab === "Live-MES" && <LiveMES />}
        {activeTab === "Medallion" && <Medallion />}
        {activeTab === "Agent" && <Agent />}
        {activeTab === "Status" && <Status />}
      </main>
    </div>
  );
}
