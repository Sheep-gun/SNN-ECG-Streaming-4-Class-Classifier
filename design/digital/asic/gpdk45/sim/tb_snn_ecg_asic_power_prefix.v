`timescale 1ns / 1ps

// Matched-window activity harness for a short literal-1-kSPS power experiment.
//
// MODE=0: active-wait idle baseline after start, no accepted samples.
// MODE=1: raw ECG prefix, one accepted sample per CYCLES_PER_SAMPLE clocks.
//
// Defaults are 100 samples, 100 MHz clock, and 1 kSPS:
//   100000 clocks/sample = 1 processing clock + 99999 intervening clocks.
// The 0.1 s window does not reach a 60000-sample snapshot or final decision.
module tb_snn_ecg_asic_power_prefix;
`ifndef ASIC_DUT_INSTANCE_NAME
`define ASIC_DUT_INSTANCE_NAME dut
`endif
    localparam integer MAX_PREFIX_SAMPLES = 1024;
    localparam integer READY_TIMEOUT_CYCLES = 1000;

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

    reg [11:0] sample_mem [0:MAX_PREFIX_SAMPLES-1];
    reg [8*1024-1:0] mem_path;

    integer mode = 1;
    integer prefix_samples = 100;
    integer cycles_per_sample = 100000;
    integer warmup_cycles = 100;
    integer dump_sync = 0;
    integer total_window_cycles;
    integer cycle_index;
    integer cycle_in_period;
    integer sample_index;
    integer accepted_count;
    integer ready_wait;
    integer fail_count = 0;
    integer unknown_count = 0;
    integer scan_count;
    reg measurement_active = 1'b0;

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

    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (measurement_active && sample_valid && sample_ready) begin
            accepted_count = accepted_count + 1;
            sample_index = sample_index + 1;
        end
        if (!rst &&
            ((^{sample_ready, busy, final_valid, final_pred_class,
               final_mem_nsr, final_mem_chf, final_mem_arr,
               final_mem_aff}) === 1'bx)) begin
            unknown_count = unknown_count + 1;
        end
    end

    initial begin
        if (!$value$plusargs("MODE=%d", mode))
            scan_count = $value$plusargs("MODE+%d", mode);
        if (!$value$plusargs("PREFIX_SAMPLES=%d", prefix_samples))
            scan_count = $value$plusargs("PREFIX_SAMPLES+%d", prefix_samples);
        if (!$value$plusargs("CYCLES_PER_SAMPLE=%d", cycles_per_sample))
            scan_count = $value$plusargs("CYCLES_PER_SAMPLE+%d", cycles_per_sample);
        if (!$value$plusargs("WARMUP_CYCLES=%d", warmup_cycles))
            scan_count = $value$plusargs("WARMUP_CYCLES+%d", warmup_cycles);
        if (!$value$plusargs("DUMP_SYNC=%d", dump_sync))
            scan_count = $value$plusargs("DUMP_SYNC+%d", dump_sync);

        if ((mode != 0) && (mode != 1)) begin
            $display("ASIC_POWER_PREFIX_FAIL MODE must be 0 or 1, got=%0d", mode);
            $fatal(1);
        end
        if ((prefix_samples <= 0) ||
            (prefix_samples > MAX_PREFIX_SAMPLES) ||
            (cycles_per_sample <= 1) ||
            (warmup_cycles < 0)) begin
            $display("ASIC_POWER_PREFIX_FAIL invalid configuration samples=%0d cycles_per_sample=%0d warmup=%0d",
                     prefix_samples, cycles_per_sample, warmup_cycles);
            $fatal(1);
        end

        mem_path = 0;
        if (mode == 1) begin
            if (!$value$plusargs("MEM=%s", mem_path) &&
                !$value$plusargs("MEM+%s", mem_path)) begin
                $display("ASIC_POWER_PREFIX_FAIL MODE=1 requires +MEM=<prefix.mem>");
                $fatal(1);
            end
            $readmemh(mem_path, sample_mem, 0, prefix_samples - 1);
        end

        repeat (8) @(posedge clk);
        @(negedge clk);
        rst = 1'b0;
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        ready_wait = 0;
        while ((sample_ready !== 1'b1) &&
               (ready_wait < READY_TIMEOUT_CYCLES)) begin
            @(negedge clk);
            ready_wait = ready_wait + 1;
        end
        if ((sample_ready !== 1'b1) || (busy !== 1'b1)) begin
            $display("ASIC_POWER_PREFIX_FAIL did not enter active-wait state ready=%0d busy=%0d",
                     sample_ready, busy);
            $fatal(1);
        end

        repeat (warmup_cycles) @(posedge clk);
        total_window_cycles = prefix_samples * cycles_per_sample;
        accepted_count = 0;
        sample_index = 0;
        cycle_in_period = 0;

        // Stop at a falling edge so the dump Tcl can open the database before
        // the first measured rising edge. Both modes use the same window.
        @(negedge clk);
        measurement_active = 1'b1;
        $display("ASIC_POWER_PREFIX_WINDOW_BEGIN mode=%0d samples=%0d cycles_per_sample=%0d window_cycles=%0d",
                 mode, prefix_samples, cycles_per_sample, total_window_cycles);
        if (dump_sync != 0)
            $stop;

        for (cycle_index = 0;
             cycle_index < total_window_cycles;
             cycle_index = cycle_index + 1) begin
            if (cycle_index != 0)
                @(negedge clk);

            if ((mode == 1) && (cycle_in_period == 0)) begin
                if ((sample_ready !== 1'b1) ||
                    (sample_index >= prefix_samples)) begin
                    $display("ASIC_POWER_PREFIX_FAIL scheduled sample not ready cycle=%0d index=%0d ready=%0d",
                             cycle_index, sample_index, sample_ready);
                    fail_count = fail_count + 1;
                    sample_valid = 1'b0;
                    adc_data = 12'sd0;
                end else begin
                    sample_valid = 1'b1;
                    adc_data = sample_mem[sample_index];
                end
            end else begin
                sample_valid = 1'b0;
                if ((mode == 1) && (sample_index > 0))
                    adc_data = sample_mem[sample_index - 1];
                else
                    adc_data = 12'sd0;
            end

            @(posedge clk);
            #1;

            if (cycle_in_period == (cycles_per_sample - 1))
                cycle_in_period = 0;
            else
                cycle_in_period = cycle_in_period + 1;
        end

        @(negedge clk);
        measurement_active = 1'b0;
        sample_valid = 1'b0;
        adc_data = 12'sd0;
        $display("ASIC_POWER_PREFIX_WINDOW_END mode=%0d accepted=%0d window_cycles=%0d",
                 mode, accepted_count, total_window_cycles);
        if (dump_sync != 0)
            $stop;

        if ((mode == 0) && (accepted_count != 0)) begin
            $display("ASIC_POWER_PREFIX_FAIL idle mode accepted=%0d", accepted_count);
            fail_count = fail_count + 1;
        end
        if ((mode == 1) && (accepted_count != prefix_samples)) begin
            $display("ASIC_POWER_PREFIX_FAIL literal mode accepted=%0d expected=%0d",
                     accepted_count, prefix_samples);
            fail_count = fail_count + 1;
        end
        if ((busy !== 1'b1) || (final_valid !== 1'b0)) begin
            $display("ASIC_POWER_PREFIX_FAIL terminal busy=%0d final_valid=%0d",
                     busy, final_valid);
            fail_count = fail_count + 1;
        end
        if (unknown_count != 0) begin
            $display("ASIC_POWER_PREFIX_FAIL unknown_observations=%0d", unknown_count);
            fail_count = fail_count + 1;
        end
        if (fail_count != 0) begin
            $display("ASIC_POWER_PREFIX_FAIL_COUNT %0d", fail_count);
            $fatal(1);
        end else begin
            $display("ASIC_POWER_PREFIX_PASS mode=%0d accepted=%0d samples=%0d cycles_per_sample=%0d window_cycles=%0d",
                     mode, accepted_count, prefix_samples,
                     cycles_per_sample, total_window_cycles);
        end
        $finish;
    end

endmodule
