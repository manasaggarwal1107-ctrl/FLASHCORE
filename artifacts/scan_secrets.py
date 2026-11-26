import re
from pathlib import Path

files_to_scan = [
    'backend/app/models/rossmann.py',
    'backend/app/routes/admin.py',
    'backend/app/routes/simulation.py',
    'backend/main.py',
    'frontend/API_CONTRACT.md',
    'frontend/eslint.config.js',
    'frontend/src/features/customers/CustomersPage.tsx',
    'frontend/src/features/orders/OrdersPage.tsx',
    'frontend/src/features/pages.test.tsx',
    'frontend/src/lib/config.ts',
    'frontend/src/services/api/endpoints.test.ts',
    'frontend/src/services/api/endpoints.ts',
    'backend/app/routes/imports.py',
    'backend/tests/test_imports_audit_health.py',
    'frontend/.gitignore',
]

secret_patterns = [
    (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'"][^\'"]+[\'"]'), 'Hardcoded password'),
    (re.compile(r'(?i)(secret|api_key|apikey|access_token|private_key)\s*[:=]\s*[\'"][^\'"]+[\'"]'), 'Hardcoded secret/key'),
    (re.compile(r'postgres(ql)?://[^\s\'"<>]+:[^\s\'"<>]+@'), 'Database URI with credentials'),
    (re.compile(r'ghp_[A-Za-z0-9_]{36}'), 'GitHub Personal Access Token'),
    (re.compile(r'ey[A-Za-z0-9-_=]{20,}\.[A-Za-z0-9-_=]{20,}\.?[A-Za-z0-9-_.+/=]*'), 'JWT Token string'),
]

findings = []
for f_path in files_to_scan:
    p = Path(f_path)
    if not p.exists():
        print(f'File not found: {f_path}')
        continue
    content = p.read_text(encoding='utf-8')
    for pat, desc in secret_patterns:
        for m in pat.finditer(content):
            match_str = m.group(0)
            # check false positives
            if any(term in match_str.lower() for term in ('dummy', 'placeholder', 'example', 'secret_term', 'redacted')):
                continue
            findings.append((f_path, desc, match_str[:40]))

if not findings:
    print('SECRET SCAN PASSED: 0 secrets found across all candidate files.')
else:
    print(f'SECRET SCAN WARNING: {len(findings)} potential matches found:')
    for f, d, s in findings:
        print(f'  {f}: {d} -> {s}')
