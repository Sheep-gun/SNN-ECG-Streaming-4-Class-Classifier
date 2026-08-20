`timescale 1ns / 1ps

// Short timing-check diagnostic for the fixed post-route gate netlist.
// It does not replace the full manifest regression or claim a final decision.
module tb_snn_ecg_asic_sdf_timing_diag;
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

    snn_ecg_asic_core_top dut (
        .clk(clk), .rst(rst), .start(start),
        .sample_valid(sample_valid), .adc_data(adc_data),
        .sample_ready(sample_ready), .busy(busy), .final_valid(final_valid),
        .final_pred_class(final_pred_class),
        .final_mem_nsr(final_mem_nsr), .final_mem_chf(final_mem_chf),
        .final_mem_arr(final_mem_arr), .final_mem_aff(final_mem_aff)
    );

    always #5 clk = ~clk;

    initial begin
        repeat (8) @(posedge clk);
        @(negedge clk);
        rst = 1'b0;
        start = 1'b1;
        @(negedge clk);
        start = 1'b0;

        for (index = 0; index < 16; index = index + 1) begin
            while (!sample_ready)
                @(negedge clk);
            sample_valid = 1'b1;
            adc_data = $signed((index * 37) - 200);
            @(negedge clk);
            sample_valid = 1'b0;
            adc_data = 12'sd0;
            repeat (2) @(negedge clk);
        end
        repeat (200) @(posedge clk);
        $display("ASIC_SDF_TIMING_DIAG_DONE samples=16 busy=%0d final_valid=%0d", busy, final_valid);
        $finish;
    end
endmodule
