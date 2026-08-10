"use client";

interface HeaderProps {
  onLogout: () => void;
}

export default function Header({ onLogout }: HeaderProps) {
  return (
    <header className="grid grid-cols-1 md:grid-cols-3 items-center border-b border-slate-800 pb-4 gap-4">
      {/* Spacer for symmetrical 3-column centering */}
      <div className="hidden md:block"></div>

      {/* Centered App Title & Subtitle */}
      <div className="text-center space-y-1">
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-emerald-400">
          🇸🇬 One Day Out Planner
        </h1>
        <p className="text-slate-400 text-xs sm:text-sm">
          AI Travel Orchestrator powered by GPT-4o & Google Maps
        </p>
      </div>

      {/* Top-Right Logout Button */}
      <div className="flex justify-center md:justify-end">
        <button
          onClick={onLogout}
          className="text-xs px-4 py-2 border border-slate-700 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
        >
          Log Out
        </button>
      </div>
    </header>
  );
}