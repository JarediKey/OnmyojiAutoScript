"""Local-only fixed operations for the private SSH consumer; never dump config."""
import base64
import json
from pathlib import Path
import sys
import time

from service import Store
from runtime import Runtime


def main():
    settings = json.loads(Path(__file__).resolve().parents[1].joinpath('settings.json').read_text(encoding='utf-8-sig'))
    runtime = Runtime(settings)
    store = Store(str(runtime.private / 'incidents.sqlite'))
    request = json.loads(base64.b64decode(sys.argv[1]))
    operation = request['operation']
    rows = store.rows(['needs_ai'])
    if operation == 'list':
        print(json.dumps([{'id': r['id'], 'name': r['name']} for r in rows], ensure_ascii=False))
        return
    row = next((r for r in rows if r['id'] == request.get('id')), None)
    if row is None:
        print('{}')
        return
    if operation == 'report':
        path = runtime.private / 'ai' / row['id'] / 'incident.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        report['current_log_tail'] = runtime.log_tail(row['name'], 80)
        report['currently_alive'] = row['name'] in runtime.status()
        image_path = path.parent / 'screen.png'
        if image_path.exists() and image_path.stat().st_size < 5_000_000:
            report['image_base64'] = base64.b64encode(image_path.read_bytes()).decode()
        print(json.dumps(report, ensure_ascii=False))
    elif operation == 'decision':
        decision = request['decision']
        path = runtime.private / 'ai' / row['id'] / 'decision.json'
        if path.exists():
            summary = 'AI 允许的一次恢复重试仍收到终止通知，需要人工检查。'
            store.update(row['id'], 'manual', {'summary_zh': summary})
            print(json.dumps({'notify': summary}, ensure_ascii=False))
            return
        if decision.get('action') not in ['retry_once', 'needs_human']:
            raise ValueError('Invalid decision')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding='utf-8')
        if decision['action'] == 'retry_once' and row['name'] not in runtime.status():
            store.update(row['id'], 'queued', {'ai_retry_used': True})
        else:
            store.update(row['id'], 'manual', decision)
        print('{}')
    else:
        raise ValueError('Unknown operation')


if __name__ == '__main__':
    main()
