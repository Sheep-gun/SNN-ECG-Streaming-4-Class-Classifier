`timescale 1ns / 1ps

// Optional diagnostic for forced digital two-state initialization sensitivity.
//
// Four-state GLS left persistent sequential Xs and licensed X-pessimism
// correction could not be executed.  This experiment therefore samples a
// Boolean initial state without classifying every observed X as false
// pessimism.  In this digital abstraction, after analog settling each sampled
// Q is assigned an arbitrary stable 0/1; supply ramp, metastability, and
// physical bias or correlation are not modeled.
//
// When +GATE_RANDOM_POWERUP is present, hold each sequential Q at a fixed-seed
// pseudo-random 0/1 value during the early reset window, then release it at the
// configurable GATE_FORCE_RELEASE_NS time (70 ns by default) while reset is
// still active.  The published run-2 sensitivity uses 10 ns, immediately after
// the first reset capture and before seven further reset-active rising edges.
//
// This is a sensitivity experiment, not an unqualified GLS pass and not a
// substitute for reset verification or the unavailable X-pessimism app.
package gpdk45_gate_random_powerup_pkg;
    integer initialized_instance_count = 0;
    integer release_unknown_count = 0;
    integer initialized_zero_count = 0;
    integer initialized_one_count = 0;
    integer release_time_ns = 70;
    parameter integer REPORT_LIMIT = 100;
endpackage

module gpdk45_gate_random_powerup(output wire q);
    import gpdk45_gate_random_powerup_pkg::*;
    reg initial_value;
    integer configured_release_ns;
    initial begin
        if ($test$plusargs("GATE_RANDOM_POWERUP")) begin
            configured_release_ns = 70;
            void'($value$plusargs("GATE_FORCE_RELEASE_NS=%d", configured_release_ns));
            release_time_ns = configured_release_ns;
            initialized_instance_count = initialized_instance_count + 1;
            initial_value = $urandom_range(1, 0);
            if (initial_value)
                initialized_one_count = initialized_one_count + 1;
            else
                initialized_zero_count = initialized_zero_count + 1;
            force q = initial_value;
            #(configured_release_ns);
            release q;
            #0.001;
            if ((q !== 1'b0) && (q !== 1'b1)) begin
                release_unknown_count = release_unknown_count + 1;
                if (release_unknown_count <= REPORT_LIMIT)
                    $display("GPDK45_GATE_POWERUP_RELEASE_X instance=%m time=%0t q=%b",
                             $time, q);
            end
        end
    end
endmodule

module gpdk45_gate_random_powerup_dual(output wire q, output wire qn);
    import gpdk45_gate_random_powerup_pkg::*;
    reg initial_value;
    integer configured_release_ns;
    initial begin
        if ($test$plusargs("GATE_RANDOM_POWERUP")) begin
            configured_release_ns = 70;
            void'($value$plusargs("GATE_FORCE_RELEASE_NS=%d", configured_release_ns));
            release_time_ns = configured_release_ns;
            initialized_instance_count = initialized_instance_count + 1;
            initial_value = $urandom_range(1, 0);
            if (initial_value)
                initialized_one_count = initialized_one_count + 1;
            else
                initialized_zero_count = initialized_zero_count + 1;
            force q = initial_value;
            force qn = ~initial_value;
            #(configured_release_ns);
            release q;
            release qn;
            #0.001;
            if (((q !== 1'b0) && (q !== 1'b1)) ||
                ((qn !== 1'b0) && (qn !== 1'b1)) || (qn === q)) begin
                release_unknown_count = release_unknown_count + 1;
                if (release_unknown_count <= REPORT_LIMIT)
                    $display("GPDK45_GATE_POWERUP_RELEASE_X_DUAL instance=%m time=%0t q=%b qn=%b",
                             $time, q, qn);
            end
        end
    end
endmodule

module gpdk45_gate_random_powerup_summary;
    import gpdk45_gate_random_powerup_pkg::*;
    final begin
        $display("GPDK45_GATE_POWERUP_SUMMARY initialized_instances=%0d zeros=%0d ones=%0d release_ns=%0d release_unknown=%0d",
                 initialized_instance_count, initialized_zero_count,
                 initialized_one_count, release_time_ns,
                 release_unknown_count);
    end
endmodule

bind DFFHQX1  gpdk45_gate_random_powerup powerup_q (.q(Q));
bind DFFHQX4  gpdk45_gate_random_powerup powerup_q (.q(Q));
bind DFFQX2   gpdk45_gate_random_powerup powerup_q (.q(Q));
bind DFFQXL   gpdk45_gate_random_powerup powerup_q (.q(Q));
bind DFFX1    gpdk45_gate_random_powerup_dual powerup_q (.q(Q), .qn(QN));
bind DFFX2    gpdk45_gate_random_powerup_dual powerup_q (.q(Q), .qn(QN));
bind MDFFHQX4 gpdk45_gate_random_powerup powerup_q (.q(Q));
bind tb_snn_ecg_asic_gate_16sample_diag gpdk45_gate_random_powerup_summary powerup_summary ();
bind tb_snn_ecg_asic_core_manifest gpdk45_gate_random_powerup_summary powerup_summary ();
bind tb_snn_ecg_asic_power_prefix gpdk45_gate_random_powerup_summary powerup_summary ();
