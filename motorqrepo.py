# -*- coding: utf-8 -*-
"""MotorQRepo

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1DrD3a-SSJ9N5DO8q-Krqzz-2IQKhpZyd
"""

# Install dependencies if not already available
!pip install pandas numpy matplotlib seaborn plotly

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from datetime import datetime

# Load the different feeds
tlm = pd.read_csv('/content/sample_data/telemetry_data.csv')
trg = pd.read_csv('/content/sample_data/triggers_soc.csv')
map_df = pd.read_csv('/content/sample_data/vehicle_pnid_mapping.csv')
syn = pd.read_json('/content/sample_data/artificial_ign_off_data.json')

def parse_ids(val):
    # Case 1: missing or NaN
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    # Case 2: already a list
    if isinstance(val, list):
        return val
    # Case 3: a numpy array
    if isinstance(val, np.ndarray):
        return val.tolist()
    # Case 4: string that looks like JSON
    if isinstance(val, str):
        try:
            return json.loads(val.replace('""','"'))
        except Exception as e:
            print("Parse failed:", val, e)
            return []
    # Fallback: unknown type
    return []

# Apply parser
map_df['IDS'] = map_df['IDS'].apply(parse_ids)

# Quick check
for idx, row in map_df.head(5).iterrows():
    print(f"VEHICLE_ID {row['ID']} → {row['IDS']}")

"""TLM (High-rate Telematics Snapshots)
Missing Data

SPEED: 703,853 missing (~79%)

IGNITION_STATUS: 782,084 missing (~88%)

EV_BATTERY_LEVEL: 705,931 missing (~79%)

ODOMETER: 642,107 missing (~72%)

VEHICLE_ID and TIMESTAMP: 1 missing each

Ranges

Battery %: 0.0 – 110.0 (values >100 flagged as invalid)

Speed: 0.0 – 96.0 (plausible, no extreme outliers)

Odometer: 30,207 – 66,270 km (consistent with real-world use)

Duplicates

9,778 duplicate records (by VEHICLE_ID + TIMESTAMP).

Actions

Drop rows with missing VEHICLE_ID or TIMESTAMP.

Cap battery % at [0,100]; flag >100 as anomalies.

Deduplicate records by keeping the earliest row per (VEHICLE_ID,TIMESTAMP).

Treat SPEED, IGNITION_STATUS, and BATTERY as optional features (not always available).

TRG (Low-rate Trigger Log)
Missing Data: None.

Duplicates: 9,627 duplicates across (PNID, CTS, NAME, VAL).

Notes: Values for NAME include IGN_CYL and CHARGE_STATE — critical for ignition and charging event detection.

Actions: Remove exact duplicates before downstream processing.

MAP (Vehicle ID Map)
Missing Data

IDS: 6 of 19 entries missing → vehicles without PNID mappings.

Actions

Build a lookup dictionary (PNID → VEHICLE_ID) for TRG → TLM joins.

Flag TRG events with unmapped PNIDs as “unknown vehicle”.

SYN (Synthetic Overrides)
Missing Data: None.

Notes

411 curated ignition-off events across 11 vehicles.

Trusted override source; will supersede conflicting TLM/TRG events.

**Key Assumptio**ns

All timestamps normalized to UTC for alignment.

Ignition hierarchy: SYN > TRG > TLM.

EV_BATTERY_LEVEL valid only if within 0–100%; >100 treated as anomaly.

Odometer expected to be non-decreasing; any drop is flagged.

Duplicate TLM/TRG rows considered sensor noise → removed.
"""

# Timestamps
tlm['TIMESTAMP'] = pd.to_datetime(tlm['TIMESTAMP'], errors='coerce', utc=True)
trg['CTS'] = pd.to_datetime(trg['CTS'], errors='coerce', utc=True)
syn['timestamp'] = pd.to_datetime(syn['timestamp'], errors='coerce', utc=True)

# Missing counts
print("Missing TLM:", tlm.isna().sum())
print("Missing TRG:", trg.isna().sum())
print("Missing MAP:", map_df.isna().sum())
print("Missing SYN:", syn.isna().sum())

