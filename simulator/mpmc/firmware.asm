; ==============================================================================
; Smart ICU Guardian - MPMC Embedded Telemetry Firmware
; Target: Educational Biomedical Microprocessor / Microcontroller
; Purpose: Samples ICU sensor ports, executes range verification,
;          and generates bus signals for the Verilog Safety Controller.
; ==============================================================================

; Memory mapped I/O ports
; PORT 0x10: Heart Rate ADC (bpm)
; PORT 0x11: SpO2 ADC (%)
; PORT 0x12: Respiratory Rate ADC (breaths/min)
; PORT 0x13: Temperature ADC (tenths of C, e.g. 370 = 37.0 C)
; PORT 0x14: Sensor Signal Integrity Line (1 = OK, 0 = Fault)
; PORT 0x20: Safety Controller Command Bus

START:
    ; 1. Check Sensor Signal Integrity
    IN   R3, 0x14           ; Read sensor integrity line into R3
    CMP  R3, 1              ; Test if data_valid == 1
    JEQ  SENSORS_VALID      ; If valid, jump to vital signs processing
    MOV  R0, 3              ; Load DATA_FAULT state code (0x03)
    OUT  0x20, R0           ; Transmit FAULT to Safety Controller
    HALT                    ; Suspend until next sampling period

SENSORS_VALID:
    ; 2. Sample Heart Rate ADC
    IN   R0, 0x10           ; Read Heart Rate into R0
    CMP  R0, 40             ; Compare with CRITICAL_MIN (40 bpm)
    JLT  ALERT_CRITICAL     ; If HR < 40 -> Critical Bradycardia
    CMP  R0, 130            ; Compare with CRITICAL_MAX (130 bpm)
    JGT  ALERT_CRITICAL     ; If HR > 130 -> Critical Tachycardia

    ; 3. Sample Oxygen Saturation (SpO2) ADC
    IN   R1, 0x11           ; Read SpO2 percentage into R1
    CMP  R1, 85             ; Compare with CRITICAL_MAX (85%)
    JLE  ALERT_CRITICAL     ; If SpO2 <= 85% -> Critical Hypoxia

    ; 4. Sample Respiratory Rate (RR) ADC
    IN   R2, 0x12           ; Read Respiratory Rate into R2
    CMP  R2, 6              ; Compare with CRITICAL_MIN (6 bpm)
    JLT  ALERT_CRITICAL     ; If RR < 6 -> Severe Bradypnea / Apnea
    CMP  R2, 30             ; Compare with CRITICAL_MAX (30 bpm)
    JGT  ALERT_CRITICAL     ; If RR > 30 -> Severe Tachypnea

    ; 5. Sample Temperature ADC
    IN   R3, 0x13           ; Read Temperature into R3 (scaled tenths)
    CMP  R3, 340            ; Compare with CRITICAL_MIN (34.0 C)
    JLT  ALERT_CRITICAL     ; If Temp < 34.0 C -> Hypothermia
    CMP  R3, 400            ; Compare with CRITICAL_MAX (40.0 C)
    JGT  ALERT_CRITICAL     ; If Temp > 40.0 C -> Hyperpyrexia

    ; 6. Evaluate Warning Thresholds
    CMP  R0, 50             ; Check HR Warning Min (50)
    JLT  ALERT_WARNING
    CMP  R0, 110            ; Check HR Warning Max (110)
    JGT  ALERT_WARNING

    CMP  R1, 90             ; Check SpO2 Warning Min (90)
    JLT  ALERT_WARNING

    CMP  R2, 10             ; Check RR Warning Min (10)
    JLT  ALERT_WARNING
    CMP  R2, 24             ; Check RR Warning Max (24)
    JGT  ALERT_WARNING

    CMP  R3, 355            ; Check Temp Warning Min (35.5 C)
    JLT  ALERT_WARNING
    CMP  R3, 380            ; Check Temp Warning Max (38.0 C)
    JGT  ALERT_WARNING

    ; All vital parameters within normal baseline
    MOV  R0, 0              ; NORMAL State code (0x00)
    OUT  0x20, R0           ; Send NORMAL to safety bus
    HALT

ALERT_WARNING:
    MOV  R0, 1              ; WARNING State code (0x01)
    OUT  0x20, R0           ; Send WARNING to safety bus
    HALT

ALERT_CRITICAL:
    MOV  R0, 2              ; CRITICAL State code (0x02)
    OUT  0x20, R0           ; Send CRITICAL to safety bus
    HALT
