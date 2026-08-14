# gmaps_service.py
# -*- coding: utf-8 -*-
import os
import math
from datetime import datetime
import googlemaps
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY) if API_KEY else None


def haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculates straight-line distance in meters between two lat/lng points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def resolve_venue_location(venue_name: str) -> dict | None:
    """
    Geocodes a venue name using Google Places API to retrieve exact lat, lng, and place_id.
    Prevents ambiguous string matching in directions routing.
    """
    if not gmaps or not venue_name:
        return None

    try:
        # Search specifically within Singapore
        query = f"{venue_name}, Singapore"
        place_result = gmaps.find_place(
            input=query,
            input_type="textquery",
            fields=["name", "geometry", "place_id", "formatted_address"]
        )

        candidates = place_result.get("candidates", [])
        if candidates:
            best = candidates[0]
            loc = best["geometry"]["location"]
            return {
                "name": best.get("name", venue_name),
                "lat": loc["lat"],
                "lng": loc["lng"],
                "place_id": best.get("place_id"),
                "formatted_address": best.get("formatted_address", "")
            }
    except Exception as e:
        print(f"⚠️ Geocoding error for '{venue_name}': {e}")

    return None


def calculate_sg_taxi_fare(
    distance_meters: int,
    duration_seconds: int,
    departure_datetime: datetime | None = None
) -> dict:
    """
    Calculates estimated Singapore Taxi / Ride-Hailing (Grab/Gojek) fare range
    based on Google Maps driving distance and travel duration.
    """
    dist_km = distance_meters / 1000.0
    drive_mins = round(duration_seconds / 60)

    # 1. Flagdown Base (covers first 1.0 km)
    base_fare = 4.50

    # 2. Distance Fare Calculation
    distance_cost = 0.0
    if dist_km > 1.0:
        if dist_km <= 10.0:
            distance_cost = ((dist_km - 1.0) / 0.40) * 0.26
        else:
            tier1 = (9.0 / 0.40) * 0.26
            tier2 = ((dist_km - 10.0) / 0.35) * 0.26
            distance_cost = tier1 + tier2

    # 3. Time Fare Calculation (~$0.26 per 45 seconds)
    time_cost = (duration_seconds / 45.0) * 0.26
    subtotal = base_fare + distance_cost + time_cost

    # 4. Peak / Night Surcharges
    surcharge_multiplier = 1.0
    if departure_datetime:
        hour = departure_datetime.hour
        is_weekday = departure_datetime.weekday() < 5

        if 0 <= hour < 6:
            surcharge_multiplier = 1.50  # Late night +50%
        elif (is_weekday and 7 <= hour < 10) or (17 <= hour <= 23):
            surcharge_multiplier = 1.25  # Peak hours +25%

    estimated_fare = subtotal * surcharge_multiplier
    min_fare = max(6.0, round(estimated_fare))
    max_fare = round(min_fare * 1.30)

    return {
        "drive_mins": drive_mins,
        "min_fare_sgd": int(min_fare),
        "max_fare_sgd": int(max_fare),
        "formatted_estimate": f"~{drive_mins} mins (${int(min_fare)}-${int(max_fare)} SGD)",
    }


def get_driving_fallback(
    origin_target: str | dict,
    destination_target: str | dict,
    departure_datetime: datetime
) -> dict | None:
    """
    Queries Google Maps Directions API in DRIVING mode to calculate
    real driving duration and ride-hailing/taxi fare estimates.
    """
    if not gmaps:
        return None

    try:
        directions = gmaps.directions(
            origin=origin_target,
            destination=destination_target,
            mode="driving",
            departure_time=departure_datetime,
        )

        if not directions:
            return None

        leg = directions[0]["legs"][0]
        dist_m = leg["distance"]["value"]

        dur_s = (
            leg["duration_in_traffic"]["value"]
            if "duration_in_traffic" in leg
            else leg["duration"]["value"]
        )

        fare_data = calculate_sg_taxi_fare(
            distance_meters=dist_m,
            duration_seconds=dur_s,
            departure_datetime=departure_datetime,
        )

        return fare_data

    except Exception as e:
        print(f"⚠️ Driving fallback query error: {e}")
        return None


