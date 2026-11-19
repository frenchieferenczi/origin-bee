"""Drop bundled assets the page never loads, so the file is smaller and nothing extra runs.
Usage: prune.py <index.html>   (edits in place; run after bundle.py)

An asset is kept only if its uuid appears in the template island or in ext_resources
(React, which the runtime loads itself). The claude.ai/design export also ships the whole
Origin design-system bundle (~3 MB of JS, including saved copies of the booking flow's
gtm.js, fbevents.js and analytics.js); the games use none of it, so its <script> tag is
removed from the template and its manifest entry goes with it."""
import re, json, sys

DS_MARK = '/* @ds-bundle:'

def prune(s):
    from bundle import enc, split
    import base64, gzip
    mm = re.search(r'(<script type="__bundler/manifest">)(.*?)(</script>)', s, re.S)
    man = json.loads(mm.group(2))
    m = split(s); tpl = json.loads(m.group(2))
    for k, v in list(man.items()):
        if 'javascript' not in v['mime']: continue
        raw = base64.b64decode(v['data'])
        body = gzip.decompress(raw) if v.get('compressed') else raw
        if body.lstrip().startswith(DS_MARK.encode()):
            tpl = re.sub(r'\s*<script src="%s"></script>' % re.escape(k), '', tpl)
    s = s[:m.start(2)] + enc(tpl) + s[m.end(2):]
    ext = re.search(r'<script type="__bundler/ext_resources">(.*?)</script>', s, re.S).group(1)
    keep = {k: v for k, v in man.items() if k in tpl or k in ext}
    mm = re.search(r'(<script type="__bundler/manifest">)(.*?)(</script>)', s, re.S)
    new = json.dumps(keep, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\u002F')
    g = mm.group(2); lead = g[:len(g) - len(g.lstrip())]; trail = g[len(g.rstrip()):]
    return s[:mm.start(2)] + lead + new + trail + s[mm.end(2):], sorted(set(man) - set(keep)), tpl

if __name__ == '__main__':
    p = sys.argv[1]; s = open(p).read()
    out, dropped, tpl = prune(s)
    open(p, 'w').write(out)
    print('dropped', len(dropped), 'assets:', dropped, f'{len(s):,} -> {len(out):,} bytes')
