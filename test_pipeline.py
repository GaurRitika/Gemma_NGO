import requests, json, time

t0 = time.time()

# 1. Start demo
r = requests.post('http://localhost:8080/api/start_demo')
data = r.json()
ep = data['episode_id']
print(f"Episode: {ep}")
print(f"Sources: {data['observation']['available_sources']}")

# 2. Run full batch pipeline (should be fast - rule-based if Ollama slow)
r2 = requests.post(f'http://localhost:8080/api/run_full_pipeline/{ep}')
res = r2.json()
elapsed = time.time() - t0

print(f"\nSteps executed : {res['total_steps']}")
print(f"Total reward   : {res['total_reward']}")
print(f"Done           : {res['done']}")
print(f"Total time     : {elapsed:.2f}s")
print("\nStep log:")
for s in res['steps_log']:
    col = s['column'] or '-'
    print(f"  [{s['step']:02d}] {s['action']:<22} {s['source']}.{col:<20} reward={s['reward']:+.3f}  {s['feedback'][:55]}")
