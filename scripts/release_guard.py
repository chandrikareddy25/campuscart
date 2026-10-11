"""Local-cluster release verification with compare-and-swap Git restoration."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from context_policy import decide, compare

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'release/known-good.json'
MANIFEST=ROOT/'k8s/application.yaml'

def command(args,**kwargs):
    return subprocess.run(args,text=True,capture_output=True,**kwargs)
def git(*args):
    r=command(['git',*args],cwd=ROOT)
    if r.returncode: raise RuntimeError('Git operation failed: '+args[0])
    return r.stdout.strip()
def kube(*args,**kwargs):
    env=dict(os.environ);env.setdefault('KUBECONFIG',str(Path.home()/'.kube/campuscart.config'))
    return command(['kubectl','--context','kind-campuscart',*args],env=env,**kwargs)
def schema_hash():
    h=hashlib.sha256()
    for p in sorted((ROOT/'backend/app/migrations').glob('*.sql')):
        h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()
def images(text):
    return {s:re.findall(r'(?m)^\s*image:\s*(ghcr\.io/[^/\s]+/campuscart-'+s+r':[^\s]+)\s*$',text)[0] for s in ('backend','frontend')}
def replace_images(text,target):
    for s,image in target.items():
        text,n=re.subn(r'(?m)^(\s*image:\s*)ghcr\.io/[^/\s]+/campuscart-'+s+r':[^\s]+',lambda m:m[1]+image,text)
        if n!=1: raise RuntimeError('Expected exactly one '+s+' image')
    return text

def wait_release(target,revision,timeout=300):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app=kube('-n','argocd','get','application','campuscart','-o','json')
        d=kube('-n','campuscart','get','deployments','backend','frontend','-o','json')
        if app.returncode==0 and d.returncode==0:
            a=json.loads(app.stdout);deployments=json.loads(d.stdout)['items']
            good=a.get('status',{}).get('sync',{}).get('revision')==revision and a.get('status',{}).get('sync',{}).get('status')=='Synced'
            for item in deployments:
                s=item['metadata']['name'];status=item.get('status',{});replicas=item['spec'].get('replicas',1)
                good=good and replicas>0 and status.get('observedGeneration',0)>=item['metadata']['generation'] and status.get('updatedReplicas',0)==replicas and status.get('readyReplicas',0)==replicas and status.get('replicas',0)==replicas and status.get('availableReplicas',0)==replicas and any(c['image']==target[s] for c in item['spec']['template']['spec']['containers'])
            if good:return True
        time.sleep(3)
    return False

def probe(password,mode='transactional'):
    filename='transaction_probe.py' if mode=='contextual' else 'transaction_probe_legacy.py'
    code=(ROOT/'scripts'/filename).read_text()
    wrapper='import sys,json; payload=json.loads(sys.stdin.read()); sys.stdin=__import__("io").StringIO(json.dumps({"password":payload["password"]})); exec(compile(payload["code"],"transaction_probe.py","exec"),{"__name__":"__main__"})'
    r=kube('-n','campuscart','exec','-i','deployment/backend','--','python','-c',wrapper,input=json.dumps({'code':code,'password':password}),timeout=180)
    try:return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):return {'status':'inconclusive','reason':'Probe did not return a report'}

def remote_snapshot():
    code=(ROOT/'scripts/transaction_probe.py').read_text()
    wrapper='import json,sys; scope={"__name__":"probe_snapshot"}; exec(compile(sys.stdin.read(),"transaction_probe.py","exec"),scope); print(json.dumps(scope["snapshot"]()))'
    r=kube('-n','campuscart','exec','-i','deployment/backend','--','python','-c',wrapper,input=code,timeout=90)
    if r.returncode:raise RuntimeError('Cannot snapshot business data')
    return json.loads(r.stdout.strip().splitlines()[-1])

def commit_files(message,files):
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add',*files);git('commit','-m',message);git('push','origin','HEAD:main')
    return git('rev-parse','HEAD')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision');parser.add_argument('--preflight',action='store_true');parser.add_argument('--mode',choices=['health','transactional','contextual'],default='contextual');args=parser.parse_args()
    if args.preflight:
        if schema_hash()!=json.loads(POLICY.read_text())['schema_sha256']:raise SystemExit('Schema compatibility review required')
        result=probe(os.environ.get('RELEASE_TEST_PASSWORD',''),'contextual')
        if result['status']!='passed':raise SystemExit('Preflight verification failed: '+result.get('reason','unknown'))
        print(json.dumps(remote_snapshot()))
        return 0
    if not args.revision:parser.error('--revision is required')
    report={'mode':args.mode,'deployment_commit':args.revision,'started_at':datetime.now(timezone.utc).isoformat(),'status':'inconclusive'}
    started=time.monotonic();exit_code=1
    try:
        policy=json.loads(POLICY.read_text());target=images(MANIFEST.read_text())
        if schema_hash()!=policy['schema_sha256']:raise RuntimeError('Schema changed: automatic rollback requires a new compatibility review')
        password=os.environ.get('RELEASE_TEST_PASSWORD','')
        if args.mode!='health' and not password:raise RuntimeError('Missing RELEASE_TEST_PASSWORD')
        if kube('cluster-info',timeout=30).returncode:raise RuntimeError('Local cluster unreachable; no rollback attempted')
        baseline=json.loads(os.environ['RELEASE_BASELINE'])
        report['data_before_deployment']=baseline
        report['candidate_images']=target;report['previous_images']=policy['images']
        healthy=wait_release(target,args.revision)
        report['wait_to_healthy_seconds']=round(time.monotonic()-started,3)
        # Timer starts when guard runs, not when CI started or Git was pushed.
        result=probe(password,args.mode) if healthy and args.mode!='health' else {'status':'passed' if healthy else 'failed','reason':'Infrastructure readiness check'}
        report['verification']=result
        if healthy and args.mode=='contextual':
            attempts=[result]
            decision=decide(result)
            for attempt in range(2):
                if decision['action']!='retry':break
                time.sleep(5)
                result=probe(password,'contextual');attempts.append(result);decision=decide(result)
            if decision['action']=='retry':
                decision={'action':'defer','classification':'retry_budget_exhausted','reason':'Unresolved dependency/observation failure; no release attribution'}
            report['attempts']=attempts;report['decision']=decision
            report['comparative_decisions']=compare(attempts[0],healthy)
            report['comparison_kind']='policy interpretation; use context-benchmark.json for measured baseline probes'
            report['verification']=result
        if healthy:
            report['data_after_candidate']=remote_snapshot()
            if report['data_after_candidate']!=baseline:
                result={'status':'failed','reason':'Existing business data changed since preflight'}
                report['verification']=result
                report['decision']={'action':'reject','classification':'integrity_violation','reason':result['reason']}
        if args.mode=='contextual' and report.get('decision',{}).get('action')=='defer':
            report['status']='deferred'
            raise RuntimeError(report['decision']['reason'])
        if result['status']=='inconclusive':raise RuntimeError('Probe inconclusive: inspect runner connectivity and configuration')
        git('fetch','origin','main')
        if git('rev-parse','origin/main')!=args.revision:raise RuntimeError('Main changed: refusing to overwrite a newer release')
        if result['status']=='passed':
            report['status']='passed';exit_code=0
            # Health-only experiments must never promote an unverified rollback target.
            if args.mode!='health':
                policy['images']=target;policy['verified_deployment_commit']=args.revision
                POLICY.write_text(json.dumps(policy,indent=2)+'\n')
                report['promotion_commit']=commit_files('Record verified CampusCart release [skip ci]',['release/known-good.json'])
        else:
            rollback_start=time.monotonic()
            MANIFEST.write_text(replace_images(MANIFEST.read_text(),policy['images']))
            revision=commit_files('Restore verified CampusCart images [skip ci]',['k8s/application.yaml'])
            report['rollback_commit']=revision
            recovered=wait_release(policy['images'],revision)
            report['rollback_to_ready_seconds']=round(time.monotonic()-rollback_start,3)
            report['recovery_verification']=probe(password,args.mode) if recovered and args.mode!='health' else {'status':'passed' if recovered else 'failed'}
            if recovered:
                report['data_after_rollback']=remote_snapshot()
                report['data_integrity_preserved']=report['data_after_rollback']==baseline
            report['status']='rolled_back' if recovered and report['recovery_verification']['status']=='passed' and report.get('data_integrity_preserved') else 'recovery_failed'
            # A rejected release remains a failed Actions run even if recovery succeeds.
    except Exception as e:
        report['reason']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();report['total_guard_seconds']=round(time.monotonic()-started,3)
        path=ROOT/'release-results';path.mkdir(exist_ok=True)
        (path/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    return exit_code

if __name__=='__main__':sys.exit(main())