# Range & plausibility checks
print("Battery %:", tlm['EV_BATTERY_LEVEL'].min(), "-", tlm['EV_BATTERY_LEVEL'].max())
print("Speed Range:", tlm['SPEED'].min(), "-", tlm['SPEED'].max())
print("Odometer Range:", tlm['ODOMETER'].min(), "-", tlm['ODOMETER'].max())

# Check duplicates
dupes_tlm = tlm.duplicated(subset=['VEHICLE_ID','TIMESTAMP']).sum()
dupes_trg = trg.duplicated(subset=['PNID','CTS','NAME','VAL']).sum()
print("TLM Duplicates:", dupes_tlm)
print("TRG Duplicates:", dupes_trg)

# Sort by VEHICLE_ID and TIMESTAMP
tlm_sorted = tlm.sort_values(['VEHICLE_ID', 'TIMESTAMP']).reset_index(drop=True)

# Compute difference in ODOMETER per vehicle
tlm_sorted['ODOMETER_DIFF'] = tlm_sorted.groupby('VEHICLE_ID')['ODOMETER'].diff()

# Flag decreases
odometer_decreasing = tlm_sorted[tlm_sorted['ODOMETER_DIFF'] < 0]

print("Odometer decreases found:", len(odometer_decreasing))
display(odometer_decreasing[['VEHICLE_ID','TIMESTAMP','ODOMETER','ODOMETER_DIFF']].head())

"""Odometer decreases found: 5 (Diff = -1)"""

import matplotlib.pyplot as plt

def plot_odometer_over_time(tlm, vehicle_id):
    subset = tlm[tlm['VEHICLE_ID'] == vehicle_id].copy()
    if subset.empty:
        print(f"No data for vehicle {vehicle_id}")
        return

    # Ensure sorted by time
    subset['TIMESTAMP'] = pd.to_datetime(subset['TIMESTAMP'], errors='coerce')
    subset = subset.sort_values('TIMESTAMP')

    # Plot
    plt.figure(figsize=(12,5))
    plt.plot(subset['TIMESTAMP'], subset['ODOMETER'], marker='o', linestyle='-')
    plt.xlabel("Time")
    plt.ylabel("Odometer (km)")
    plt.title(f"Odometer Readings Over Time — Vehicle {vehicle_id[:8]}...")
    plt.grid(True)
    plt.show()

    # Highlight decreases
    subset['prev_odom'] = subset['ODOMETER'].shift()
    subset['diff'] = subset['ODOMETER'] - subset['prev_odom']
    decreases = subset[subset['diff'] < 0]
    if not decreases.empty:
        print("Odometer decreases detected:")
        print(decreases[['TIMESTAMP','ODOMETER','diff']])
    else:
        print("No decreases detected.")

plot_odometer_over_time(tlm, '66bd55df-eaf0-49c8-b9e1-7759b85e9325')

"""Graph attached in PDF"""

# Map TRG PNIDs to VEHICLE_IDs
trg['PNID'] = trg['PNID'].astype(str)  # ensure PNIDs are strings
trg['VEHICLE_ID'] = trg['PNID'].map(pnid_map)

# Check results
print("Total TRG rows:", len(trg))
print("Mapped VEHICLE_IDs:", trg['VEHICLE_ID'].notna().sum())
print("Unmapped TRG rows:", trg['VEHICLE_ID'].isna().sum())

# Preview
print(trg[['PNID', 'VEHICLE_ID', 'NAME', 'VAL']].head(20))

total = len(trg)
unknown = ((trg['VEHICLE_ID'] == 'UNKNOWN') | (trg['VEHICLE_ID'].isna())).sum()
mapped = total - unknown

unknown_pct = (unknown / total) * 100

print(f"Total: {total}, Mapped: {mapped}, Unknown: {unknown} ({unknown_pct:.1f}%)")

"""Total: 68670, Mapped: 23423, Unknown: 45247 (65.9%)

ID Mapping Coverage
Using the MAP file, we linked TRG PNIDs to TLM VEHICLE_IDs.

Total TRG rows: 68,670

Successfully mapped: 23,423 (34.1%)

Flagged as UNKNOWN: 45,247 (65.9%)

We retained UNKNOWN rows for completeness but excluded them from any analysis that required telemetry context (e.g., associating with TLM battery levels or odometer readings). This ensures robust analysis for mapped vehicles while maintaining visibility into the full TRG dataset.
"""

