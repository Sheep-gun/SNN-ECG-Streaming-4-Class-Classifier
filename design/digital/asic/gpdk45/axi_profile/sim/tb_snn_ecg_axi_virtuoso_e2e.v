`timescale 1ns / 1ps

// Replays a canonical signed 12-bit ADC dump through both project-owned
// digital boundaries: the direct classifier core and the AXI4-Lite/AXI-Stream
// integration wrapper.  The manifest is whitespace-delimited:
// case_id expected_class sample_count exp_nsr exp_chf exp_arr exp_aff case_name mem_path
module tb_snn_ecg_axi_virtuoso_e2e #(
    parameter MAX_SAMPLES = 1800000,
    parameter MANIFEST_FILE = "",
    parameter RESULT_CSV = "",
    parameter SAMPLE_GAP_CYCLES = 2,
    parameter DUT_SNAPSHOT_SAMPLES = 60000,
    parameter DUT_SNAPSHOTS_PER_CHUNK = 30,
    parameter DUT_POST_DONE_TICKS = 37
)();
    localparam integer AXI_ADDR_WIDTH = 12;
    localparam integer AXI_DATA_WIDTH = 32;
    localparam integer S_AXIS_TDATA_WIDTH = 16;

    localparam [AXI_ADDR_WIDTH-1:0] ADDR_CONTROL          = 12'h000;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_STATUS           = 12'h004;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_ERROR_STATUS     = 12'h008;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_TOTAL_SAMPLES    = 12'h010;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_SAMPLES_ACCEPTED = 12'h014;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_SAMPLES_CONSUMED = 12'h018;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_FINAL_MEM_NSR    = 12'h020;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_FINAL_MEM_CHF    = 12'h024;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_FINAL_MEM_ARR    = 12'h028;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_FINAL_MEM_AFF    = 12'h02c;
    localparam [AXI_ADDR_WIDTH-1:0] ADDR_FINAL_PRED       = 12'h030;

    reg clk = 1'b0;
    reg aresetn = 1'b0;
    reg ref_rst = 1'b1;
    reg ref_start = 1'b0;

    reg [AXI_ADDR_WIDTH-1:0] awaddr = 0;
    reg [2:0] awprot = 0;
    reg awvalid = 1'b0;
    wire awready;
    reg [AXI_DATA_WIDTH-1:0] wdata = 0;
    reg [(AXI_DATA_WIDTH/8)-1:0] wstrb = 0;
    reg wvalid = 1'b0;
    wire wready;
    wire [1:0] bresp;
    wire bvalid;
    reg bready = 1'b0;

    reg [AXI_ADDR_WIDTH-1:0] araddr = 0;
    reg [2:0] arprot = 0;
    reg arvalid = 1'b0;
    wire arready;
    wire [AXI_DATA_WIDTH-1:0] rdata;
    wire [1:0] rresp;
    wire rvalid;
    reg rready = 1'b0;

    reg [S_AXIS_TDATA_WIDTH-1:0] tdata = 0;
    reg tvalid = 1'b0;
    wire tready;
    reg tlast = 1'b0;
    wire irq;

    reg ref_sample_valid = 1'b0;
    reg signed [11:0] ref_adc_data = 12'sd0;
    wire ref_sample_ready;
    wire ref_busy;
    wire ref_final_valid;
    wire [1:0] ref_final_pred_class;
    wire signed [31:0] ref_final_mem_nsr;
    wire signed [31:0] ref_final_mem_chf;
    wire signed [31:0] ref_final_mem_arr;
    wire signed [31:0] ref_final_mem_aff;

    reg ref_final_seen = 1'b0;
    reg [1:0] ref_pred_latched = 2'd0;
    reg signed [31:0] ref_mem_nsr_latched = 32'sd0;
    reg signed [31:0] ref_mem_chf_latched = 32'sd0;
    reg signed [31:0] ref_mem_arr_latched = 32'sd0;
    reg signed [31:0] ref_mem_aff_latched = 32'sd0;

    reg [11:0] sample_mem [0:MAX_SAMPLES-1];
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
    reg [8*256-1:0] case_name_i;
    reg [8*512-1:0] mem_path_i;
    reg [8*512-1:0] manifest_path_runtime;
    reg [8*512-1:0] result_path_runtime;

    integer sample_index;
    integer gap_count;
    integer drive_fire;
    integer cycles;
    integer timeout_cycles;
    integer fail_count = 0;
    integer fail_before_case;
    integer total_cases = 0;
    integer passed_cases = 0;
    reg [31:0] rd_status;
    reg [31:0] rd_error;
    reg [31:0] rd_total;
    reg [31:0] rd_accepted;
    reg [31:0] rd_consumed;
    reg [31:0] rd_pred;
    reg [31:0] rd_mem_nsr;
    reg [31:0] rd_mem_chf;
    reg [31:0] rd_mem_arr;
    reg [31:0] rd_mem_aff;

    always #5 clk = ~clk;

    snn_ecg_axi_asic_top #(
        .SNAPSHOT_SAMPLES(DUT_SNAPSHOT_SAMPLES),
        .SNAPSHOTS_PER_CHUNK(DUT_SNAPSHOTS_PER_CHUNK),
        .POST_DONE_TICKS(DUT_POST_DONE_TICKS)
    ) dut (
        .s_axi_aclk(clk), .s_axi_aresetn(aresetn),
        .s_axi_awaddr(awaddr), .s_axi_awprot(awprot),
        .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(wstrb),
        .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(arprot),
        .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp),
        .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .s_axis_tdata(tdata), .s_axis_tvalid(tvalid),
        .s_axis_tready(tready), .s_axis_tlast(tlast), .irq(irq)
    );

    snn_ecg_asic_core_top #(
        .SNAPSHOT_SAMPLES(DUT_SNAPSHOT_SAMPLES),
        .SNAPSHOTS_PER_CHUNK(DUT_SNAPSHOTS_PER_CHUNK),
        .POST_DONE_TICKS(DUT_POST_DONE_TICKS)
    ) reference (
        .clk(clk), .rst(ref_rst), .start(ref_start),
        .sample_valid(ref_sample_valid), .adc_data(ref_adc_data),
        .sample_ready(ref_sample_ready), .busy(ref_busy),
        .final_valid(ref_final_valid),
        .final_pred_class(ref_final_pred_class),
        .final_mem_nsr(ref_final_mem_nsr), .final_mem_chf(ref_final_mem_chf),
        .final_mem_arr(ref_final_mem_arr), .final_mem_aff(ref_final_mem_aff)
    );

`ifdef AXI_SDF_FILE
    initial begin
        $display("VIRTUOSO_AXI_E2E_SDF_ANNOTATE file=%0s", `AXI_SDF_FILE);
        $sdf_annotate(`AXI_SDF_FILE, dut);
    end
