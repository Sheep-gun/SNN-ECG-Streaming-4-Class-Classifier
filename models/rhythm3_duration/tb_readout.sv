`timescale 1ns/1ps
module tb_readout;
 reg clk=0;always #8 clk=~clk;
 reg rst=1,clear=0,capture=0,last_snapshot=0,test_enable=0,debug_force_on=0;
 reg [511:0] features=0;
 wire pending,snapshot_done,final_valid,clock_active,clock_enable;
 wire [1:0] snapshot_pred,final_pred;
 wire signed [47:0] final_nsr,final_af,final_other;
 rhythm3_snapshot_final_readout dut(.*);
 integer f,rc,i,first_flag,last_flag,pred,expected_final_pred,waits,rows=0,decisions=0,edges=0,old_edges;
 reg [511:0] vector_features;
 reg [47:0] s0,s1,s2,f0,f1,f2;
 reg [4095:0] path;
 always @(posedge clock_active)begin
   if(clk!==1'b1)$fatal(1,"GATED_CLOCK_PHASE");
   edges=edges+1;
 end
 initial begin
  if(!$value$plusargs("VECTORS=%s",path))$fatal(1,"VECTORS_REQUIRED");
  f=$fopen(path,"r");if(!f)$fatal(1,"VECTOR_OPEN");
  repeat(4)@(negedge clk);rst=0;
  while(!$feof(f))begin
   rc=$fscanf(f,"%h %d %d %d %d %h %h %h %h %h %h\n",vector_features,first_flag,last_flag,pred,expected_final_pred,s0,s1,s2,f0,f1,f2);
   if(rc!=11)$fatal(1,"VECTOR_FORMAT %d",rc);
   if(first_flag)begin @(negedge clk);clear=1;@(negedge clk);clear=0;end
   @(negedge clk);features=vector_features;last_snapshot=last_flag;capture=1;
   @(negedge clk);capture=0;features=~vector_features; // Operand hold must isolate this switching.
   waits=0;
   while(!snapshot_done && waits<512)begin @(posedge clk);#1;waits=waits+1;end
   if(!snapshot_done)$fatal(1,"READOUT_TIMEOUT");
   if(snapshot_pred!==pred[1:0] || $signed(dut.smem[0])!==$signed(s0) || $signed(dut.smem[1])!==$signed(s1) || $signed(dut.smem[2])!==$signed(s2))
     $fatal(1,"SNAPSHOT_MISMATCH row=%d got=%d expected=%d",rows,snapshot_pred,pred);
   if(final_nsr!==f0 || final_af!==f1 || final_other!==f2)$fatal(1,"FINAL_MEM_MISMATCH row=%d",rows);
   if(final_valid!==last_flag[0])$fatal(1,"FINAL_VALID_MISMATCH");
   if(last_flag && final_pred!==expected_final_pred[1:0])$fatal(1,"FINAL_PRED_MISMATCH");
   rows=rows+1;if(last_flag)decisions=decisions+1;
   repeat(3)@(negedge clk);old_edges=edges;
   repeat(3)begin @(negedge clk);features=~features;end
   if(edges!=old_edges || pending || snapshot_done || final_valid)$fatal(1,"IDLE_GATE_OR_STALE_VALID");
  end
  $fclose(f);
  @(negedge clk);test_enable=1;old_edges=edges;repeat(3)@(negedge clk);
  if(edges-old_edges!=3)$fatal(1,"TEST_ENABLE");test_enable=0;
  @(negedge clk);debug_force_on=1;old_edges=edges;repeat(3)@(negedge clk);
  if(edges-old_edges!=3)$fatal(1,"DEBUG_FORCE_ON");debug_force_on=0;
  // Reset an in-flight token. It must cancel pending state and re-open safely.
  @(negedge clk);capture=1;@(negedge clk);capture=0;
  @(negedge clk);rst=1;repeat(2)@(negedge clk);rst=0;repeat(3)@(negedge clk);
  if(pending || final_valid || snapshot_done)$fatal(1,"RESET_DRAIN");
  $display("RHYTHM3_READOUT_PASS snapshots=%0d decisions=%0d",rows,decisions);$finish;
 end
 initial begin #10000000000;$fatal(1,"GLOBAL_TIMEOUT");end
endmodule
