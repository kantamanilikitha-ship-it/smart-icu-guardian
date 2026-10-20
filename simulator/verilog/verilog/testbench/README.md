# Verilog Safety Controller Testbench

Contains the hardware verification suite for the `safety_controller` Verilog module.

## Files
- `safety_controller_tb.v`: Testbench exercising all state transitions (`NORMAL` -> `WARNING` -> `CRITICAL` -> `ACKNOWLEDGED` -> `DATA_FAULT` -> `RESET`).

## Running with Icarus Verilog
If Icarus Verilog (`iverilog`) and `vvp` are installed:
```bash
iverilog -o sim.vvp ../safety_controller.v safety_controller_tb.v
vvp sim.vvp
```
If `iverilog` is not installed, the system automatically runs the Python cycle-exact behavioral twin (`behavioral_fsm.py`).