#Mapping instead of deleting to preserve trends that are important

trg['mapped_flag'] = np.where(
    (trg['VEHICLE_ID'] == 'UNKNOWN') | (trg['VEHICLE_ID'].isna()),
    'unmapped',
    'mapped'
)

print(trg[['PNID', 'VEHICLE_ID', 'mapped_flag']].head(20))

#A. Ignition from TLM

# Sort by vehicle and time
tlm_sorted = tlm.sort_values(['VEHICLE_ID', 'TIMESTAMP']).reset_index(drop=True)

# Detect ignition status flips
tlm_sorted['ignition_change'] = tlm_sorted['IGNITION_STATUS'].ne(
    tlm_sorted['IGNITION_STATUS'].shift()
)

# Keep rows with changes (and non-null ignition)
ignition_tlm = tlm_sorted.loc[
    tlm_sorted['ignition_change'] & tlm_sorted['IGNITION_STATUS'].notna(),
    ['VEHICLE_ID', 'TIMESTAMP', 'IGNITION_STATUS']
]

# Normalize event names
status_map = {
    'on': 'ignitionon',
    'off': 'ignitionoff',
}
ignition_tlm['event'] = (
    ignition_tlm['IGNITION_STATUS']
    .str.strip().str.lower()
    .map(status_map)
    .fillna('unknown')
)

# Rename for output
ignition_tlm.rename(columns={'TIMESTAMP':'event_ts'}, inplace=True)
ignition_tlm['source'] = 'TLM'

print("TLM ignition events:", ignition_tlm.shape[0])
print(ignition_tlm.head())

# Step 1: Filter for valid statuses
valid_status = ['on','off']
tlm_valid = tlm_sorted[tlm_sorted['IGNITION_STATUS'].str.lower().isin(valid_status)].copy()

# Step 2: Sort
tlm_valid = tlm_valid.sort_values(['VEHICLE_ID','TIMESTAMP']).reset_index(drop=True)

# Step 3: Detect ignition changes per vehicle (using transform to preserve index)
tlm_valid['ignition_change'] = tlm_valid.groupby('VEHICLE_ID')['IGNITION_STATUS'] \
                                        .transform(lambda x: x != x.shift())

# Step 4: Keep only rows where a change happened
ignition_tlm = tlm_valid.loc[tlm_valid['ignition_change']].copy()

# Step 5: Map ON/OFF to standardized values
status_map = {'on':'ignitionon','off':'ignitionoff','1':'ignitionon','0':'ignitionoff'}
ignition_tlm['event'] = ignition_tlm['IGNITION_STATUS'].str.lower().map(status_map)

# Step 6: Finalize output schema
ignition_tlm = ignition_tlm[['VEHICLE_ID','TIMESTAMP','event']].rename(columns={'TIMESTAMP':'event_ts'})
ignition_tlm['source'] = 'TLM'

print("Final cleaned TLM ignition events:", ignition_tlm.shape[0])
print(ignition_tlm.head(20))

import pandas as pd

# Ensure event_ts is in datetime format
ignition_tlm['event_ts'] = pd.to_datetime(ignition_tlm['event_ts'], errors='coerce')

# Set the minimum time gap to flag as a flicker (short toggle)
min_gap = 60  # seconds

# Get the previous event timestamp per vehicle
ignition_tlm['prev_ts'] = ignition_tlm.groupby('VEHICLE_ID')['event_ts'].shift()

# Compute time difference in seconds
ignition_tlm['time_diff'] = (ignition_tlm['event_ts'] - ignition_tlm['prev_ts']).dt.total_seconds()

# Mark flickers (events happening too close together)
ignition_tlm['flicker_flag'] = ignition_tlm['time_diff'] < min_gap

# View the result
print(ignition_tlm[['VEHICLE_ID', 'event_ts', 'event', 'time_diff', 'flicker_flag']].head(20))

#Ignition from TRG
# Filter for IGN_CYL rows
ignition_trg = trg[trg['NAME'] == 'IGN_CYL'][['VEHICLE_ID','CTS','VAL']]

