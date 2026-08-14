# gmaps_service.py
# -*- coding: utf-8 -*-
import os
import math
import re
from datetime import datetime
import googlemaps
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY) if API_KEY else None


def clean_venue_name(name: str) -> str:
    """Removes parenthetical notes like '(Inside VivoCity Mall)' for cleaner API searches."""
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


def extract_parent_complex(name: str) -> str | None:
    """Extracts parent venue names from patterns like '(Inside VivoCity Mall)' or '(at RWS)'."""
    match = re.search(r"\((?:inside|at)\s+(.*?)\)", name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


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
    Strips parenthetical context to get precise shop/attraction coordinates.
    """
    if not gmaps or not venue_name:
        return None

    try:
        # Strip parenthetical annotations before searching Google Places
        search_name = clean_venue_name(venue_name)
        query = f"{search_name}, Singapore"

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
                "name": best.get("name", search_name),
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
    Detects same-building/nearby stops (<300m) and calculates realistic indoor transition times.
    """
    if not gmaps:
        raise ValueError("GOOGLE_MAPS_API_KEY is missing from .env")

    try:
        # Step 1: Geocode both venues to get precise Place IDs and Coordinates
        start_loc = resolve_venue_location(start_venue)
        end_loc = resolve_venue_location(end_venue)

        start_coords = {"lat": start_loc["lat"], "lng": start_loc["lng"]} if start_loc else None
        end_coords = {"lat": end_loc["lat"], "lng": end_loc["lng"]} if end_loc else None

        clean_start = clean_venue_name(start_venue).lower()
        clean_end = clean_venue_name(end_venue).lower()

        start_parent = extract_parent_complex(start_venue)
        end_parent = extract_parent_complex(end_venue)

        # Calculate straight-line distance in meters
        dist_meters = (
            haversine_distance_meters(
                start_loc["lat"], start_loc["lng"], end_loc["lat"], end_loc["lng"]
            )
            if (start_loc and end_loc)
            else 0
        )

        # Step 2: INTRA-COMPLEX / SAME VENUE DETECTION
        is_same_place_id = bool(start_loc and end_loc and start_loc["place_id"] == end_loc["place_id"])

        shared_parent = bool(
            (start_parent and end_parent and start_parent.lower() == end_parent.lower())
            or (start_parent and start_parent.lower() in clean_end)
            or (end_parent and end_parent.lower() in clean_start)
        )

        is_intra_venue = is_same_place_id or shared_parent or dist_meters < 300

        if is_intra_venue:
            # Case A: Literally the exact same venue/shop
            if clean_start == clean_end:
                walk_mins = 1
                est_dist = round(dist_meters)
                walk_desc = "🚶 Located at the exact same spot (<1 min walk)"
            # Case B: Distinct sub-locations inside the same complex or nearby (<300m)
            else:
                # If geocoding collapsed both venues to the exact same point (< 30m gap),
                # allocate a realistic indoor mall/complex walking buffer (~200m / 4 mins)
                if dist_meters < 30:
                    est_dist = 200  # Default ~200m indoor walking distance
                    walk_mins = 4  # ~4 mins to walk between floors/halls
                else:
                    est_dist = round(dist_meters)
                    # ~70m per minute indoor walking speed, floor minimum of 3 mins
                    walk_mins = max(3, round(est_dist / 70))

                complex_name = end_parent or start_parent or "the same venue/complex"
                walk_desc = f"🚶 Walk inside {complex_name} (~{est_dist}m, {walk_mins} mins)"

            return {
                "drive_mins": 0,
                "real_commute_mins": walk_mins,
                "walk_distance_m": est_dist,
                "step_by_step": walk_desc,
                "start_coords": start_coords,
                "end_coords": end_coords,
            }

        # Step 3: Construct precise targets for Directions API
        origin_target = (
            f"place_id:{start_loc['place_id']}"
            if (start_loc and start_loc.get("place_id"))
            else f"{clean_venue_name(start_venue)}, Singapore"
        )
        destination_target = (
            f"place_id:{end_loc['place_id']}"
            if (end_loc and end_loc.get("place_id"))
            else f"{clean_venue_name(end_venue)}, Singapore"
        )

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
                vehicle_type = line_info["vehicle"]["type"]
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

        # Fallback to driving if walking distance is excessive (>800m)
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