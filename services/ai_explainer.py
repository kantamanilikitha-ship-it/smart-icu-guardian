"""
AI Clinical Explanation Engine for Smart ICU Guardian.
Provides structured physiological explanations for alerts.
Guarantees reliable deterministic fallback when no AI API key is configured.
Ensures deterministic safety: AI strictly explains alerts, NEVER determines alert severity.
"""

import os
from typing import Dict, Any, List, Optional


class AIClinicalExplainer:
    """
    Generates physiological explanations for patient telemetry events.
    Prioritizes deterministic safety and reliable offline educational operation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def explain_alert(
        self,
        severity: str,
        trigger_reasons: List[str],
        vitals: Dict[str, Any],
        patient_name: str = "ICU Patient",
        bed_id: str = "BED-01"
    ) -> Dict[str, Any]:
        """
        Generates an explanation. Tries LLM if API key exists, otherwise
        seamlessly uses the verified Deterministic Clinical Knowledge Engine.
        """
        if self.api_key:
            try:
                # Attempt external LLM explanation
                explanation = self._query_llm(severity, trigger_reasons, vitals, patient_name, bed_id)
                return {
                    "explanation": explanation,
                    "provider_status": "AI_ONLINE",
                    "disclaimer": "Academic educational prototype only. Not for clinical diagnosis."
                }
            except Exception as e:
                # Fall through to deterministic fallback if LLM request fails
                pass

        fallback_text = self._deterministic_clinical_fallback(
            severity, trigger_reasons, vitals, patient_name, bed_id
        )
        return {
            "explanation": fallback_text,
            "provider_status": "DETERMINISTIC_FALLBACK",
            "disclaimer": "Academic educational prototype only. Generated via deterministic clinical rules engine."
        }

    def _query_llm(
        self,
        severity: str,
        trigger_reasons: List[str],
        vitals: Dict[str, Any],
        patient_name: str,
        bed_id: str
    ) -> str:
        """Queries LLM with strict deterministic safety guardrails."""
        prompt = f"""
You are an educational ICU Clinical Telemetry Assistant.
Patient: {patient_name} ({bed_id})
Deterministic Alert Severity (Decided by Verilog FSM): {severity}
Trigger Reasons: {', '.join(trigger_reasons) if trigger_reasons else 'Routine assessment'}
Current Vitals:
- Heart Rate: {vitals.get('heart_rate')} bpm
- SpO2: {vitals.get('spo2')}%
- Respiratory Rate: {vitals.get('respiratory_rate')} bpm
- Temperature: {vitals.get('temperature')} °C
- Signal Valid: {vitals.get('data_valid')}

Provide a concise educational clinical explanation in 4 sections:
1. Physiological Mechanism
2. Differential Etiologies
3. Bedside Priority Checks
4. Educational Insight

