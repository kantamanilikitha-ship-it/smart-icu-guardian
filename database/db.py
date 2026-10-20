"""
Database service for Smart ICU Guardian.
Manages SQLite operations using database/schema.sql.
Provides multi-patient synchronization, active alert tracking, separate acknowledgement vs resolution,
and duplicate alert prevention.
"""

import os
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "smart_icu.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "schema.sql")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a connection to SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the database schema and seeds default patients and scenarios."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)

    # Perform schema migrations for patients table
    cursor.execute("PRAGMA table_info(patients)")
    p_cols = [col[1] for col in cursor.fetchall()]
    if "ward" not in p_cols:
        cursor.execute("ALTER TABLE patients ADD COLUMN ward TEXT NOT NULL DEFAULT 'ICU-North'")
    if "room" not in p_cols:
        cursor.execute("ALTER TABLE patients ADD COLUMN room TEXT NOT NULL DEFAULT '101'")
    if "bed" not in p_cols:
        cursor.execute("ALTER TABLE patients ADD COLUMN bed TEXT NOT NULL DEFAULT 'Bed-A'")
    if "current_scenario" not in p_cols:
        cursor.execute("ALTER TABLE patients ADD COLUMN current_scenario TEXT NOT NULL DEFAULT 'Normal Recovery'")

    # Perform schema migrations for alert_history table
    cursor.execute("PRAGMA table_info(alert_history)")
    a_cols = [col[1] for col in cursor.fetchall()]
    if "acknowledged_at" not in a_cols:
        cursor.execute("ALTER TABLE alert_history ADD COLUMN acknowledged_at TEXT")
    if "resolved_at" not in a_cols:
        cursor.execute("ALTER TABLE alert_history ADD COLUMN resolved_at TEXT")

    # Seed initial patients if empty or update locations
    default_patients = [
        ("P101", "BED-01", "Eleanor Vance (Post-Op Cardiac)", "ICU-North", "101", "Bed-A", "Normal Recovery"),
        ("P102", "BED-02", "Marcus Sterling (Pneumonia Recovery)", "ICU-North", "101", "Bed-B", "Acute Hypoxia"),
        ("P103", "BED-03", "Sophia Lin (Septic Shock Observation)", "ICU-North", "102", "Bed-A", "Septic Shock"),
        ("P104", "BED-04", "Arthur Pendelton (Heart Failure)", "ICU-South", "201", "Bed-A", "Cardiac Bradycardia"),
        ("P105", "BED-05", "Clara Oswald (Post-Surgical)", "ICU-South", "202", "Bed-A", "Sensor Disconnection")
    ]

    for p in default_patients:
        cursor.execute("SELECT patient_id FROM patients WHERE patient_id = ?", (p[0],))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                INSERT INTO patients (patient_id, bed_id, display_name, ward, room, bed, current_scenario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                p
            )
        else:
            # Update ward, room, bed for existing entries
            cursor.execute(
                """
                UPDATE patients 
                SET ward = ?, room = ?, bed = ?, display_name = ?
                WHERE patient_id = ?
                """,
                (p[3], p[4], p[5], p[2], p[0])
            )

    # Seed initial test scenarios if empty
    cursor.execute("SELECT COUNT(*) FROM test_scenarios")
    if cursor.fetchone()[0] == 0:
        default_scenarios = [
            ("Normal Recovery", "Stable vitals reflecting standard post-operative recovery", "NORMAL"),
            ("Acute Hypoxia", "Oxygen desaturation below 85% with compensatory tachypnea", "CRITICAL"),
            ("Septic Shock", "Hyperpyrexia over 40.0 C with profound tachycardia", "CRITICAL"),
            ("Cardiac Bradycardia", "Severe heart rate drop below 40 bpm", "CRITICAL"),
            ("Sensor Disconnection", "Loss of signal / Lead-off triggering DATA_FAULT", "DATA_FAULT"),
            ("Interactive Custom", "Live interactive manual adjustment of vital sliders", "CUSTOM")
        ]
        cursor.executemany(
            "INSERT INTO test_scenarios (scenario_name, description, scenario_type) VALUES (?, ?, ?)",
            default_scenarios
        )

    conn.commit()
    conn.close()


