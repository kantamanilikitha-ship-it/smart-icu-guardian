"""
Python Cycle-Exact Behavioral Twin of safety_controller.v.
Implements the exact finite state machine and threshold evaluation matching the hardware RTL.
Used for verification, test suites, and transparent fallback when native Verilog simulators are unavailable.
"""

from typing import Dict, Any, List, Optional, Tuple


class BehavioralSafetyController:
    """
    Behavioral digital FSM matching simulator/verilog/verilog/safety_controller.v.
    States:
      0: NORMAL
      1: WARNING
      2: CRITICAL
      3: DATA_FAULT
    """

    STATE_NORMAL = "NORMAL"
    STATE_WARNING = "WARNING"
    STATE_CRITICAL = "CRITICAL"
    STATE_DATA_FAULT = "DATA_FAULT"

    STATE_CODES = {
        STATE_NORMAL: 0,
        STATE_WARNING: 1,
        STATE_CRITICAL: 2,
        STATE_DATA_FAULT: 3
    }

    def __init__(self):
        self.state = self.STATE_NORMAL
        self.alarm_audio_en = False
        self.alarm_visual_en = False
        self.ack_active = False
        self.fault_reasons: List[str] = []
        self.cycle_count = 0

    def reset(self):
        """Hardware reset emulation (active-low rst_n = 0)."""
        self.state = self.STATE_NORMAL
        self.alarm_audio_en = False
        self.alarm_visual_en = False
        self.ack_active = False
        self.fault_reasons = []
        self.cycle_count = 0

    def evaluate_cycle(
        self,
        hr: Optional[float],
        spo2: Optional[float],
        rr: Optional[float],
        temp: Optional[float],
        data_valid: int = 1,
        ack_btn: bool = False
    ) -> Dict[str, Any]:
        """
        Executes one clock cycle evaluation matching the Verilog always blocks.
        """
        self.cycle_count += 1
        reasons = []

        # Check DATA_FAULT condition (data_valid == 0 or missing/null vitals)
        if (not data_valid) or (hr is None) or (spo2 is None) or (rr is None) or (temp is None):
            next_state = self.STATE_DATA_FAULT
            reasons.append("Sensor Disconnected or Invalid Telemetry (data_valid=0)")
        else:
            # Check CRITICAL conditions
            is_critical = False
            if hr < 40:
                is_critical = True
                reasons.append(f"Critical Bradycardia: Heart Rate {hr} bpm (< 40 bpm)")
            elif hr > 130:
                is_critical = True
                reasons.append(f"Critical Tachycardia: Heart Rate {hr} bpm (> 130 bpm)")

            if spo2 <= 85:
                is_critical = True
                reasons.append(f"Critical Hypoxemia: SpO2 {spo2}% (<= 85%)")

            if rr < 6:
                is_critical = True
                reasons.append(f"Critical Bradypnea: Respiratory Rate {rr} bpm (< 6 bpm)")
            elif rr > 30:
                is_critical = True
                reasons.append(f"Critical Tachypnea: Respiratory Rate {rr} bpm (> 30 bpm)")

            if temp < 34.0:
                is_critical = True
                reasons.append(f"Critical Severe Hypothermia: Temp {temp} °C (< 34.0 °C)")
            elif temp > 40.0:
                is_critical = True
                reasons.append(f"Critical Hyperpyrexia: Temp {temp} °C (> 40.0 °C)")

            if is_critical:
                next_state = self.STATE_CRITICAL
            else:
                # Check WARNING conditions
                is_warning = False
                if 40 <= hr < 50:
                    is_warning = True
                    reasons.append(f"Warning: Low Heart Rate {hr} bpm (50 bpm minimum)")
                elif 110 < hr <= 130:
                    is_warning = True
                    reasons.append(f"Warning: Elevated Heart Rate {hr} bpm (110 bpm maximum)")

                if 85 < spo2 < 90:
                    is_warning = True
                    reasons.append(f"Warning: Desaturation SpO2 {spo2}% (90% minimum)")

                if 6 <= rr < 10:
                    is_warning = True
                    reasons.append(f"Warning: Low Respiratory Rate {rr} bpm (10 bpm minimum)")
                elif 24 < rr <= 30:
                    is_warning = True
                    reasons.append(f"Warning: Tachypnea {rr} bpm (24 bpm maximum)")

                if 34.0 <= temp < 35.5:
                    is_warning = True
                    reasons.append(f"Warning: Mild Hypothermia {temp} °C (35.5 °C minimum)")
                elif 38.0 < temp <= 40.0:
                    is_warning = True
                    reasons.append(f"Warning: Pyrexia / Fever {temp} °C (38.0 °C maximum)")

                if is_warning:
                    next_state = self.STATE_WARNING
                else:
                    next_state = self.STATE_NORMAL

        self.state = next_state
        self.fault_reasons = reasons

        # Sequential ACK logic
        if ack_btn:
            self.ack_active = True
        elif next_state == self.STATE_NORMAL:
            self.ack_active = False

        # Output pin generation
        if next_state == self.STATE_NORMAL:
            self.alarm_visual_en = False
            self.alarm_audio_en = False
        else:
            self.alarm_visual_en = True
            # Audio is active unless acknowledged
            self.alarm_audio_en = not self.ack_active

        return {
            "state": self.state,
            "state_code": self.STATE_CODES[self.state],
            "alarm_audio_en": self.alarm_audio_en,
            "alarm_visual_en": self.alarm_visual_en,
            "ack_active": self.ack_active,
            "fault_reasons": self.fault_reasons,
            "cycle_count": self.cycle_count
        }
