"use client";

interface ItineraryTimelineProps {
  itinerary: any;
  activeStopNumber: number | null;
  onSelectStop: (stopNumber: number) => void;
}

export default function ItineraryTimeline({
  itinerary,
  activeStopNumber,
  onSelectStop,
}: ItineraryTimelineProps) {
  return (
    <div className="space-y-6">
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 space-y-2">
        <h2 className="text-2xl font-bold text-white">
          {itinerary.title || "Your Itinerary Plan"}
        </h2>
        <p className="text-slate-300 text-sm leading-relaxed">{itinerary.summary}</p>
      </div>

      <div className="relative pl-6 border-l-2 border-emerald-500/30 space-y-8">
        {/* START LOCATION */}
        <div className="relative space-y-4">
          <div className="absolute -left-[31px] top-4 w-4 h-4 rounded-full bg-blue-500 ring-4 ring-slate-900" />

          <div className="bg-slate-800/90 border border-blue-500/40 rounded-xl p-4 space-y-1">
            <div className="flex items-center justify-between text-xs font-semibold text-blue-400">
              <span>🚩 STARTING POINT</span>
              <span className="font-mono text-slate-400">⏰ Depart at {itinerary.start_time}</span>
            </div>
            <h3 className="text-base font-bold text-white">{itinerary.start_location}</h3>
          </div>

          {itinerary.initial_transit && (
            <div className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-4 ml-2 text-xs space-y-2 text-slate-300">
              <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                <span>🚍 COMMUTE TO STOP #1</span>
                <span>({itinerary.initial_transit.commute_mins} mins)</span>
              </div>
              <p className="font-mono whitespace-pre-line text-slate-300 leading-relaxed">
                {itinerary.initial_transit.step_by_step}
              </p>
            </div>
          )}
        </div>

        {/* ITINERARY STOPS */}
        {(itinerary.stops || []).map((stop: any, index: number) => {
          const stopNum = stop.stop_number ?? index + 1;
          const isSelected = activeStopNumber === stopNum;

          return (
            <div key={`stop-${stopNum}-${index}`} className="relative space-y-4">
              <div
                className={`absolute -left-[31px] top-4 w-4 h-4 rounded-full ring-4 transition-all ${
                  isSelected
                    ? "bg-emerald-400 ring-emerald-400/50 scale-125"
                    : "bg-emerald-500 ring-slate-900"
                }`}
              />

              <div
                id={`stop-card-${stopNum}`}
                onClick={() => onSelectStop(stopNum)}
                className={`cursor-pointer transition-all duration-300 rounded-xl p-5 space-y-3 shadow-lg border ${
                  isSelected
                    ? "bg-slate-800 ring-2 ring-emerald-400 border-emerald-500/80 shadow-emerald-500/10 scale-[1.01]"
                    : "bg-slate-800 border-slate-700 hover:border-slate-500"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span
                    className={`text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md border transition-colors ${
                      isSelected
                        ? "bg-emerald-500 text-slate-950 border-emerald-400 font-bold"
                        : "text-emerald-400 bg-emerald-950/60 border-emerald-800/50"
                    }`}
                  >
                    Stop #{stopNum}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    ⏰ {stop.start_time} – {stop.end_time} (
                    {stop.duration_mins || stop.stay_duration_mins} mins)
                  </span>
                </div>

                <h3 className="text-lg font-bold text-white">{stop.venue_name}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{stop.why_go}</p>
              </div>

              {stop.transit_to_next && (
                <div className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-4 ml-2 text-xs space-y-2 text-slate-300">
                  <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                    <span>🚍 COMMUTE</span>
                    <span>({stop.transit_to_next.commute_mins} mins)</span>
                  </div>
                  <p className="font-mono whitespace-pre-line text-slate-300 leading-relaxed">
                    {stop.transit_to_next.step_by_step}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}