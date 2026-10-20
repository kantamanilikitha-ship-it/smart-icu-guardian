# Verilog Safety Controller Subsystem

This subsystem implements the deterministic hardware safety controller monitoring patient vital signs.

## Directory Structure
- `verilog/`: Synthesizable Verilog HDL source (`safety_controller.v`).
- `verilog/testbench/`: Complete hardware simulation testbench (`safety_controller_tb.v`).
- `integration/`: Python hardware integration bridge and cycle-exact behavioral twin FSM.

## Operational Principle
The hardware safety controller acts as a strict deterministic arbiter. It implements an FSM with 4 discrete states:
1. `NORMAL` (`2'b00`): Patient telemetry within established safe bounds.
2. `WARNING` (`2'b01`): Borderline parameter deviation requiring clinical vigilance.
3. `CRITICAL` (`2'b10`): Severe physiological distress requiring immediate intervention.
4. `DATA_FAULT` (`2'b11`): Transducer disconnection, signal dropout, or telemetry line fault (`data_valid = 0`).

The controller asserts discrete audio/visual alarm enable lines and responds to clinician acknowledgement signals.
