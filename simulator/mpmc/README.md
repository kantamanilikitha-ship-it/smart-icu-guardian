# MPMC Educational Simulator

This module implements an educational Microprocessor and Microcontroller (MPMC) simulator modeling embedded telemetry acquisition in biomedical patient monitors.

## Architecture & Components
- **`mpmc_core.py`**: Virtual CPU engine with registers (`R0`–`R3`, `ACC`, `PC`), status flags (`ZF`, `SF`, `CF`), memory-mapped I/O ports (`0x10`–`0x14` for sensor ADC and `0x20` for the safety controller command bus), instruction decoder, and visible execution trace logger.
- **`firmware.asm`**: Assembly language firmware routine that polls telemetry ADC ports, performs arithmetic/relational boundary checks, and transmits safety state codes to the safety controller bus.

## Visible Execution Trace
For each cycle, the simulator logs:
- Step count and Program Counter (`0x00`, `0x01`, etc.)
- Assembly instruction (`IN`, `OUT`, `CMP`, `JEQ`, `JLT`, `JGT`, `MOV`, `HALT`)
- Register snapshots (`R0`–`R3`)
- Condition flags (`ZF`, `SF`, `CF`)
- Human-readable clinical commentary explaining why the instruction executed.
