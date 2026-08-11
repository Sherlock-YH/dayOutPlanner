# helperFunction.py
from datetime import datetime
import os
import random
import resend

# Initialize Resend API Key
resend.api_key = os.getenv("RESEND_API_KEY", "")


def generate_otp() -> str:
    """Generates a random 6-digit numeric string."""
    return f"{random.randint(100000, 999999)}"


def send_otp_email(to_email: str, code: str) -> bool:
    """
    Sends an OTP email via Resend.
    Returns True if sent successfully, False otherwise.
    """
    api_key = os.getenv("RESEND_API_KEY", "")

    if not api_key:
        print("⚠️ [WARNING] RESEND_API_KEY is missing!")
        print(f"🔑 [LOCAL OTP CODE FOR {to_email}]: {code}")
        return False

    resend.api_key = api_key

    try:
        params: resend.Emails.SendParams = {
            "from": "One Day Out <noreply@dayout.sherlock-yh.top>",
            "to": [to_email],
            "subject": "Your Verification Code - One Day Out Planner",
            "html": f"""
                <div style="font-family: sans-serif; padding: 20px; background-color: #0f172a; color: #f8fafc; border-radius: 12px;">
                    <h2 style="color: #34d399;">🇸🇬 One Day Out Planner</h2>
                    <p>Use the following 6-digit code to complete your registration:</p>
                    <h1 style="font-size: 36px; letter-spacing: 6px; color: #34d399; margin: 20px 0;">{code}</h1>
                    <p style="color: #94a3b8; font-size: 12px;">This code will expire in 10 minutes.</p>
                </div>
            """,
        }
        response = resend.Emails.send(params)
        print(f"✅ Email sent successfully to {to_email}. ID: {response}")
        return True

    except Exception as e:
        # Catch Resend API errors so the endpoint doesn't return a 500 error
        print(f"❌ Resend API Error for {to_email}: {str(e)}")
        return False


def calculate_sg_taxi_fare(
    distance_meters: int,
    duration_seconds: int,
    departure_datetime: datetime | None = None,
) -> dict:
    """
    Calculates estimated Singapore Taxi / Ride-Hailing (Grab/Gojek) fare range
    based on Google Maps driving distance and travel duration.

    Standard SG Metered Fare Structure (ComfortDelGro / Trans-Cab baseline):
    - Flagdown (includes 1st km): $4.50 SGD
    - Every 400m thereafter (up to 10km): $0.26 SGD
    - Every 350m thereafter (above 10km): $0.26 SGD
    - Every 45 seconds of travel/waiting time: $0.26 SGD
    - Late Night Surcharge (00:00 - 05:59): +50% on metered fare
    - Peak Hour Surcharge (07:00 - 09:59 Mon-Fri, 17:00 - 23:59 Daily): +25%
    """
    dist_km = distance_meters / 1000.0
    drive_mins = round(duration_seconds / 60)

    # 1. Flagdown Base (covers first 1.0 km)
    base_fare = 4.50

    # 2. Distance Fare Calculation
    distance_cost = 0.0
    if dist_km > 1.0:
        if dist_km <= 10.0:
            # Tier 1: 1km to 10km (every 400m = $0.26)
            remaining_km = dist_km - 1.0
            distance_cost = (remaining_km / 0.40) * 0.26
        else:
            # Tier 1: 1km to 10km
            tier1_cost = (9.0 / 0.40) * 0.26
            # Tier 2: Above 10km (every 350m = $0.26)
            remaining_km = dist_km - 10.0
            tier2_cost = (remaining_km / 0.35) * 0.26
            distance_cost = tier1_cost + tier2_cost

    # 3. Time Fare Calculation (traffic slowdown / waiting time factor)
    # Average travel time component (~$0.26 per 45s)
    time_cost = (duration_seconds / 45.0) * 0.26

    # Metered Subtotal
    subtotal = base_fare + distance_cost + time_cost

    # 4. Surcharge Multipliers based on Departure Time
    surcharge_multiplier = 1.0
    if departure_datetime:
        hour = departure_datetime.hour
        is_weekday = departure_datetime.weekday() < 5  # Mon - Fri

        # Late Night (00:00 AM - 05:59 AM): +50%
        if 0 <= hour < 6:
            surcharge_multiplier = 1.50
        # Morning Peak (07:00 AM - 09:59 AM, Mon-Fri): +25%
        elif is_weekday and (7 <= hour < 10):
            surcharge_multiplier = 1.25
        # Evening Peak (05:00 PM - 11:59 PM, Daily): +25%
        elif 17 <= hour <= 23:
            surcharge_multiplier = 1.25

    # Calculate Base Estimate
    estimated_fare = subtotal * surcharge_multiplier

    # Standard SG Taxi/Ride-Hail Minimum Fare threshold is ~$6.00 SGD
    min_fare = max(6.0, round(estimated_fare))

    # Upper bound includes buffer for dynamic surge pricing (Grab/Gojek) or ERP tolls
    max_fare = round(min_fare * 1.30)

    return {
        "drive_mins": drive_mins,
        "min_fare_sgd": int(min_fare),
        "max_fare_sgd": int(max_fare),
        "formatted_estimate": f"~{drive_mins} mins (${int(min_fare)}-${int(max_fare)} SGD)",
    }