Do NOT change the alert severity. This is for educational training only.
"""
        # Test Groq first if available
        if "gsk_" in (self.api_key or ""):
            try:
                from groq import Groq
                client = Groq(api_key=self.api_key)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400,
                    timeout=5.0
                )
                return response.choices[0].message.content
            except Exception:
                pass

        # Try requests to generic OpenAI compatible endpoint
        import requests
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=4.0)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        raise RuntimeError("API request unsuccessful")

    def _deterministic_clinical_fallback(
        self,
        severity: str,
        trigger_reasons: List[str],
        vitals: Dict[str, Any],
        patient_name: str,
        bed_id: str
    ) -> str:
        """
        Rule-based deterministic clinical knowledge engine providing high-fidelity
        medical explanations for all standard ICU telemetry events.
        """
        hr = vitals.get("heart_rate")
        spo2 = vitals.get("spo2")
        rr = vitals.get("respiratory_rate")
        temp = vitals.get("temperature")
        data_valid = vitals.get("data_valid", 1)

        lines = []
        lines.append(f"### Clinical Assessment: {severity} Telemetry Event")
        lines.append(f"**Patient**: {patient_name} [{bed_id}] | **Deterministic FSM State**: `{severity}`\n")

        if not data_valid or severity == "DATA_FAULT":
            lines.append("#### 1. Sensor & Telemetry Integrity")
            lines.append(
                "- **Finding**: The telemetry bus received an invalid data signal or loss of transducer contact (`data_valid = 0`).\n"
                "- **Etiology**: Optical probe displacement (finger clip slipped), ECG lead detachment ('lead-off'), severe patient motion artifact, or low peripheral perfusion index.\n"
                "- **Bedside Actions**:\n"
                "  1. Inspect physical placement of pulse oximeter sensor and ECG leads.\n"
                "  2. Verify cable connections to bedside monitor telemetry junction.\n"
                "  3. Check peripheral capillary refill time (> 2 seconds may impede optical absorption).\n"
                "  4. Reattach transducer with skin prep if adhesive is loose."
            )
            return "\n".join(lines)

        # Handle specific vital signs deviations
        hypoxia = spo2 is not None and spo2 < 90
        tachycardia = hr is not None and hr > 110
        bradycardia = hr is not None and hr < 50
        hyperthermia = temp is not None and temp > 38.0
        tachypnea = rr is not None and rr > 24

        lines.append("#### 1. Physiological Pathophysiology")
        if hypoxia and tachycardia:
            lines.append(
                f"- **Cardiorespiratory Stress**: Significant hypoxemia (SpO2 {spo2}%) has triggered carotid/aortic chemoreceptor reflexes, "
                f"stimulating sympathetic outflow and resulting in compensatory sinus tachycardia ({hr} bpm) and tachypnea ({rr} bpm) "
                f"to preserve tissue oxygen delivery (DO2)."
            )
        elif hypoxia:
            lines.append(
                f"- **Impaired Gas Exchange**: Oxygen saturation of {spo2}% indicates arterial hypoxemia. "
                f"Alveolar-arterial gradient is likely widened due to ventilation-perfusion (V/Q) mismatch, alveolar hypoventilation, or diffusion impairment."
            )
        elif tachycardia and hyperthermia:
            lines.append(
                f"- **Hypermetabolic Inflammatory Cascade**: Elevated core temperature ({temp} °C) induces increased basal metabolic rate. "
                f"For every 1 °C rise in body temperature, heart rate characteristically accelerates by 10-15 bpm ({hr} bpm observed) "
                f"alongside peripheral vasodilation."
            )
        elif bradycardia:
            lines.append(
                f"- **Conduction / Chronotropic Compromise**: Heart rate of {hr} bpm risks critical reductions in cardiac output (CO = HR x SV). "
                f"May be driven by enhanced vagal tone, sinoatrial exit block, high-degree AV block, or severe electrolyte derangements (e.g. hyperkalemia)."
            )
        else:
            reasons_str = "; ".join(trigger_reasons) if trigger_reasons else "Normal physiological baseline"
            lines.append(f"- **Telemetry Observations**: Monitored parameters ({reasons_str}) within observed telemetry envelope.")

        lines.append("\n#### 2. Key Differential Considerations")
        if hypoxia:
            lines.append("- Acute atelectasis, mucous plugging, aspiration, or worsening pulmonary infiltrate / edema.")
            lines.append("- Pulmonary embolism (particularly if tachycardia accompanied by sudden desaturation).")
        if hyperthermia:
            lines.append("- Systemic Inflammatory Response Syndrome (SIRS) / Sepsis.")
            lines.append("- Central neurogenic fever or adverse pharmacologic reaction.")
        if bradycardia:
            lines.append("- Medication effect (beta-blockers, calcium channel blockers, digoxin).")
            lines.append("- Increased intracranial pressure (Cushing's triad: bradycardia, hypertension, irregular respirations).")
        if not hypoxia and not hyperthermia and not bradycardia:
            lines.append("- Stable convalescence; routine ICU monitoring protocol indicated.")

        lines.append("\n#### 3. Recommended Nursing & Clinical Bedside Actions")
        lines.append("1. **Visual Confirmation**: Immediately assess patient airway, work of breathing, and conscious state.")
        if hypoxia:
            lines.append("2. **Oxygen Delivery**: Verify high-flow oxygen line connections; consider titrating FiO2 per unit protocol.")
            lines.append("3. **Auscultation**: Auscultate bilateral lung fields to assess for wheezes, crackles, or absent breath sounds.")
        elif hyperthermia:
            lines.append("2. **Sepsis Protocol**: Draw blood cultures if temperature > 38.3 °C; initiate targeted cooling and fluid assessment.")
        elif bradycardia:
            lines.append("2. **Hemodynamic Check**: Evaluate non-invasive blood pressure, pulse volume, and mental alertness.")
            lines.append("3. **Pharmacology**: Have Atropine and transcutaneous pacing pads accessible if symptomatic.")
        else:
            lines.append("2. **Ongoing Telemetry**: Continue continuous multi-lead cardiac and pulse oximetry monitoring.")

        lines.append("\n> [!NOTE]\n> *Determinism Guarantee*: Severity (`" + severity + "`) is locked by hardware safety controller logic. AI explanations assist clinical education and never override alarm classification.")

        return "\n".join(lines)
