// =============================================================================
// Smart ICU Guardian: Verilog Safety Controller Testbench
// Module: safety_controller_tb
// Description: Comprehensive testbench verifying FSM state transitions:
//              NORMAL -> WARNING -> CRITICAL -> ACKNOWLEDGED -> DATA_FAULT
// =============================================================================

`timescale 1ns / 1ps

module safety_controller_tb;

    reg        clk;
    reg        rst_n;
    reg        data_valid;
    reg  [7:0] hr_val;
    reg  [7:0] spo2_val;
    reg  [7:0] rr_val;
    reg [11:0] temp_scaled;
    reg        ack_btn;

    wire [1:0]  state_out;
    wire        alarm_audio_en;
    wire        alarm_visual_en;
    wire        ack_active;
    wire [31:0] fault_code;

    // Instantiate Unit Under Test (UUT)
    safety_controller uut (
        .clk(clk),
        .rst_n(rst_n),
        .data_valid(data_valid),
        .hr_val(hr_val),
        .spo2_val(spo2_val),
        .rr_val(rr_val),
        .temp_scaled(temp_scaled),
        .ack_btn(ack_btn),
        .state_out(state_out),
        .alarm_audio_en(alarm_audio_en),
        .alarm_visual_en(alarm_visual_en),
        .ack_active(ack_active),
        .fault_code(fault_code)
    );

    // Clock generator (10ns period = 100MHz)
    always #5 clk = ~clk;

    initial begin
        $display("=== STARTING SAFETY CONTROLLER VERILOG TESTBENCH ===");
        clk = 0;
        rst_n = 0;
        data_valid = 1;
        hr_val = 8'd75;
        spo2_val = 8'd98;
        rr_val = 8'd16;
        temp_scaled = 12'd370;
        ack_btn = 0;

        #20 rst_n = 1; // Release reset
        #10;

        // Test 1: Verify NORMAL state
        if (state_out === 2'b00 && alarm_audio_en === 0)
            $display("[PASS] Test 1: Normal baseline verified. State=%b", state_out);
        else
            $display("[FAIL] Test 1: Expected State=00, got %b", state_out);

        // Test 2: Trigger WARNING state (Mild Tachycardia: HR = 115)
        hr_val = 8'd115;
        #10;
        if (state_out === 2'b01 && alarm_audio_en === 1)
            $display("[PASS] Test 2: Warning state verified (HR=115). State=%b, Audio=%b", state_out, alarm_audio_en);
        else
            $display("[FAIL] Test 2: Expected State=01, got %b", state_out);

        // Test 3: Trigger CRITICAL state (Severe Hypoxia: SpO2 = 82%)
        spo2_val = 8'd82;
        #10;
        if (state_out === 2'b10 && alarm_audio_en === 1)
            $display("[PASS] Test 3: Critical state verified (SpO2=82). State=%b, Audio=%b", state_out, alarm_audio_en);
        else
            $display("[FAIL] Test 3: Expected State=10, got %b", state_out);

        // Test 4: Verify Clinician Acknowledgement silences audio
        ack_btn = 1;
        #10;
        ack_btn = 0;
        #10;
        if (state_out === 2'b10 && alarm_audio_en === 0 && ack_active === 1)
            $display("[PASS] Test 4: Clinician ACK verified. Audio silenced, State=%b", state_out);
        else
            $display("[FAIL] Test 4: ACK failed. Audio=%b, ACK=%b", alarm_audio_en, ack_active);

        // Test 5: Trigger DATA_FAULT (Sensor Disconnection: data_valid = 0)
        data_valid = 0;
        #10;
        if (state_out === 2'b11)
            $display("[PASS] Test 5: Data fault state verified (data_valid=0). State=%b", state_out);
        else
            $display("[FAIL] Test 5: Expected State=11, got %b", state_out);

        // Test 6: Recovery back to NORMAL
        data_valid = 1;
        hr_val = 8'd72;
        spo2_val = 8'd98;
        rr_val = 8'd15;
        temp_scaled = 12'd368;
        #10;
        if (state_out === 2'b00 && alarm_audio_en === 0 && ack_active === 0)
            $display("[PASS] Test 6: Recovery to NORMAL state verified. State=%b", state_out);
        else
            $display("[FAIL] Test 6: Recovery failed. State=%b", state_out);

        $display("=== ALL VERILOG TESTBENCH CHECKS COMPLETED ===");
        $finish;
    end

endmodule
