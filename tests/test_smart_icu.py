"""
Comprehensive Unit and Integration Test Suite for Smart ICU Guardian.
Validates:
- SQLite Database operations, schema migrations, and patient locations (Ward, Room, Bed)
- Duplicate alert prevention for continuous events
- Separate tracking of Clinician Acknowledgement vs Condition Recovery/Resolution
- Physiological Vitals Generator & realistic clinical scenarios
- MPMC Architecture Simulator & instruction execution trace
- Verilog Safety Controller FSM (NORMAL, WARNING, CRITICAL, DATA_FAULT)
- Verilog Bridge toolchain transparency (never fakes native execution)
- Alert Manager & Web Audio API synthesizer
- Deterministic AI Clinical Explainer & offline fallback safety isolation
"""

import os
import sys
import pytest
import tempfile

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import (
    init_db,
    insert_reading,
    get_recent_readings,
    get_latest_reading,
    get_patients,
    get_patient_by_id,
    get_scenarios,
    log_alert,
    acknowledge_alert,
    resolve_patient_alerts,
    get_active_alerts,
    get_all_alerts,
    store_ai_explanation,
    get_latest_explanation
)
from services.vitals_generator import VitalSimulator, load_thresholds
from simulator.mpmc.mpmc_core import MPMCSimulator
from simulator.verilog.integration.behavioral_fsm import BehavioralSafetyController
from simulator.verilog.integration.verilog_bridge import VerilogSafetyBridge
from services.alert_manager import AlertManager
from services.ai_explainer import AIClinicalExplainer


# ==============================================================================
# Database Tests
# ==============================================================================
def test_database_init_and_locations():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        patients = get_patients(db_path)
        assert len(patients) >= 5
        # Verify location fields: Ward, Room, Bed
        p101 = next(p for p in patients if p["patient_id"] == "P101")
        assert p101["ward"] == "ICU-North"
        assert p101["room"] == "101"
        assert p101["bed"] == "Bed-A"

        p104 = next(p for p in patients if p["patient_id"] == "P104")
        assert p104["ward"] == "ICU-South"
        assert p104["room"] == "201"

        scenarios = get_scenarios(db_path)
        assert len(scenarios) >= 5
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_database_readings_and_alerts():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        # Insert reading
        rid = insert_reading(
            patient_id="P101",
            heart_rate=78.5,
            spo2=98.0,
            respiratory_rate=16.0,
            temperature=37.0,
            data_valid=1,
            db_path=db_path
        )
        assert rid is not None and rid > 0

        readings = get_recent_readings("P101", limit=10, db_path=db_path)
        assert len(readings) == 1
        assert readings[0]["heart_rate"] == 78.5

        # Log alert
        aid1 = log_alert(
            patient_id="P101",
            alert_type="PHYSIOLOGICAL",
            severity="CRITICAL",
            trigger_reason="SpO2 <= 85%",
            db_path=db_path
        )
        assert aid1 is not None and aid1 > 0

        # Test duplicate prevention for continuous event:
        # Logging another alert for same patient and same severity returns existing alert_id
        aid2 = log_alert(
            patient_id="P101",
            alert_type="PHYSIOLOGICAL",
            severity="CRITICAL",
            trigger_reason="SpO2 still <= 85%",
            db_path=db_path
        )
        assert aid1 == aid2, "Duplicate continuous alerts must be prevented"

        active = get_active_alerts("P101", db_path=db_path)
        assert len(active) == 1
        assert active[0]["acknowledged"] == 0
        assert active[0]["resolved"] == 0

        # Acknowledge alert: records acknowledgement separately from recovery
        acked = acknowledge_alert(aid1, db_path=db_path)
        assert acked is True

        active_after_ack = get_active_alerts("P101", db_path=db_path)
        # Alert remains visually active until resolution, but acknowledged = 1
        assert len(active_after_ack) == 1
        assert active_after_ack[0]["acknowledged"] == 1
        assert active_after_ack[0]["resolved"] == 0
        assert active_after_ack[0]["acknowledged_at"] is not None

        # Recovery: patient vitals normalize -> resolved
        resolve_count = resolve_patient_alerts("P101", db_path=db_path)
        assert resolve_count == 1

        active_after_resolve = get_active_alerts("P101", db_path=db_path)
        assert len(active_after_resolve) == 0

        # Store AI explanation
        eid = store_ai_explanation(
            alert_id=aid1,
            explanation_text="Hypoxia induced tachycardia",
            provider_status="DETERMINISTIC_FALLBACK",
            db_path=db_path
        )
        assert eid is not None and eid > 0

        exp_record = get_latest_explanation(aid1, db_path=db_path)
        assert exp_record is not None
        assert "Hypoxia" in exp_record["explanation_text"]
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