# Normalize ON/OFF
ignition_trg['event'] = ignition_trg['VAL'].str.strip().str.lower().map({
    'on':'ignitionon', 'off':'ignitionoff'
})

# Rename columns
ignition_trg.rename(columns={'CTS':'event_ts'}, inplace=True)
ignition_trg['source'] = 'TRG'

print("TRG ignition events:", ignition_trg.shape[0])
print(ignition_trg.head())

#Not removing NULL values, filling them with a placeholder instead, since many new vehicles may not have a Vehicle_ID

ignition_trg['VEHICLE_ID'] = ignition_trg['VEHICLE_ID'].fillna('UNKNOWN')
ignition_trg['mapped_flag'] = np.where(
    ignition_trg['VEHICLE_ID'] == 'UNKNOWN', 'unmapped', 'mapped'
)
print(ignition_trg['mapped_flag'].value_counts(normalize=True) * 100)

#3. Ignition From SYN
ignition_syn = syn[['vehicleId','timestamp']].copy()
ignition_syn.rename(columns={'vehicleId':'VEHICLE_ID','timestamp':'event_ts'}, inplace=True)
ignition_syn['event'] = 'ignitionoff'
ignition_syn['source'] = 'SYN'

print("SYN ignition overrides:", ignition_syn.shape[0])
print(ignition_syn.head())

# Ensure all event_ts are datetime and timezone-naive - NORMALISE for timezone inconsistencies (some are in IST, some are not)
for df in [ignition_tlm, ignition_trg, ignition_syn]:
    df['event_ts'] = pd.to_datetime(df['event_ts'], errors='coerce')  # Ensure datetime
    df['event_ts'] = df['event_ts'].dt.tz_localize(None)              # Remove timezone info

# Combine all ignition events
ignition_events = pd.concat([
    ignition_tlm[['VEHICLE_ID', 'event_ts', 'event', 'source']],
    ignition_trg[['VEHICLE_ID', 'event_ts', 'event', 'source']],
    ignition_syn[['VEHICLE_ID', 'event_ts', 'event', 'source']]
], ignore_index=True)

# Sort chronologically
ignition_events.sort_values(['VEHICLE_ID', 'event_ts'], inplace=True)

print("Total ignition events:", ignition_events.shape[0])
print(ignition_events.head(20))

print(ignition_events['source'].value_counts())
print(ignition_events.groupby('source')['event'].value_counts())

"""Ignition Event Breakdown

TRG contributed 30,880 events (≈50% ignitionon, 50% ignitionoff).

TLM contributed 3,620 events (balanced between ignitionon and ignitionoff).

SYN contributed 411 curated ignitionoff events (no ignitionon).

The split confirms TRG and TLM provide balanced ON/OFF signals, while SYN supplements with authoritative OFF overrides.

"""

# Create summary table
summary = ignition_events.groupby(['source','event']).size().unstack(fill_value=0)

# Add total per source
summary['Total'] = summary.sum(axis=1)

# Add grand total row
summary.loc['Total'] = summary.sum()

import pandas as pd
from tabulate import tabulate

# Pretty print in Markdown style
print(tabulate(summary, headers='keys', tablefmt='github'))

"""Across all sources, we identified 34,911 ignition events — moments when vehicles were turned ON or OFF.

The majority (89%) came from trigger logs, which directly record ignition status.

Another 10% came from telematics sensor data, which we cleaned and filtered to remove noise.

Finally, 1% came from synthetic overrides — trusted manual corrections that confirm ignition-off moments.
Together, these sources give a reliable picture of when cars in the fleet were powered on or shut down.


"""

# Select and standardize columns for each source

# TLM
ignition_tlm_final = ignition_tlm[['VEHICLE_ID','event_ts','event']].copy()
ignition_tlm_final.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)

# TRG
ignition_trg_final = ignition_trg[['VEHICLE_ID','event_ts','event']].copy()
ignition_trg_final.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)

# SYN
ignition_syn_final = ignition_syn[['VEHICLE_ID','event_ts','event']].copy()
ignition_syn_final.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)

