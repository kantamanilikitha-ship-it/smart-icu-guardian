CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    bed_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    ward TEXT NOT NULL DEFAULT 'ICU-North',
    room TEXT NOT NULL DEFAULT '101',
    bed TEXT NOT NULL DEFAULT 'Bed-A',
    current_scenario TEXT NOT NULL DEFAULT 'Normal Recovery',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_scenarios (
    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name TEXT NOT NULL,
    description TEXT,
    scenario_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulated_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    scenario_id INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    heart_rate REAL,
    spo2 REAL,
    respiratory_rate REAL,
    temperature REAL,
    oxygen_line_status TEXT,
    data_valid INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (scenario_id) REFERENCES test_scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS alert_history (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    scenario_id INTEGER,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    trigger_reason TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (scenario_id) REFERENCES test_scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS scenario_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    execution_status TEXT NOT NULL,
    FOREIGN KEY (scenario_id) REFERENCES test_scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS ai_explanations (
    explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL,
    explanation_text TEXT NOT NULL,
    provider_status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alert_history(alert_id)
);
