`timescale 1ns/1ps
`default_nettype none
// Fail closed for physical builds: A18_ICG must have an approved 1.8V binding.
// The explicitly requested functional profile uses ONLY a logic test model.
module snn_ecg_mh_icg(
    input wire clk_in,enable,reset_force_on,test_enable,debug_force_on,
    output wire clk_out
);
    wire enabled=enable||reset_force_on||debug_force_on;
`ifdef MEMBRANE_FUNCTIONAL_MODEL
    TLATNTSCAX4 u_functional_only(.CK(clk_in),.E(enabled),.SE(test_enable),.ECK(clk_out));
`else
    A18_ICG u_physical(.CK(clk_in),.E(enabled),.SE(test_enable),.ECK(clk_out));
`endif
endmodule
`default_nettype wire
