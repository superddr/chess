# -*- coding: utf-8 -*-
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
for name, path in [('web-xiangqi', 'web/index.html'),
                   ('web-intl', 'web/international/index.html')]:
    html = open(os.path.join(ROOT, path), encoding='utf-8').read()
    js = re.search(r'<script>([\s\S]*)</script>', html).group(1)
    s = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", js)
    s = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', s)
    s = re.sub(r'`(?:\\.|[^`\\])*`', '``', s)
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'/\*[\s\S]*?\*/', '', s)
    ok = all(s.count(a) == s.count(b) for a, b in [('{', '}'), ('(', ')'), ('[', ']')])
    print(name, 'brackets', 'OK' if ok else 'MISMATCH',
          {a + b: (s.count(a), s.count(b)) for a, b in [('{', '}'), ('(', ')'), ('[', ']')]})
    m = re.search(r"new Worker\('([^']+)'\)", js)
    wf = m.group(1) if m else None
    exists = wf and os.path.exists(os.path.join(ROOT, os.path.dirname(path), wf))
    print('  worker:', wf, 'exists:', exists)
    print('  残留 fetch(:', js.count("fetch("), ' noteReconnect:', js.count('noteReconnect'))