def get_transit_route_by_name(
    start_venue: str,
    end_venue: str,
    departure_datetime: datetime
) -> dict:
    """
    Queries Google Directions API using exact Place IDs / Lat-Lng coordinates.
    Detects same-building/nearby stops (<100m) and prevents false route loops.
    """
    if not gmaps:
        raise ValueError("GOOGLE_MAPS_API_KEY is missing from .env")

    try:
        # Step 1: Geocode both venues to get precise Place IDs and Coordinates
        start_loc = resolve_venue_location(start_venue)
        end_loc = resolve_venue_location(end_venue)

        start_coords = {"lat": start_loc["lat"], "lng": start_loc["lng"]} if start_loc else None
        end_coords = {"lat": end_loc["lat"], "lng": end_loc["lng"]} if end_loc else None

        start_lower = start_venue.lower()
        end_lower = end_venue.lower()

        # Step 2: SAME VENUE / SAME BUILDING CHECK
        # A) Explicit string overlap (e.g., both contain "national gallery")
        # B) Place IDs match
        # C) Distance between coordinates is less than 100 meters
        is_same_place = False

        if start_loc and end_loc:
            if start_loc["place_id"] == end_loc["place_id"]:
                is_same_place = True
            else:
                dist = haversine_distance_meters(start_loc["lat"], start_loc["lng"], end_loc["lat"], end_loc["lng"])
                if dist < 100:  # Within 100 meters = same building / complex
                    is_same_place = True

        if start_lower in end_lower or end_lower in start_lower or "inside" in end_lower:
            is_same_place = True

        if is_same_place:
            return {
                "drive_mins": 0,
                "real_commute_mins": 0,
                "walk_distance_m": 0,
                "step_by_step": "🚶 Located inside or at the same venue (<1 min walk)",
                "start_coords": start_coords,
                "end_coords": start_coords,  # Keep coordinates identical on map!
            }

        # Step 3: Construct precise targets for Directions API (Use place_id or lat,lng)
        origin_target = f"place_id:{start_loc['place_id']}" if (start_loc and start_loc.get("place_id")) else f"{start_venue}, Singapore"
        destination_target = f"place_id:{end_loc['place_id']}" if (end_loc and end_loc.get("place_id")) else f"{end_venue}, Singapore"

        directions = gmaps.directions(
            origin=origin_target,
            destination=destination_target,
            mode="transit",
            departure_time=departure_datetime,
        )

        # --- CASE 1: No Transit Route Found (Try Driving Fallback) ---
        if not directions:
            driving_info = get_driving_fallback(origin_target, destination_target, departure_datetime)
            if driving_info:
                return {
                    "drive_mins": driving_info["drive_mins"],
                    "real_commute_mins": driving_info["drive_mins"],
                    "walk_distance_m": 0,
                    "step_by_step": f"🚖 Recommended Option: Taxi/Grab {driving_info['formatted_estimate']}\n      ⚠️ No direct public transit route found.",
                    "start_coords": start_coords,
                    "end_coords": end_coords,
                }

            return {
                "drive_mins": None,
                "real_commute_mins": 0,
                "walk_distance_m": 0,
                "step_by_step": f"No route found between {start_venue} and {end_venue}.",
                "start_coords": start_coords,
                "end_coords": end_coords,
            }

        # --- CASE 2: Transit Route Found ---
        leg = directions[0]["legs"][0]

        # Use Google's verified start/end coords if geocoding failed earlier
        if not start_coords:
            start_coords = {"lat": leg["start_location"]["lat"], "lng": leg["start_location"]["lng"]}
        if not end_coords:
            end_coords = {"lat": leg["end_location"]["lat"], "lng": leg["end_location"]["lng"]}

        total_duration_mins = round(leg["duration"]["value"] / 60)
        total_distance_m = leg["distance"]["value"]

        legs_summary = []
        has_excessive_walk = False

        steps = leg.get("steps", [])
        is_pure_walk = all(step.get("travel_mode") == "WALKING" for step in steps)

        for step in steps:
            travel_mode = step["travel_mode"]

            if travel_mode == "TRANSIT":
                transit = step["transit_details"]
                line_info = transit["line"]
                vehicle_type = line_info["vehicle"]["type"]  # BUS, SUBWAY, FERRY
                line_name = line_info.get("short_name") or line_info.get("name", "")
                dep_stop = transit["departure_stop"]["name"]
                arr_stop = transit["arrival_stop"]["name"]
                dur_mins = round(step["duration"]["value"] / 60)

                if vehicle_type == "FERRY":
                    legs_summary.append(
                        f"⛵ Take Ferry ({line_name}) from '{dep_stop}' to '{arr_stop}' ({dur_mins} mins)"
                    )
                elif vehicle_type == "SUBWAY":
                    legs_summary.append(
                        f"🚇 Take MRT {line_name} from '{dep_stop}' to '{arr_stop}' ({dur_mins} mins)"
                    )
                else:
                    legs_summary.append(
                        f"🚌 Take Bus {line_name} from '{dep_stop}' to '{arr_stop}' ({dur_mins} mins)"
                    )

            elif travel_mode == "WALKING":
                dist_m = step["distance"]["value"]
                dur_mins = round(step["duration"]["value"] / 60)

                if dist_m > 1010:
                    has_excessive_walk = True

                if dist_m > 50:
                    legs_summary.append(f"🚶 Walk {dist_m}m ({dur_mins} mins)")

        transit_summary_str = " ➔ ".join(legs_summary)

        # Check for driving fallback if walking distance is excessive (>800m)
        driving_info = None
        if has_excessive_walk or (is_pure_walk and total_distance_m > 800):
            driving_info = get_driving_fallback(origin_target, destination_target, departure_datetime)

            if driving_info:
                taxi_str = f"🚖 Recommended Option: Taxi/Grab {driving_info['formatted_estimate']}"
                step_by_step_output = f"{taxi_str}\n      🚌 Public Transit Alternative: {transit_summary_str}"
            else:
                step_by_step_output = transit_summary_str
        else:
            step_by_step_output = transit_summary_str

        return {
            "drive_mins": driving_info["drive_mins"] if driving_info else None,
            "real_commute_mins": total_duration_mins,
            "walk_distance_m": total_distance_m,
            "step_by_step": step_by_step_output,
            "start_coords": start_coords,
            "end_coords": end_coords,
        }

    except Exception as e:
        return {
            "drive_mins": None,
            "real_commute_mins": 0,
            "walk_distance_m": 0,
            "step_by_step": f"Routing error: {e}",
            "start_coords": None,
            "end_coords": None,
        }