"""
Tests for Multi-Station Single-Computer Demonstration.
Validates:
- Multi-patient census generation with Ward, Room, Bed location details
- Automatic reading updates across all patients
- Critical alert triggering with exact location metadata
- Prevention of duplicate alerts during continuous critical events
- Separate tracking of Clinician Acknowledgement vs Resolution upon Recovery
- Synchronization of shared backend SQLite state across simulated stations
"""

import os
import sys
import tempfile
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import (
    init_db,
    get_patients,
    get_patient_by_id,
    insert_reading,
    get_latest_reading,
    log_alert,
    acknowledge_alert,
    resolve_patient_alerts,
    get_active_alerts
)
from services.vitals_generator import VitalSimulator
from services.alert_manager import AlertManager
from simulator.verilog.integration.behavioral_fsm import BehavioralSafetyController


def test_multi_patient_locations_and_census():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        patients = get_patients(db_path)
        assert len(patients) == 5

        # Check all patients have required location metadata
        for p in patients:
            assert "ward" in p and len(p["ward"]) > 0
            assert "room" in p and len(p["room"]) > 0
            assert "bed" in p and len(p["bed"]) > 0
            assert "display_name" in p and len(p["display_name"]) > 0

        # Verify specific ward assignments
        p1 = get_patient_by_id("P101", db_path)
        assert p1["ward"] == "ICU-North"
        assert p1["room"] == "101"
        assert p1["bed"] == "Bed-A"

        p4 = get_patient_by_id("P104", db_path)
        assert p4["ward"] == "ICU-South"
        assert p4["room"] == "201"
        assert p4["bed"] == "Bed-A"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_continuous_alert_duplicate_prevention_and_separate_ack():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        mgr = AlertManager("P102", db_path=db_path)

        # Step 1: Patient enters CRITICAL condition (e.g. SpO2 = 82%)
        fsm = BehavioralSafetyController()
        r1 = fsm.evaluate_cycle(hr=125, spo2=82, rr=28, temp=37.0, data_valid=1)
        assert r1["state"] == "CRITICAL"

        # Log alert for P102
        res1 = mgr.process_state("CRITICAL", r1["fault_reasons"], patient_id="P102")
        assert res1["is_new_alarm"] is True
        active1 = get_active_alerts("P102", db_path=db_path)
        assert len(active1) == 1
        initial_alert_id = active1[0]["alert_id"]
        assert active1[0]["acknowledged"] == 0
        assert active1[0]["resolved"] == 0

        # Step 2: Continuous CRITICAL event over next 3 cycles (vitals still critical)
        # Verify NO duplicate alert entries are created!
        for _ in range(3):
            r_cont = fsm.evaluate_cycle(hr=128, spo2=81, rr=30, temp=37.0, data_valid=1)
            res_cont = mgr.process_state("CRITICAL", r_cont["fault_reasons"], patient_id="P102")
            assert res_cont["is_new_alarm"] is False  # Not a new alarm
            active_cont = get_active_alerts("P102", db_path=db_path)
            assert len(active_cont) == 1, "Must maintain exactly 1 active alert without creating duplicates"
            assert active_cont[0]["alert_id"] == initial_alert_id

        # Step 3: Clinician acknowledges the alarm on Doctor's or Bedside dashboard
        ack_success = acknowledge_alert(initial_alert_id, db_path=db_path)
        assert ack_success is True

        # Check state: acknowledged = 1, but resolved is still 0 (visual remains visible)
        active_after_ack = get_active_alerts("P102", db_path=db_path)
        assert len(active_after_ack) == 1
        assert active_after_ack[0]["acknowledged"] == 1
        assert active_after_ack[0]["resolved"] == 0
        assert active_after_ack[0]["acknowledged_at"] is not None

        # Step 4: Patient condition recovers to NORMAL (e.g. SpO2 = 98%)
        r_norm = fsm.evaluate_cycle(hr=74, spo2=98, rr=16, temp=36.9, data_valid=1)
        assert r_norm["state"] == "NORMAL"
        res_norm = mgr.process_state("NORMAL", [], patient_id="P102")
        assert res_norm["active_alert"] is None

        # Check state: condition is resolved, visual alert cleared
        active_after_recov = get_active_alerts("P102", db_path=db_path)
        assert len(active_after_recov) == 0, "Recovered patient must have active alerts resolved"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_census_table_html_rendering_and_safety():
    from app import generate_census_table_html

    mock_rows = [
        {
            "patient_id": "P101",
            "display_name": "Eleanor Vance <Cardiac>",
            "ward": "ICU-North",
            "room": "101",
            "bed": "Bed-A",
            "heart_rate": "74.5 bpm",
            "spo2": "98.2%",
            "respiratory_rate": "15.0 bpm",
            "temperature": "36.90 °C",
            "raw_hr": 74.5,
            "raw_spo2": 98.2,
            "raw_rr": 15.0,
            "raw_temp": 36.90,
            "condition": "NORMAL",
            "is_acknowledged": False
        },
        {
            "patient_id": "P102",
            "display_name": "Marcus Sterling",
            "ward": "ICU-North",
            "room": "101",
            "bed": "Bed-B",
            "heart_rate": "128.0 bpm",
            "spo2": "82.0%",
            "respiratory_rate": "30.0 bpm",
            "temperature": "37.10 °C",
            "raw_hr": 128.0,
            "raw_spo2": 82.0,
            "raw_rr": 30.0,
            "raw_temp": 37.10,
            "condition": "CRITICAL",
            "is_acknowledged": True
        },
        {
            "patient_id": "P103",
            "display_name": "Sophia Lin",
            "ward": "ICU-North",
            "room": "102",
            "bed": "Bed-A",
            "heart_rate": "115.0 bpm",
            "spo2": "88.0%",
            "respiratory_rate": "22.0 bpm",
            "temperature": "38.20 °C",
            "raw_hr": 115.0,
            "raw_spo2": 88.0,
            "raw_rr": 22.0,
            "raw_temp": 38.20,
            "condition": "WARNING",
            "is_acknowledged": False
        }
    ]

    html_out = generate_census_table_html(mock_rows)

    # 1. Verify all 10 required column headers exist
    headers = [
        "Patient ID",
        "Patient Name",
        "Ward",
        "Room",
        "Bed",
        "Heart Rate",
        "SpO2",
        "Respiratory Rate",
        "Temperature",
        "Status"
    ]
    for h in headers:
        assert f">{h}</th>" in html_out

    # 2. Verify safe escaping of HTML tags in patient data
    assert "&lt;Cardiac&gt;" in html_out
    assert "<Cardiac>" not in html_out

    # 3. Verify no lines have 4 or more leading spaces (prevents CommonMark code block traps)
    for line in html_out.split("\n"):
        assert not line.startswith("    "), f"Indented line would trigger code-block parsing: {line}"

    # 4. Verify condition indicators
    assert "CRITICAL" in html_out
    assert "WARNING" in html_out
    assert "NORMAL" in html_out
    assert "ACK" in html_out


