"""Generate only the frozen 3-class serial Snapshot/Final integer readout.

The ICG resolves through the preserved 1.8 V wrapper. This is synchronous
event-clock-gated logic, not an asynchronous implementation or PPA result.
"""
import argparse,json
from pathlib import Path
from train_hierarchy import read,sha,write

def literal(v,bits=48):return ('-' if int(v)<0 else '')+f"{bits}'sd{abs(int(v))}"
def value_function(name,spec):
    lines=[f'function [31:0] {name}; input [7:0] ix; input [511:0] bank; begin case(ix)']
    for i,s in enumerate(spec):
        x=f'bank[{s["feature"]}*32 +: 32]'
        if s['kind']=='greater':x=f'({x} > 32\'d{s["threshold"]})'
        lines.append(f"8'd{i}: {name} = {x};")
    lines+= [f'default: {name}=0; endcase end endfunction']
    return '\n'.join(lines)
def weight_function(name,weights):
    lines=[f'function signed [19:0] {name}; input [7:0] ix; input [1:0] lane; begin case({{ix,lane}})']
    for i,row in enumerate(weights):
        for k,w in enumerate(row):lines.append(f"10'd{i*4+k}: {name}={literal(w,20)};")
    lines+=[f'default: {name}=0; endcase end endfunction'];return '\n'.join(lines)
def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    m=read(a.model);receipt=read(a.model.parent/'freeze_receipt.json');assert sha(a.model)==receipt['sha256']
    if a.out.exists():raise SystemExit('OUTPUT_EXISTS')
    a.out.mkdir(parents=True)
    ss=m['snapshot']['spec'];fs=m['final_spec'];sw=m['snapshot']['readout']['weights'];fw=m['final_readout']['weights']
    sb=m['snapshot']['readout']['bias'];fb=m['final_readout']['bias']
    # Conservative per-Snapshot event bound exceeds the number of canonical
    # frontend ticks, including drain. RAM/RDM carry their maximum payload.
    maxima=[180100]*16;maxima[5]*=63;maxima[8]*=15
    def limits(spec):return [maxima[v['feature']] if v['kind']=='count' else 1 for v in spec]
    sbound=[sum(abs(w[k])*x for w,x in zip(sw,limits(ss)))+abs(sb[k]) for k in range(3)]
    fbound=[m['snapshots']*sum(abs(w[k])*x for w,x in zip(fw,limits(fs)+[1,1,1]))+abs(fb[k]) for k in range(3)]
    assert max(sbound+fbound)<2**47,'THEORETICAL_48BIT_BOUND_FAILED'
    # Proven lossless narrowing, not quantization/weight retuning. The external
    # and golden numeric contract stays signed48; storage is sign-extended.
    snap_bits=min(48,8*((max(sbound).bit_length()+1+7)//8))
    final_bits=min(48,8*((max(fbound).bit_length()+1+7)//8))
    text='''`timescale 1ns/1ps
`default_nettype none
module rhythm3_snapshot_final_readout(
 input wire clk,rst,clear,capture,last_snapshot,test_enable,debug_force_on,
 input wire [511:0] features,
 output wire pending,
 output reg snapshot_done,final_valid,
 output reg [1:0] snapshot_pred,final_pred,
 output wire signed [47:0] final_nsr,final_af,final_other,
 output wire clock_active,clock_enable
);
 reg [511:0] held;
 reg [2:0] state;
 reg [7:0] index;
 reg last_held;
 reg signed [47:0] smem[0:2];
 reg signed [47:0] fmem[0:2];
 wire gated_clk;
 assign pending=(state!=0);
 assign clock_enable=capture||clear||pending;
 snn_ecg_mh_icg u_readout_icg(.clk_in(clk),.enable(clock_enable),.reset_force_on(rst),
 .test_enable(test_enable),.debug_force_on(debug_force_on),.clk_out(gated_clk));
 assign clock_active=gated_clk;
 assign final_nsr=fmem[0];assign final_af=fmem[1];assign final_other=fmem[2];
 function [1:0] winner;
 input signed [47:0] a,b,c;
 begin if(a>=b && a>=c)winner=0;else if(b>=c)winner=1;else winner=2;end
 endfunction
'''
    text=text.replace('reg signed [47:0] smem',f'reg signed [{snap_bits-1}:0] smem').replace('reg signed [47:0] fmem',f'reg signed [{final_bits-1}:0] fmem')
    text+='\n'+value_function('svalue',ss)+'\n'+value_function('fvalue',fs)+'\n'
    text+=weight_function('sweight',sw)+'\n'+weight_function('fweight',fw)+'\n'
    text+=f''' wire [31:0] fv = (index < {len(fs)}) ? fvalue(index,held) : ((index-{len(fs)})==snapshot_pred);
 wire signed [47:0] sv_signed=$signed({{1'b0,svalue(index,held)}});
 wire signed [47:0] fv_signed=$signed({{1'b0,fv}});
 integer k;
 always @(posedge gated_clk) begin
  if(rst||clear) begin
   state<=0;index<=0;held<=0;last_held<=0;snapshot_done<=0;final_valid<=0;snapshot_pred<=0;final_pred<=0;
'''
    for k in range(3):text+=f'   smem[{k}]<={literal(sb[k])};fmem[{k}]<={literal(fb[k])};\n'
    text+='''  end else begin
   snapshot_done<=0;final_valid<=0;
   case(state)
    0: if(capture) begin
      held<=features;last_held<=last_snapshot;index<=0;state<=1;
'''
    for k in range(3):text+=f'      smem[{k}]<={literal(sb[k])};\n'
    text+=f'''    end
    1: begin
      for(k=0;k<3;k=k+1)smem[k]<=smem[k]+sv_signed*sweight(index,k);
      if(index=={len(ss)-1})begin state<=2;index<=0;end else index<=index+1;
    end
    2: begin snapshot_pred<=winner(smem[0],smem[1],smem[2]);state<=3;index<=0;end
    3: begin
      for(k=0;k<3;k=k+1)fmem[k]<=fmem[k]+fv_signed*fweight(index,k);
      if(index=={len(fw)-1})begin state<=4;index<=0;end else index<=index+1;
    end
    4: begin
      snapshot_done<=1;
      if(last_held)begin final_valid<=1;final_pred<=winner(fmem[0],fmem[1],fmem[2]);end
      state<=5;
    end
    5: state<=0;
    default: state<=0;
   endcase
  end
 end
endmodule
`default_nettype wire
'''
    target=a.out/'rhythm3_snapshot_final_readout.sv';target.write_text(text,encoding='ascii',newline='\n')
    write(a.out/'readout_provenance.json',{'status':'GENERATED_NOT_VERIFIED','model_sha256':sha(a.model),'source_sha256':sha(target),
       'generator_sha256':sha(Path(__file__)),'snapshot_abs_bound':sbound,'final_abs_bound':fbound,
       'lossless_internal_snapshot_bits':snap_bits,'lossless_internal_final_bits':final_bits,'external_signed_bits':48,
       'max_compute_cycles_per_snapshot':len(ss)+len(fw)+5,'clock':'same root through characterized ICG binding',
       'physical_claim':'NONE; use project1.8 V views and measured workload only'})
if __name__=='__main__':main()