# ==============================================================================
# Threshold Configuration & Vitals Generator Tests
# ==============================================================================
def test_thresholds_loading():
    thresholds = load_thresholds()
    assert "heart_rate" in thresholds
    assert "spo2" in thresholds
    assert "respiratory_rate" in thresholds
    assert "temperature" in thresholds
    assert thresholds["heart_rate"]["critical_min"] == 40
    assert thresholds["heart_rate"]["critical_max"] == 130


def test_vitals_scenarios():
    sim = VitalSimulator()

    # Normal Recovery
    normal_v = sim.generate_reading("Normal Recovery", step=0)
    assert 60 <= normal_v.heart_rate <= 95
    assert normal_v.spo2 >= 95
    assert normal_v.data_valid == 1

    # Acute Hypoxia Progression
    hypoxia_v0 = sim.generate_reading("Acute Hypoxia", step=0)
    hypoxia_v20 = sim.generate_reading("Acute Hypoxia", step=20)
    assert hypoxia_v20.spo2 < hypoxia_v0.spo2
    assert hypoxia_v20.spo2 <= 85  # Crosses critical threshold
    assert hypoxia_v20.heart_rate > hypoxia_v0.heart_rate  # Compensatory tachycardia

    # Septic Shock (High Temp)
    septic_v = sim.generate_reading("Septic Shock", step=20)
    assert septic_v.temperature >= 40.0
    assert septic_v.heart_rate >= 130

    # Cardiac Bradycardia (Low HR)
    brady_v = sim.generate_reading("Cardiac Bradycardia", step=20)
    assert brady_v.heart_rate <= 40

    # Sensor Disconnection
    fault_v = sim.generate_reading("Sensor Disconnection", step=10)
    assert fault_v.data_valid == 0
    assert fault_v.heart_rate is None
    assert fault_v.oxygen_line_status == "DISCONNECTED"


# ==============================================================================
# MPMC Simulator Tests
# ==============================================================================
def test_mpmc_normal_execution():
    sim = MPMCSimulator()
    result = sim.run_full_cycle(hr=75.0, spo2=98.0, rr=16.0, temp=37.0, data_valid=1)
    assert result["state_name"] == "NORMAL"
    assert result["state_code"] == 0
    assert result["steps_count"] > 10
    assert len(result["trace"]) > 0
    # Trace items have required fields
    first_step = result["trace"][0]
    assert "step" in first_step
    assert "pc" in first_step
    assert "instruction" in first_step
    assert "explanation" in first_step


def test_mpmc_critical_tachycardia_execution():
    sim = MPMCSimulator()
    result = sim.run_full_cycle(hr=145.0, spo2=98.0, rr=16.0, temp=37.0, data_valid=1)
    assert result["state_name"] == "CRITICAL"
    assert result["state_code"] == 2
    # Verify jump to ALERT_CRITICAL
    trace_instructions = [t["instruction"] for t in result["trace"]]
    assert any("ALERT_CRITICAL" in instr for instr in trace_instructions)


def test_mpmc_data_fault_execution():
    sim = MPMCSimulator()
    result = sim.run_full_cycle(hr=None, spo2=None, rr=None, temp=None, data_valid=0)
    assert result["state_name"] == "DATA_FAULT"
    assert result["state_code"] == 3