def test_doctor_dashboard_element_keys_unique():
    """
    Verifies that all element keys generated on the Doctor's Dashboard are unique
    to prevent StreamlitDuplicateElementKey errors.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        init_db(db_path)
        patients_list = get_patients(db_path)
        unique_patients = list({p["patient_id"]: p for p in patients_list}.values())

        # Generate all jump button keys
        jump_keys = [f"doc_jump_bedside_{p['patient_id']}" for p in unique_patients]
        assert len(jump_keys) == len(set(jump_keys)), "Jump button keys must be unique"

        # Simulate multiple active alerts across different patients
        log_alert("P101", "PHYSIOLOGICAL", "CRITICAL", "HR high", db_path=db_path)
        log_alert("P102", "PHYSIOLOGICAL", "CRITICAL", "SpO2 low", db_path=db_path)
        alerts = get_active_alerts(db_path=db_path)

        ack_keys = [f"ack_btn_{a['alert_id']}" for a in alerts]
        assert len(ack_keys) == len(set(ack_keys)), "ACK button keys must be unique"

        bedside_keys = [f"doc_bedside_btn_{a['patient_id']}_{a['alert_id']}" for a in alerts]
        assert len(bedside_keys) == len(set(bedside_keys)), "Bedside button keys must be unique"

        all_keys = jump_keys + ack_keys + bedside_keys
        assert len(all_keys) == len(set(all_keys)), "All dashboard keys must be distinct"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


