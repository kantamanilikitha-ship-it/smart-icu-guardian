# Verilog Integration Bridge & Behavioral Model

Bridges the software telemetry pipeline with hardware safety controller simulation.

## Files
- `verilog_bridge.py`: Hardware bridge inspecting host PATH for `iverilog`/`vvp`. If present, compiles and executes native Verilog RTL. If absent, delegates transparently to the Behavioral Twin without falsely claiming hardware execution.
- `behavioral_fsm.py`: Cycle-exact Python FSM mirroring every register, state transition, and threshold in `safety_controller.v`.
