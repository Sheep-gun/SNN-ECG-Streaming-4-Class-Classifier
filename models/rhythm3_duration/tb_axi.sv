`timescale 1ns/1ps
module tb_axi;
 reg clk=0;always #8 clk=~clk;
 reg resetn=0,awvalid=0,wvalid=0,arvalid=0,tvalid=0,tlast=0;
 reg [11:0] awaddr=0,araddr=0;reg [31:0] wdata=0;reg [15:0] tdata=0;
 wire awready,wready,bvalid,arready,rvalid,tready,irq;
 wire [1:0] bresp,rresp;wire [31:0] rdata;
 rhythm3_axi_event_cf_1v8 dut(.s_axi_aclk(clk),.s_axi_aresetn(resetn),.test_enable(1'b0),.debug_force_core_clock_on(1'b0),
 .s_axi_awaddr(awaddr),.s_axi_awprot(3'd0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
 .s_axi_wdata(wdata),.s_axi_wstrb(4'hf),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(1'b1),
 .s_axi_araddr(araddr),.s_axi_arprot(3'd0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
 .s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(1'b1),
 .s_axis_tdata(tdata),.s_axis_tvalid(tvalid),.s_axis_tready(tready),.s_axis_tlast(tlast),.irq(irq));
 task write_control;input [31:0] value;reg a_done,w_done;integer wait_count;
 begin
  @(negedge clk);awaddr=0;wdata=value;awvalid=1;wvalid=1;a_done=0;w_done=0;wait_count=0;
  while(!(a_done&&w_done)&&wait_count<100)begin
   @(posedge clk);if(awvalid&&awready)a_done=1;if(wvalid&&wready)w_done=1;
   @(negedge clk);awvalid=!a_done;wvalid=!w_done;wait_count=wait_count+1;
  end
  if(!(a_done&&w_done))$fatal(1,"AXI_WRITE_TIMEOUT");
  while(!bvalid && wait_count<200)begin @(posedge clk);wait_count=wait_count+1;end
  if(!bvalid||bresp!=0)$fatal(1,"AXI_WRITE_RESPONSE");
  @(negedge clk);
 end endtask
 task read_check;input [11:0] address;input [31:0] expected;integer wait_count;
 begin
  @(negedge clk);araddr=address;arvalid=1;wait_count=0;
  @(posedge clk);while(!arready&&wait_count<100)begin @(posedge clk);wait_count=wait_count+1;end
  if(!arready)$fatal(1,"AXI_READ_ADDRESS_TIMEOUT");
  @(negedge clk);arvalid=0;
  while(!rvalid&&wait_count<200)begin @(posedge clk);wait_count=wait_count+1;end
  if(!rvalid||rresp!=0||rdata!==expected)$fatal(1,"CSR_MISMATCH address=%h actual=%h expected=%h response=%d",address,rdata,expected,rresp);
  @(negedge clk);
 end endtask
 integer adc_file,gold_file,rc,raw,i,j,n,pred,total,accepted=0,snapshots=0,waits=0,spacing=3;
 reg [4095:0] adc_path,gold_path;reg [511:0] expected_features[0:29];reg [47:0] nsr,af,other;
 always @(posedge clk)begin
  if(resetn && tvalid && tready)accepted=accepted+1;
  if(resetn && dut.u_core.final_snapshot_done)begin
   if(dut.u_core.rhythm3_features!==expected_features[snapshots])begin
    for(j=0;j<16;j=j+1)if(dut.u_core.rhythm3_features[j*32 +: 32]!==expected_features[snapshots][j*32 +: 32])
     $display("AXI_FEATURE_MISMATCH snapshot=%d feature=%d actual=%d expected=%d",snapshots,j,dut.u_core.rhythm3_features[j*32 +: 32],expected_features[snapshots][j*32 +: 32]);
    $fatal(1,"AXI_FEATURE_BOUNDARY");
   end
   snapshots=snapshots+1;
  end
 end
 initial begin
  if(!$value$plusargs("ADC=%s",adc_path)||!$value$plusargs("GOLD=%s",gold_path))$fatal(1,"PATH_REQUIRED");
  rc=$value$plusargs("SPACING=%d",spacing);if(spacing<3)$fatal(1,"SPACING");
  gold_file=$fopen(gold_path,"r");if(!gold_file)$fatal(1,"GOLD_OPEN");
  rc=$fscanf(gold_file,"%d %d %h %h %h\n",n,pred,nsr,af,other);
  if(rc!=5||n!=dut.SNAPSHOTS_PER_CHUNK)$fatal(1,"GOLD_HEADER");
  for(i=0;i<n;i=i+1)begin rc=$fscanf(gold_file,"%h\n",expected_features[i]);if(rc!=1)$fatal(1,"GOLD_FEATURES");end
  $fclose(gold_file);adc_file=$fopen(adc_path,"r");if(!adc_file)$fatal(1,"ADC_OPEN");
  for(i=0;i<5000;i=i+1)begin rc=$fscanf(adc_file,"%h\n",raw);if(rc!=1)$fatal(1,"ADC_CONTEXT");end
  repeat(6)@(negedge clk);resetn=1;repeat(8)@(negedge clk);total=n*60000;
  read_check(12'h010,total);write_control(1);
  for(i=0;i<total;i=i+1)begin
   rc=$fscanf(adc_file,"%h\n",raw);if(rc!=1||raw>4095)$fatal(1,"ADC_DATA");
   @(negedge clk);tdata=raw-2048;tvalid=1;tlast=(i==total-1);
   @(posedge clk);waits=0;while(!tready&&waits<2000)begin @(posedge clk);waits=waits+1;end
   if(!tready)$fatal(1,"AXIS_TIMEOUT");
   @(negedge clk);tvalid=0;tdata=0;tlast=0;repeat(spacing-2)@(negedge clk);
  end
  rc=$fscanf(adc_file,"%h\n",raw);if(rc==1)$fatal(1,"EXTRA_ADC_SAMPLE");$fclose(adc_file);
  waits=0;while(!irq&&waits<2000)begin @(posedge clk);#1;waits=waits+1;end
  if(!irq||accepted!=total||snapshots!=n)$fatal(1,"AXI_COMPLETION_COUNTS");
  read_check(12'h008,0);read_check(12'h014,total);read_check(12'h018,total);read_check(12'h030,32'h101|(pred<<1));
  read_check(12'h020,nsr[31:0]);read_check(12'h02c,af[31:0]);read_check(12'h028,other[31:0]);read_check(12'h024,0);
  read_check(12'h034,{{16{nsr[47]}},nsr[47:32]});read_check(12'h038,{{16{af[47]}},af[47:32]});read_check(12'h03c,{{16{other[47]}},other[47:32]});
  $display("RHYTHM3_AXI_PASS accepted=%0d snapshots=%0d spacing=%0d",accepted,snapshots,spacing);$finish;
 end
 initial begin #100000000000;$fatal(1,"GLOBAL_TIMEOUT");end
endmodule
