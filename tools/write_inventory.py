import json,pathlib
root=pathlib.Path('.')
checks={
'api-contract':['api-contract'],'migrations':['api-contract','backup-restore'],'ingestion':['worker-recovery','R003'],'route-registry':['route-registry','R004','parse_historical_archive'],'normalization':['R002','R009'],'launch-windows':['launch-windows'],'assessment-provenance':['reproducibility','R010'],'worker-recovery':['worker-recovery'],'security':['privacy-security'],'browser-location':['browser-journeys'],'accessibility':['browser-journeys'],'browser-guidance':['browser-journeys','R007','R010'],'browser-subscriptions':['browser-journeys','R012','R013'],'postgres-races':['postgres-races'],'calendar':['calendar'],'health':['worker-recovery','api-contract'],'optional-email-policy':['scope-cost'],'deployment':['backup-restore','privacy-security'],'backup-restore':['backup-restore'],'full-release':['all'],'load-100':['load-100'],'release-recovery':['backup-restore','worker-recovery'],'pilot-archive':['pilot-archive']}
(root/'tests/acceptance/checks.json').write_text(json.dumps({'version':1,'dispatcher':'python -m implementation.checks NAME','must_fail_unknown_or_missing_suite':True,'mapping':checks,'notes':'Alias dispatcher runs every listed real acceptance suite and writes command/exit/hash evidence. Browser subjourneys and actual deployment add task-specific assertions; broad aliases never waive plan acceptance criteria.'},indent=2)+'\n')
p=root/'tests/acceptance/README.md';s=p.read_text();s+='\nThe complete planned check-name dispatch table is [checks.json](checks.json). Implement it in T01; each alias must run all listed suites. Add focused assertions required by its task (e.g. browser subscription journey), not only broad smoke checks.\n\nRelease manifests: `evidence/releases/G-REAL.json` etc contain `reviewed_input_manifest` pointing to a real file plus nonempty `checks` entries with `command`, `exit_code`, `status`, `artifact_path`, `sha256`. Source manifests include immutable URLs, hashes, roles (training/heldout), exact mission/attempt association and reviewer rationale. Do not pass by editing gate status; command evidence is required. Software release checks G-SPEC/G-SOFTWARE/G-REAL/G-UPCOMING/G-GUIDANCE; `--stage pilot` additionally requires G-PILOT.\n';p.write_text(s)
p=root/'VERIFICATION.md';s=p.read_text();s=s.replace('-9 ','- 9 ').replace('-10 ','- 10 ').replace('-44 ','- 44 ').replace('-15 ','- 15 ');p.write_text(s)
(root/'README.md').write_text('''# Launch visibility specification workspace

This is the executable specification and implementation handoff for the supplied PRD, not a built application.

Start at [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Agent instructions: [AGENTS.md](AGENTS.md). Read [verification results](VERIFICATION.md) and the [generated file inventory](GENERATED_FILES.md).

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r requirements-spec.lock.txt
python tools/check_spec.py
python tools/start_implementation.py
```

Windows without activation: `.venv/Scripts/python.exe tools/check_spec.py`. GNU make targets provide the same commands on systems with make. `make acceptance` must fail until a real application adapter exists; live integration and empirical visibility are separate gates. No paid API credentials are required.
''')
files=sorted(p.as_posix() for p in root.rglob('*') if p.is_file() and not any(s in p.parts for s in ['.venv','__pycache__','.git']) and p.name not in ['Launch_Visibility_PRD.md','GENERATED_FILES.md','live-ll2-budget.json'])
(root/'GENERATED_FILES.md').write_text('# Generated file inventory\n\nOriginal `Launch_Visibility_PRD.md` preserved and excluded below. Local `.venv`, bytecode caches and live smoke budget ledger are tooling state, not deliverables. This inventory lists every generated deliverable (plus this inventory itself).\n\n'+'\n'.join('- `'+x+'`' for x in files)+'\n- `GENERATED_FILES.md`\n')
print('Generated deliverables:',len(files)+1)
