"""
Alert Management and Medical Telemetry Audio System for Smart ICU Guardian.
Coordinates alarm state, clinician acknowledgement, database logging,
and browser-based repeating Web Audio API synthesis conforming to medical alarm patterns.
Guarantees duplicate prevention for continuous events, separate acknowledgement vs resolution tracking,
and multi-patient alert arbitration.
"""

from typing import Dict, Any, List, Optional
from database.db import log_alert, acknowledge_alert, resolve_patient_alerts, get_active_alerts


class AlertManager:
    """
    Manages clinical alarms, state transitions, acknowledgements,
    and generates repeating Web Audio API alarm synthesizers.
    """

    def __init__(self, patient_id: str = "P101", db_path: Optional[str] = None):
        self.patient_id = patient_id
        self.db_path = db_path
        self.current_alert_id: Optional[int] = None
        self.last_severity: str = "NORMAL"

    def _db_args(self) -> Dict[str, Any]:
        return {"db_path": self.db_path} if self.db_path else {}

    def process_state(
        self,
        severity: str,
        trigger_reasons: List[str],
        scenario_id: Optional[int] = None,
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes FSM state output for a patient.
        If normal, marks unresolved alerts as resolved (recovery).
        If non-normal, logs/retrieves active alert (preventing continuous duplicates).
        """
        pid = patient_id or self.patient_id
        db_kwargs = self._db_args()

        if severity == "NORMAL":
            # Recovered condition -> resolve active alerts
            resolve_patient_alerts(pid, **db_kwargs)
            self.current_alert_id = None
            self.last_severity = "NORMAL"
            return {
                "active_alert": None,
                "is_new_alarm": False,
                "has_unacknowledged": False
            }

        # Check existing active alerts before logging
        existing_active = get_active_alerts(pid, **db_kwargs)
        had_unacknowledged_before = any(a["acknowledged"] == 0 for a in existing_active)

        reason_str = "; ".join(trigger_reasons) if trigger_reasons else f"State changed to {severity}"
        alert_id = log_alert(
            patient_id=pid,
            alert_type="PHYSIOLOGICAL" if severity != "DATA_FAULT" else "TECHNICAL",
            severity=severity,
            trigger_reason=reason_str,
            scenario_id=scenario_id,
            **db_kwargs
        )
        self.current_alert_id = alert_id
        self.last_severity = severity

        # Re-fetch active alert record
        active_list = get_active_alerts(pid, **db_kwargs)
        current_active = next((a for a in active_list if a["alert_id"] == alert_id), None)
        if not current_active and active_list:
            current_active = active_list[0]

        is_new = not had_unacknowledged_before and bool(current_active and current_active["acknowledged"] == 0)

        return {
            "active_alert": current_active,
            "is_new_alarm": is_new,
            "has_unacknowledged": bool(current_active and current_active["acknowledged"] == 0)
        }

    def acknowledge(self, alert_id: Optional[int] = None) -> bool:
        """Acknowledges the specified or current active alert."""
        aid = alert_id or self.current_alert_id
        if aid:
            return acknowledge_alert(aid, **self._db_args())
        return False

    @staticmethod
    def generate_web_audio_player(
        severity: str,
        is_active: bool,
        is_acknowledged: bool,
        audio_enabled: bool = True
    ) -> str:
        """
        Generates HTML5 Web Audio API synthesizer for repeating medical alarm chimes.
        Conforms conceptually to IEC 60601-1-8 medical alarm annunciator patterns.
        """
        if not audio_enabled or not is_active or is_acknowledged or severity == "NORMAL":
            ack_msg = "🔕 Audible Alarm: Silenced (Acknowledged by Clinician)" if is_acknowledged and is_active else "🔕 Audible Alarm: Silent (Normal / Muted)"
            return f"""
            <div style="padding: 10px; border-radius: 8px; background: #1e293b; color: #94a3b8; font-size: 13px; text-align: center; border: 1px solid #334155;">
                {ack_msg}
            </div>
            """

        # Choose frequency and repetition interval based on severity
        if severity == "CRITICAL":
            # Urgent high-priority burst: 880Hz / 1046Hz repeating every 1.8s
            freq_main = 880
            freq_alt = 1046
            burst_count = 5
            repeat_ms = 1800
            banner_color = "#ef4444"
            label = "🚨 CRITICAL AUDIBLE ALARM ACTIVE (IEC 60601-1-8 High Priority)"
        elif severity == "WARNING":
            # Medium-priority chime: 587Hz repeating every 3.5s
            freq_main = 587
            freq_alt = 659
            burst_count = 3
            repeat_ms = 3500
            banner_color = "#f59e0b"
            label = "⚠️ WARNING AUDIBLE ALARM ACTIVE (IEC 60601-1-8 Medium Priority)"
        else: # DATA_FAULT
            # Rapid alternating technical buzzer: 440Hz / 350Hz repeating every 2.0s
            freq_main = 440
            freq_alt = 350
            burst_count = 4
            repeat_ms = 2000
            banner_color = "#8b5cf6"
            label = "⚡ TECHNICAL TELEMETRY FAULT ALARM (Sensor Disconnect)"

        html_code = f"""
        <div style="padding: 12px; border-radius: 8px; background: {banner_color}22; border: 2px solid {banner_color}; color: white; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="font-weight: bold; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 18px;">🔊</span>
                    <span>{label}</span>
                </div>
                <div style="font-size: 12px; color: #cbd5e1; background: #00000044; padding: 4px 8px; border-radius: 4px;">
                    Repeating every {repeat_ms/1000.0:.1f}s until acknowledged
                </div>
            </div>
        </div>

        <script>
        (function() {{
            try {{
                var AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                var ctx = new AudioContext();

                function playBeep(frequency, startTime, duration) {{
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(frequency, startTime);

                    gain.gain.setValueAtTime(0, startTime);
                    gain.gain.linearRampToValueAtTime(0.2, startTime + 0.02);
                    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

                    osc.connect(gain);
                    gain.connect(ctx.destination);

                    osc.start(startTime);
                    osc.stop(startTime + duration);
                }}

                function triggerBurst() {{
                    if (ctx.state === 'suspended') {{
                        ctx.resume();
                    }}
                    var now = ctx.currentTime;
                    var count = {burst_count};
                    var baseFreq = {freq_main};
                    var altFreq = {freq_alt};

                    for (var i = 0; i < count; i++) {{
                        var freq = (i % 2 === 0) ? baseFreq : altFreq;
                        playBeep(freq, now + (i * 0.15), 0.12);
                    }}
                }}

                // Immediate initial burst
                triggerBurst();

                // Periodic repeating interval
                if (window._icuAlarmInterval) {{
                    clearInterval(window._icuAlarmInterval);
                }}
                window._icuAlarmInterval = setInterval(triggerBurst, {repeat_ms});
            }} catch(e) {{
                console.warn('Web Audio alarm init error:', e);
            }}
        }})();
        </script>
        """
        return html_code
