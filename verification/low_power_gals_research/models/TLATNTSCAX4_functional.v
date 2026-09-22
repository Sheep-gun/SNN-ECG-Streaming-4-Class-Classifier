`timescale 1ns / 1ps

// Verification-only functional model for the characterized GSCLIB045 ICG.
// It is never present in a Genus source list. Physical builds resolve the
// TLATNTSCAX4 Liberty/LEF/Verilog cell from the installed GPDK045 kit.
module TLATNTSCAX4 (
    input  wire CK,
    input  wire E,
    input  wire SE,
    output wire ECK
);
    reg enable_latched;

    always @(CK or E or SE) begin
        if (!CK)
            enable_latched <= E | SE;
    end

    and u_clock_gate_model(ECK, CK, enable_latched);
endmodule