# Combine all
ignition_events = pd.concat(
    [ignition_tlm_final, ignition_trg_final, ignition_syn_final],
    ignore_index=True
)

# Sort for readability
ignition_events = ignition_events.sort_values(['vehicle_id','event_ts']).reset_index(drop=True)

print("Final IgnitionEvents:", ignition_events.shape[0])
print(ignition_events.head(20))

# Save as CSV
ignition_events.to_csv("IgnitionEvents.csv", index=False)

# Save as Parquet
ignition_events.to_parquet("IgnitionEvents.parquet", index=False)

#PLOT IN PDF

# Recreate with source tags for visualization only
ignition_tlm_viz = ignition_tlm[['VEHICLE_ID','event_ts','event']].copy()
ignition_tlm_viz.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)
ignition_tlm_viz['source'] = 'TLM'

ignition_trg_viz = ignition_trg[['VEHICLE_ID','event_ts','event']].copy()
ignition_trg_viz.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)
ignition_trg_viz['source'] = 'TRG'

ignition_syn_viz = ignition_syn[['VEHICLE_ID','event_ts','event']].copy()
ignition_syn_viz.rename(columns={'VEHICLE_ID':'vehicle_id'}, inplace=True)
ignition_syn_viz['source'] = 'SYN'

ignition_events_viz = pd.concat(
    [ignition_tlm_viz, ignition_trg_viz, ignition_syn_viz],
    ignore_index=True
)

# 1️⃣ Counts by source and event
import matplotlib.pyplot as plt

event_counts = ignition_events_viz.groupby(['source','event']).size().unstack(fill_value=0)
event_counts.plot(kind='bar', stacked=True)

plt.ylabel("Number of Events")
plt.title("Ignition Events by Source and Type")
plt.show()

# 2️⃣ Timeline for a sample vehicle
def plot_ignition_state(vehicle_id, ignition_events):
    subset = ignition_events[ignition_events['vehicle_id'] == vehicle_id].copy()
    if subset.empty:
        print(f"No data for {vehicle_id}")
        return

    # Ensure proper datetime and sorting
    subset['event_ts'] = pd.to_datetime(subset['event_ts'])
    subset = subset.sort_values('event_ts')

    # Map ON/OFF to 1/0
    state_map = {'ignitionon': 1, 'ignitionoff': 0}
    subset['state'] = subset['event'].map(state_map)

    plt.figure(figsize=(12,4))
    plt.step(subset['event_ts'], subset['state'], where='post', label='Ignition State', color='blue')
    plt.yticks([0,1], ['OFF','ON'])
    plt.title(f"Ignition State Timeline for Vehicle {vehicle_id[:8]}...")
    plt.xlabel("Timestamp")
    plt.ylabel("Ignition State")
    plt.grid(True)
    plt.show()

# Example: rerun for your vehicle
plot_ignition_state('04105a12-59b9-447b-865f-599f48eed1d7', ignition_events)

"""Sample Vehicle Timeline
The chart below shows ignition events for one vehicle between Sept 2021 and Feb 2022.

Green markers (TRG) indicate balanced ON and OFF cycles.

Red markers (SYN) appear later, representing curated OFF overrides.

Together, these confirm consistent start/stop behavior, with SYN ensuring authoritative shut-down coverage.


"""

#TASK 3
# Step 1: Sort by VEHICLE_ID and TIMESTAMP
tlm_sorted = tlm.sort_values(['VEHICLE_ID','TIMESTAMP']).reset_index(drop=True)

# Step 2: Find rows where IGNITION_STATUS changes from previous row
tlm_sorted['ignition_shift'] = tlm_sorted['IGNITION_STATUS'].ne(
    tlm_sorted['IGNITION_STATUS'].shift()
)

# Step 3: Keep only rows where a change occurred and IGNITION_STATUS is not null
ignition_tlm = tlm_sorted.loc[
    tlm_sorted['ignition_shift'] & tlm_sorted['IGNITION_STATUS'].notna(),
    ['VEHICLE_ID','TIMESTAMP','IGNITION_STATUS']
]

# Step 4: Rename columns to match required schema
ignition_tlm.rename(columns={
    'IGNITION_STATUS':'event',
    'TIMESTAMP':'event_ts'
}, inplace=True)

