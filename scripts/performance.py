"""Measure a fixed local fixture, never imply production capacity."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import sys
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.fixture_server import fixture_server


def main():
    results={}
    with fixture_server(name='performance',port=8024) as (base,password,database):
        with httpx.Client(base_url=base,headers={'X-Requested-With':'EmojiApp'},timeout=20) as c:
            c.post('/api/auth/login',json={'username':'student','password':password}).raise_for_status()
            for i in range(50):
                c.post('/api/emoji',json={'session_id':1,'emoji':['happy','neutral','surprised','sad','angry'][i%5]}).raise_for_status()
            for concurrency in [1,10]:
                def request(_):
                    start=time.perf_counter();r=c.get('/api/emoji/history?page_size=20');r.raise_for_status()
                    assert r.json()['total']==50
                    return (time.perf_counter()-start)*1000
                start=time.perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:latencies=list(pool.map(request,range(100)))
                elapsed=time.perf_counter()-start
                latencies.sort()
                results[str(concurrency)]={'requests':100,'records':50,'concurrency':concurrency,
                    'p50_ms':round(statistics.median(latencies),2),'p95_ms':round(latencies[94],2),
                    'max_ms':round(max(latencies),2),'requests_per_second':round(100/elapsed,2)}
    output={'environment':'Windows Python3.12 SQLite localhost; authenticated history 20 rows per page',
        'scope':'Local course verification; not a production load estimate','results':results}
    (ROOT/'docs'/'performance.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
