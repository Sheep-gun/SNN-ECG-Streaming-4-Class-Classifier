`timescale 1ns/1ps
module tb_core;
 reg clk=0;always #8 clk=~clk;
 reg rst=1,start=0,sample_valid=0;
 reg signed [11:0] adc_data=0;
 wire sample_ready,busy,final_valid;
 wire [1:0] final_pred_class;
 wire signed [47:0] final_mem_nsr,final_mem_chf,final_mem_arr,final_mem_aff;
 rhythm3_duration_core #(.PROFILE_EN(0)) dut(.clk(clk),.rst(rst),.event_test_enable(1'b0),.event_debug_force_on(1'b0),
  .start(start),.sample_valid(sample_valid),.adc_data(adc_data),.sample_ready(sample_ready),.busy(busy),.final_valid(final_valid),
  .final_pred_class(final_pred_class),.final_mem_nsr(final_mem_nsr),.final_mem_chf(final_mem_chf),
  .final_mem_arr(final_mem_arr),.final_mem_aff(final_mem_aff));
 reg [511:0] expected_features[0:29];
 reg [47:0] expected_nsr,expected_af,expected_other;
 integer adc_file,gold_file,rc,raw,i,j,total,n,accepted=0,snapshots=0,waits=0,pred,spacing=3;
 reg [4095:0] adc_path,gold_path;
 always @(posedge clk)begin
  if(!rst && sample_valid && sample_ready)accepted=accepted+1;
  if(!rst && dut.final_snapshot_done)begin
   if(dut.rhythm3_features!==expected_features[snapshots])begin
    for(j=0;j<16;j=j+1)if(dut.rhythm3_features[j*32 +: 32]!==expected_features[snapshots][j*32 +: 32])
      $display("FEATURE_MISMATCH snap=%0d feature=%0d actual=%0d expected=%0d",snapshots,j,dut.rhythm3_features[j*32 +: 32],expected_features[snapshots][j*32 +: 32]);
    $fatal(1,"FEATURE_BOUNDARY_MISMATCH");
   end
   snapshots=snapshots+1;
  end
 end
 initial begin
  if(!$value$plusargs("ADC=%s",adc_path)||!$value$plusargs("GOLD=%s",gold_path))$fatal(1,"PATH_REQUIRED");
  rc=$value$plusargs("SPACING=%d",spacing);
  if(spacing<3)$fatal(1,"SPACING_MIN_THREE");
  gold_file=$fopen(gold_path,"r");if(!gold_file)$fatal(1,"GOLD_OPEN");
  rc=$fscanf(gold_file,"%d %d %h %h %h\n",n,pred,expected_nsr,expected_af,expected_other);
  if(rc!=5 || n!=dut.SNAPSHOTS_PER_CHUNK)$fatal(1,"GOLD_HEADER");
  for(i=0;i<n;i=i+1)begin rc=$fscanf(gold_file,"%h\n",expected_features[i]);if(rc!=1)$fatal(1,"GOLD_FEATURES");end
  $fclose(gold_file);adc_file=$fopen(adc_path,"r");if(!adc_file)$fatal(1,"ADC_OPEN");
  for(i=0;i<5000;i=i+1)begin rc=$fscanf(adc_file,"%h\n",raw);if(rc!=1)$fatal(1,"ADC_CONTEXT");end
  repeat(5)@(negedge clk);rst=0;start=1;@(negedge clk);start=0;
  total=n*60000;
  for(i=0;i<total;i=i+1)begin
   rc=$fscanf(adc_file,"%h\n",raw);if(rc!=1 || raw>4095)$fatal(1,"ADC_DATA");
   @(negedge clk);while(!sample_ready)@(negedge clk);
   sample_valid=1;adc_data=raw-2048;
   @(negedge clk);sample_valid=0;adc_data=0;
   repeat(spacing-2)@(negedge clk);
  end
  rc=$fscanf(adc_file,"%h\n",raw);if(rc==1)$fatal(1,"EXTRA_ADC_SAMPLE");$fclose(adc_file);
  while(!final_valid && waits<2000)begin @(posedge clk);#1;waits=waits+1;end
  if(!final_valid || final_pred_class!==pred[1:0] || final_mem_nsr!==expected_nsr || final_mem_aff!==expected_af || final_mem_arr!==expected_other || final_mem_chf!==48'd0)
   $fatal(1,"FINAL_RESULT_MISMATCH");
  if(accepted!=total || snapshots!=n)$fatal(1,"ACCEPTED_OR_SNAPSHOT_COUNT");
  $display("RHYTHM3_CORE_PASS accepted=%0d snapshots=%0d spacing=%0d",accepted,snapshots,spacing);$finish;
 end
 initial begin #100000000000;$fatal(1,"GLOBAL_TIMEOUT");end
endmodule