print(ignition_tlm.head(10))

import matplotlib.pyplot as plt

def plot_odometer_over_time(tlm, vehicle_id):
    subset = tlm[tlm['VEHICLE_ID'] == vehicle_id].copy()
    if subset.empty:
        print(f"No data for vehicle {vehicle_id}")
        return

    # Ensure sorted by time
    subset['TIMESTAMP'] = pd.to_datetime(subset['TIMESTAMP'], errors='coerce')
    subset = subset.sort_values('TIMESTAMP')

    # Plot
    plt.figure(figsize=(12,5))
    plt.plot(subset['TIMESTAMP'], subset['ODOMETER'], marker='o', linestyle='-')
    plt.xlabel("Time")
    plt.ylabel("Odometer (km)")
    plt.title(f"Odometer Readings Over Time — Vehicle {vehicle_id[:8]}...")
    plt.grid(True)
    plt.show()

    # Highlight decreases
    subset['prev_odom'] = subset['ODOMETER'].shift()
    subset['diff'] = subset['ODOMETER'] - subset['prev_odom']
    decreases = subset[subset['diff'] < 0]
    if not decreases.empty:
        print("Odometer decreases detected:")
        print(decreases[['TIMESTAMP','ODOMETER','diff']])
    else:
        print("No decreases detected.")

# Filter TRG for charging status rows
charging_trg = trg[trg['NAME'] == 'EV_CHARGE_STATE'][['VEHICLE_ID','CTS','VAL']].copy()

# Normalize event values
status_map = {
    'Active': 'Active',
    'Aborted': 'Abort',
    'Completed': 'Completed'
}
charging_trg['event'] = charging_trg['VAL'].str.strip().map(status_map)

# Rename columns
charging_trg.rename(columns={'CTS':'event_ts','VEHICLE_ID':'vehicle_id'}, inplace=True)

# Drop rows with missing or invalid event
charging_trg = charging_trg.dropna(subset=['event'])

print("Charging Status Events extracted:", charging_trg.shape[0])
print(charging_trg.head())

# Save as CSV/Parquet
charging_trg.to_csv("ChargingStatusEvents.csv", index=False)
charging_trg.to_parquet("ChargingStatusEvents.parquet", index=False)

# Filter only EV_CHARGE_STATE rows
charging_trg = trg[trg['NAME'] == 'EV_CHARGE_STATE'][['VEHICLE_ID','CTS','VAL']].copy()

# Normalize events
event_map = {'Active':'Active', 'Aborted':'Abort', 'Complete':'Complete'}
charging_trg['event'] = charging_trg['VAL'].map(event_map)

# Rename columns
charging_trg.rename(columns={'VEHICLE_ID':'vehicle_id', 'CTS':'event_ts'}, inplace=True)

# Fill missing vehicle IDs
charging_trg['vehicle_id'] = charging_trg['vehicle_id'].fillna('UNKNOWN')

# Final dataset
charging_events = charging_trg[['vehicle_id','event_ts','event']].dropna(subset=['event']).reset_index(drop=True)

print("Charging Status Events:", charging_events.shape[0])
print(charging_events['event'].value_counts())

"""Charging Status Events: 6423


event

Active      3607

Abort       2401

Complete     415

Name: count, dtype: int64


"""

#TASK 4
import pandas as pd
from datetime import timedelta

# Step 1: Load candidate events
candidates = pd.concat([ignition_events, charging_events], ignore_index=True)

# Step 2: Collect battery readings
battery_tlm = tlm[['VEHICLE_ID','TIMESTAMP','EV_BATTERY_LEVEL']].dropna()
battery_tlm.rename(columns={
    'VEHICLE_ID':'vehicle_id',
    'TIMESTAMP':'reading_ts',
    'EV_BATTERY_LEVEL':'battery_level'
}, inplace=True)

battery_trg = trg[trg['NAME'] == 'CHARGE_STATE'][['VEHICLE_ID','CTS','VAL']]
battery_trg.rename(columns={
    'VEHICLE_ID':'vehicle_id',
    'CTS':'reading_ts',
    'VAL':'battery_level'
}, inplace=True)
battery_trg['battery_level'] = pd.to_numeric(battery_trg['battery_level'], errors='coerce')

