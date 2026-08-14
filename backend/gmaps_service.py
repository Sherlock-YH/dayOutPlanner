# gmaps_service.py
# -*- coding: utf-8 -*-
import os
from datetime import datetime
import googlemaps
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=API_KEY) if API_KEY else None


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
    start_venue: str,
    end_venue: str,
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
            origin=f"{start_venue}, Singapore",
            destination=f"{end_venue}, Singapore",
            mode="driving",
            departure_time=departure_datetime,
        )

        if not directions:
            return None

        leg = directions[0]["legs"][0]
        dist_m = leg["distance"]["value"]

        # Use live traffic duration if available
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
    Queries Google Directions API using human-readable venue names directly.
    Automatically checks for excessive walking (>800m) and includes a taxi fallback option.
    """
    if not gmaps:
        raise ValueError("GOOGLE_MAPS_API_KEY is missing from .env")

    try:
        origin_str = f"{start_venue}, Singapore"
        destination_str = f"{end_venue}, Singapore"

        directions = gmaps.directions(
            origin=origin_str,
            destination=destination_str,
            mode="transit",
            departure_time=departure_datetime,
        )

        # --- CASE 1: No Transit Route Found (Try Driving Fallback) ---
        if not directions:
            start_lower = start_venue.lower()
            end_lower = end_venue.lower()

            if start_lower in end_lower or end_lower in start_lower or "inside" in end_lower:
                return {
                    "drive_mins": 0,
                    "real_commute_mins": 0,
                    "walk_distance_m": 0,
                    "step_by_step": "🚶 Located inside or adjacent to current venue (<1 min walk)",
                    "start_coords": None,
                    "end_coords": None,
                }

            # Try driving fallback if public transit isn't available
            driving_info = get_driving_fallback(start_venue, end_venue, departure_datetime)
            if driving_info:
                return {
                    "drive_mins": driving_info["drive_mins"],
                    "real_commute_mins": driving_info["drive_mins"],
                    "walk_distance_m": 0,
                    "step_by_step": f"🚖 Recommended Option: Taxi/Grab {driving_info['formatted_estimate']}\n      ⚠️ No direct public transit route found.",
                    "start_coords": None,
                    "end_coords": None,
                }

            return {
                "drive_mins": None,
                "real_commute_mins": 0,
                "walk_distance_m": 0,
                "step_by_step": f"No route found between {start_venue} and {end_venue}.",
                "start_coords": None,
                "end_coords": None,
            }

        # --- CASE 2: Transit Route Found ---
        leg = directions[0]["legs"][0]

        start_coords = {
            "lat": leg["start_location"]["lat"],
            "lng": leg["start_location"]["lng"],
        }
        end_coords = {
            "lat": leg["end_location"]["lat"],
            "lng": leg["end_location"]["lng"],
        }

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
            driving_info = get_driving_fallback(start_venue, end_venue, departure_datetime)

            if driving_info:
                taxi_str = f"🚖 Recommended Option: Taxi/Grab {driving_info['formatted_estimate']}"
                step_by_step_output = f"{taxi_str}\n      🚌 Public Transit Alternative: {transit_summary_str}"
            else:
                step_by_step_output = transit_summary_str
        else:
            step_by_step_output = transit_summary_str

        # ✅ FIXED RETURN DICT: Pass drive_mins directly to top level!
        return {
            "drive_mins": driving_info["drive_mins"] if driving_info else None, # 👈 ADDED HERE
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