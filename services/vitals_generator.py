"""
Vital Signs Simulation Engine for Smart ICU Guardian.
Simulates physiological signals based on clinical profiles and realistic patient scenarios.
"""

import json
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "thresholds.json"
)


def load_thresholds() -> Dict[str, Any]:
    """Loads vital signs threshold configuration."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "heart_rate": {"warning_min": 50, "warning_max": 110, "critical_min": 40, "critical_max": 130},
        "spo2": {"warning_min": 90, "critical_max": 85},
        "respiratory_rate": {"warning_min": 10, "warning_max": 24, "critical_min": 6, "critical_max": 30},
        "temperature": {"warning_min": 35.5, "warning_max": 38.0, "critical_min": 34.0, "critical_max": 40.0},
        "alert_states": ["NORMAL", "WARNING", "CRITICAL", "DATA_FAULT"]
    }


@dataclass
class VitalReading:
    heart_rate: Optional[float]
    spo2: Optional[float]
    respiratory_rate: Optional[float]
    temperature: Optional[float]
    oxygen_line_status: str
    data_valid: int
    scenario_name: str
    step: int
    timestamp_str: str


class VitalSimulator:
    """Simulates realistic ICU patient vitals across multiple clinical scenarios."""

    def __init__(self):
        self.step = 0
        self.thresholds = load_thresholds()

    def generate_reading(
        self,
        scenario_name: str,
        step: int,
        custom_overrides: Optional[Dict[str, Any]] = None
    ) -> VitalReading:
        """
        Generates a vital sign reading according to scenario name and progression step.
        """
        self.step = step
        time_sec = step * 1.5

        if scenario_name == "Interactive Custom" and custom_overrides:
            hr = float(custom_overrides.get("heart_rate", 75.0))
            spo2 = float(custom_overrides.get("spo2", 98.0))
            rr = float(custom_overrides.get("respiratory_rate", 16.0))
            temp = float(custom_overrides.get("temperature", 37.0))
            data_valid = int(custom_overrides.get("data_valid", 1))
            o2_status = str(custom_overrides.get("oxygen_line_status", "CONNECTED"))
            
            # Subtle physiological noise if data is valid
            if data_valid:
                hr += round(random.gauss(0, 0.5), 1)
                spo2 += round(random.gauss(0, 0.2), 1)
                rr += round(random.gauss(0, 0.3), 1)
                temp += round(random.gauss(0, 0.05), 2)
                spo2 = min(100.0, max(0.0, spo2))

            from datetime import datetime
            return VitalReading(
                heart_rate=round(hr, 1) if data_valid else None,
                spo2=round(spo2, 1) if data_valid else None,
                respiratory_rate=round(rr, 1) if data_valid else None,
                temperature=round(temp, 2) if data_valid else None,
                oxygen_line_status=o2_status if data_valid else "FAULT",
                data_valid=data_valid,
                scenario_name=scenario_name,
                step=step,
                timestamp_str=datetime.now().strftime("%H:%M:%S")
            )

        elif scenario_name == "Normal Recovery":
            # Stable recovery: gentle respiratory sinus arrhythmia
            hr = 74.0 + 3.0 * math.sin(time_sec * 0.1) + random.gauss(0, 0.8)
            spo2 = 98.5 + 0.8 * math.cos(time_sec * 0.05) + random.gauss(0, 0.2)
            rr = 15.0 + 1.2 * math.sin(time_sec * 0.08) + random.gauss(0, 0.3)
            temp = 36.9 + 0.1 * math.sin(time_sec * 0.02) + random.gauss(0, 0.04)
            spo2 = min(100.0, max(95.0, spo2))
            data_valid = 1
            o2_status = "CONNECTED"

        elif scenario_name == "Acute Hypoxia":
            # Progressive desaturation with compensatory tachycardia and tachypnea
            progression = min(1.0, step / 20.0)
            # SpO2 drops from 97% to 81%
            spo2 = 97.0 - (18.0 * progression) + random.gauss(0, 0.5)
            # HR climbs compensatorily from 78 to 128 bpm
            hr = 78.0 + (50.0 * progression) + random.gauss(0, 1.2)
            # RR climbs from 16 to 34 bpm
            rr = 16.0 + (18.0 * progression) + random.gauss(0, 0.6)
            temp = 37.1 + random.gauss(0, 0.05)
            spo2 = min(100.0, max(60.0, spo2))
            data_valid = 1
            o2_status = "CONNECTED"

        elif scenario_name == "Septic Shock":
            # Severe infection with hyperthermia and marked tachycardia
            progression = min(1.0, step / 18.0)
            temp = 37.5 + (3.1 * progression) + random.gauss(0, 0.06)  # reaches 40.6°C
            hr = 85.0 + (52.0 * progression) + random.gauss(0, 1.5)    # reaches 137 bpm
            rr = 18.0 + (14.0 * progression) + random.gauss(0, 0.8)    # reaches 32 bpm
            spo2 = 96.0 - (7.0 * progression) + random.gauss(0, 0.6)   # dips to ~89%
            spo2 = min(100.0, max(75.0, spo2))
            data_valid = 1
            o2_status = "CONNECTED"

        elif scenario_name == "Cardiac Bradycardia":
            # Progressive sinus node depression / conduction block
            progression = min(1.0, step / 18.0)
            hr = 72.0 - (38.0 * progression) + random.gauss(0, 0.9)    # drops to 34 bpm
            spo2 = 97.0 - (4.0 * progression) + random.gauss(0, 0.4)
            rr = 15.0 - (6.0 * progression) + random.gauss(0, 0.4)     # drops to ~9 bpm
            temp = 36.6 - (1.5 * progression) + random.gauss(0, 0.05)  # mild hypothermia 35.1°C
            hr = max(25.0, hr)
            data_valid = 1
            o2_status = "CONNECTED"

        elif scenario_name == "Sensor Disconnection":
            # Signal drops or loses pulse waveform at step >= 5
            if step >= 5:
                hr = None
                spo2 = None
                rr = None
                temp = None
                data_valid = 0
                o2_status = "DISCONNECTED"
            else:
                hr = 75.0 + random.gauss(0, 0.8)
                spo2 = 98.0 + random.gauss(0, 0.3)
                rr = 16.0 + random.gauss(0, 0.4)
                temp = 36.9 + random.gauss(0, 0.04)
                data_valid = 1
                o2_status = "CONNECTED"

        else:
            # Default fallback: stable
            hr = 75.0 + random.gauss(0, 1.0)
            spo2 = 98.0 + random.gauss(0, 0.3)
            rr = 16.0 + random.gauss(0, 0.5)
            temp = 37.0 + random.gauss(0, 0.05)
            data_valid = 1
            o2_status = "CONNECTED"

        from datetime import datetime
        return VitalReading(
            heart_rate=round(hr, 1) if hr is not None else None,
            spo2=round(spo2, 1) if spo2 is not None else None,
            respiratory_rate=round(rr, 1) if rr is not None else None,
            temperature=round(temp, 2) if temp is not None else None,
            oxygen_line_status=o2_status,
            data_valid=data_valid,
            scenario_name=scenario_name,
            step=step,
            timestamp_str=datetime.now().strftime("%H:%M:%S")
        )

    def generate_patient_reading(
        self,
        patient: Dict[str, Any],
        step: int,
        custom_overrides: Optional[Dict[str, Any]] = None
    ) -> VitalReading:
        """Generates reading for a specific patient using their assigned scenario."""
        scenario = patient.get("current_scenario", "Normal Recovery")
        return self.generate_reading(scenario, step, custom_overrides=custom_overrides)

