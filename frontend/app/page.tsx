"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";
import AuthCard from "@/components/AuthCard";
import PlannerForm from "@/components/PlannerForm";
import ItineraryTimeline from "@/components/ItineraryTimeline";
import ItineraryMap from "@/components/ItineraryMap";

// Fallback to production API and sanitize trailing slashes
const RAW_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://dayoutplanner.up.railway.app";
const API_BASE = RAW_API_BASE.replace(/\/$/, "");

export default function Home() {
  // Auth State
  const [token, setToken] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  // App Input States
  const [prompt, setPrompt] = useState("");
  const [startLocation, setStartLocation] = useState("");
  const [startTime, setStartTime] = useState("10:00");
  const [selectedChips, setSelectedChips] = useState<string[]>([]);

  // UI & Data States
  const [loading, setLoading] = useState(false);
  const [itinerary, setItinerary] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStopNumber, setActiveStopNumber] = useState<number | null>(null);

  // Restore saved auth token on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    if (savedToken) {
      setToken(savedToken);
    }
    setIsInitializing(false);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setItinerary(null);
    setError(null);
    setActiveStopNumber(null);
  };

  const handleSelectStop = (stopNumber: number) => {
    setActiveStopNumber(stopNumber);
    if (!stopNumber) return;

    const cardElement = document.getElementById(`stop-card-${stopNumber}`);
    if (cardElement) {
      cardElement.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    const fullPromptParts = [prompt.trim(), ...selectedChips].filter(Boolean);
    const finalPrompt = fullPromptParts.join(", ");

    if (!finalPrompt.trim()) return;

    setLoading(true);
    setError(null);
    setActiveStopNumber(null);

    try {
      const response = await fetch(`${API_BASE}/api/plan`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          prompt: finalPrompt,
          start_location: startLocation.trim(),
          start_time: startTime,
        }),
      });

      if (response.status === 401) {
        handleLogout();
        throw new Error("Session expired. Please log in again.");
      }

      const contentType = response.headers.get("content-type");
      let data: any = {};
      if (contentType && contentType.includes("application/json")) {
        data = await response.json();
      }

      if (!response.ok) {
        throw new Error(data?.detail || `Error ${response.status}`);
      }

      setItinerary(data);
    } catch (err: any) {
      setError(err.message || "Unable to connect to planner backend.");
    } finally {
      setLoading(false);
    }
  };

  // Prevent UI flash during local storage check
  if (isInitializing) {
    return (
      <main className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-slate-400 text-sm animate-pulse">
          Loading Planner...
        </div>
      </main>
    );
  }

  // VIEW 1: AUTHENTICATION SCREEN
  if (!token) {
    return (
      <AuthCard
        apiBase={API_BASE}
        onAuthSuccess={(newToken) => setToken(newToken)}
      />
    );
  }

  // VIEW 2: MAIN PLANNER DASHBOARD
  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Header onLogout={handleLogout} />

        <PlannerForm
          prompt={prompt}
          setPrompt={setPrompt}
          startLocation={startLocation}
          setStartLocation={setStartLocation}
          startTime={startTime}
          setStartTime={setStartTime}
          selectedChips={selectedChips}
          setSelectedChips={setSelectedChips}
          loading={loading}
          onSubmit={handleGenerate}
        />

        {error && (
          <div className="p-4 bg-red-900/40 border border-red-700 rounded-xl text-red-200 text-sm max-w-2xl mx-auto text-left">
            ⚠️ {error}
          </div>
        )}

        {itinerary && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start pt-4 text-left">
            <div className="lg:col-span-7">
              <ItineraryTimeline
                itinerary={itinerary}
                activeStopNumber={activeStopNumber}
                onSelectStop={handleSelectStop}
              />
            </div>

            <div className="lg:col-span-5 lg:sticky lg:top-8 h-[500px] lg:h-[calc(100vh-4rem)]">
              <ItineraryMap
                startLocation={
                  itinerary?.initial_transit?.start_coords
                    ? {
                        name: itinerary.start_location,
                        lat: itinerary.initial_transit.start_coords.lat,
                        lng: itinerary.initial_transit.start_coords.lng,
                      }
                    : undefined
                }
                stops={itinerary?.stops || []}
                activeStopNumber={activeStopNumber}
                onSelectStop={handleSelectStop}
              />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}