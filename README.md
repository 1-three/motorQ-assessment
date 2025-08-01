
# MotorQ Take-Home Assignment

## Overview
This project processes raw telematics (TLM), trigger logs (TRG), synthetic overrides (SYN), and mapping (MAP) data 
to extract and analyze vehicle events, specifically focusing on ignition events, charging status events, and charging sessions.

---

## Discovered Schemas & Data Issues

### TLM (Telematics)
- **Columns:** ID, VEHICLE_ID, TIMESTAMP, SPEED, IGNITION_STATUS, EV_BATTERY_LEVEL, ODOMETER
- **Issues:**
  - Missing values in SPEED, BATTERY_LEVEL, ODOMETER
  - IGNITION_STATUS contained values like "Unknown" and nulls
  - Some odometer readings decreased (impossible physically) → flagged
  - Timestamp inconsistencies →  some are in IST some are not
  
### TRG (Trigger Logs)
- **Columns:** CTS, PNID, NAME, VAL
- **Issues:**
  - Many rows lacked VEHICLE_ID (mapped via MAP)
  - Some VALs were invalid strings
  - Unmapped PNIDs flagged as UNKNOWN

### MAP (Vehicle Mapping)
- **Columns:** ID, IDS
- **Role:** Links TLM VEHICLE_IDs to TRG PNIDs
- **Issues:**
  - Some VEHICLE_IDs had empty mappings
  - IDS values stored as JSON strings → needed parsing

### SYN (Synthetic Overrides)
- **Keys:** vehicleId, timestamp, type
- **Role:** Override ignitions (mainly ignitionoff events)
- **Issues:** None major; used highest priority when overlaps

---

## Design Choices

1. **Ignition Events**
   - Extracted from **TLM, TRG (IGN_CYL), and SYN**
   - Normalized to `ignitionon` and `ignitionoff`
   - Debounced TLM to avoid flicker (≥60s gap for true state changes)
   - SYN used highest priority to ensure coverage

2. **Charging Status Events**
   - Extracted from TRG rows where NAME = EV_CHARGE_STATE
   - Normalized to {Active, Abort, Completed}
   - Unmapped PNIDs flagged as UNKNOWN

3. **Battery Association**
   - For each ignition/charging status event, linked closest battery % 
     within ±300s
   - Tie-breaker: earliest timestamp

4. **Charging Event Detection**
   - Identified real charging sessions as ≥5% battery increase
   - Stricter threshold when ignition was ON (to filter noise)
   - Sessions merged if less than 10 minutes apart to avoid double counting

---

## Evaluation Coverage

- **Correctness & robustness:** Multi-source fusion (TLM, TRG, SYN), debounced flickers, validated against MAP
- **Clarity & structure:** Modularized Python pipeline
- **Data-quality review:** Documented anomalies (NaNs, Unknowns, odometer decreases, unmapped PNIDs)
- **Write-up:** Clear design choices and next steps

---

## Next Steps & Improvements

- Improve mapping completeness (reduce UNKNOWN PNIDs from ~65%)
- Enhance odometer anomaly handling (e.g., GPS vs. odometer cross-check)
- More advanced noise filtering for ignition flickers
- Add visualization dashboards for non-technical stakeholders
- Consider statistical thresholds per-vehicle for charging session detection

---

## Submission Checklist

- [x] `IgnitionEvents.csv` and `ChargingEvents.csv` generated
- [x] All scripts modularized in Jupyter Notebook (`MotorQ.ipynb`)
- [x] README (this file) included
