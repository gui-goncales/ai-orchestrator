"""Local persistence benchmark. MOCK only; no token or quality savings claims."""
import json
import statistics
import tempfile
import time
from pathlib import Path
from backend.core import Store, Supervisor

class MockAdapter:
    def execute(self, prompt, cwd, emit, cancel):
        return {'status':'completed','result':'MOCK result','usage':{},'error':None}

with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'benchmark.sqlite', tmp)
    supervisor=Supervisor(store, MockAdapter())
    times=[]
    for i in range(50):
        start=time.perf_counter()
        store.create('MOCK benchmark objective', 'local', 'auto', str(i))
        supervisor.run_once()
        times.append((time.perf_counter()-start)*1000)
    report={'kind':'local_mock_persistence_only','samples':len(times),'median_ms':round(statistics.median(times),3),'p95_ms':round(sorted(times)[int(len(times)*.95)-1],3),'completed':sum(t['status']=='completed' for t in store.snapshot()['tasks']),'provider_calls':0,'token_savings':None,'quality_evaluation':None}
    Path('evidence/benchmark-local.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
