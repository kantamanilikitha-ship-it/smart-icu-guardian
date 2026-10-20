"""
Integration test for the UI telemetry pipeline and safety controller.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulator.verilog.integration.verilog_bridge import VerilogSafetyBridge
from simulator.mpmc.mpmc_core import MPMCSimulator
from services.vitals_generator import VitalSimulator


def test_full_pipeline_step():
    vsim = VitalSimulator()
    v_reading = vsim.generate_reading("Normal Recovery", step=1)
    
    bridge = VerilogSafetyBridge()
    fsm_res = bridge.evaluate_vitals(
        hr=v_reading.heart_rate,
        spo2=v_reading.spo2,
        rr=v_reading.respiratory_rate,
        temp=v_reading.temperature,
        data_valid=v_reading.data_valid
    )
    assert fsm_res["state"] == "NORMAL"
    
    mpmc = MPMCSimulator()
    mpmc_res = mpmc.run_full_cycle(
        hr=v_reading.heart_rate,
        spo2=v_reading.spo2,
        rr=v_reading.respiratory_rate,
        temp=v_reading.temperature,
        data_valid=v_reading.data_valid
    )
    assert mpmc_res["state_name"] == "NORMAL"
    assert len(mpmc_res["trace"]) > 0
