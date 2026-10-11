"""Run actual HTTP probes on the current release; change only dedicated fixtures."""
import getpass
import json
import subprocess
from pathlib import Path
from release_guard import kube,ROOT

CODE=r'''
import json,sys,time,types
payload=json.load(sys.stdin)
def load(name,code):
    m=types.ModuleType(name);sys.modules[name]=m;exec(compile(code,name+'.py','exec'),m.__dict__);return m
legacy=load('legacy_probe',payload['legacy'])
context=load('context_probe',payload['context'])
from app.db import connect
from urllib.request import urlopen

def execute(module):
    started=time.monotonic()
    try:return {'status':'passed',**module.run(payload['password']),'seconds':round(time.monotonic()-started,3)}
    except module.ProbeFailure as e:return {'status':'failed','reason':str(e),'kind':getattr(e,'kind','legacy_failure'),'seconds':round(time.monotonic()-started,3)}
    except Exception as e:return {'status':'inconclusive','reason':type(e).__name__}

with connect() as c:
    c.execute('SELECT pg_advisory_xact_lock(892316)')
    products=c.execute("SELECT id,stock,active FROM products WHERE specifications->>'release_probe'='true'").fetchall()
    if len(products)!=1 or products[0]['stock']<=5:raise SystemExit('Primary fixture not ready')
    p=products[0]
    locations=c.execute("SELECT id FROM pickup_locations WHERE name='Release verification desk'").fetchall()
    if len(locations)!=1:raise SystemExit('Primary pickup desk missing')
    from app.services import ensure_slots
    ensure_slots(c,locations[0]['id'])
    slots=c.execute('SELECT id,booked,capacity FROM pickup_slots WHERE location_id=%s AND starts_at>now()',(locations[0]['id'],)).fetchall()
    if not slots or any(s['booked'] for s in slots):raise SystemExit('Primary test slots are not empty; inspect previous experiments')
# Never conduct fixture experiments against a release already failing transactions.
preflight=execute(context)
if preflight['status']!='passed':raise SystemExit('Current release must pass contextual checks before benchmarking')
before=context.snapshot();results=[]
try:
    for case in ('healthy','stock_unavailable','slots_full','both_constraints'):
        with connect() as c:
            c.execute('UPDATE products SET stock=%s WHERE id=%s',(0 if case in ('stock_unavailable','both_constraints') else p['stock'],p['id']))
            for slot in slots:
                c.execute('UPDATE pickup_slots SET booked=%s WHERE id=%s',(slot['capacity'] if case in ('slots_full','both_constraints') else slot['booked'],slot['id']))
        with urlopen('http://backend:8000/health/ready',timeout=5) as r:healthy=json.load(r)['status']=='ready'
        a=execute(legacy);b=execute(context)
        results.append({'scenario':case,'ground_truth':'accept_if_valid_control_checkout_passes','health_only':{'status':'passed' if healthy else 'failed'},'existing_guard':a,'contextual_guard':b})
finally:
    with connect() as c:
        c.execute('UPDATE products SET stock=%s WHERE id=%s',(p['stock'],p['id']))
        for slot in slots:c.execute('UPDATE pickup_slots SET booked=%s WHERE id=%s',(slot['booked'],slot['id']))
after=context.snapshot()
print(json.dumps({'comparison_kind':'same deployed release, real HTTP and controlled dedicated DB fixtures','results':results,'business_data_unchanged':before==after,'before':before,'after':after}))
'''
if __name__=='__main__':
    password=getpass.getpass('Test account password: ')
    result=kube('-n','campuscart','exec','-i','deployment/backend','--','python','-c',CODE,input=json.dumps({'password':password,'legacy':(ROOT/'scripts/transaction_probe_legacy.py').read_text(),'context':(ROOT/'scripts/transaction_probe.py').read_text()}),timeout=240)
    if result.returncode:
        print(result.stderr.strip());raise SystemExit('Benchmark did not finish. Check dedicated fixture state before retrying.')
    report=json.loads(result.stdout.strip().splitlines()[-1])
    folder=ROOT/'release-results';folder.mkdir(exist_ok=True)
    file=folder/'context-benchmark.json';file.write_text(json.dumps(report,indent=2)+'\n')
    for case in report['results']:
        print(case['scenario']+': '+', '.join(k+'='+case[k]['status'] for k in ('health_only','existing_guard','contextual_guard')))
    print('Existing business data unchanged:',report['business_data_unchanged'])
    print('Saved:',file)
