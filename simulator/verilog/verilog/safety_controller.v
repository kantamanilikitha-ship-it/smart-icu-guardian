// =============================================================================
// Smart ICU Guardian: Verilog Safety Controller
// Module: safety_controller
// Description: Deterministic hardware safety controller monitoring patient vitals
// States: 
//   2'b00: NORMAL
//   2'b01: WARNING
//   2'b10: CRITICAL
//   2'b11: DATA_FAULT
// Educational ICU Telemetry Safety FSM
// =============================================================================

`timescale 1ns / 1ps

module safety_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        data_valid,
    input  wire [7:0]  hr_val,
    input  wire [7:0]  spo2_val,
    input  wire [7:0]  rr_val,
    input  wire [11:0] temp_scaled,      // Temp in tenths of °C (e.g., 370 = 37.0°C)
    input  wire        ack_btn,
    output reg  [1:0]  state_out,
    output reg         alarm_audio_en,
    output reg         alarm_visual_en,
    output reg         ack_active,
    output reg  [31:0] fault_code        // Bitmask for root cause identification
);

    // State definitions
    localparam STATE_NORMAL     = 2'b00;
    localparam STATE_WARNING    = 2'b01;
    localparam STATE_CRITICAL   = 2'b10;
    localparam STATE_DATA_FAULT = 2'b11;

    // Threshold constants derived from config/thresholds.json
    localparam [7:0]  HR_WARN_MIN   = 8'd50;
    localparam [7:0]  HR_WARN_MAX   = 8'd110;
    localparam [7:0]  HR_CRIT_MIN   = 8'd40;
    localparam [7:0]  HR_CRIT_MAX   = 8'd130;

    localparam [7:0]  SPO2_WARN_MIN = 8'd90;
    localparam [7:0]  SPO2_CRIT_MAX = 8'd85;

    localparam [7:0]  RR_WARN_MIN   = 8'd10;
    localparam [7:0]  RR_WARN_MAX   = 8'd24;
    localparam [7:0]  RR_CRIT_MIN   = 8'd6;
    localparam [7:0]  RR_CRIT_MAX   = 8'd30;

    localparam [11:0] TEMP_WARN_MIN = 12'd355; // 35.5 C
    localparam [11:0] TEMP_WARN_MAX = 12'd380; // 38.0 C
    localparam [11:0] TEMP_CRIT_MIN = 12'd340; // 34.0 C
    localparam [11:0] TEMP_CRIT_MAX = 12'd400; // 40.0 C

    // Combinatorial condition flags
    wire is_critical;
    wire is_warning;

    wire crit_hr   = (hr_val < HR_CRIT_MIN) || (hr_val > HR_CRIT_MAX);
    wire crit_spo2 = (spo2_val <= SPO2_CRIT_MAX);
    wire crit_rr   = (rr_val < RR_CRIT_MIN) || (rr_val > RR_CRIT_MAX);
    wire crit_temp = (temp_scaled < TEMP_CRIT_MIN) || (temp_scaled > TEMP_CRIT_MAX);

    wire warn_hr   = ((hr_val < HR_WARN_MIN) && (hr_val >= HR_CRIT_MIN)) || 
                     ((hr_val > HR_WARN_MAX) && (hr_val <= HR_CRIT_MAX));
    wire warn_spo2 = (spo2_val < SPO2_WARN_MIN) && (spo2_val > SPO2_CRIT_MAX);
    wire warn_rr   = ((rr_val < RR_WARN_MIN) && (rr_val >= RR_CRIT_MIN)) || 
                     ((rr_val > RR_WARN_MAX) && (rr_val <= RR_CRIT_MAX));
    wire warn_temp = ((temp_scaled < TEMP_WARN_MIN) && (temp_scaled >= TEMP_CRIT_MIN)) || 
                     ((temp_scaled > TEMP_WARN_MAX) && (temp_scaled <= TEMP_CRIT_MAX));

    assign is_critical = crit_hr | crit_spo2 | crit_rr | crit_temp;
    assign is_warning  = warn_hr | warn_spo2 | warn_rr | warn_temp;

    // Next state logic
    reg [1:0] next_state;
    reg [31:0] next_fault_code;

    always @(*) begin
        next_fault_code = 32'd0;
        if (!data_valid) begin
            next_state = STATE_DATA_FAULT;
            next_fault_code[0] = 1'b1; // Signal invalid / sensor disconnected
        end else if (is_critical) begin
            next_state = STATE_CRITICAL;
            if (crit_hr)   next_fault_code[1] = 1'b1;
            if (crit_spo2) next_fault_code[2] = 1'b1;
            if (crit_rr)   next_fault_code[3] = 1'b1;
            if (crit_temp) next_fault_code[4] = 1'b1;
        end else if (is_warning) begin
            next_state = STATE_WARNING;
            if (warn_hr)   next_fault_code[5] = 1'b1;
            if (warn_spo2) next_fault_code[6] = 1'b1;
            if (warn_rr)   next_fault_code[7] = 1'b1;
            if (warn_temp) next_fault_code[8] = 1'b1;
        end else begin
            next_state = STATE_NORMAL;
        end
    end

    // Sequential State Update & Audio/Visual Driver
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_out       <= STATE_NORMAL;
            alarm_audio_en  <= 1'b0;
            alarm_visual_en <= 1'b0;
            ack_active      <= 1'b0;
            fault_code      <= 32'd0;
        end else begin
            state_out  <= next_state;
            fault_code <= next_fault_code;

            // Handle Acknowledgement button
            if (ack_btn) begin
                ack_active <= 1'b1;
            end else if (next_state == STATE_NORMAL) begin
                ack_active <= 1'b0; // Reset ACK on return to healthy state
            end

            // Drive visual and audio alarm outputs
            case (next_state)
                STATE_NORMAL: begin
                    alarm_audio_en  <= 1'b0;
                    alarm_visual_en <= 1'b0;
                end

                STATE_WARNING: begin
                    alarm_visual_en <= 1'b1;
                    alarm_audio_en  <= (ack_btn || ack_active) ? 1'b0 : 1'b1;
                end

                STATE_CRITICAL: begin
                    alarm_visual_en <= 1'b1;
                    alarm_audio_en  <= (ack_btn || ack_active) ? 1'b0 : 1'b1;
                end

                STATE_DATA_FAULT: begin
                    alarm_visual_en <= 1'b1;
                    alarm_audio_en  <= (ack_btn || ack_active) ? 1'b0 : 1'b1;
                end

                default: begin
                    alarm_audio_en  <= 1'b0;
                    alarm_visual_en <= 1'b0;
                end
            endcase
        end
    end

endmodule
