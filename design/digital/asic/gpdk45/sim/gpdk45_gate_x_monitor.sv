package gpdk45_gate_x_monitor_pkg;
    integer initial_unknown_count = 0;
    integer runtime_x_transition_count = 0;
    parameter integer REPORT_LIMIT = 100;
endpackage

module gpdk45_gate_x_monitor(input wire q);
    import gpdk45_gate_x_monitor_pkg::*;

    // The manifest harness holds reset for eight 10 ns clocks.  Sample after
    // reset/start have settled so persistent uninitialized sequential state is
    // distinguishable from normal time-zero X state.
    initial begin
        #200;
        if ((q !== 1'b0) && (q !== 1'b1)) begin
            initial_unknown_count = initial_unknown_count + 1;
            if (initial_unknown_count <= REPORT_LIMIT)
                $display("GPDK45_GATE_X_INITIAL instance=%m time=%0t q=%b", $time, q);
        end
    end

    always @(q) begin
        if (($time > 200) && (q !== 1'b0) && (q !== 1'b1)) begin
            runtime_x_transition_count = runtime_x_transition_count + 1;
            if (runtime_x_transition_count <= REPORT_LIMIT)
                $display("GPDK45_GATE_X_RUNTIME instance=%m time=%0t", $time);
        end
    end
endmodule

module gpdk45_gate_x_monitor_summary;
    import gpdk45_gate_x_monitor_pkg::*;
    final begin
        $display("GPDK45_GATE_X_SUMMARY initial_unknown=%0d runtime_x_transitions=%0d",
                 initial_unknown_count, runtime_x_transition_count);
    end
endmodule

bind DFFHQX1  gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFHQX4  gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFQX2   gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFQXL   gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFX1    gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFX1    gpdk45_gate_x_monitor xmon_qn (.q(QN));
bind DFFX2    gpdk45_gate_x_monitor xmon_q (.q(Q));
bind DFFX2    gpdk45_gate_x_monitor xmon_qn (.q(QN));
bind MDFFHQX4 gpdk45_gate_x_monitor xmon_q (.q(Q));
bind tb_snn_ecg_asic_gate_16sample_diag gpdk45_gate_x_monitor_summary xmon_summary ();
bind tb_snn_ecg_asic_core_manifest gpdk45_gate_x_monitor_summary xmon_summary ();
bind tb_snn_ecg_asic_power_prefix gpdk45_gate_x_monitor_summary xmon_summary ();
