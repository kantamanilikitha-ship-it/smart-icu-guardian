"""
Educational MPMC (Microprocessor / Microcontroller) Simulator.
Simulates an embedded ICU telemetry processor executing firmware for vital sign monitoring.
Generates an instruction-by-instruction execution trace for educational inspection.
"""

import os
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_ASM_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "firmware.asm"
)

# Port definitions matching firmware.asm
PORT_HR = 0x10
PORT_SPO2 = 0x11
PORT_RR = 0x12
PORT_TEMP = 0x13
PORT_SIGNAL = 0x14
PORT_SAFETY_BUS = 0x20


class MPMCSimulator:
    """
    Virtual Microprocessor / Microcontroller core for biomedical monitoring.
    Architecture:
    - Registers: R0, R1, R2, R3, ACC, PC
    - Flags: ZF (Zero), SF (Sign), CF (Carry), FF (Fault)
    - I/O Ports: ADC sensor lines (0x10-0x14), Safety Controller bus (0x20)
    """

    def __init__(self, asm_file: str = DEFAULT_ASM_PATH):
        self.asm_file = asm_file
        self.registers = {"R0": 0, "R1": 0, "R2": 0, "R3": 0, "ACC": 0}
        self.flags = {"ZF": 0, "SF": 0, "CF": 0, "FF": 0}
        self.pc = 0
        self.ports = {
            PORT_HR: 75,
            PORT_SPO2: 98,
            PORT_RR: 16,
            PORT_TEMP: 370,
            PORT_SIGNAL: 1,
            PORT_SAFETY_BUS: 0
        }
        self.instructions: List[Tuple[str, List[str]]] = []
        self.labels: Dict[str, int] = {}
        self.trace: List[Dict[str, Any]] = []
        self.halted = False
        self.load_firmware()

    def load_firmware(self):
        """Parses the assembly firmware file into instructions and symbol labels."""
        self.instructions = []
        self.labels = {}
        if not os.path.exists(self.asm_file):
            return

        with open(self.asm_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        cleaned = []
        for line in lines:
            line = line.strip()
            # Remove comments
            if ";" in line:
                line = line.split(";", 1)[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(cleaned)
            else:
                parts = line.replace(",", " ").split()
                opcode = parts[0].upper()
                operands = [p.strip() for p in parts[1:]]
                cleaned.append((opcode, operands))

        self.instructions = cleaned

    def set_sensor_inputs(
        self,
        hr: Optional[float],
        spo2: Optional[float],
        rr: Optional[float],
        temp: Optional[float],
        data_valid: int = 1
    ):
        """Loads ADC sensor register values onto input ports."""
        self.ports[PORT_HR] = int(round(hr)) if (hr is not None and data_valid) else 0
        self.ports[PORT_SPO2] = int(round(spo2)) if (spo2 is not None and data_valid) else 0
        self.ports[PORT_RR] = int(round(rr)) if (rr is not None and data_valid) else 0
        self.ports[PORT_TEMP] = int(round(temp * 10)) if (temp is not None and data_valid) else 0
        self.ports[PORT_SIGNAL] = int(data_valid)
        self.ports[PORT_SAFETY_BUS] = 0

    def reset(self):
        """Resets CPU registers and program counter."""
        self.registers = {"R0": 0, "R1": 0, "R2": 0, "R3": 0, "ACC": 0}
        self.flags = {"ZF": 0, "SF": 0, "CF": 0, "FF": 0}
        self.pc = 0
        self.trace = []
        self.halted = False

    def step(self) -> Optional[Dict[str, Any]]:
        """Executes a single instruction and logs trace."""
        if self.halted or self.pc >= len(self.instructions):
            self.halted = True
            return None

        opcode, operands = self.instructions[self.pc]
        current_pc = self.pc
        explanation = ""

        # Decode & Execute
        if opcode == "IN":
            dest, port_str = operands[0], operands[1]
            port_val = int(port_str, 16) if "0x" in port_str.lower() else int(port_str)
            val = self.ports.get(port_val, 0)
            self.registers[dest] = val
            explanation = f"Read ADC Port 0x{port_val:02X} -> {dest} = {val}"
            self.pc += 1

        elif opcode == "OUT":
            port_str, src = operands[0], operands[1]
            port_val = int(port_str, 16) if "0x" in port_str.lower() else int(port_str)
            val = self.registers.get(src, 0) if src in self.registers else int(src)
            self.ports[port_val] = val
            state_map = {0: "NORMAL (0)", 1: "WARNING (1)", 2: "CRITICAL (2)", 3: "DATA_FAULT (3)"}
            state_text = state_map.get(val, str(val))
            explanation = f"Transmit safety bus 0x{port_val:02X} = {state_text}"
            self.pc += 1

        elif opcode == "MOV":
            dest, val_str = operands[0], operands[1]
            val = self.registers.get(val_str, None)
            if val is None:
                val = int(val_str, 16) if "0x" in val_str.lower() else int(val_str)
            self.registers[dest] = val
            explanation = f"Move immediate {val} into {dest}"
            self.pc += 1

        elif opcode == "CMP":
            reg, val_str = operands[0], operands[1]
            reg_val = self.registers[reg]
            cmp_val = self.registers.get(val_str, None)
            if cmp_val is None:
                cmp_val = int(val_str, 16) if "0x" in val_str.lower() else int(val_str)

            diff = reg_val - cmp_val
            self.flags["ZF"] = 1 if diff == 0 else 0
            self.flags["SF"] = 1 if diff < 0 else 0
            self.flags["CF"] = 1 if diff < 0 else 0
            explanation = f"Compare {reg} ({reg_val}) vs {cmp_val} -> ZF={self.flags['ZF']}, SF={self.flags['SF']}"
            self.pc += 1

        elif opcode == "JEQ":
            target = operands[0]
            if self.flags["ZF"] == 1:
                explanation = f"ZF=1: Jump taken to label '{target}'"
                self.pc = self.labels[target]
            else:
                explanation = f"ZF=0: Jump not taken"
                self.pc += 1

        elif opcode == "JNE":
            target = operands[0]
            if self.flags["ZF"] == 0:
                explanation = f"ZF=0: Jump taken to label '{target}'"
                self.pc = self.labels[target]
            else:
                explanation = f"ZF=1: Jump not taken"
                self.pc += 1

        elif opcode == "JLT":
            target = operands[0]
            if self.flags["SF"] == 1:
                explanation = f"SF=1 (Less than): Jump taken to label '{target}'"
                self.pc = self.labels[target]
            else:
                explanation = f"SF=0: Jump not taken"
                self.pc += 1

        elif opcode == "JLE":
            target = operands[0]
            if self.flags["SF"] == 1 or self.flags["ZF"] == 1:
                explanation = f"SF=1 or ZF=1 (Less or equal): Jump taken to '{target}'"
                self.pc = self.labels[target]
            else:
                explanation = f"Jump not taken"
                self.pc += 1

        elif opcode == "JGT":
            target = operands[0]
            if self.flags["SF"] == 0 and self.flags["ZF"] == 0:
                explanation = f"Greater than: Jump taken to label '{target}'"
                self.pc = self.labels[target]
            else:
                explanation = f"Jump not taken"
                self.pc += 1

        elif opcode == "JMP":
            target = operands[0]
            explanation = f"Unconditional jump to '{target}'"
            self.pc = self.labels[target]

        elif opcode == "HALT":
            explanation = f"HALT: Telemetry evaluation cycle complete."
            self.halted = True
            self.pc += 1

        else:
            explanation = f"Unknown opcode {opcode}"
            self.pc += 1

        entry = {
            "step": len(self.trace) + 1,
            "pc": f"0x{current_pc:02X}",
            "instruction": f"{opcode} {', '.join(operands)}",
            "registers": dict(self.registers),
            "flags": dict(self.flags),
            "explanation": explanation
        }
        self.trace.append(entry)
        return entry

    def run_full_cycle(
        self,
        hr: Optional[float],
        spo2: Optional[float],
        rr: Optional[float],
        temp: Optional[float],
        data_valid: int = 1,
        max_steps: int = 100
    ) -> Dict[str, Any]:
        """
        Loads sensor inputs, runs the firmware from start to HALT,
        and returns the resulting safety bus command and instruction execution trace.
        """
        self.reset()
        self.set_sensor_inputs(hr, spo2, rr, temp, data_valid)

        steps_executed = 0
        while not self.halted and steps_executed < max_steps:
            self.step()
            steps_executed += 1

        state_code = self.ports.get(PORT_SAFETY_BUS, 0)
        state_map = {0: "NORMAL", 1: "WARNING", 2: "CRITICAL", 3: "DATA_FAULT"}

        return {
            "state_code": state_code,
            "state_name": state_map.get(state_code, "UNKNOWN"),
            "steps_count": len(self.trace),
            "trace": self.trace,
            "final_registers": dict(self.registers),
            "final_flags": dict(self.flags)
        }
