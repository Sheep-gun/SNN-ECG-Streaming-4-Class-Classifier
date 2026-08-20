`timescale 1ns / 1ps

// Fast mapped/post-route gate diagnostic using the same deterministic
// synthetic 16-sample sequence as the reduced RTL wrapper smoke.
//
// This test intentionally uses the canonical mapped gate netlist, so sixteen
// samples cannot produce a final 30-minute decision. It validates reset/start,
// ready/valid acceptance, known top-level state, and (when REQUIRE_DELAY=1)
// at least one non-zero clock-to-output transition in the gate timing model.
// SDF annotation diagnostics must still be checked for unmatched cells/pins;
// the delay observation alone cannot distinguish built-in specify delay from
// SDF override and does not prove that every annotated path was toggled.
module tb_snn_ecg_asic_gate_16sample_diag;
`ifndef ASIC_DUT_INSTANCE_NAME
`define ASIC_DUT_INSTANCE_NAME dut
`endif
    localparam integer SAMPLE_COUNT = 16;
    localparam integer READY_TIMEOUT_CYCLES = 200;

    reg clk = 1'b0;
    reg rst = 1'b1;
    reg start = 1'b0;
    reg sample_valid = 1'b0;
    reg signed [11:0] adc_data = 12'sd0;

    wire sample_ready;
    wire busy;
    wire final_valid;
    wire [1:0] final_pred_class;
    wire signed [31:0] final_mem_nsr;
    wire signed [31:0] final_mem_chf;
    wire signed [31:0] final_mem_arr;
    wire signed [31:0] final_mem_aff;

    integer index;
    integer wait_cycles;
    integer accepted_count = 0;
    integer ready_cycle_count = 0;
    integer busy_cycle_count = 0;
    integer unknown_count = 0;
    integer delayed_transition_count = 0;
    integer fail_count = 0;
    integer require_delay = 0;
    reg monitor_enable = 1'b0;
    realtime last_clock_posedge = 0.0;

    snn_ecg_asic_core_top `ASIC_DUT_INSTANCE_NAME (
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
        .final_mem_aff(final_mem_aff)
    );

`ifdef ASIC_SDF_FILE
    initial begin
        $display("ASIC_GATE_16S_SDF annotate=%s", `ASIC_SDF_FILE);
        $sdf_annotate(`ASIC_SDF_FILE, dut);
    end
`endif

    always #5 clk = ~clk;

    always @(posedge clk) begin
        last_clock_posedge = $realtime;
        if (monitor_enable && !rst) begin
            if (sample_valid && sample_ready)
                accepted_count = accepted_count + 1;
            if (sample_ready)
                ready_cycle_count = ready_cycle_count + 1;
            if (busy)
                busy_cycle_count = busy_cycle_count + 1;
            if ((^{sample_ready, busy, final_valid, final_pred_class,
                   final_mem_nsr, final_mem_chf, final_mem_arr,
                   final_mem_aff}) === 1'bx) begin
                unknown_count = unknown_count + 1;
                $display("ASIC_GATE_16S_UNKNOWN time=%0t", $time);
            end
        end
    end

    // With zero-delay cell models these transitions occur in the same time
    // slot as the active clock edge. A positive delta proves that at least one
    // exercised sequential/output path carries a non-zero gate-model delay.
    // A clean verbose SDF annotation log is separately required to attribute
    // that delay specifically to successful SDF back-annotation.
    always @(busy or sample_ready or final_valid) begin
        if (monitor_enable && !rst &&
            (($realtime - last_clock_posedge) > 0.0) &&
            (($realtime - last_clock_posedge) < 5.0)) begin
            delayed_transition_count = delayed_transition_count + 1;
        end
    end

    initial begin
        if (!$value$plusargs("REQUIRE_DELAY=%d", require_delay))
            require_delay = 0;

        repeat (8) @(posedge clk);
        @(negedge clk);
        rst = 1'b0;
        monitor_enable = 1'b1;
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        wait_cycles = 0;
        while ((busy !== 1'b1) && (wait_cycles < READY_TIMEOUT_CYCLES)) begin
            @(negedge clk);
            wait_cycles = wait_cycles + 1;
        end
        if (busy !== 1'b1) begin
            $display("ASIC_GATE_16S_FAIL busy did not assert");
            fail_count = fail_count + 1;
        end

        for (index = 0; index < SAMPLE_COUNT; index = index + 1) begin
            wait_cycles = 0;
            while ((sample_ready !== 1'b1) &&
                   (wait_cycles < READY_TIMEOUT_CYCLES)) begin
                @(negedge clk);
                wait_cycles = wait_cycles + 1;
            end
            if (sample_ready !== 1'b1) begin
                $display("ASIC_GATE_16S_FAIL ready timeout index=%0d", index);
                fail_count = fail_count + 1;
                index = SAMPLE_COUNT;
            end else begin
                sample_valid = 1'b1;
                adc_data = $signed((index * 37) - 200);
                @(negedge clk);
                sample_valid = 1'b0;
                adc_data = 12'sd0;
                repeat (2) @(negedge clk);
            end
        end

        repeat (20) @(posedge clk);

        if (accepted_count != SAMPLE_COUNT) begin
            $display("ASIC_GATE_16S_FAIL accepted=%0d expected=%0d",
                     accepted_count, SAMPLE_COUNT);
            fail_count = fail_count + 1;
        end
        if ((busy !== 1'b1) || (final_valid !== 1'b0)) begin
            $display("ASIC_GATE_16S_FAIL terminal busy=%0d final_valid=%0d",
                     busy, final_valid);
            fail_count = fail_count + 1;
        end
        if ((final_mem_nsr !== 32'sd0) ||
            (final_mem_chf !== 32'sd0) ||
            (final_mem_arr !== 32'sd0) ||
            (final_mem_aff !== 32'sd0)) begin
            $display("ASIC_GATE_16S_FAIL unexpected final membranes=%0d,%0d,%0d,%0d",
                     final_mem_nsr, final_mem_chf,
                     final_mem_arr, final_mem_aff);
            fail_count = fail_count + 1;
        end
        if ((ready_cycle_count == 0) || (busy_cycle_count == 0)) begin
            $display("ASIC_GATE_16S_FAIL no ready/busy activity ready=%0d busy=%0d",
                     ready_cycle_count, busy_cycle_count);
            fail_count = fail_count + 1;
        end
        if (unknown_count != 0) begin
            $display("ASIC_GATE_16S_FAIL unknown_observations=%0d", unknown_count);
            fail_count = fail_count + 1;
        end
        if ((require_delay != 0) && (delayed_transition_count == 0)) begin
            $display("ASIC_GATE_16S_FAIL no nonzero delayed transition observed");
            fail_count = fail_count + 1;
        end

        if (fail_count != 0) begin
            $display("ASIC_GATE_16S_FAIL_COUNT %0d", fail_count);
            $fatal(1);
        end

        $display("ASIC_GATE_16S_PASS samples=%0d ready_cycles=%0d busy_cycles=%0d delayed_transitions=%0d require_delay=%0d",
                 accepted_count, ready_cycle_count, busy_cycle_count,
                 delayed_transition_count, require_delay);
        $finish;
    end

endmodule