def insert_reading(
    patient_id: str,
    heart_rate: Optional[float],
    spo2: Optional[float],
    respiratory_rate: Optional[float],
    temperature: Optional[float],
    scenario_id: Optional[int] = None,
    oxygen_line_status: str = "CONNECTED",
    data_valid: int = 1,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Inserts a simulated vital signs reading into SQLite."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO simulated_readings 
        (patient_id, scenario_id, timestamp, heart_rate, spo2, respiratory_rate, temperature, oxygen_line_status, data_valid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            patient_id,
            scenario_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            heart_rate,
            spo2,
            respiratory_rate,
            temperature,
            oxygen_line_status,
            data_valid
        )
    )
    reading_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reading_id


def get_recent_readings(patient_id: str, limit: int = 50, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves the most recent readings for a patient."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM simulated_readings 
        WHERE patient_id = ? 
        ORDER BY reading_id DESC LIMIT ?
        """,
        (patient_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_latest_reading(patient_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves the single latest reading for a patient."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM simulated_readings 
        WHERE patient_id = ? 
        ORDER BY reading_id DESC LIMIT 1
        """,
        (patient_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def log_alert(
    patient_id: str,
    alert_type: str,
    severity: str,
    trigger_reason: str,
    scenario_id: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Logs an alert. If an unresolved alert of the same severity already exists for this patient,
    returns its ID to prevent duplicate alerts for the same continuous event.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check for existing unresolved alert for this patient with this severity
    cursor.execute(
        """
        SELECT alert_id FROM alert_history
        WHERE patient_id = ? AND resolved = 0 AND severity = ?
        ORDER BY alert_id DESC LIMIT 1
        """,
        (patient_id, severity)
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing[0]

    # Resolve any existing unresolved alert of different severity for this patient
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        UPDATE alert_history 
        SET resolved = 1, resolved_at = ?
        WHERE patient_id = ? AND resolved = 0
        """,
        (now_str, patient_id)
    )

    cursor.execute(
        """
        INSERT INTO alert_history 
        (patient_id, scenario_id, timestamp, alert_type, severity, trigger_reason, acknowledged, resolved)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (
            patient_id,
            scenario_id,
            now_str,
            alert_type,
            severity,
            trigger_reason
        )
    )
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id


def acknowledge_alert(alert_id: int, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Marks an alert as acknowledged by clinician.
    Keeps resolved = 0 so visual alert remains visible until condition is resolved.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE alert_history SET acknowledged = 1, acknowledged_at = ? WHERE alert_id = ?",
        (now_str, alert_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def resolve_patient_alerts(patient_id: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Marks all unresolved alerts for a patient as resolved upon recovery.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE alert_history SET resolved = 1, resolved_at = ? WHERE patient_id = ? AND resolved = 0",
        (now_str, patient_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def get_active_alerts(patient_id: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Retrieves currently unresolved alerts (resolved = 0) with patient metadata.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if patient_id:
        cursor.execute(
            """
            SELECT a.*, p.display_name, p.ward, p.room, p.bed, p.bed_id
            FROM alert_history a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.patient_id = ? AND a.resolved = 0 AND a.severity != 'NORMAL'
            ORDER BY a.alert_id DESC
            """,
            (patient_id,)
        )
    else:
        cursor.execute(
            """
            SELECT a.*, p.display_name, p.ward, p.room, p.bed, p.bed_id
            FROM alert_history a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.resolved = 0 AND a.severity != 'NORMAL'
            ORDER BY a.alert_id DESC
            """
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_alerts(limit: int = 50, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves recent alerts history."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.*, p.display_name, p.ward, p.room, p.bed, p.bed_id
        FROM alert_history a
        JOIN patients p ON a.patient_id = p.patient_id
        ORDER BY a.alert_id DESC LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def store_ai_explanation(
    alert_id: int,
    explanation_text: str,
    provider_status: str = "DETERMINISTIC_FALLBACK",
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Stores an AI explanation associated with an alert."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ai_explanations (alert_id, explanation_text, provider_status, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (alert_id, explanation_text, provider_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    exp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return exp_id


def get_latest_explanation(alert_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Gets the latest explanation for an alert."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM ai_explanations WHERE alert_id = ? ORDER BY explanation_id DESC LIMIT 1",
        (alert_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_patients(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Gets all registered patients."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients ORDER BY patient_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient_by_id(patient_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Gets a specific patient's details."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_patient_scenario(patient_id: str, scenario_name: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Updates the scenario assigned to a patient."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET current_scenario = ? WHERE patient_id = ?", (scenario_name, patient_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_scenarios(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Gets all predefined test scenarios."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test_scenarios ORDER BY scenario_id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