# Combine both sources
battery_readings = pd.concat([battery_tlm, battery_trg], ignore_index=True).dropna()

# ✅ Ensure datetime AFTER creation
candidates['event_ts'] = pd.to_datetime(candidates['event_ts'], errors='coerce', utc=True)
battery_readings['reading_ts'] = pd.to_datetime(battery_readings['reading_ts'], errors='coerce', utc=True)

# Step 3: Associate nearest reading (±300s)
def find_nearest(row, readings):
    subset = readings[readings['vehicle_id'] == row['vehicle_id']].copy()
    if subset.empty:
        return None
    subset['time_diff'] = (subset['reading_ts'] - row['event_ts']).abs()
    subset = subset[subset['time_diff'] <= pd.Timedelta(seconds=300)]
    if subset.empty:
        return None
    # tie-breaker: earliest
    return subset.sort_values(['time_diff','reading_ts']).iloc[0]['battery_level']

candidates['battery_level'] = candidates.apply(
    lambda r: find_nearest(r, battery_readings), axis=1
)

print("Battery-level enriched events:", candidates.head())

import pandas as pd

# Load the file
battery_events = pd.read_csv("BatteryEvents.csv")

# Quick overview
print("Shape:", battery_events.shape)
print(battery_events.head())

# Check coverage of battery readings
coverage = battery_events['battery_level'].notna().mean() * 100
print(f"Battery coverage: {coverage:.2f}%")

# Range of battery % (ignoring NaN)
print("Battery % range:", battery_events['battery_level'].min(), "-", battery_events['battery_level'].max())

# Min/Max timestamps
battery_events['event_ts'] = pd.to_datetime(battery_events['event_ts'], errors='coerce')
print("Time span:", battery_events['event_ts'].min(), "to", battery_events['event_ts'].max())

import pandas as pd
from datetime import timedelta

# Load enriched events
battery_events = pd.read_csv("BatteryEvents.csv", parse_dates=['event_ts'])

# Clean up battery % (cap at 100, floor at 0)
battery_events['battery_level'] = pd.to_numeric(battery_events['battery_level'], errors='coerce')
battery_events['battery_level'] = battery_events['battery_level'].clip(lower=0, upper=100)

# Sort by vehicle and time
battery_events = battery_events.sort_values(['vehicle_id', 'event_ts']).reset_index(drop=True)

print("Rows:", battery_events.shape[0])
print(battery_events.head())

"""This vehicle #4 appears to never turn off because the underlying battery readings are flat around 47%.
It’s possible that either the telematics feed didn’t capture real discharge/charge changes, or that synthetic overrides injected OFF events without corresponding battery updates.
I accounted for this by allowing ±5 minutes for battery association, but for vehicles with sparse data, coverage is limited.
In production, I’d validate with raw TRG data or extend the window to confirm true ON/OFF behavior.
"""

import pandas as pd
from datetime import timedelta

# Ensure event_ts is datetime
battery_events['event_ts'] = pd.to_datetime(battery_events['event_ts'], errors='coerce', utc=True)

charging_sessions = []
threshold = 5  # % increase to count as "real charging"

for vid, group in battery_events.groupby('vehicle_id'):
    # Drop rows without a valid battery reading
    group = group.dropna(subset=['battery_level'])
    # Ensure timestamps are datetime
    group = group.sort_values('event_ts').reset_index(drop=True)

    prev_level, prev_ts = None, None

    for _, row in group.iterrows():
        if prev_level is not None:
            # Now subtraction works since both are datetime
            diff = row['battery_level'] - prev_level
            gap = row['event_ts'] - prev_ts

            if diff >= threshold:
                charging_sessions.append({
                    'vehicle_id': vid,
                    'start_ts': prev_ts,
                    'end_ts': row['event_ts'],
                    'start_level': prev_level,
                    'end_level': row['battery_level'],
                    'ignition_state': row['event'] if 'ignition' in row['event'].lower() else 'unknown'
                })
        prev_level, prev_ts = row['battery_level'], row['event_ts']

