"""
Smart ICU Guardian - Integrated Multi-Page Telemetry System
Includes:
- Page 1: Doctor's Dashboard (Multi-patient central telemetry, location tracking, repeating alarm, ACK)
- Page 2: Bedside Dashboard (Single-patient high-visibility monitor, clinical explanation, no engineering clutter)
- Page 3: Engineering Dashboard (MPMC simulator & trace, Verilog safety FSM, hardware status, SQLite logs)
"""

import os
import sys
import html
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import (
    init_db,
    insert_reading,
    get_recent_readings,
    get_latest_reading,
    get_patients,
    get_patient_by_id,
    update_patient_scenario,
    get_scenarios,
    get_all_alerts,
    get_active_alerts,
    acknowledge_alert,
    resolve_patient_alerts,
    store_ai_explanation,
    get_latest_explanation
)
from services.vitals_generator import VitalSimulator
from services.alert_manager import AlertManager
from services.ai_explainer import AIClinicalExplainer
from simulator.mpmc.mpmc_core import MPMCSimulator
from simulator.verilog.integration.verilog_bridge import VerilogSafetyBridge

# Initialize database schema and seeds
init_db()

# Page Configuration
st.set_page_config(
    page_title="Smart ICU Guardian",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Shared CSS Styles
st.markdown("""
<style>
    /* Global Clean ICU Styling */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .top-header {
        font-size: 24px;
        font-weight: 800;
        color: #38bdf8;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 2px;
    }
    .top-subheader {
        font-size: 13px;
        color: #94a3b8;
        margin-bottom: 12px;
    }
    .edu-banner {
        background: #0f172a;
        border-left: 4px solid #38bdf8;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 14px;
    }
    /* Critical Alert Callout Banner */
    .alert-card-critical {
        background: linear-gradient(90deg, #7f1d1d 0%, #991b1b 100%);
        border: 2px solid #ef4444;
        border-radius: 8px;
        padding: 14px 18px;
        color: white;
        margin-bottom: 15px;
        box-shadow: 0 4px 14px 0 rgba(239, 68, 68, 0.4);
    }
    .alert-card-warning {
        background: linear-gradient(90deg, #78350f 0%, #92400e 100%);
        border: 2px solid #f59e0b;
        border-radius: 8px;
        padding: 14px 18px;
        color: white;
        margin-bottom: 15px;
    }
    .alert-card-fault {
        background: linear-gradient(90deg, #4c1d95 0%, #5b21b6 100%);
        border: 2px solid #a855f7;
        border-radius: 8px;
        padding: 14px 18px;
        color: white;
        margin-bottom: 15px;
    }
    /* Bedside Telemetry Display */
    .bedside-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px 16px;
        text-align: center;
        margin-bottom: 12px;
    }
    .bedside-num {
        font-size: 52px;
        font-weight: 900;
        font-family: monospace;
        line-height: 1.1;
    }
    .bedside-unit {
        font-size: 16px;
        color: #94a3b8;
        font-weight: 600;
    }
    .bedside-title {
        font-size: 14px;
        text-transform: uppercase;
        font-weight: 700;
        color: #cbd5e1;
        margin-bottom: 6px;
    }
    .bedside-range {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
    }
    /* Condition Badges */
    .cond-normal {
        background: #065f46;
        color: #a7f3d0;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        display: inline-block;
    }
    .cond-warning {
        background: #92400e;
        color: #fde68a;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        display: inline-block;
    }
    .cond-critical {
        background: #991b1b;
        color: #fecaca;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        display: inline-block;
        animation: pulse 1.5s infinite;
    }
    .cond-fault {
        background: #5b21b6;
        color: #e9d5ff;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        display: inline-block;
    }
    /* Doctor Table Highlight */
    .patient-row-critical {
        background: rgba(239, 68, 68, 0.15) !important;
        border-left: 6px solid #ef4444 !important;
    }
    .patient-row-warning {
        background: rgba(245, 158, 11, 0.1) !important;
        border-left: 6px solid #f59e0b !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "sim_step" not in st.session_state:
    st.session_state.sim_step = 0
if "auto_stream" not in st.session_state:
    st.session_state.auto_stream = True
if "stream_speed" not in st.session_state:
    st.session_state.stream_speed = 2.0
if "vitals_simulator" not in st.session_state:
    st.session_state.vitals_simulator = VitalSimulator()
if "verilog_bridge" not in st.session_state:
    st.session_state.verilog_bridge = VerilogSafetyBridge()
if "mpmc_simulator" not in st.session_state:
    st.session_state.mpmc_simulator = MPMCSimulator()
if "alert_manager" not in st.session_state:
    st.session_state.alert_manager = AlertManager()
if "ai_explainer" not in st.session_state:
    st.session_state.ai_explainer = AIClinicalExplainer()
if "audio_enabled" not in st.session_state:
    st.session_state.audio_enabled = True

# -----------------------------------------------------------------------------
# Shared Telemetry Cycle Step Function
# Evaluates and updates all patients in SQLite
# -----------------------------------------------------------------------------
def run_telemetry_tick(step_num: int, custom_overrides: Optional[Dict[str, Any]] = None):
    """
    Simulates vital signs for all registered patients, executes Verilog safety FSM,
    records readings in SQLite, and synchronizes clinical alarms.
    """
    patients_list = get_patients()
    for p in patients_list:
        pid = p["patient_id"]
        # Allow interactive overrides only for P101 if selected
        overrides = custom_overrides if pid == "P101" and p.get("current_scenario") == "Interactive Custom" else None
        reading = st.session_state.vitals_simulator.generate_patient_reading(
            patient=p,
            step=step_num,
            custom_overrides=overrides
        )

        # Evaluate safety state via deterministic Verilog Safety Controller
        fsm_eval = st.session_state.verilog_bridge.evaluate_vitals(
            hr=reading.heart_rate,
            spo2=reading.spo2,
            rr=reading.respiratory_rate,
            temp=reading.temperature,
            data_valid=reading.data_valid
        )
        severity = fsm_eval["state"]
        reasons = fsm_eval["fault_reasons"]

        # Insert reading into SQLite
        insert_reading(
            patient_id=pid,
            heart_rate=reading.heart_rate,
            spo2=reading.spo2,
            respiratory_rate=reading.respiratory_rate,
            temperature=reading.temperature,
            oxygen_line_status=reading.oxygen_line_status,
            data_valid=reading.data_valid
        )

        # Process alert state (prevents duplicates, records ack separately from resolution)
        alert_result = st.session_state.alert_manager.process_state(
            severity=severity,
            trigger_reasons=reasons,
            patient_id=pid
        )

        # If a new alert was created, generate AI clinical explanation
        act_alert = alert_result.get("active_alert")
        if act_alert and alert_result.get("is_new_alarm"):
            explanation_data = st.session_state.ai_explainer.explain_alert(
                severity=severity,
                trigger_reasons=reasons,
                vitals={
                    "heart_rate": reading.heart_rate,
                    "spo2": reading.spo2,
                    "respiratory_rate": reading.respiratory_rate,
                    "temperature": reading.temperature,
                    "data_valid": reading.data_valid
                },
                patient_name=p["display_name"],
                bed_id=f"{p['ward']}-{p['room']}-{p['bed']}"
            )
            store_ai_explanation(
                alert_id=act_alert["alert_id"],
                explanation_text=explanation_data["explanation"],
                provider_status=explanation_data["provider_status"]
            )


# -----------------------------------------------------------------------------
# Query Parameters & Page Routing
# Supports separate browser tabs on the same computer!
# -----------------------------------------------------------------------------
query_params = st.query_params
current_page_query = query_params.get("page", "doctor").lower()
selected_bedside_patient_query = query_params.get("patient_id", "P101")

# Sidebar Navigation
st.sidebar.markdown("## 🏥 Smart ICU Guardian")
PAGE_OPTIONS = {
    "doctor": "🩺 Doctor's Dashboard",
    "bedside": "🛌 Bedside Dashboard",
    "engineering": "⚙️ Engineering Dashboard"
}

# Determine default radio index based on query parameter
page_keys = list(PAGE_OPTIONS.keys())
default_index = page_keys.index(current_page_query) if current_page_query in page_keys else 0

selected_page_key = st.sidebar.radio(
    "Select Station View",
    options=page_keys,
    format_func=lambda k: PAGE_OPTIONS[k],
    index=default_index
)

# Keep query parameter in sync for easy multi-tab sharing
if selected_page_key != current_page_query:
    st.query_params["page"] = selected_page_key
    st.rerun()

st.sidebar.markdown("---")

# Global Telemetry Simulation Controller (Shared across all tabs)
st.sidebar.markdown("### ⏱️ Shared Telemetry Engine")
col_t1, col_t2 = st.sidebar.columns(2)
if col_t1.button("⏸ Pause" if st.session_state.auto_stream else "▶ Stream", key="global_stream_toggle_btn", use_container_width=True):
    st.session_state.auto_stream = not st.session_state.auto_stream
    st.rerun()

if col_t2.button("⏭ Step", key="global_step_btn", use_container_width=True):
    st.session_state.sim_step += 1
    run_telemetry_tick(st.session_state.sim_step)
    st.rerun()

st.session_state.stream_speed = st.sidebar.slider("Stream Tick Interval (s)", min_value=1.0, max_value=4.0, value=2.0, step=0.5)
st.session_state.audio_enabled = st.sidebar.toggle("Enable Alarm Audio", value=st.session_state.audio_enabled)

st.sidebar.markdown("---")
st.sidebar.caption("Educational Telemetry Prototype • Multi-Station Demonstration")


# =============================================================================
# Helper: Census Table HTML Generator (Clean, Unindented, Safely Escaped)
# =============================================================================
def generate_census_table_html(census_rows: List[Dict[str, Any]]) -> str:
    """
    Constructs clean, unindented HTML for the Doctor's Dashboard patient table.
    Columns: Patient ID, Patient Name, Ward, Room, Bed, Heart Rate, SpO2, Respiratory Rate, Temperature, Status.
    All data is safely escaped with html.escape to prevent injection and formatting corruption.
    """
    lines = [
        '<div style="overflow-x:auto; margin-bottom:20px; border-radius:8px; border:1px solid #334155;">',
        '<table style="width:100%; border-collapse:collapse; font-size:13px; text-align:left; background:#1e293b; color:#f8fafc;">',
        '<thead>',
        '<tr style="background:#0f172a; color:#94a3b8; border-bottom:2px solid #334155; text-transform:uppercase; font-size:12px; letter-spacing:0.5px;">',
        '<th style="padding:12px 10px;">Patient ID</th>',
        '<th style="padding:12px 10px;">Patient Name</th>',
        '<th style="padding:12px 10px;">Ward</th>',
        '<th style="padding:12px 10px;">Room</th>',
        '<th style="padding:12px 10px;">Bed</th>',
        '<th style="padding:12px 10px;">Heart Rate</th>',
        '<th style="padding:12px 10px;">SpO2</th>',
        '<th style="padding:12px 10px;">Respiratory Rate</th>',
        '<th style="padding:12px 10px;">Temperature</th>',
        '<th style="padding:12px 10px;">Status</th>',
        '</tr>',
        '</thead>',
        '<tbody>'
    ]

    for row in census_rows:
        sev = str(row.get("condition", "NORMAL")).upper()
        is_acked = bool(row.get("is_acknowledged", False))

        safe_pid = html.escape(str(row.get("patient_id", "--")))
        safe_name = html.escape(str(row.get("display_name", "--")))
        safe_ward = html.escape(str(row.get("ward", "--")))
        safe_room = html.escape(str(row.get("room", "--")))
        safe_bed = html.escape(str(row.get("bed", "--")))
        safe_hr = html.escape(str(row.get("heart_rate", "--")))
        safe_spo2 = html.escape(str(row.get("spo2", "--")))
        safe_rr = html.escape(str(row.get("respiratory_rate", "--")))
        safe_temp = html.escape(str(row.get("temperature", "--")))

        # Colors and badges based on severity
        if sev in ("CRITICAL", "DATA_FAULT"):
            row_style = "background-color: rgba(239, 68, 68, 0.16); border-left: 6px solid #ef4444;"
            badge_color = "#991b1b"
            badge_text_color = "#fecaca"
            badge_border = "#ef4444"
            badge_icon = "🚨 "
        elif sev == "WARNING":
            row_style = "background-color: rgba(245, 158, 11, 0.12); border-left: 6px solid #f59e0b;"
            badge_color = "#92400e"
            badge_text_color = "#fde68a"
            badge_border = "#f59e0b"
            badge_icon = "⚠️ "
        else:
            row_style = "background-color: rgba(15, 23, 42, 0.6); border-left: 6px solid #10b981;"
            badge_color = "#065f46"
            badge_text_color = "#a7f3d0"
            badge_border = "#10b981"
            badge_icon = "✅ "

        badge_html = f'<span style="background-color:{badge_color}; color:{badge_text_color}; border:1px solid {badge_border}; padding:4px 8px; border-radius:6px; font-weight:700; font-size:12px; display:inline-block;">{badge_icon}{sev}</span>'
        if is_acked:
            badge_html += ' <span style="background-color:#065f46; color:#a7f3d0; padding:2px 6px; border-radius:4px; font-size:11px; margin-left:4px; font-weight:600;">ACK</span>'

        # Vital text coloring
        hr_raw = row.get("raw_hr")
        spo2_raw = row.get("raw_spo2")
        rr_raw = row.get("raw_rr")
        temp_raw = row.get("raw_temp")

        hr_color = "#ef4444" if (hr_raw is not None and (hr_raw < 40 or hr_raw > 130)) else "#f59e0b" if (hr_raw is not None and (hr_raw < 50 or hr_raw > 110)) else "#38bdf8"
        spo2_color = "#ef4444" if (spo2_raw is not None and spo2_raw <= 85) else "#f59e0b" if (spo2_raw is not None and spo2_raw < 90) else "#10b981"
        rr_color = "#ef4444" if (rr_raw is not None and (rr_raw < 6 or rr_raw > 30)) else "#f59e0b" if (rr_raw is not None and (rr_raw < 10 or rr_raw > 24)) else "#a855f7"
        temp_color = "#ef4444" if (temp_raw is not None and (temp_raw < 34.0 or temp_raw > 40.0)) else "#f59e0b" if (temp_raw is not None and (temp_raw < 35.5 or temp_raw > 38.0)) else "#f97316"

        lines.append(f'<tr style="{row_style} border-bottom:1px solid #334155;">')
        lines.append(f'<td style="padding:12px 10px; font-weight:700; font-family:monospace; color:#38bdf8;">{safe_pid}</td>')
        lines.append(f'<td style="padding:12px 10px; font-weight:600; color:#f8fafc;">{safe_name}</td>')
        lines.append(f'<td style="padding:12px 10px; color:#cbd5e1;">{safe_ward}</td>')
        lines.append(f'<td style="padding:12px 10px; color:#cbd5e1;">{safe_room}</td>')
        lines.append(f'<td style="padding:12px 10px; color:#cbd5e1;">{safe_bed}</td>')
        lines.append(f'<td style="padding:12px 10px; font-weight:700; font-family:monospace; color:{hr_color};">{safe_hr}</td>')
        lines.append(f'<td style="padding:12px 10px; font-weight:700; font-family:monospace; color:{spo2_color};">{safe_spo2}</td>')
        lines.append(f'<td style="padding:12px 10px; font-weight:700; font-family:monospace; color:{rr_color};">{safe_rr}</td>')
        lines.append(f'<td style="padding:12px 10px; font-weight:700; font-family:monospace; color:{temp_color};">{safe_temp}</td>')
        lines.append(f'<td style="padding:12px 10px;">{badge_html}</td>')
        lines.append('</tr>')

    lines.append('</tbody>')
    lines.append('</table>')
    lines.append('</div>')
    return "\n".join(lines)


# =============================================================================
# PAGE 1: DOCTOR'S DASHBOARD
# =============================================================================
def render_doctor_dashboard():
    st.markdown('<div class="top-header">🩺 ICU Central Doctor\'s Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="top-subheader">Multi-Patient Clinical Telemetry Station &bull; '
        f'Active ICU Beds: <strong>5</strong> &bull; '
        f'Last Global Update: <code>{datetime.now().strftime("%H:%M:%S")}</code> (Cycle #{st.session_state.sim_step})</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="edu-banner">
        <strong>Academic Prototype:</strong> All vitals and clinical telemetry are simulated.
        Patient safety state is determined deterministically by the Verilog Safety FSM.
    </div>
    """, unsafe_allow_html=True)

    # 1. Active Emergency Alerts Callout & Audible Alarm
    active_alerts = get_active_alerts()
    critical_alerts = [a for a in active_alerts if a["severity"] in ("CRITICAL", "DATA_FAULT")]
    warning_alerts = [a for a in active_alerts if a["severity"] == "WARNING"]

    # Check if there are unacknowledged critical alerts requiring audible alarm
    has_unack_critical = any(a["acknowledged"] == 0 for a in critical_alerts)
    has_unack_warning = any(a["acknowledged"] == 0 for a in warning_alerts)

    # Play repeating audible alarm if unacknowledged
    if has_unack_critical:
        audio_html = AlertManager.generate_web_audio_player(
            severity="CRITICAL",
            is_active=True,
            is_acknowledged=False,
            audio_enabled=st.session_state.audio_enabled
        )
        st.components.v1.html(audio_html, height=75)
    elif has_unack_warning:
        audio_html = AlertManager.generate_web_audio_player(
            severity="WARNING",
            is_active=True,
            is_acknowledged=False,
            audio_enabled=st.session_state.audio_enabled
        )
        st.components.v1.html(audio_html, height=75)

    # Display Active Alerts Banner
    if active_alerts:
        for alert in active_alerts:
            sev = alert["severity"]
            card_class = "alert-card-critical" if sev in ("CRITICAL", "DATA_FAULT") else "alert-card-warning"
            is_acked = bool(alert["acknowledged"] == 1)
            ack_badge = f'<span style="background:#065f46; color:#a7f3d0; padding:2px 8px; border-radius:4px; font-size:12px; margin-left:8px;">ACKNOWLEDGED by Clinician ({alert.get("acknowledged_at", "Recorded")})</span>' if is_acked else '<span style="background:#dc2626; color:white; padding:2px 8px; border-radius:4px; font-size:12px; margin-left:8px; animation:blink 1s infinite;">UNACKNOWLEDGED</span>'

            col_a1, col_a2 = st.columns([4, 1])
            with col_a1:
                alert_card_lines = [
                    f'<div class="{card_class}">',
                    f'<div style="font-size: 16px; font-weight: 800; display:flex; align-items:center; justify-content:space-between;">',
                    f'<span>🚨 {html.escape(sev)} ALARM: Patient {html.escape(str(alert["patient_id"]))} - {html.escape(str(alert["display_name"]))} {ack_badge}</span>',
                    f'<span style="font-size:13px; font-weight:600;">{html.escape(str(alert["timestamp"]))}</span>',
                    f'</div>',
                    f'<div style="margin-top: 6px; font-size: 14px;">',
                    f'<strong>Exact Location:</strong> Ward <code>{html.escape(str(alert["ward"]))}</code> &bull; Room <code>{html.escape(str(alert["room"]))}</code> &bull; Bed <code>{html.escape(str(alert["bed"]))}</code> ({html.escape(str(alert["bed_id"]))})',
                    f'</div>',
                    f'<div style="margin-top: 4px; font-size: 13px; background: rgba(0,0,0,0.25); padding: 6px 10px; border-radius: 4px;">',
                    f'<strong>Trigger Reason:</strong> {html.escape(str(alert["trigger_reason"]))}',
                    f'</div>',
                    f'<div style="margin-top: 4px; font-size: 11px; opacity: 0.85;">',
                    f'<em>Visual alert remains active until the patient condition is resolved in SQLite. Acknowledgement silences audio.</em>',
                    f'</div>',
                    f'</div>'
                ]
                alert_card_html = "\n".join(alert_card_lines)
                if hasattr(st, "html"):
                    st.html(alert_card_html)
                else:
                    st.markdown(alert_card_html, unsafe_allow_html=True)
            with col_a2:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                if not is_acked:
                    if st.button(f"🔔 ACK ALARM\n({alert['patient_id']})", key=f"ack_btn_{alert['alert_id']}", use_container_width=True, type="primary"):
                        acknowledge_alert(alert["alert_id"])
                        st.rerun()
                else:
                    st.info("Audio Silenced")
                    if st.button(f"👁️ View Bedside", key=f"doc_bedside_btn_{alert['patient_id']}_{alert['alert_id']}", use_container_width=True):
                        st.query_params["page"] = "bedside"
                        st.query_params["patient_id"] = alert["patient_id"]
                        st.rerun()

    # 2. Multi-Patient Telemetry Table
    st.markdown("### 📋 ICU Inpatient Telemetry Census")

    patients_list = get_patients()
    census_rows = []
    
    for p in patients_list:
        pid = p["patient_id"]
        latest = get_latest_reading(pid)
        p_alerts = get_active_alerts(pid)
        active_sev = p_alerts[0]["severity"] if p_alerts else "NORMAL"
        is_p_acked = bool(p_alerts and p_alerts[0]["acknowledged"] == 1)

        raw_hr = latest['heart_rate'] if latest and latest['heart_rate'] is not None else None
        raw_spo2 = latest['spo2'] if latest and latest['spo2'] is not None else None
        raw_rr = latest['respiratory_rate'] if latest and latest['respiratory_rate'] is not None else None
        raw_temp = latest['temperature'] if latest and latest['temperature'] is not None else None

        hr = f"{raw_hr:.1f} bpm" if raw_hr is not None else "--"
        spo2 = f"{raw_spo2:.1f}%" if raw_spo2 is not None else "--"
        rr = f"{raw_rr:.1f} bpm" if raw_rr is not None else "--"
        temp = f"{raw_temp:.2f} °C" if raw_temp is not None else "--"

        census_rows.append({
            "patient_id": pid,
            "display_name": p["display_name"],
            "ward": p["ward"],
            "room": p["room"],
            "bed": p["bed"],
            "heart_rate": hr,
            "spo2": spo2,
            "respiratory_rate": rr,
            "temperature": temp,
            "raw_hr": raw_hr,
            "raw_spo2": raw_spo2,
            "raw_rr": raw_rr,
            "raw_temp": raw_temp,
            "condition": active_sev,
            "is_acknowledged": is_p_acked,
            "has_active_alert": bool(p_alerts)
        })

    # Render clean HTML Table via Streamlit st.html
    table_html = generate_census_table_html(census_rows)
    if hasattr(st, "html"):
        st.html(table_html)
    else:
        st.markdown(table_html, unsafe_allow_html=True)

    # Quick Bedside Patient Direct Jump
    st.markdown("#### 🛌 Switch Current View to Bedside Patient")
    unique_patients = list({p["patient_id"]: p for p in patients_list}.values())
    if unique_patients:
        p_cols = st.columns(len(unique_patients))
        for i, p in enumerate(unique_patients):
            if p_cols[i].button(
                f"{p['patient_id']}\n{p['ward']}-{p['room']}",
                key=f"doc_jump_bedside_{p['patient_id']}",
                use_container_width=True
            ):
                st.query_params["page"] = "bedside"
                st.query_params["patient_id"] = p["patient_id"]
                st.rerun()


# =============================================================================
# PAGE 2: BEDSIDE DASHBOARD
# =============================================================================
def render_bedside_dashboard():
    patients_list = get_patients()
    patient_ids = [p["patient_id"] for p in patients_list]

    # Bedside Patient Selector
    st.sidebar.markdown("### 🛌 Bedside Station Selector")
    current_pid = (
        st.query_params.get("patient_id", "P101")
    )

    if current_pid not in patient_ids:
        current_pid = patient_ids[0] if patient_ids else None

    if not patient_ids:
        st.warning("No patients are available.")
        return

    if "bedside_patient_selector" not in st.session_state:
        st.session_state.bedside_patient_selector = current_pid

    chosen_pid = st.sidebar.selectbox(
        "Select Bedside Patient",
        options=patient_ids,
        format_func=lambda pid: (
            f"{pid} - {get_patient_by_id(pid)['display_name']} "
            f"({get_patient_by_id(pid)['ward']}-"
            f"{get_patient_by_id(pid)['bed']})"
        ),
        key="bedside_patient_selector",
    )

    if st.session_state.bedside_patient_selector != st.query_params.get("patient_id"):
       st.query_params["patient_id"] = st.session_state.bedside_patient_selector
    patient = get_patient_by_id(chosen_pid)
    latest_reading = get_latest_reading(chosen_pid)
    active_alerts = get_active_alerts(chosen_pid)
    active_alert = active_alerts[0] if active_alerts else None
    current_condition = active_alert["severity"] if active_alert else "NORMAL"
    is_acknowledged = bool(active_alert and active_alert["acknowledged"] == 1)

    # Bedside Header
    st.markdown('<div class="top-header">🛌 Bedside Telemetry Monitor</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="top-subheader">Location: <strong>Ward {patient["ward"]}</strong> &bull; '
        f'Room: <strong>{patient["room"]}</strong> &bull; '
        f'Bed: <strong>{patient["bed"]}</strong> &bull; '
        f'Patient: <strong>{patient["display_name"]}</strong> (ID: <code>{patient["patient_id"]}</code>) &bull; '
        f'Time: <code>{latest_reading["timestamp"] if latest_reading else datetime.now().strftime("%H:%M:%S")}</code></div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="edu-banner">
        <strong>Bedside Telemetry Monitor:</strong> Real-time clinical parameters for bedside nursing care.
        This display is dedicated strictly to clinical vitals and physiological explanations.
    </div>
    """, unsafe_allow_html=True)

    # Condition & Acknowledge Banner
    cond_class_map = {
        "NORMAL": "cond-normal",
        "WARNING": "cond-warning",
        "CRITICAL": "cond-critical",
        "DATA_FAULT": "cond-fault"
    }

    col_stat1, col_stat2 = st.columns([4, 1])
    with col_stat1:
        if current_condition == "NORMAL":
            st.markdown(f'<div style="font-size:20px; font-weight:800; padding:10px 0;">Condition: <span class="{cond_class_map[current_condition]}">✅ PATIENT STABLE (NORMAL)</span></div>', unsafe_allow_html=True)
        elif current_condition == "WARNING":
            st.markdown(f'<div style="font-size:20px; font-weight:800; padding:10px 0;">Condition: <span class="{cond_class_map[current_condition]}">⚠️ WARNING &bull; Parameter Deviation</span></div>', unsafe_allow_html=True)
        elif current_condition == "CRITICAL":
            ack_tag = " [ACKNOWLEDGED]" if is_acknowledged else " [UNACKNOWLEDGED]"
            st.markdown(f'<div style="font-size:20px; font-weight:800; padding:10px 0;">Condition: <span class="{cond_class_map[current_condition]}">🚨 CRITICAL ALARM{ack_tag}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size:20px; font-weight:800; padding:10px 0;">Condition: <span class="{cond_class_map[current_condition]}">⚡ DATA FAULT &bull; Transducer Disconnected</span></div>', unsafe_allow_html=True)

    with col_stat2:
        if active_alert and not is_acknowledged:
            if st.button("🔔 ACK ALARM", key=f"bedside_ack_btn_{chosen_pid}_{active_alert['alert_id']}", use_container_width=True, type="primary"):
                acknowledge_alert(active_alert["alert_id"])
                st.session_state.alert_manager.acknowledge(active_alert["alert_id"])
                st.rerun()
        elif is_acknowledged:
            st.success("Alarm Acknowledged")

    # Audible alarm at bedside
    if active_alert and not is_acknowledged:
        bedside_audio = AlertManager.generate_web_audio_player(
            severity=current_condition,
            is_active=True,
            is_acknowledged=is_acknowledged,
            audio_enabled=st.session_state.audio_enabled
        )
        st.components.v1.html(bedside_audio, height=75)

    # Large Readable Vitals Cards (4 Columns)
    col1, col2, col3, col4 = st.columns(4)

    hr_val = latest_reading["heart_rate"] if latest_reading else 75.0
    spo2_val = latest_reading["spo2"] if latest_reading else 98.0
    rr_val = latest_reading["respiratory_rate"] if latest_reading else 16.0
    temp_val = latest_reading["temperature"] if latest_reading else 37.0

    # Heart Rate Color
    hr_color = "#ef4444" if (hr_val is not None and (hr_val < 40 or hr_val > 130)) else "#f59e0b" if (hr_val is not None and (hr_val < 50 or hr_val > 110)) else "#38bdf8"
    with col1:
        st.markdown(f"""
        <div class="bedside-card">
            <div class="bedside-title">Heart Rate (ECG)</div>
            <div class="bedside-num" style="color: {hr_color};">{f"{hr_val:.1f}" if hr_val is not None else "--"}</div>
            <div class="bedside-unit">beats / min</div>
            <div class="bedside-range">Normal: 50 – 110 bpm</div>
        </div>
        """, unsafe_allow_html=True)

    # SpO2 Color
    spo2_color = "#ef4444" if (spo2_val is not None and spo2_val <= 85) else "#f59e0b" if (spo2_val is not None and spo2_val < 90) else "#10b981"
    with col2:
        st.markdown(f"""
        <div class="bedside-card">
            <div class="bedside-title">Oxygen Saturation (SpO2)</div>
            <div class="bedside-num" style="color: {spo2_color};">{f"{spo2_val:.1f}" if spo2_val is not None else "--"}</div>
            <div class="bedside-unit">percentage (%)</div>
            <div class="bedside-range">Normal: &ge; 90%</div>
        </div>
        """, unsafe_allow_html=True)

    # Respiratory Rate Color
    rr_color = "#ef4444" if (rr_val is not None and (rr_val < 6 or rr_val > 30)) else "#f59e0b" if (rr_val is not None and (rr_val < 10 or rr_val > 24)) else "#a855f7"
    with col3:
        st.markdown(f"""
        <div class="bedside-card">
            <div class="bedside-title">Respiratory Rate</div>
            <div class="bedside-num" style="color: {rr_color};">{f"{rr_val:.1f}" if rr_val is not None else "--"}</div>
            <div class="bedside-unit">breaths / min</div>
            <div class="bedside-range">Normal: 10 – 24 bpm</div>
        </div>
        """, unsafe_allow_html=True)

    # Temperature Color
    temp_color = "#ef4444" if (temp_val is not None and (temp_val < 34.0 or temp_val > 40.0)) else "#f59e0b" if (temp_val is not None and (temp_val < 35.5 or temp_val > 38.0)) else "#f97316"
    with col4:
        st.markdown(f"""
        <div class="bedside-card">
            <div class="bedside-title">Body Temperature</div>
            <div class="bedside-num" style="color: {temp_color};">{f"{temp_val:.2f}" if temp_val is not None else "--"}</div>
            <div class="bedside-unit">&deg;Celsius</div>
            <div class="bedside-range">Normal: 35.5 – 38.0 &deg;C</div>
        </div>
        """, unsafe_allow_html=True)

    # Vital Trends Chart
    st.markdown("### 📈 Bedside Telemetry Trend")
    readings = get_recent_readings(chosen_pid, limit=25)
    if readings:
        df_r = pd.DataFrame(readings)
        df_r["index"] = range(len(df_r))
        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("**Heart Rate & SpO2**")
            st.line_chart(df_r[["index", "heart_rate", "spo2"]].dropna().set_index("index"))
        with ch2:
            st.markdown("**Respiratory Rate & Temperature**")
            st.line_chart(df_r[["index", "respiratory_rate", "temperature"]].dropna().set_index("index"))

    # Abnormal Reading Clinical Explanation
    st.markdown("### 🩺 Clinical Assessment & Physiological Explanation")
    if active_alert:
        explanation_record = get_latest_explanation(active_alert["alert_id"])
        if explanation_record:
            st.info(f"**Provider**: `{explanation_record.get('provider_status', 'DETERMINISTIC_FALLBACK')}`")
            st.markdown(explanation_record["explanation_text"])
        else:
            # Generate fallback on the fly
            exp_fallback = st.session_state.ai_explainer.explain_alert(
                severity=current_condition,
                trigger_reasons=[active_alert["trigger_reason"]],
                vitals={
                    "heart_rate": hr_val,
                    "spo2": spo2_val,
                    "respiratory_rate": rr_val,
                    "temperature": temp_val,
                    "data_valid": 1 if hr_val is not None else 0
                },
                patient_name=patient["display_name"],
                bed_id=f"{patient['ward']}-{patient['bed']}"
            )
            st.markdown(exp_fallback["explanation"])
    else:
        st.success(
            f"**Patient Baseline Normal**: All monitored parameters for {patient['display_name']} are within safe physiological boundaries. "
            "Continue standard ICU telemetry monitoring."
        )


# =============================================================================
# PAGE 3: ENGINEERING DASHBOARD
# =============================================================================
def render_engineering_dashboard():
    st.markdown('<div class="top-header">⚙️ Biomedical Engineering & Architecture Station</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="top-subheader">MPMC Instruction Execution Trace &bull; '
        f'Verilog Hardware Safety Controller &bull; '
        f'RTL Testbench &bull; SQLite Schema & Logs</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="edu-banner">
        <strong>Engineering Station:</strong> Demonstrates the embedded biomedical architecture:
        MPMC Assembly execution trace, synthesizable Verilog FSM safety controller, and SQLite persistence.
    </div>
    """, unsafe_allow_html=True)

    # Patient & Scenario Control
    patients_list = get_patients()
    patient_ids = [p["patient_id"] for p in patients_list]
    scenarios = get_scenarios()
    scenario_names = [s["scenario_name"] for s in scenarios]

    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    with col_ctrl1:
        st.markdown("#### 🎛️ Assign Simulation Scenario")
        target_pid = st.selectbox("Select Patient to Configure", options=patient_ids, format_func=lambda pid: f"{pid} - {get_patient_by_id(pid)['display_name']}")
        target_patient = get_patient_by_id(target_pid)
        
        current_scen = target_patient.get("current_scenario", "Normal Recovery")
        scen_index = scenario_names.index(current_scen) if current_scen in scenario_names else 0
        new_scen = st.selectbox("Assign Scenario", options=scenario_names, index=scen_index)

        if new_scen != current_scen:
            update_patient_scenario(target_pid, new_scen)
            st.success(f"Updated {target_pid} scenario to '{new_scen}'.")
            st.rerun()

    with col_ctrl2:
        st.markdown("#### 🧪 Manual Telemetry Injection")
        custom_overrides = None
        if new_scen == "Interactive Custom":
            st.caption("Live manual override controls for testing edge cases:")
            hr_ov = st.slider("Inject Heart Rate (bpm)", min_value=20, max_value=200, value=75)
            spo2_ov = st.slider("Inject SpO2 (%)", min_value=50, max_value=100, value=98)
            rr_ov = st.slider("Inject Resp Rate (bpm)", min_value=0, max_value=50, value=16)
            temp_ov = st.slider("Inject Temp (°C)", min_value=32.0, max_value=42.0, value=37.0, step=0.1)
            valid_ov = st.checkbox("Transducer Line Valid (data_valid)", value=True)
            custom_overrides = {
                "heart_rate": hr_ov,
                "spo2": spo2_ov,
                "respiratory_rate": rr_ov,
                "temperature": temp_ov,
                "data_valid": 1 if valid_ov else 0,
                "oxygen_line_status": "CONNECTED" if valid_ov else "FAULT"
            }

    st.markdown("---")

    # Tabs for MPMC, Verilog, AI, Database
    tab_mpmc, tab_verilog, tab_ai, tab_db = st.tabs([
        "🔬 MPMC Instruction Trace",
        "⚡ Verilog Safety FSM",
        "🧠 AI Explainer & Guardrails",
        "🗄️ SQLite Database Logs"
    ])

    # 1. MPMC Simulator Tab
    with tab_mpmc:
        st.markdown("### 🔬 MPMC Telemetry Processor Simulation")
        st.markdown(
            "Emulates the biomedical microprocessor / microcontroller (MPMC) running embedded firmware "
            "(`firmware.asm`) polling ADC input ports `0x10`–`0x14` and driving the safety command bus `0x20`."
        )

        latest_p = get_latest_reading(target_pid)
        mpmc_exec = st.session_state.mpmc_simulator.run_full_cycle(
            hr=latest_p["heart_rate"] if latest_p else 75,
            spo2=latest_p["spo2"] if latest_p else 98,
            rr=latest_p["respiratory_rate"] if latest_p else 16,
            temp=latest_p["temperature"] if latest_p else 37.0,
            data_valid=latest_p["data_valid"] if latest_p else 1
        )

        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            st.markdown("#### CPU Register & Port Architecture")
            m_regs = mpmc_exec["final_registers"]
            m_flags = mpmc_exec["final_flags"]
            st.markdown(f"""
            - **Registers**:
              - `R0`: `{m_regs.get('R0', 0)}` (Sampled HR / Bus Output)
              - `R1`: `{m_regs.get('R1', 0)}` (Sampled SpO2)
              - `R2`: `{m_regs.get('R2', 0)}` (Sampled RR)
              - `R3`: `{m_regs.get('R3', 0)}` (Sampled Temp / Signal)
            - **ALU Condition Flags**:
              - `ZF` (Zero): `{m_flags.get('ZF', 0)}`
              - `SF` (Sign / Less-Than): `{m_flags.get('SF', 0)}`
              - `CF` (Carry): `{m_flags.get('CF', 0)}`
            - **Bus Output Port 0x20**: `{mpmc_exec['state_code']} ({mpmc_exec['state_name']})`
            - **Instructions Executed This Cycle**: `{mpmc_exec['steps_count']}`
            """)

            with st.expander("📄 View Assembly Firmware (`firmware.asm`)"):
                asm_path = os.path.join(PROJECT_ROOT, "simulator", "mpmc", "firmware.asm")
                if os.path.exists(asm_path):
                    with open(asm_path, "r", encoding="utf-8") as f:
                        st.code(f.read(), language="assembly")

        with col_m2:
            st.markdown("#### Visible Instruction Execution Trace")
            trace_data = mpmc_exec["trace"]
            if trace_data:
                df_tr = pd.DataFrame(trace_data)[["step", "pc", "instruction", "explanation"]]
                df_tr.columns = ["Step", "PC", "Assembly Instruction", "Clinical / Architectural Rationale"]
                st.dataframe(df_tr, use_container_width=True, height=340)

    # 2. Verilog Tab
    with tab_verilog:
        st.markdown("### ⚡ Synthesizable Verilog Safety Controller (FSM)")
        engine_info = st.session_state.verilog_bridge.get_engine_status()
        if engine_info["native_toolchain_available"]:
            st.success(f"**Execution Engine**: {engine_info['engine_name']} (Native Toolchain)")
        else:
            st.warning(f"**Execution Engine**: {engine_info['engine_name']}\n\n*{engine_info['description']}*")

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown("#### FSM Pin & State Architecture")
            st.markdown("""
            | State | Code | Trigger Condition | Alarm Action |
            |---|---|---|---|
            | `NORMAL` | `2'b00` | All parameters within safe threshold bounds | Disarmed (Silent) |
            | `WARNING` | `2'b01` | Parameter crosses warning threshold | Audio + Visual |
            | `CRITICAL` | `2'b10` | Parameter crosses critical life-threatening threshold | Urgent Repeating Audio + Visual |
            | `DATA_FAULT` | `2'b11` | Transducer disconnect / `data_valid = 0` | Rapid Buzzy Audio + Visual |
            """)

            if st.button("▶ Execute Verilog Testbench Suite", key="eng_exec_verilog_tb_btn"):
                tb_res = st.session_state.verilog_bridge.run_hardware_testbench()
                if tb_res["executed"]:
                    st.text(tb_res["log"])
                else:
                    st.info(tb_res["log"])

        with col_v2:
            with st.expander("📄 View Verilog HDL Module (`safety_controller.v`)"):
                v_path = os.path.join(PROJECT_ROOT, "simulator", "verilog", "verilog", "safety_controller.v")
                if os.path.exists(v_path):
                    with open(v_path, "r", encoding="utf-8") as f:
                        st.code(f.read(), language="verilog")

            with st.expander("📄 View Verilog Testbench (`safety_controller_tb.v`)"):
                tb_path = os.path.join(PROJECT_ROOT, "simulator", "verilog", "verilog", "testbench", "safety_controller_tb.v")
                if os.path.exists(tb_path):
                    with open(tb_path, "r", encoding="utf-8") as f:
                        st.code(f.read(), language="verilog")

    # 3. AI Explainer Tab
    with tab_ai:
        st.markdown("### 🧠 AI Clinical Explainer & Safety Isolation Guardrails")
        st.markdown("""
        > **Deterministic Safety Isolation Principle**: Medical telemetry alarm severity is computed strictly 
        > by the Verilog Safety FSM. The AI Explainer agent provides physiological education and differential 
        > diagnoses, but **NEVER decides, overrides, or alters safety classification**.
        """)
        api_key_input = st.text_input("Optional LLM API Key (Groq / OpenAI)", type="password", help="Leave blank for 100% offline Deterministic Clinical Engine.")
        if api_key_input:
            st.session_state.ai_explainer = AIClinicalExplainer(api_key=api_key_input)

    # 4. Database Tab
    with tab_db:
        st.markdown("### 🗄️ SQLite Database Records (`smart_icu.db`)")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown("#### Recent Readings (`simulated_readings`)")
            readings_db = get_recent_readings(target_pid, limit=15)
            if readings_db:
                st.dataframe(pd.DataFrame(readings_db), use_container_width=True, height=250)
        with col_d2:
            st.markdown("#### Clinical Alert History (`alert_history`)")
            alerts_db = get_all_alerts(limit=15)
            if alerts_db:
                st.dataframe(pd.DataFrame(alerts_db), use_container_width=True, height=250)


# =============================================================================
# Main Application Router
# =============================================================================
if selected_page_key == "doctor":
    render_doctor_dashboard()
elif selected_page_key == "bedside":
    render_bedside_dashboard()
elif selected_page_key == "engineering":
    render_engineering_dashboard()

# -----------------------------------------------------------------------------
# Streaming Loop Tick
# -----------------------------------------------------------------------------
# Streaming Loop Tick
if st.session_state.auto_stream:
    time.sleep(st.session_state.stream_speed)
    st.session_state.sim_step += 1
    run_telemetry_tick(st.session_state.sim_step)
    st.rerun()