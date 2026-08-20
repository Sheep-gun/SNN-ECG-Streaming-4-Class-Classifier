`timescale 1ns / 1ps

// Full-default core-wrapper regression harness for RTL or gate netlists.
// Manifest columns:
// case_id expected_class sample_count mem_nsr mem_chf mem_arr mem_aff mem_path
module tb_snn_ecg_asic_core_manifest;
`ifndef ASIC_DUT_INSTANCE_NAME
`define ASIC_DUT_INSTANCE_NAME dut
`endif
    localparam MAX_SAMPLES = 1800000;
    localparam SAMPLE_GAP_CYCLES = 2;

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

    reg [11:0] sample_mem [0:MAX_SAMPLES-1];
    reg [8*1024-1:0] manifest_path;
    reg [8*1024-1:0] result_path;
    reg [8*1024-1:0] mem_path;

    integer manifest_fd;
    integer result_fd;
    integer scan_count;
    integer case_id_i;
    integer expected_class_i;
    integer sample_count_i;
    integer expected_mem_nsr_i;
    integer expected_mem_chf_i;
    integer expected_mem_arr_i;
    integer expected_mem_aff_i;
    integer sample_index;
    integer gap_count;
    integer cycles;
    integer timeout_cycles;
    integer total_count = 0;
    integer pass_count = 0;
    integer fail_count = 0;

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
        $display("ASIC_MANIFEST_SDF annotate=%s", `ASIC_SDF_FILE);
        $sdf_annotate(`ASIC_SDF_FILE, dut);
    end
`endif

    always #5 clk = ~clk;

    task reset_dut;
        begin
            @(negedge clk);
            rst = 1'b1;
            start = 1'b0;
            sample_valid = 1'b0;
            adc_data = 12'sd0;
            repeat (8) @(posedge clk);
            @(negedge clk);
            rst = 1'b0;
        end
    endtask

    task run_case;
        reg case_pass;
        begin
            $readmemh(mem_path, sample_mem);
            reset_dut();

            @(negedge clk);
            start = 1'b1;
            @(negedge clk);
            start = 1'b0;

            sample_index = 0;
            gap_count = 0;
            cycles = 0;
            timeout_cycles = (sample_count_i * (SAMPLE_GAP_CYCLES + 2)) + 20000;
            while ((final_valid !== 1'b1) && (cycles < timeout_cycles)) begin
                @(negedge clk);
                if ((sample_ready === 1'b1) && (gap_count == 0) &&
                    (sample_index < sample_count_i)) begin
                    sample_valid = 1'b1;
                    adc_data = sample_mem[sample_index];
                    sample_index = sample_index + 1;
                    gap_count = SAMPLE_GAP_CYCLES;
                end else begin
                    sample_valid = 1'b0;
                    adc_data = 12'sd0;
                    if (gap_count > 0)
                        gap_count = gap_count - 1;
                end
                @(posedge clk);
                #1;
                cycles = cycles + 1;
            end

            @(negedge clk);
            sample_valid = 1'b0;
            adc_data = 12'sd0;

            case_pass = (final_valid === 1'b1) &&
                        (sample_index == sample_count_i) &&
                        (final_pred_class === expected_class_i[1:0]) &&
                        (final_mem_nsr === expected_mem_nsr_i) &&
                        (final_mem_chf === expected_mem_chf_i) &&
                        (final_mem_arr === expected_mem_arr_i) &&
                        (final_mem_aff === expected_mem_aff_i);
            total_count = total_count + 1;
            if (case_pass)
                pass_count = pass_count + 1;
            else
                fail_count = fail_count + 1;

            $fdisplay(result_fd,
                "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                case_id_i, expected_class_i, final_pred_class, case_pass,
                final_valid, sample_index, cycles,
                expected_mem_nsr_i, final_mem_nsr,
                expected_mem_chf_i, final_mem_chf,
                expected_mem_arr_i, final_mem_arr,
                expected_mem_aff_i, final_mem_aff);
            $display("ASIC_MANIFEST_CASE case=%0d pass=%0d pred=%0d expected=%0d samples=%0d cycles=%0d mem=%0d,%0d,%0d,%0d",
                case_id_i, case_pass, final_pred_class, expected_class_i,
                sample_index, cycles, final_mem_nsr, final_mem_chf,
                final_mem_arr, final_mem_aff);
        end
    endtask

    initial begin
        if (!$value$plusargs("MANIFEST=%s", manifest_path)) begin
            $display("ASIC_MANIFEST_FAIL missing +MANIFEST=<path>");
            $fatal(1);
        end
        if (!$value$plusargs("RESULT=%s", result_path)) begin
            $display("ASIC_MANIFEST_FAIL missing +RESULT=<path>");
            $fatal(1);
        end
        manifest_fd = $fopen(manifest_path, "r");
        result_fd = $fopen(result_path, "w");
        if ((manifest_fd == 0) || (result_fd == 0)) begin
            $display("ASIC_MANIFEST_FAIL cannot open manifest/result");
            $fatal(1);
        end
        $fdisplay(result_fd,
            "case_id,expected_class,final_pred_class,pass,final_valid,samples,cycles,expected_mem_nsr,final_mem_nsr,expected_mem_chf,final_mem_chf,expected_mem_arr,final_mem_arr,expected_mem_aff,final_mem_aff");

        while (!$feof(manifest_fd)) begin
            mem_path = 0;
            scan_count = $fscanf(manifest_fd, "%d %d %d %d %d %d %d %s\n",
                case_id_i, expected_class_i, sample_count_i,
                expected_mem_nsr_i, expected_mem_chf_i,
                expected_mem_arr_i, expected_mem_aff_i, mem_path);
            if (scan_count == 8)
                run_case();
        end

        $fclose(manifest_fd);
        $fclose(result_fd);
        if (fail_count != 0) begin
            $display("ASIC_MANIFEST_FAIL pass=%0d total=%0d", pass_count, total_count);
            $fatal(1);
        end
        $display("ASIC_MANIFEST_PASS pass=%0d total=%0d", pass_count, total_count);
        $finish;
    end
endmodule
