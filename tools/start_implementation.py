import json,pathlib
root=pathlib.Path(__file__).resolve().parents[1]
t=json.loads((root/'plans/tasks.json').read_text())[0]
print('START '+t['id']+': '+t['title'])
print('Read AGENTS.md, spec/requirements.md, and '+t['plan'])
print('Acceptance: '+t['acceptance'])
print('Affected components: '+', '.join(t['files']))
print('Verify with:')
for command in t['commands']:print('  '+command)
print('Then continue T02 historical Cape/Maryland, T03 upcoming attempt, and every remaining milestone.')
