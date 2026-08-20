`timescale 1ns / 1ps

module tb_asic_core_wrapper_smoke;
    localparam SNAPSHOT_SAMPLES = 8;
    localparam SNAPSHOTS_PER_CHUNK = 2;

    reg clk = 1'b0;
    reg rst = 1'b1;
    reg start = 1'b0;
    reg sample_valid = 1'b0;
    reg signed [11:0] adc_data = 12'sd0;

    wire dut_sample_ready;
    wire dut_busy;
    wire dut_final_valid;
    wire [1:0] dut_final_pred_class;
    wire signed [31:0] dut_final_mem_nsr;
    wire signed [31:0] dut_final_mem_chf;
    wire signed [31:0] dut_final_mem_arr;
    wire signed [31:0] dut_final_mem_aff;

    wire ref_sample_ready;
    wire ref_busy;
    wire ref_final_valid;
    wire [1:0] ref_final_pred_class;
    wire signed [31:0] ref_final_mem_nsr;
    wire signed [31:0] ref_final_mem_chf;
    wire signed [31:0] ref_final_mem_arr;
    wire signed [31:0] ref_final_mem_aff;

    integer sample_idx;
    integer timeout_cycles;
    integer mismatch_count = 0;

    always #5 clk = ~clk;

    snn_ecg_asic_core_top #(
        .SNAPSHOT_SAMPLES(SNAPSHOT_SAMPLES),
        .SNAPSHOTS_PER_CHUNK(SNAPSHOTS_PER_CHUNK),
        .POST_DONE_TICKS(37)
    ) dut (
        .clk(clk),
        .rst(rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(dut_sample_ready),
        .busy(dut_busy),
        .final_valid(dut_final_valid),
        .final_pred_class(dut_final_pred_class),
        .final_mem_nsr(dut_final_mem_nsr),
        .final_mem_chf(dut_final_mem_chf),
        .final_mem_arr(dut_final_mem_arr),
        .final_mem_aff(dut_final_mem_aff)
    );

    snn_ecg_30min_final_top #(
        .SNAPSHOT_SAMPLES(SNAPSHOT_SAMPLES),
        .SNAPSHOTS_PER_CHUNK(SNAPSHOTS_PER_CHUNK),
        .POST_DONE_TICKS(37),
        .PROFILE_EN(1)
    ) reference (
        .clk(clk),
        .rst(rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(ref_sample_ready),
        .busy(ref_busy),
        .final_valid(ref_final_valid),
        .final_pred_class(ref_final_pred_class),
        .final_mem_nsr(ref_final_mem_nsr),
        .final_mem_chf(ref_final_mem_chf),
        .final_mem_arr(ref_final_mem_arr),
        .final_mem_aff(ref_final_mem_aff),
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

    always @(posedge clk) begin
        if (!rst) begin
            if ({dut_sample_ready, dut_busy, dut_final_valid,
                 dut_final_pred_class, dut_final_mem_nsr, dut_final_mem_chf,
                 dut_final_mem_arr, dut_final_mem_aff} !==
                {ref_sample_ready, ref_busy, ref_final_valid,
                 ref_final_pred_class, ref_final_mem_nsr, ref_final_mem_chf,
                 ref_final_mem_arr, ref_final_mem_aff}) begin
                mismatch_count = mismatch_count + 1;
                $display("ASIC_WRAPPER_MISMATCH time=%0t", $time);
            end
        end
    end

    initial begin
        repeat (6) @(posedge clk);
        rst <= 1'b0;
        repeat (3) @(posedge clk);

        start <= 1'b1;
        @(posedge clk);
        start <= 1'b0;

        for (sample_idx = 0; sample_idx < (SNAPSHOT_SAMPLES * SNAPSHOTS_PER_CHUNK); sample_idx = sample_idx + 1) begin
            while (!(dut_sample_ready && ref_sample_ready))
                @(posedge clk);
            adc_data <= $signed((sample_idx * 37) - 200);
            sample_valid <= 1'b1;
            @(posedge clk);
            sample_valid <= 1'b0;
            repeat (2) @(posedge clk);
        end

        timeout_cycles = 0;
        while (!dut_final_valid && timeout_cycles < 2000) begin
            @(posedge clk);
            timeout_cycles = timeout_cycles + 1;
        end

        if (!dut_final_valid) begin
            $display("ASIC_CORE_SMOKE_FAIL timeout");
            $fatal(1);
        end
        if (mismatch_count != 0) begin
            $display("ASIC_CORE_SMOKE_FAIL mismatches=%0d", mismatch_count);
            $fatal(1);
        end

        $display("ASIC_CORE_SMOKE_PASS class=%0d mem=%0d,%0d,%0d,%0d",
                 dut_final_pred_class, dut_final_mem_nsr, dut_final_mem_chf,
                 dut_final_mem_arr, dut_final_mem_aff);
        $finish;
    end
endmodule