# ==============================================================================
# Verilog Safety Controller FSM Tests
# ==============================================================================
def test_verilog_fsm_states():
    controller = BehavioralSafetyController()

    # 1. Normal state
    r1 = controller.evaluate_cycle(hr=75, spo2=98, rr=16, temp=37.0, data_valid=1)
    assert r1["state"] == "NORMAL"
    assert r1["alarm_audio_en"] is False
    assert r1["alarm_visual_en"] is False

    # 2. Warning state (mild tachycardia: HR=115)
    r2 = controller.evaluate_cycle(hr=115, spo2=98, rr=16, temp=37.0, data_valid=1)
    assert r2["state"] == "WARNING"
    assert r2["alarm_audio_en"] is True
    assert r2["alarm_visual_en"] is True

    # 3. Critical state (severe hypoxia: SpO2=82)
    r3 = controller.evaluate_cycle(hr=115, spo2=82, rr=16, temp=37.0, data_valid=1)
    assert r3["state"] == "CRITICAL"
    assert r3["alarm_audio_en"] is True
    assert r3["alarm_visual_en"] is True

    # 4. Clinician Acknowledgement
    r4 = controller.evaluate_cycle(hr=115, spo2=82, rr=16, temp=37.0, data_valid=1, ack_btn=True)
    assert r4["state"] == "CRITICAL"
    assert r4["ack_active"] is True
    assert r4["alarm_audio_en"] is False  # Audio silenced upon acknowledgement
    assert r4["alarm_visual_en"] is True   # Visual strobe remains active

    # 5. Data Fault
    r5 = controller.evaluate_cycle(hr=None, spo2=None, rr=None, temp=None, data_valid=0)
    assert r5["state"] == "DATA_FAULT"
    assert r5["alarm_visual_en"] is True


def test_verilog_bridge_transparency():
    bridge = VerilogSafetyBridge()
    status = bridge.get_engine_status()
    assert "engine_name" in status
    assert "description" in status

    # Ensure it never claims native execution when iverilog is absent
    if not bridge.has_native_iverilog:
        assert status["native_toolchain_available"] is False
        assert "Behavioral Twin" in status["engine_name"]

    eval_res = bridge.evaluate_vitals(75, 98, 16, 37.0)
    assert "engine_info" in eval_res
    assert eval_res["state"] == "NORMAL"


# ==============================================================================
# Alert Manager & Web Audio Synthesizer Tests
# ==============================================================================
def test_alert_manager_lifecycle():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        mgr = AlertManager("P101")

        # Normal state produces no active alarm
        res_norm = mgr.process_state("NORMAL", [])
        assert res_norm["has_unacknowledged"] is False

        # Transition to Critical
        res_crit = mgr.process_state("CRITICAL", ["SpO2 <= 85%"])
        assert res_crit["is_new_alarm"] is True
        assert res_crit["has_unacknowledged"] is True

        # Web Audio Player generation (Unacknowledged -> Repeating Audio)
        audio_html = AlertManager.generate_web_audio_player(
            severity="CRITICAL",
            is_active=True,
            is_acknowledged=False,
            audio_enabled=True
        )
        assert "AudioContext" in audio_html
        assert "setInterval" in audio_html
        assert "CRITICAL" in audio_html

        # Clinician Acknowledgement
        acked = mgr.acknowledge()
        assert acked is True

        # Web Audio Player generation (Acknowledged -> Silenced)
        audio_acked_html = AlertManager.generate_web_audio_player(
            severity="CRITICAL",
            is_active=True,
            is_acknowledged=True,
            audio_enabled=True
        )
        assert "Silenced (Acknowledged by Clinician)" in audio_acked_html

        # Patient Recovery back to Normal
        res_recov = mgr.process_state("NORMAL", [])
        assert res_recov["has_unacknowledged"] is False
        assert len(get_active_alerts("P101", db_path=db_path)) == 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


# ==============================================================================
# AI Clinical Explainer Tests (Deterministic Safety Isolation)
# ==============================================================================
def test_ai_explainer_fallback_deterministic():
    explainer = AIClinicalExplainer(api_key=None)  # Force offline fallback
    result = explainer.explain_alert(
        severity="CRITICAL",
        trigger_reasons=["Critical Hypoxemia: SpO2 81% (<= 85%)", "Critical Tachycardia: Heart Rate 135 bpm"],
        vitals={"heart_rate": 135, "spo2": 81, "respiratory_rate": 32, "temperature": 37.2, "data_valid": 1},
        patient_name="Test Patient",
        bed_id="BED-TEST"
    )
    assert result["provider_status"] == "DETERMINISTIC_FALLBACK"
    assert "Clinical Assessment: CRITICAL Telemetry Event" in result["explanation"]
    assert "hypoxemia" in result["explanation"].lower() or "hypoxia" in result["explanation"].lower()
    assert "Bedside Actions" in result["explanation"]
    assert "Determinism Guarantee" in result["explanation"]
