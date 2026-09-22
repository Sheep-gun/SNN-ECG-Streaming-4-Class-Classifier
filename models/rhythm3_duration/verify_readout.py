"""Integer-vs-RTL verification using all registered features at frozen duration."""
import argparse,json,re,subprocess
from pathlib import Path
import numpy as np
from train_hierarchy import read,sha,write,rows,data,transform,infer,snapshot_predict

def main():
    p=argparse.ArgumentParser()
    for k in ['repo','dataset','work','model','rtl','out']:p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--splits',nargs='+',default=['train','validation']);a=p.parse_args()
    if a.out.exists():raise SystemExit('OUTPUT_EXISTS')
    m=read(a.model);assert sha(a.model)==read(a.model.parent/'freeze_receipt.json')['sha256']
    a.out.mkdir(parents=True);rr=[r for part in a.splits for r in rows(a,m['seconds'],part)];x=data(a,rr)
    sp,ss,_=snapshot_predict(x,m['snapshot']);evidence=transform(x,m['final_spec'])
    fw=np.asarray(m['final_readout']['weights'],dtype=np.int64);fb=np.asarray(m['final_readout']['bias'],dtype=np.int64)
    vectors=a.out/'vectors.txt';expected=[]
    with vectors.open('x',encoding='ascii',newline='\n') as f:
        for i,r in enumerate(rr):
            fm=fb.copy()
            for j in range(m['snapshots']):
                inp=np.r_[evidence[i,j],np.eye(3,dtype=np.int64)[sp[i,j]]];fm+=inp@fw
                values=[''.join(f'{int(v):08x}' for v in x[i,j,::-1]),str(int(j==0)),str(int(j==m['snapshots']-1)),str(int(sp[i,j])),str(int(fm.argmax()))]
                values += [f'{int(v)&((1<<48)-1):012x}' for v in np.r_[ss[i,j],fm]]
                f.write(' '.join(values)+'\n')
            expected.append({'case_id':r['case_id'],'final_membrane':fm.tolist(),'prediction':int(fm.argmax())})
    # Direct full-AXI compile catches closure errors as well as readout compile.
    simulator=Path('C:/Xilinx/Vivado/2020.2/bin');sources=[a.rtl/line for line in (a.rtl/'sources.f').read_text().splitlines()]
    sources += [a.repo/'verification/low_power_gals_research/models/TLATNTSCAX4_functional.v',Path(__file__).with_name('tb_readout.sv')]
    commands=[('compile','xvlog.bat',['-sv','-d','MEMBRANE_FUNCTIONAL_MODEL',*[str(s.resolve()) for s in sources]]),
      ('axi_elaborate','xelab.bat',['work.rhythm3_axi_event_cf_1v8','-s','axi_closure','-mt','off']),
      ('elaborate','xelab.bat',['work.tb_readout','-s','readout_test','-mt','off']),
      ('run','xsim.bat',['readout_test','-testplusarg','VECTORS=vectors.txt','-runall'])]
    results=[]
    for name,exe,args in commands:
        command='"'+str(simulator/exe)+'" '+' '.join('"'+str(arg)+'"' for arg in args)
        run=subprocess.run(command,shell=True,cwd=a.out,capture_output=True,text=True,timeout=900)
        (a.out/(name+'.log')).write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
        results.append({'stage':name,'exit':run.returncode,'log_sha256':sha(a.out/(name+'.log'))})
        if run.returncode:raise RuntimeError('RTL_'+name+'_FAILED: '+run.stdout[-1200:]+run.stderr[-500:])
    match=re.search(r'RHYTHM3_READOUT_PASS snapshots=(\d+) decisions=(\d+)',run.stdout)
    assert match and int(match[1])==len(rr)*m['snapshots'] and int(match[2])==len(rr),'PASS_COUNTS'
    write(a.out/'summary.json',{'status':'PASS_READOUT_BIT_EXACT','cases':len(rr),'snapshots':len(rr)*m['snapshots'],
       'membrane_comparisons':len(rr)*m['snapshots']*6,'splits':a.splits,'model_sha256':sha(a.model),
       'rtl_sha256':sha(a.rtl/'rhythm3_snapshot_final_readout.sv'),'vectors_sha256':sha(vectors),
       'stages':results,'testbench_sha256':sha(Path(__file__).with_name('tb_readout.sv')),
       'checks':['snapshot score/pred','Final membrane after every Snapshot','Final class','idle gate','operand isolation','test/debug enable','active reset'],
       'scope':'Readout transaction boundary only. Does not prove full ADC-to-RTL frontend or AXI protocol equivalence, STA or PPA.'})
    print((a.out/'summary.json').read_text())
if __name__=='__main__':main()