`endif

    always @(posedge clk) begin
        if (ref_rst) begin
            ref_final_seen <= 1'b0;
            ref_pred_latched <= 2'd0;
            ref_mem_nsr_latched <= 32'sd0;
            ref_mem_chf_latched <= 32'sd0;
            ref_mem_arr_latched <= 32'sd0;
            ref_mem_aff_latched <= 32'sd0;
        end else if (ref_final_valid) begin
            ref_final_seen <= 1'b1;
            ref_pred_latched <= ref_final_pred_class;
            ref_mem_nsr_latched <= ref_final_mem_nsr;
            ref_mem_chf_latched <= ref_final_mem_chf;
            ref_mem_arr_latched <= ref_final_mem_arr;
            ref_mem_aff_latched <= ref_final_mem_aff;
        end
    end

    task record_fail;
        input [8*128-1:0] reason;
        begin
            $display("VIRTUOSO_AXI_E2E_FAIL case=%0d name=%0s reason=%0s",
                     case_id_i, case_name_i, reason);
            fail_count = fail_count + 1;
        end
    endtask

    task axi_write;
        input [AXI_ADDR_WIDTH-1:0] addr;
        input [31:0] data;
        begin
            @(posedge clk);
            awaddr <= addr;
            wdata <= data;
            wstrb <= 4'hf;
            awvalid <= 1'b1;
            wvalid <= 1'b1;
            bready <= 1'b1;
            while (!(awready && wready)) @(posedge clk);
            @(posedge clk);
            awvalid <= 1'b0;
            wvalid <= 1'b0;
            wait (bvalid);
            if (bresp !== 2'b00)
                record_fail("AXI write response");
            @(posedge clk);
            bready <= 1'b0;
            awaddr <= 0;
            wdata <= 0;
            wstrb <= 0;
        end
    endtask

    task axi_read;
        input [AXI_ADDR_WIDTH-1:0] addr;
        output [31:0] data;
        begin
            @(posedge clk);
            araddr <= addr;
            arvalid <= 1'b1;
            wait (arready);
            @(posedge clk);
            arvalid <= 1'b0;
            wait (rvalid);
            data = rdata;
            if (rresp !== 2'b00)
                record_fail("AXI read response");
            rready <= 1'b1;
            @(posedge clk);
            rready <= 1'b0;
            araddr <= 0;
        end
    endtask

    task reset_both;
        begin
            @(negedge clk);
            aresetn = 1'b0;
            ref_rst = 1'b1;
            ref_start = 1'b0;
            ref_sample_valid = 1'b0;
            ref_adc_data = 12'sd0;
            tvalid = 1'b0;
            tlast = 1'b0;
            tdata = 0;
            awvalid = 1'b0;
            wvalid = 1'b0;
            bready = 1'b0;
            arvalid = 1'b0;
            rready = 1'b0;
            repeat (8) @(posedge clk);
            @(negedge clk);
            aresetn = 1'b1;
            ref_rst = 1'b0;
            repeat (8) @(posedge clk);
        end
    endtask

    task start_both;
        begin
            axi_write(ADDR_CONTROL, 32'h00000001);
            @(negedge clk);
            ref_start = 1'b1;
            @(posedge clk);
            #1;
            @(negedge clk);
            ref_start = 1'b0;
        end
    endtask

    task run_case;
        begin
            fail_before_case = fail_count;
            total_cases = total_cases + 1;
            if ((sample_count_i <= 0) || (sample_count_i > MAX_SAMPLES)) begin
                record_fail("invalid sample_count");
            end else if ((expected_class_i < 0) || (expected_class_i > 3)) begin
                record_fail("invalid expected_class");
            end else begin
                $readmemh(mem_path_i, sample_mem, 0, sample_count_i - 1);
                reset_both();
                start_both();

                sample_index = 0;
                gap_count = 0;
                cycles = 0;
                timeout_cycles = (sample_count_i * (SAMPLE_GAP_CYCLES + 4)) + 50000;

                while ((sample_index < sample_count_i) && (cycles < timeout_cycles)) begin
                    @(negedge clk);
                    drive_fire = 0;
                    if ((gap_count == 0) && (tready === 1'b1) &&
                        (ref_sample_ready === 1'b1)) begin
                        if (^sample_mem[sample_index] === 1'bx) begin
                            record_fail("unknown ADC token");
                            sample_index = sample_count_i;
                        end else begin
                            tdata = {{4{sample_mem[sample_index][11]}}, sample_mem[sample_index]};
                            ref_adc_data = sample_mem[sample_index];
                            tlast = (sample_index == (sample_count_i - 1));
                            tvalid = 1'b1;
                            ref_sample_valid = 1'b1;
                            // ready was sampled before the active edge.  Use
                            // this decision after the edge instead of reading
                            // the newly updated registered ready signals.
                            drive_fire = 1;
                        end
                    end else begin
                        tvalid = 1'b0;
                        ref_sample_valid = 1'b0;
                        tlast = 1'b0;
                        tdata = 0;
                        ref_adc_data = 12'sd0;
                    end
                    @(posedge clk);
                    #1;
                    if (drive_fire != 0) begin
                        sample_index = sample_index + 1;
                        gap_count = SAMPLE_GAP_CYCLES;
                    end else if (gap_count > 0) begin
                        gap_count = gap_count - 1;
                    end
                    cycles = cycles + 1;
                end

                @(negedge clk);
                tvalid = 1'b0;
                ref_sample_valid = 1'b0;
                tlast = 1'b0;
                tdata = 0;
                ref_adc_data = 12'sd0;

                while (((irq !== 1'b1) || (ref_final_seen !== 1'b1)) &&
                       (cycles < timeout_cycles)) begin
                    @(posedge clk);
                    #1;
                    cycles = cycles + 1;
                end

                if (sample_index != sample_count_i)
                    record_fail("stream timeout or sample count mismatch");
                if (irq !== 1'b1)
                    record_fail("AXI completion timeout");
                if (ref_final_seen !== 1'b1)
                    record_fail("reference completion timeout");

                axi_read(ADDR_STATUS, rd_status);
                axi_read(ADDR_ERROR_STATUS, rd_error);
                axi_read(ADDR_TOTAL_SAMPLES, rd_total);
                axi_read(ADDR_SAMPLES_ACCEPTED, rd_accepted);
                axi_read(ADDR_SAMPLES_CONSUMED, rd_consumed);
                axi_read(ADDR_FINAL_PRED, rd_pred);
                axi_read(ADDR_FINAL_MEM_NSR, rd_mem_nsr);
                axi_read(ADDR_FINAL_MEM_CHF, rd_mem_chf);
                axi_read(ADDR_FINAL_MEM_ARR, rd_mem_arr);
                axi_read(ADDR_FINAL_MEM_AFF, rd_mem_aff);

                if (rd_status[2:1] !== 2'b11)
                    record_fail("AXI done/result status");
                if (rd_error !== 32'd0)
                    record_fail("AXI error_status nonzero");
                if (rd_total !== sample_count_i)
                    record_fail("configured total sample mismatch");
                if (rd_accepted !== sample_count_i)
                    record_fail("AXI accepted sample mismatch");
                if (rd_consumed !== sample_count_i)
                    record_fail("AXI consumed sample mismatch");
                if ((rd_pred[0] !== 1'b1) || (rd_pred[8] !== 1'b1))
                    record_fail("AXI result-valid bits");
                if (rd_pred[2:1] !== expected_class_i[1:0])
                    record_fail("AXI expected class mismatch");
                if (ref_pred_latched !== expected_class_i[1:0])
                    record_fail("reference expected class mismatch");
                if (rd_pred[2:1] !== ref_pred_latched)
                    record_fail("AXI/reference class mismatch");

                if ($signed(rd_mem_nsr) !== expected_mem_nsr_i)
                    record_fail("AXI expected NSR membrane mismatch");
                if ($signed(rd_mem_chf) !== expected_mem_chf_i)
                    record_fail("AXI expected CHF membrane mismatch");
                if ($signed(rd_mem_arr) !== expected_mem_arr_i)
                    record_fail("AXI expected ARR membrane mismatch");
                if ($signed(rd_mem_aff) !== expected_mem_aff_i)
                    record_fail("AXI expected AFF membrane mismatch");
                if ((ref_mem_nsr_latched !== expected_mem_nsr_i) ||
                    (ref_mem_chf_latched !== expected_mem_chf_i) ||
                    (ref_mem_arr_latched !== expected_mem_arr_i) ||
                    (ref_mem_aff_latched !== expected_mem_aff_i))
                    record_fail("reference expected membrane mismatch");
                if (($signed(rd_mem_nsr) !== ref_mem_nsr_latched) ||
                    ($signed(rd_mem_chf) !== ref_mem_chf_latched) ||
                    ($signed(rd_mem_arr) !== ref_mem_arr_latched) ||
                    ($signed(rd_mem_aff) !== ref_mem_aff_latched))
                    record_fail("AXI/reference membrane mismatch");
            end

            if (fail_count == fail_before_case) begin
                passed_cases = passed_cases + 1;
                $display("VIRTUOSO_AXI_E2E_CASE_PASS case=%0d name=%0s samples=%0d pred=%0d mem=%0d/%0d/%0d/%0d cycles=%0d",
                         case_id_i, case_name_i, sample_count_i, rd_pred[2:1],
                         $signed(rd_mem_nsr), $signed(rd_mem_chf),
                         $signed(rd_mem_arr), $signed(rd_mem_aff), cycles);
            end
            $fdisplay(result_fd,
                "%0d,%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                case_id_i, case_name_i, sample_count_i, expected_class_i,
                rd_pred[2:1], ref_pred_latched,
                expected_mem_nsr_i, expected_mem_chf_i, expected_mem_arr_i, expected_mem_aff_i,
                $signed(rd_mem_nsr), $signed(rd_mem_chf), $signed(rd_mem_arr), $signed(rd_mem_aff),
                ref_mem_nsr_latched, ref_mem_chf_latched, ref_mem_arr_latched, ref_mem_aff_latched,
                rd_accepted, rd_consumed, (fail_count == fail_before_case));
        end
    endtask

    initial begin
        manifest_path_runtime = MANIFEST_FILE;
        result_path_runtime = RESULT_CSV;
        // Plusargs provide a Python-free entry point for restricted Cadence
        // servers.  Static parameters remain convenient for XSim wrappers.
        if ($value$plusargs("MANIFEST=%s", manifest_path_runtime))
            $display("VIRTUOSO_AXI_E2E_MANIFEST file=%0s", manifest_path_runtime);
        if ($value$plusargs("RESULT=%s", result_path_runtime))
            $display("VIRTUOSO_AXI_E2E_RESULT_FILE file=%0s", result_path_runtime);
        if ((manifest_path_runtime == 0) || (result_path_runtime == 0)) begin
            $display("VIRTUOSO_AXI_E2E_FAIL manifest/result parameters are required");
            $fatal(1);
        end
        manifest_fd = $fopen(manifest_path_runtime, "r");
        if (manifest_fd == 0) begin
            $display("VIRTUOSO_AXI_E2E_FAIL cannot open manifest=%0s", manifest_path_runtime);
            $fatal(1);
        end
        result_fd = $fopen(result_path_runtime, "w");
        if (result_fd == 0) begin
            $display("VIRTUOSO_AXI_E2E_FAIL cannot open result=%0s", result_path_runtime);
            $fatal(1);
        end
        $fdisplay(result_fd,
            "case_id,case_name,sample_count,expected_class,axi_class,reference_class,expected_mem_nsr,expected_mem_chf,expected_mem_arr,expected_mem_aff,axi_mem_nsr,axi_mem_chf,axi_mem_arr,axi_mem_aff,reference_mem_nsr,reference_mem_chf,reference_mem_arr,reference_mem_aff,axi_accepted,axi_consumed,case_pass");

        while (!$feof(manifest_fd)) begin
            case_name_i = 0;
            mem_path_i = 0;
            scan_count = $fscanf(manifest_fd, "%d %d %d %d %d %d %d %s %s\n",
                case_id_i, expected_class_i, sample_count_i,
                expected_mem_nsr_i, expected_mem_chf_i,
                expected_mem_arr_i, expected_mem_aff_i,
                case_name_i, mem_path_i);
            if (scan_count == 9)
                run_case();
            else if (scan_count != -1) begin
                $display("VIRTUOSO_AXI_E2E_FAIL malformed manifest row fields=%0d", scan_count);
                fail_count = fail_count + 1;
            end
        end

        $fclose(result_fd);
        $fclose(manifest_fd);
        if (total_cases == 0) begin
            $display("VIRTUOSO_AXI_E2E_FAIL no manifest cases");
            $fatal(1);
        end
        if (fail_count == 0) begin
            $display("VIRTUOSO_AXI_E2E_PASS cases=%0d samples_per_case=%0d",
                     passed_cases, DUT_SNAPSHOT_SAMPLES * DUT_SNAPSHOTS_PER_CHUNK);
            $finish;
        end
        $display("VIRTUOSO_AXI_E2E_FAIL_COUNT failures=%0d passed=%0d total=%0d",
                 fail_count, passed_cases, total_cases);
        $fatal(1);
    end
endmodule
