"use client";

import { useState } from "react";
import { ItineraryData } from "@/types/itinerary";

export interface LocationTarget {
  name?: string;
  placeId?: string;
  lat?: number | null;
  lng?: number | null;
}

/**
 * Sanitizes location input and generates a clean Google Maps Directions URL.
 * Prefers venue names & placeIds over raw coordinates to avoid dropped pins.
 */
export function buildDirectionsUrl(
  origin: string | LocationTarget | null | undefined,
  destination: string | LocationTarget | null | undefined
): string {
  const parseLocation = (
    loc: string | LocationTarget | null | undefined
  ): { val: string; placeId?: string } => {
    if (!loc) return { val: "" };

    if (typeof loc === "string") {
      const clean = loc.replace(/^(undefined|null)[,\s]*/i, "").trim();
      return { val: clean };
    }

    const cleanName = (loc.name || "").replace(/^(undefined|null)[,\s]*/i, "").trim();

    // Prefer venue name
    if (cleanName) {
      return { val: cleanName, placeId: loc.placeId };
    }

    // Fallback to coordinates
    if (loc.lat != null && loc.lng != null) {
      return { val: `${loc.lat},${loc.lng}`, placeId: loc.placeId };
    }

    return { val: "", placeId: loc.placeId };
  };

  const orig = parseLocation(origin);
  const dest = parseLocation(destination);

  // Fallback: If either location is missing OR origin equals destination,
  // open search view instead of attempting impossible transit directions
  if (!orig.val || !dest.val || orig.val.toLowerCase() === dest.val.toLowerCase()) {
    const fallbackTarget = dest.val || orig.val || "";
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(fallbackTarget)}`;
  }

  const params = new URLSearchParams({
    api: "1",
    travelmode: "transit",
    origin: orig.val,
    destination: dest.val,
  });

  if (orig.placeId) params.append("origin_place_id", orig.placeId);
  if (dest.placeId) params.append("destination_place_id", dest.placeId);

  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

/**
 * Generates a Google Maps Place URL using the venue name or Place ID.
 */
export function buildPlaceUrl(
  name: string,
  coords?: { lat: number | null; lng: number | null },
  placeId?: string
): string {
  const cleanName = (name || "").replace(/^(undefined|null)[,\s]*/i, "").trim();
  const encodedName = encodeURIComponent(cleanName);

  if (placeId) {
    return `https://www.google.com/maps/search/?api=1&query=${encodedName}&query_place_id=${placeId}`;
  }

  if (cleanName) {
    return `https://www.google.com/maps/search/?api=1&query=${encodedName}`;
  }

  if (coords?.lat && coords?.lng) {
    return `https://www.google.com/maps/search/?api=1&query=${coords.lat},${coords.lng}`;
  }

  return "https://www.google.com/maps";
}

interface ItineraryTimelineProps {
  itinerary: ItineraryData;
  activeStopNumber: number | null;
  onSelectStop: (stopNumber: number) => void;
}

export default function ItineraryTimeline({
  itinerary,
  activeStopNumber,
  onSelectStop,
}: ItineraryTimelineProps) {
  const [copied, setCopied] = useState(false);

  const handleCopySummary = () => {
    let text = `📍 ${itinerary.title || "Day Out Itinerary"}\n`;
    text += `Start: ${itinerary.start_location} @ ${itinerary.start_time}\n\n`;

    itinerary.stops?.forEach((stop, i) => {
      const num = stop.stop_number ?? i + 1;
      text += `Stop #${num}: ${stop.venue_name} (${stop.start_time} - ${stop.end_time})\n`;
    });

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const firstStop = itinerary.stops?.[0];

  return (
    <div className="space-y-6">
      {/* Title & Summary */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-2xl font-bold text-white">
            {itinerary.title || "Your Itinerary Plan"}
          </h2>
          <button
            type="button"
            onClick={handleCopySummary}
            className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs rounded-lg transition-colors font-medium shrink-0 print:hidden"
          >
            {copied ? "✓ Copied!" : "📋 Copy Summary"}
          </button>
        </div>
        <p className="text-slate-300 text-sm leading-relaxed">{itinerary.summary}</p>
      </div>

      {/* Timeline */}
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

          {/* INITIAL COMMUTE + DIRECTIONS BUTTON */}
          {itinerary.initial_transit && firstStop && (
            <div className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-4 ml-2 text-xs space-y-3 text-slate-300">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <span>🚍 COMMUTE TO STOP #1</span>
                  <span>({itinerary.initial_transit.commute_mins} mins)</span>
                </div>

                <a
                  href={buildDirectionsUrl(
                    itinerary.start_location,
                    {
                      name: firstStop.venue_name,
                      placeId: firstStop.place_id,
                      lat: firstStop.lat,
                      lng: firstStop.lng,
                    }
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-md font-medium transition-colors print:hidden"
                >
                  🗺️ Get Directions ↗
                </a>
              </div>
              <p className="font-mono whitespace-pre-line text-slate-300 leading-relaxed">
                {itinerary.initial_transit.step_by_step}
              </p>
            </div>
          )}
        </div>

        {/* ITINERARY STOPS */}
        {(itinerary.stops || []).map((stop, index) => {
          const stopNum = stop.stop_number ?? index + 1;
          const isSelected = activeStopNumber === stopNum;
          const nextStop = itinerary.stops[index + 1];

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

                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-lg font-bold text-white">{stop.venue_name}</h3>

                  {/* OPEN RICH PLACE CARD IN GOOGLE MAPS */}
                  <a
                    href={buildPlaceUrl(
                      stop.venue_name,
                      { lat: stop.lat, lng: stop.lng },
                      stop.place_id
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()} // Prevents toggling card selection
                    className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 shrink-0 print:hidden"
                  >
                    📍 View Place ↗
                  </a>
                </div>

                <p className="text-slate-300 text-sm leading-relaxed">{stop.why_go}</p>
              </div>

              {/* COMMUTE TO NEXT STOP + DIRECTIONS BUTTON */}
              {stop.transit_to_next && nextStop && (
                <div className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-4 ml-2 text-xs space-y-3 text-slate-300">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                      <span>🚍 COMMUTE TO STOP #{stopNum + 1}</span>
                      <span>({stop.transit_to_next.commute_mins} mins)</span>
                    </div>

                    <a
                      href={buildDirectionsUrl(
                        {
                          name: stop.venue_name,
                          placeId: stop.place_id,
                          lat: stop.lat,
                          lng: stop.lng,
                        },
                        {
                          name: nextStop.venue_name,
                          placeId: nextStop.place_id,
                          lat: nextStop.lat,
                          lng: nextStop.lng,
                        }
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-md font-medium transition-colors print:hidden"
                    >
                      🗺️ Get Directions ↗
                    </a>
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