charging_df = pd.DataFrame(charging_sessions)
print("Charging Events:", charging_df.shape[0])
print(charging_df.head())

#PLOT IN PDF
import pandas as pd
import matplotlib.pyplot as plt

# Example: load your charging events CSV
charging_events = pd.read_csv("ChargingEvents.csv", parse_dates=['start_ts','end_ts'])
battery_events = pd.read_csv("BatteryEvents.csv", parse_dates=['event_ts'])

# Choose one vehicle
vehicle_id = "56d8ca94-9b18-41d1-831f-7afd905326d4"
veh_charging = charging_events[charging_events['vehicle_id'] == vehicle_id]
veh_battery = battery_events[battery_events['vehicle_id'] == vehicle_id]

plt.figure(figsize=(12,6))

# Plot charging sessions
for _, row in veh_charging.iterrows():
    plt.plot([row['start_ts'], row['end_ts']],
             [row['start_level'], row['end_level']],
             color='blue', marker='o')

# Plot raw battery readings
plt.scatter(veh_battery['event_ts'], veh_battery['battery_level'],
            color='orange', s=20, label='Battery Readings')

plt.title(f"Battery & Charging Sessions for Vehicle {vehicle_id[:6]}...")
plt.xlabel("Time")
plt.ylabel("Battery Level (%)")
plt.legend()
plt.grid(True)
plt.show()

#PLOT IN PDF
import pandas as pd
import matplotlib.pyplot as plt

# Load and ensure datetime types
charging_events = pd.read_csv("ChargingEvents.csv")
battery_events = pd.read_csv("BatteryEvents.csv")

# Convert to datetime
charging_events['start_ts'] = pd.to_datetime(charging_events['start_ts'], errors='coerce', utc=True)
charging_events['end_ts'] = pd.to_datetime(charging_events['end_ts'], errors='coerce', utc=True)
battery_events['event_ts'] = pd.to_datetime(battery_events['event_ts'], errors='coerce', utc=True)

# Pick a few vehicles (adjust as needed)
vehicles = charging_events['vehicle_id'].dropna().unique()[:4]

fig, axes = plt.subplots(len(vehicles), 1, figsize=(14, 4*len(vehicles)), sharex=True)

if len(vehicles) == 1:
    axes = [axes]

for ax, vid in zip(axes, vehicles):
    veh_charging = charging_events[charging_events['vehicle_id'] == vid].dropna(subset=['start_ts','end_ts'])
    veh_battery = battery_events[battery_events['vehicle_id'] == vid].dropna(subset=['event_ts','battery_level'])

    # Plot raw battery readings
    if not veh_battery.empty:
        ax.scatter(veh_battery['event_ts'], veh_battery['battery_level'],
                   color='orange', s=15, label='Battery Readings')

    # Plot charging sessions as line segments
    if not veh_charging.empty:
        for _, row in veh_charging.iterrows():
            ax.plot([row['start_ts'], row['end_ts']],
                    [row['start_level'], row['end_level']],
                    color='blue', marker='o', linewidth=2, label='Charging Session')

    ax.set_title(f"Vehicle {vid[:8]}... Battery & Charging Sessions")
    ax.set_ylabel("Battery Level (%)")
    ax.grid(True)
    ax.legend(loc="upper left")

plt.xlabel("Time")
plt.tight_layout()
plt.show()

#changing to given o/p format: delta difference is diff_level
import pandas as pd

# File paths
charging1_path = "/content/ChargingEvents_normalized.csv"
output_path = "/content/ChargingEvents.csv"

# Load the CSV
df_charging1 = pd.read_csv(charging1_path)

# Ensure numeric values for levels
df_charging1['start_level'] = pd.to_numeric(df_charging1['start_level'], errors='coerce')
df_charging1['end_level'] = pd.to_numeric(df_charging1['end_level'], errors='coerce')

# Create new column for difference
df_charging1['level_diff'] = df_charging1['end_level'] - df_charging1['start_level']

# Drop the original start_level and end_level columns
df_charging1 = df_charging1.drop(columns=['start_level', 'end_level'])

# Save to new CSV
df_charging1.to_csv(output_path, index=False)

print(f"Updated CSV saved to {output_path}")
print(df_charging1.head())
