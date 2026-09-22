"""Record-weighted Snapshot classifier -> accumulated evidence Final classifier.

All train/validation candidates precede a write-once model freeze. Test is a
separate command and evaluates only the selected duration. Historical corpus
exposure is not erased by a new split. No old discarded weights are imported.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse, collections, csv, hashlib, json, time
from pathlib import Path
import numpy as np

CLASSES=['NSR','AF','OTHER']
FEATURES=['beat_count','pnn_match_count','pnn_mismatch_count','dscr_flip_count','dscr_slope_count',
 'ram_code_sum','ram_code_count','rdm_valid_count','rdm_code_sum','ectopic_pair_count','qrs_maf_count',
 'qrs_width_abn_count','qrs_complex_abn_count','qrs_energy_abn_count','rbbb_delay_like_count','pre_qrs_bump_count']
FAMILIES=['counts','predicates','mixed']
ALPHAS=[.1,1.,10.]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def rows(a,L,part):
    return [r for r in map(json.loads,(a.dataset/'gold_labels.jsonl').read_text().splitlines()) if r['seconds']==L and r['split']==part]
def data(a,rr):
    out=[]
    for r in rr:
        p=a.work/'features'/(r['case_id']+'.csv');receipt=read(a.work/'receipts'/(r['case_id']+'.json'))
        assert sha(p)==receipt['features_sha256'],'FEATURE_HASH'
        with p.open() as f:values=list(csv.DictReader(f))
        assert len(values)==r['snapshots']
        out.append([[int(v[k]) for k in FEATURES] for v in values])
    return np.array(out,dtype=np.int64)

def spec(x,family):
    result=[]
    if family in ['counts','mixed']:result.extend({'kind':'count','feature':j} for j in range(16))
    if family in ['predicates','mixed']:
        for j in range(16):
            for t in sorted(set(int(v) for v in np.quantile(x[...,j],[.1,.25,.5,.75,.9]))):
                if x[...,j].min()<=t<x[...,j].max():result.append({'kind':'greater','feature':j,'threshold':t})
    return result
def transform(x,s):return np.stack([x[...,v['feature']] if v['kind']=='count' else (x[...,v['feature']]>v['threshold']).astype(np.int64) for v in s],axis=-1)
def weights(groups,y):
    cnt=collections.Counter(zip(groups,y));result=np.array([1/cnt[g,int(k)] for g,k in zip(groups,y)],dtype=float)
    for k in range(3):result[y==k]/=result[y==k].sum()
    return result*len(y)/3
def fit(z,y,groups,alpha):
    assert set(y)=={0,1,2},'MISSING_TRAIN_CLASS'
    w=weights(groups,y);mean=np.average(z,axis=0,weights=w);scale=np.sqrt(np.average((z-mean)**2,axis=0,weights=w));scale[scale<1e-9]=1
    target=np.eye(3)[y];intercept=np.average(target,axis=0,weights=w)
    zz=(z-mean)/scale;root=np.sqrt(w)[:,None]
    coeff=np.linalg.solve((zz*root).T@(zz*root)+alpha*np.eye(z.shape[1]),(zz*root).T@((target-intercept)*root))
    wf=coeff/scale[:,None];bf=intercept-mean@wf
    factor=min(2.**28,(2**19-1)/max(np.abs(wf).max(),1e-15), (2**38-1)/max(np.abs(bf).max(),1e-15))
    wi=np.rint(wf*factor).astype(np.int64);bi=np.rint(bf*factor).astype(np.int64)
    return {'weights':wi.tolist(),'bias':bi.tolist(),'factor':factor,'weight_bits':20,'accumulator_bits':48,
            'alpha':alpha,'float_weights':wf.tolist(),'float_bias':bf.tolist()}
def infer(z,m):
    w=np.array(m['weights'],dtype=np.int64);b=np.array(m['bias'],dtype=np.int64)
    maxima=z.reshape(-1,z.shape[-1]).max(axis=0)
    bound=max(sum(int(maxima[j])*abs(int(w[j,k])) for j in range(len(maxima)))+abs(int(b[k])) for k in range(3))
    assert bound<2**47,'OBSERVED_48_BIT_BOUND'
    scores=z@w+b
    return scores.argmax(axis=-1),scores,bound
def stats(rr,y,pred):
    cm=np.zeros((3,3),dtype=int)
    for a,b in zip(y,pred):cm[a,b]+=1
    f1=[];group_recall=[]
    for k in range(3):
        den=cm[k].sum()+cm[:,k].sum();f1.append(float(2*cm[k,k]/den) if den else 0.)
        vals=[]
        for g in sorted({r['record'] for r in rr}):
            mask=np.array([r['record']==g for r in rr])&(y==k)
            if mask.any():vals.append(float((pred[mask]==k).mean()))
        group_recall.append(float(np.mean(vals)) if vals else 0.)
    return {'n':len(y),'correct':int(np.trace(cm)),'accuracy':float(np.trace(cm)/len(y)),
        'macro_f1':float(np.mean(f1)),'record_balanced_macro_recall':float(np.mean(group_recall)),
        'confusion_matrix':cm.tolist(),'record_balanced_recall_per_class':group_recall,
        'independent_records':len({r['record'] for r in rr})}

def snapshot_fit(x,rr,family,alpha):
    sy=np.array([r['snapshot_annotation_label_ids'] for r in rr]);mask=sy>=0
    specs=spec(x,family);sx=transform(x,specs)
    gg=np.repeat(np.array([r['record'] for r in rr])[:,None],x.shape[1],axis=1)
    model=fit(sx[mask],sy[mask],gg[mask],alpha)
    return {'spec':specs,'readout':model,'training_labeled_snapshots':int(mask.sum()),'training_ambiguous_snapshots':int((~mask).sum())}
def snapshot_predict(x,m):return infer(transform(x,m['spec']),m['readout'])
def final_input(x,sp,specs):
    # Both class events AND evidence reach Final. Class inputs are predictions,
    # never true annotation labels. This retains the hierarchical architecture.
    evidence=transform(x,specs).sum(axis=1)
    counts=np.stack([(sp==k).sum(axis=1) for k in range(3)],axis=1)
    return np.concatenate([evidence,counts],axis=1)
def group_folds(rr):
    # Deterministic record-exclusive OOF split with label-support balancing.
    groups=sorted({r['record'] for r in rr});cnt={g:np.zeros(3,int) for g in groups}
    for r in rr:
        for y in r['snapshot_annotation_label_ids']:
            if y>=0:cnt[r['record']][y]+=1
    totals=np.zeros((5,3));mapping={}
    order=sorted(groups,key=lambda g:(-cnt[g].sum(),hashlib.sha256(g.encode()).hexdigest()))
    scale=np.maximum(sum(cnt.values()),1)
    for g in order:
        k=min(range(5),key=lambda i:(float(((totals[i]+cnt[g])/scale).sum()),i));mapping[g]=k;totals[k]+=cnt[g]
    return np.array([mapping[r['record']] for r in rr]),mapping

def train(a):
    if (a.out/'frozen_model.json').exists():raise SystemExit('MODEL_ALREADY_FROZEN')
    assert read(a.dataset/'capture_train_validation.json')['status']=='PASS_CAPTURE_AND_FEATURE_EXTRACTION'
    split=read(a.dataset/'split.json');assert sha(a.dataset/'gold_labels.jsonl')==split['gold_labels_sha256']
    candidates=[];models=[]
    for L in [300,600,1800]:
        tr=rows(a,L,'train');vr=rows(a,L,'validation');x=data(a,tr);vx=data(a,vr)
        y=np.array([r['label_id'] for r in tr]);vy=np.array([r['label_id'] for r in vr]);groups=np.array([r['record'] for r in tr])
        fold,mapping=group_folds(tr)
        for family in FAMILIES:
            for alpha in ALPHAS:
                snapshot=snapshot_fit(x,tr,family,alpha)
                oof=np.zeros(x.shape[:2],dtype=int)
                for k in range(5):
                    keep=fold!=k;held=~keep
                    if not held.any():continue
                    fm=snapshot_fit(x[keep],[r for r,b in zip(tr,keep) if b],family,alpha)
                    oof[held]=snapshot_predict(x[held],fm)[0]
                fspec=spec(x,family);z=final_input(x,oof,fspec)
                final=fit(z,y,groups,alpha)
                sp=snapshot_predict(x,snapshot)[0];vsp=snapshot_predict(vx,snapshot)[0]
                tp,_,tb=infer(final_input(x,sp,fspec),final);vp,_,vb=infer(final_input(vx,vsp,fspec),final)
                candidate={'seconds':L,'snapshots':L//60,'family':family,'alpha':alpha,
                    'train':stats(tr,y,tp),'validation':stats(vr,vy,vp),'evidence_features':len(fspec),
                    'snapshot_oof_accuracy_on_unambiguous':float(np.mean(oof[np.array([r['snapshot_annotation_label_ids'] for r in tr])>=0]==np.array([r['snapshot_annotation_label_ids'] for r in tr])[np.array([r['snapshot_annotation_label_ids'] for r in tr])>=0])),
                    'final_training_input':'record-exclusive OOF Snapshot predictions + same feature evidence',
                    'final_observed_abs_bound':max(tb,vb)}
                model={'seconds':L,'snapshots':L//60,'snapshot':snapshot,'final_spec':fspec,'final_readout':final,'fold_assignment':mapping}
                candidates.append(candidate);models.append(model)
                print(json.dumps({'candidate':len(candidates),**candidate}),flush=True)
    order=lambda i:(candidates[i]['validation']['record_balanced_macro_recall'],candidates[i]['validation']['macro_f1'],
                    -candidates[i]['evidence_features'],-candidates[i]['seconds'],candidates[i]['alpha'])
    winner=max(range(len(candidates)),key=order);model=models[winner]
    model.update({'schema':'rhythm3_snapshot_final_hierarchy_v3','class_order':CLASSES,'features':FEATURES,
        'selection_metric':'validation record-balanced macro recall, macro F1, fewer features, shorter duration, larger alpha',
        'arithmetic':'signed 20-bit coefficients; signed 48-bit accumulators; lowest class ID on tie',
        'input_encoding':'raw offset_binary minus 2048; 5000 analog-context samples not fed to frontend',
        'fixed_snapshot_samples':60000,'analog_config_sha256':'b7a4a6dbe10670c2cf268c098acb1115a818d620d742bb68a3f9900241692ff3',
        'dataset_sha256':sha(a.dataset/'gold_labels.jsonl'),'training_script_sha256':sha(Path(__file__)),
        'historical_test_exposure':not split['pristine_vs_previous_48_record_test'],
        'claim_boundary':'software candidate; new RTL and PPA not yet verified','test_used_for_selection':False})
    write(a.out/'selection.json',{'candidates':candidates,'chosen_index':winner,'test_evaluations':0})
    write(a.out/'frozen_model.json',model)
    write(a.out/'freeze_receipt.json',{'sha256':sha(a.out/'frozen_model.json'),'dataset_sha256':model['dataset_sha256'],
        'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'test_evaluations':0})
    print(json.dumps({'status':'FROZEN_BEFORE_TEST','winner':candidates[winner]}),flush=True)

def evaluate(a):
    model=read(a.out/'frozen_model.json');receipt=read(a.out/'freeze_receipt.json')
    assert sha(a.out/'frozen_model.json')==receipt['sha256']
    write(a.out/'test_access_receipt.json',{'model_sha256':receipt['sha256'],'only_duration_seconds':model['seconds']})
    rr=rows(a,model['seconds'],'test');x=data(a,rr);y=np.array([r['label_id'] for r in rr])
    sp,ss,sbound=snapshot_predict(x,model['snapshot']);p,score,fbound=infer(final_input(x,sp,model['final_spec']),model['final_readout'])
    predictions=[{'case_id':r['case_id'],'record':r['record'],'true':int(t),'prediction':int(v),
        'snapshot_predictions':s.tolist(),'final_membrane':m.tolist(),'previous_48_record_exposure':r['previous_48_record_exposure']}
        for r,t,v,s,m in zip(rr,y,p,sp,score)]
    # Record bootstrap, not false independent-window confidence interval.
    rng=np.random.default_rng(20260916);gg=sorted({r['record'] for r in rr});values=[]
    for _ in range(2000):
        picked=rng.choice(gg,len(gg),replace=True);idx=[i for g in picked for i,r in enumerate(rr) if r['record']==g]
        values.append(float((p[idx]==y[idx]).mean()))
    report={'status':'TEST_EVALUATED_ONCE','model_sha256':receipt['sha256'],'seconds':model['seconds'],
        'metrics':stats(rr,y,p),'record_bootstrap_accuracy95':np.quantile(values,[.025,.975]).tolist(),
        'bootstrap_seed':20260916,'bootstrap_resamples':2000,'cases':predictions,
        'observed_abs_bounds':{'snapshot':sbound,'final':fbound},'historical_exposure':model['historical_test_exposure'],
        'clinical_validation':False,'rtl_bit_exact':'NOT_EXECUTED','postroute_ppa':'NOT_EXECUTED'}
    write(a.out/'test_result.json',report);print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['train','evaluate'])
    for k in ['dataset','work','out']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();(train if a.stage=='train' else evaluate)(a)
