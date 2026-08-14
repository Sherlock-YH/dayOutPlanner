"use client";

import { useEffect, useRef, useState } from "react";
import { Loader } from "@googlemaps/js-api-loader";

export interface LocationPoint {
  name: string;
  lat: number;
  lng: number;
}

export interface StopPoint {
  stop_number?: number;
  venue_name: string;
  lat: number | null;
  lng: number | null;
}

interface ItineraryMapProps {
  startLocation?: LocationPoint;
  stops: StopPoint[];
  activeStopNumber: number | null;
  onSelectStop: (stopNumber: number) => void;
}

export default function ItineraryMap({
  startLocation,
  stops,
  activeStopNumber,
  onSelectStop,
}: ItineraryMapProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<Map<string | number, google.maps.marker.AdvancedMarkerElement>>(new Map());
  const polylineRef = useRef<google.maps.Polyline | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);

  // 1. INITIALIZE GOOGLE MAP INSTANCE (Runs ONCE)
  useEffect(() => {
    const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "";
    if (!apiKey) return;

    const loader = new Loader({
      apiKey,
      version: "weekly",
      libraries: ["places", "marker"],
    });

    loader.load().then(async () => {
      if (!mapRef.current || mapInstanceRef.current) return;

      const { Map } = (await google.maps.importLibrary("maps")) as google.maps.MapsLibrary;

      mapInstanceRef.current = new Map(mapRef.current, {
        center: { lat: 1.3521, lng: 103.8198 },
        zoom: 12,
        mapId: process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
        disableDefaultUI: false,
        zoomControl: true,
      });

      setIsMapReady(true);
    });
  }, []);

  // 2. DRAW MARKERS & POLYLINES (Runs when location data changes)
  useEffect(() => {
    if (!isMapReady || !mapInstanceRef.current) return;

    const map = mapInstanceRef.current;

    const updateMapElements = async () => {
      const { AdvancedMarkerElement, PinElement } = (await google.maps.importLibrary(
        "marker"
      )) as google.maps.MarkerLibrary;

      // Clear existing markers & polylines
      markersRef.current.forEach((marker) => (marker.map = null));
      markersRef.current.clear();

      if (polylineRef.current) {
        polylineRef.current.setMap(null);
      }

      const bounds = new google.maps.LatLngBounds();
      const pathCoordinates: google.maps.LatLngLiteral[] = [];

      // Add Start Location Marker
      if (startLocation?.lat && startLocation?.lng) {
        const startPos = { lat: startLocation.lat, lng: startLocation.lng };
        bounds.extend(startPos);
        pathCoordinates.push(startPos);

        const startPin = new PinElement({
          background: "#3b82f6",
          borderColor: "#1d4ed8",
          glyphColor: "#ffffff",
          glyph: "🚩",
          scale: 1.1,
        });

        const startMarker = new AdvancedMarkerElement({
          map,
          position: startPos,
          title: `Start: ${startLocation.name}`,
          content: startPin.element,
        });

        markersRef.current.set("start", startMarker);
      }

      // Add Itinerary Stop Markers
      stops.forEach((stop, index) => {
        if (stop.lat && stop.lng) {
          const stopNum = stop.stop_number ?? index + 1;
          const pos = { lat: stop.lat, lng: stop.lng };
          const isSelected = activeStopNumber === stopNum;

          bounds.extend(pos);
          pathCoordinates.push(pos);

          const pin = new PinElement({
            background: isSelected ? "#10b981" : "#0f766e",
            borderColor: isSelected ? "#34d399" : "#115e59",
            glyphColor: "#ffffff",
            glyph: `${stopNum}`,
            scale: isSelected ? 1.3 : 1.0,
          });

          const marker = new AdvancedMarkerElement({
            map,
            position: pos,
            title: `Stop #${stopNum}: ${stop.venue_name}`,
            content: pin.element,
            zIndex: isSelected ? 1000 : stopNum,
          });

          marker.addListener("click", () => onSelectStop(stopNum));
          markersRef.current.set(stopNum, marker);
        }
      });

      // Draw Polyline Route
      if (pathCoordinates.length > 1) {
        polylineRef.current = new google.maps.Polyline({
          path: pathCoordinates,
          geodesic: true,
          strokeColor: "#10b981",
          strokeOpacity: 0.8,
          strokeWeight: 4,
          map,
        });
      }

      // Fit bounds initial render
      if (!bounds.isEmpty() && activeStopNumber === null) {
        map.fitBounds(bounds, { top: 60, bottom: 60, left: 60, right: 60 });
      }
    };

    updateMapElements();
  }, [isMapReady, startLocation, stops]);

  // 3. SMOOTH PAN TO ACTIVE STOP (Runs when activeStopNumber changes)
  useEffect(() => {
    if (!isMapReady || !mapInstanceRef.current || activeStopNumber === null) return;

    const map = mapInstanceRef.current;

    if (activeStopNumber === 0 && startLocation?.lat && startLocation?.lng) {
      map.panTo({ lat: startLocation.lat, lng: startLocation.lng });
      return;
    }

    const activeStop = stops.find(
      (s, i) => (s.stop_number ?? i + 1) === activeStopNumber
    );

    if (activeStop?.lat && activeStop?.lng) {
      map.panTo({ lat: activeStop.lat, lng: activeStop.lng });
      if (map.getZoom()! < 14) map.setZoom(14);
    }
  }, [activeStopNumber, isMapReady, stops, startLocation]);

  return (
    <div className="relative w-full h-full min-h-[400px] rounded-2xl overflow-hidden border border-slate-700 shadow-2xl">
      <div ref={mapRef} className="w-full h-full" />
    </div>
  );
}