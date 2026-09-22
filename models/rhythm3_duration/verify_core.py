"""Actual ADC -> reused feature RTL -> new hierarchy, bounded local simulation."""
import argparse,json,os,re,shutil,subprocess
from pathlib import Path
import numpy as np
from train_hierarchy import read,sha,write,rows,data,snapshot_predict,final_input,infer

def main():
    p=argparse.ArgumentParser()
    for k in ['repo','dataset','work','model','rtl','out']:p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--splits',nargs='+',default=['train','validation']);p.add_argument('--spacing',type=int,default=3)
    p.add_argument('--all-cases',action='store_true');p.add_argument('--axi',action='store_true');a=p.parse_args()
    if a.out.exists():raise SystemExit('OUTPUT_EXISTS')
    m=read(a.model);assert read(a.model.parent/'freeze_receipt.json')['sha256']==sha(a.model)
    rr=[]
    for part in a.splits:
        pool=rows(a,m['seconds'],part)
        rr+=pool if a.all_cases else [next(r for r in pool if r['label_id']==k) for k in range(3)]
    x=data(a,rr);sp=snapshot_predict(x,m['snapshot'])[0];pred,mem,_=infer(final_input(x,sp,m['final_spec']),m['final_readout'])
    a.out.mkdir(parents=True);bin=Path('C:/Xilinx/Vivado/2020.2/bin')
    sources=[a.rtl/line for line in (a.rtl/'sources.f').read_text().splitlines()]
    tb='tb_axi' if a.axi else 'tb_core'
    sources += [a.repo/'verification/low_power_gals_research/models/TLATNTSCAX4_functional.v',Path(__file__).with_name(tb+'.sv')]
    def run(name,exe,args,timeout=1800):
        command='"'+str(bin/exe)+'" '+' '.join('"'+str(arg)+'"' for arg in args)
        r=subprocess.run(command,shell=True,cwd=a.out,capture_output=True,text=True,timeout=timeout)
        (a.out/(name+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
        if r.returncode:raise RuntimeError(name+'_FAILED '+r.stdout[-700:]+r.stderr[-300:])
        return r
    run('compile','xvlog.bat',['-sv','-d','MEMBRANE_FUNCTIONAL_MODEL',*[s.resolve() for s in sources]])
    run('elaborate','xelab.bat',['work.'+tb,'-s','core_test','-mt','off'])
    results=[]
    for i,r in enumerate(rr):
        code_source=a.work/'captures'/r['case_id']/'adc_codes.hex';codes=a.out/f'adc_{i}.hex'
        receipt=read(a.work/'receipts'/(r['case_id']+'.json'));assert sha(code_source)==receipt['codes_sha256']
        try:os.link(code_source,codes)
        except OSError:shutil.copyfile(code_source,codes)
        gold=a.out/f'gold_{i}.txt'
        with gold.open('x',encoding='ascii',newline='\n') as f:
            f.write(f'{m["snapshots"]} {int(pred[i])} '+' '.join(f'{int(v)&((1<<48)-1):012x}' for v in mem[i])+'\n')
            for snap in x[i]:f.write(''.join(f'{int(v):08x}' for v in snap[::-1])+'\n')
        sim=run(f'case_{i}','xsim.bat',['core_test','-testplusarg',f'ADC={codes.name}','-testplusarg',f'GOLD={gold.name}',
            '-testplusarg',f'SPACING={a.spacing}','-runall'])
        marker='RHYTHM3_AXI_PASS' if a.axi else 'RHYTHM3_CORE_PASS'
        match=re.search(marker+r' accepted=(\d+) snapshots=(\d+) spacing=(\d+)',sim.stdout)
        if not match:raise RuntimeError('NO_CORE_PASS '+sim.stdout[-1500:])
        assert int(match[1])==m['seconds']*1000 and int(match[2])==m['snapshots']
        results.append({'case_id':r['case_id'],'split':r['split'],'accepted':int(match[1]),'snapshots':int(match[2]),
            'adc_sha256':sha(code_source),'gold_sha256':sha(gold),'log_sha256':sha(a.out/f'case_{i}.log')})
        print(json.dumps({'rtl_core_cases_passed':len(results),'planned':len(rr),'case_id':r['case_id']}),flush=True)
    write(a.out/'summary.json',{'status':'PASS_ADC_TO_AXI_BIT_EXACT' if a.axi else 'PASS_ADC_TO_CORE_BIT_EXACT','cases':results,'selected_all_cases':a.all_cases,
        'model_sha256':sha(a.model),'testbench_sha256':sha(Path(__file__).with_name(tb+'.sv')),
        'spacing_source_cycles':a.spacing,'source_period_ns':16,'activity_dump':False,
        'scope':('AXI-inclusive stimulus, counters, error flags and full48-bit CSR readback. ' if a.axi else 'Streaming core only. ')+
        'Not exhaustive protocol/formal verification or SDF. Physical 1kSPS PPA is not established by compressed-cadence RTL simulation.'})
if __name__=='__main__':main()
