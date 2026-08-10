"use client";

import LocationAutocomplete from "@/components/LocationAutocomplete";

const TIME_OPTIONS = (() => {
  const options = [];
  for (let hour = 0; hour < 24; hour++) {
    for (let min = 0; min < 60; min += 30) {
      const hStr = hour.toString().padStart(2, "0");
      const mStr = min.toString().padStart(2, "0");
      const value = `${hStr}:${mStr}`;

      const period = hour >= 12 ? "PM" : "AM";
      const displayHour = hour % 12 === 0 ? 12 : hour % 12;
      const label = `${displayHour}:${mStr} ${period}`;

      options.push({ value, label });
    }
  }
  return options;
})();

const QUICK_CHIP_GROUPS = [
  {
    category: "Pace",
    chips: ["Relaxed (1-2 stops)", "Moderate(3-4)", "Packed (5+ stops)"],
  },
  {
    category: "Diet",
    chips: ["Halal", "Vegetarian", "Hawker Only", "Meat Lover", "No Food"],
  },
  {
    category: "Style",
    chips: ["Air-Conditioned / Indoor", "Outdoor & Nature", "Family Friendly", "Pet Friendly"],
  },
];

interface PlannerFormProps {
  prompt: string;
  setPrompt: (value: string) => void;
  startLocation: string;
  setStartLocation: (value: string) => void;
  startTime: string;
  setStartTime: (value: string) => void;
  selectedChips: string[];
  setSelectedChips: React.Dispatch<React.SetStateAction<string[]>>;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export default function PlannerForm({
  prompt,
  setPrompt,
  startLocation,
  setStartLocation,
  startTime,
  setStartTime,
  selectedChips,
  setSelectedChips,
  loading,
  onSubmit,
}: PlannerFormProps) {
  const toggleChip = (chip: string) => {
    setSelectedChips((prev) =>
      prev.includes(chip) ? prev.filter((c) => c !== chip) : [...prev, chip]
    );
  };

  return (
    <form
      onSubmit={onSubmit}
      className="bg-slate-800/80 border border-slate-700 rounded-2xl p-5 space-y-5 shadow-xl max-w-3xl mx-auto"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Start Location Input */}
        <div className="space-y-1.5 text-left">
          <label className="text-xs font-semibold text-slate-400">📍 Start Location</label>
          <LocationAutocomplete
            value={startLocation}
            onChange={setStartLocation}
            placeholder="e.g. Marina Bay Sands, Changi Airport..."
            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none"
          />
        </div>

        {/* Start Time Dropdown */}
        <div className="space-y-1.5 text-left">
          <label className="text-xs font-semibold text-slate-400">⏰ Start Time</label>
          <div className="relative">
            <select
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none appearance-none cursor-pointer"
            >
              {TIME_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 text-xs">
              ▼
            </div>
          </div>
        </div>
      </div>

      {/* Quick-Chips */}
      <div className="space-y-3 pt-2 border-t border-slate-700/60 text-left">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400">
            🎛️ Quick Filters & Pace Presets
          </span>
          {selectedChips.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedChips([])}
              className="text-xs text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer"
            >
              Clear filters ({selectedChips.length})
            </button>
          )}
        </div>

        <div className="space-y-2">
          {QUICK_CHIP_GROUPS.map((group) => (
            <div key={group.category} className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-slate-400 min-w-[45px]">
                {group.category}:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {group.chips.map((chip) => {
                  const isSelected = selectedChips.includes(chip);
                  return (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => toggleChip(chip)}
                      className={`text-xs px-3 py-1.5 rounded-lg border transition-all font-medium cursor-pointer ${
                        isSelected
                          ? "bg-emerald-500/20 border-emerald-500 text-emerald-300 ring-1 ring-emerald-500/50"
                          : "bg-slate-900/60 border-slate-700 text-slate-300 hover:border-slate-500 hover:bg-slate-800"
                      }`}
                    >
                      {isSelected && <span className="mr-1 text-emerald-400">✓</span>}
                      {chip}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Prompt Input */}
      <div className="space-y-1.5 text-left pt-1">
        <label className="text-xs font-semibold text-slate-400">🎯 Trip Theme & Preferences</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Family-friendly indoor tour with local coffee..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-emerald-500 hover:bg-emerald-600 font-bold text-slate-950 px-6 py-3 rounded-xl transition-all disabled:opacity-50 text-sm whitespace-nowrap cursor-pointer shadow-lg shadow-emerald-500/10"
          >
            {loading ? "Planning..." : "Generate Plan"}
          </button>
        </div>
      </div>
    </form>
  );
}