`timescale 1ns / 1ps

// Core-only ASIC implementation boundary.
//
// The canonical classifier remains snn_ecg_30min_final_top. This wrapper
// removes FPGA-facing profiling/debug ports from the physical-design boundary
// and disables their counters so that PPA reflects the functional classifier.
module snn_ecg_asic_core_top #(
    parameter SNAPSHOT_SAMPLES = 60000,
    parameter SNAPSHOTS_PER_CHUNK = 30,
    parameter POST_DONE_TICKS = 37
)(
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        start,
    input  wire                        sample_valid,
    input  wire signed [11:0]          adc_data,
    output wire                        sample_ready,
    output wire                        busy,
    output wire                        final_valid,
    output wire [1:0]                  final_pred_class,
    output wire signed [31:0]          final_mem_nsr,
    output wire signed [31:0]          final_mem_chf,
    output wire signed [31:0]          final_mem_arr,
    output wire signed [31:0]          final_mem_aff
);

    snn_ecg_30min_final_top #(
        .ADC_WIDTH(12),
        .SNAPSHOT_SAMPLES(SNAPSHOT_SAMPLES),
        .SNAPSHOTS_PER_CHUNK(SNAPSHOTS_PER_CHUNK),
        .POST_DONE_TICKS(POST_DONE_TICKS),
        .PROFILE_EN(0),
        .PROF_COUNTER_W(64)
    ) u_core (
        .clk(clk),
        .rst(rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(sample_ready),
        .busy(busy),
        .final_valid(final_valid),
        .final_pred_class(final_pred_class),
        .final_mem_nsr(final_mem_nsr),
        .final_mem_chf(final_mem_chf),
        .final_mem_arr(final_mem_arr),
        .final_mem_aff(final_mem_aff),
        .snapshot_index_dbg(),
        .prof_total_cycle_counter(),
        .prof_busy_cycle_counter(),
        .prof_run_cycle_counter(),
        .prof_input_wait_cycle_counter(),
        .prof_accepted_sample_counter(),
        .prof_window_counter(),
        .prof_decision_counter(),
        .prof_last_window_latency(),
        .prof_max_window_latency(),
        .prof_last_decision_latency()
    );

endmodule
