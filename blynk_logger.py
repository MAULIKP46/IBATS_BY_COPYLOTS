import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import json

# Blynk details
BLYNK_AUTH_TOKEN = "oNJEiuSijoO0u3YsaxbeQB3ZeJcAgned"
VIRTUAL_PINS = ["V0", "V1", "V2", "V3", "V4", "V5"]
BASE_URL = f"https://blynk.cloud/external/api/get?token={BLYNK_AUTH_TOKEN}"

# File paths
CSV_FILE = "blynk_volume.csv"
LATEST_FILE = "latest_volume.json"

# Create CSV if not exists
if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["Timestamp", "TotalVolume(ml)", "Switch_1(s)", "Switch_2(s)", "Flag"]).to_csv(CSV_FILE, index=False)

print("Starting V4 volume logger... Press Ctrl+C to stop.")

# Initialize counters
last_updated_time = datetime.now()
totalVolume = 0.0
v4_prev = 0.0
v0_time = 0.0
v1_time = 0.0
flag = 0
flag_expiry_time = None

try:
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success = True

        # Fetch V4 for volume tracking
        try:
            response_v4 = requests.get(f"{BASE_URL}&V4", timeout=5)
            value_v4 = response_v4.text.strip()

            if value_v4.lower() in ["null", "", "error"]:
                print(f"Invalid response from V4: {value_v4}")
                success = False
            else:
                v4_value = float(value_v4)
        except requests.RequestException as e:
            print(f"Connection error for V4: {e}")
            success = False

        # Volume logic
        if success:
            difference = v4_value - v4_prev
            if abs(difference) <= 3:
                print(f"{timestamp} → V4 change too small: {difference:.2f}ml")
            else:
                totalVolume += v4_value
                print(f"{timestamp} → Added V4(ml): {v4_value}, TotalVolume(ml): {totalVolume:.2f}")
            v4_prev = v4_value

        # Fetch V0, V1, V2 and update time counters
        try:
            v0 = float(requests.get(f"{BASE_URL}&V0", timeout=5).text.strip())
            v1 = float(requests.get(f"{BASE_URL}&V1", timeout=5).text.strip())
            v2 = float(requests.get(f"{BASE_URL}&V2", timeout=5).text.strip())

            if v0 == 1:
                v0_time += 0.5
            if v1 == 1:
                v1_time += 0.5
            if v2 == 1:
                v0_time += 0.5
                v1_time += 0.5

        except requests.RequestException as e:
            print(f"Error fetching V0/V1/V2: {e}")

        # Fetch V3 and manage flag logic
        try:
            v3 = float(requests.get(f"{BASE_URL}&V3", timeout=5).text.strip())
            if v3 == 1:
                flag = 1
                flag_expiry_time = datetime.now() + timedelta(seconds=120)

            if flag_expiry_time and datetime.now() >= flag_expiry_time:
                flag = 0
                flag_expiry_time = None
        except requests.RequestException as e:
            print(f"Error fetching V3: {e}")

        print(f"{timestamp} → V0_time: {v0_time:.1f}s, V1_time: {v1_time:.1f}s, Flag: {flag}")

        # Save to CSV and JSON every 10 seconds
        current_time = datetime.now()
        if current_time - last_updated_time >= timedelta(seconds=10):
            data_row = {
                "Timestamp": timestamp,
                "TotalVolume(ml)": totalVolume,
                "Switch_1(s)": v0_time,
                "Switch_2(s)": v1_time,
                "Flag": flag
            }

            df_existing = pd.read_csv(CSV_FILE)
            df_new = pd.DataFrame([data_row])
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_csv(CSV_FILE, index=False)

            with open(LATEST_FILE, "w") as jf:
                json.dump(data_row, jf)

            last_updated_time = current_time

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nLogging stopped by user.")
