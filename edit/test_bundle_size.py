"""Load-time guards for index.html. Run from the repo root:  python3 -m unittest discover -s edit -v

The claude.ai/design export ships the whole Origin design-system bundle (~3 MB of JS, with saved
copies of the booking flow's gtm.js / fbevents.js / analytics.js) even though the game uses none
of it. That roughly doubled the download and ran Google Tag Manager plus an Ours Privacy ingest
call on every open. prune.py removes it; these tests stop it coming back on a re-export."""
import base64, gzip, json, re, sys, unittest, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'edit'))
from bundle import enc, split
from prune import prune, DS_MARK

INDEX = (ROOT / 'index.html').read_text()
BUDGET = 1_200_000  # bytes; was ~1.95 MB with the design-system bundle, ~1.03 MB without
TRACKERS = ['googletagmanager.com/gtm.js', 'connect.facebook.net', 'fbq(', 'oursprivacy', '@ds-bundle']

def manifest(s):
    return json.loads(re.search(r'<script type="__bundler/manifest">(.*?)</script>', s, re.S).group(1))

def ext(s):
    return re.search(r'<script type="__bundler/ext_resources">(.*?)</script>', s, re.S).group(1)

def decode(v):
    raw = base64.b64decode(v['data'])
    return gzip.decompress(raw) if v.get('compressed') else raw

def fixture(with_ds=True):
    """A tiny bundle shaped like the real export: runtime + optional DS bundle + one font."""
    def asset(body, mime):
        return {'mime': mime, 'compressed': True, 'data': base64.b64encode(gzip.compress(body)).decode()}
    man = {'rt-1': asset(b'// runtime', 'text/javascript'),
           'react-1': asset(b'/* react */', 'text/javascript'),
           'font-1': asset(b'\x00font', 'font/ttf')}
    tpl = '<html><head><script src="rt-1"></script>'
    if with_ds:
        man['ds-1'] = asset(DS_MARK.encode() + b' {} */ gtm.js', 'application/javascript')
        tpl += '\n  <script src="ds-1"></script>'
    tpl += '<style>@font-face{src:url("font-1")}</style></head></html>'
    return ('<html><body>\n  <script type="__bundler/manifest">\n' + json.dumps(man, separators=(',', ':')) +
            '\n  </script>\n  <script type="__bundler/ext_resources">\n[{"id":"react","uuid":"react-1"}]\n  </script>\n'
            '  <script type="__bundler/template">' + enc(tpl) + '</script>\n</body></html>')

class LiveBundle(unittest.TestCase):
    def test_under_size_budget(self):
        self.assertLess(len(INDEX.encode()), BUDGET)

    def test_no_design_system_or_tracking_code(self):
        for k, v in manifest(INDEX).items():
            if 'javascript' in v['mime']:
                body = decode(v).decode('utf-8', 'replace')
                for t in TRACKERS:
                    self.assertNotIn(t, body, f'{k} contains {t}')

    def test_every_asset_is_used(self):
        tpl = json.loads(split(INDEX).group(2)); e = ext(INDEX)
        unused = [k for k in manifest(INDEX) if k not in tpl and k not in e]
        self.assertEqual(unused, [])

    def test_nothing_the_page_needs_is_missing(self):
        tpl = json.loads(split(INDEX).group(2)); man = manifest(INDEX)
        refs = set(re.findall(r'(?:src="|url\(")([0-9a-f]{8}-[0-9a-f-]{27})', tpl))
        refs |= {x['uuid'] for x in json.loads(ext(INDEX))}
        self.assertTrue(refs)
        self.assertEqual(refs - set(man), set())

    def test_already_pruned(self):
        out, dropped, _ = prune(INDEX)
        self.assertEqual(dropped, []); self.assertEqual(out, INDEX)

class Prune(unittest.TestCase):
    def test_drops_ds_bundle_and_its_script_tag(self):
        out, dropped, tpl = prune(fixture())
        self.assertEqual(dropped, ['ds-1'])
        self.assertNotIn('ds-1', out)
        self.assertEqual(set(manifest(out)), {'rt-1', 'react-1', 'font-1'})
        self.assertIn('<script src="rt-1"></script>', tpl)

    def test_keeps_react_listed_only_in_ext_resources(self):
        out, _, tpl = prune(fixture())
        self.assertNotIn('react-1', tpl); self.assertIn('react-1', manifest(out))

    def test_noop_without_ds_and_idempotent(self):
        clean = fixture(with_ds=False)
        out, dropped, _ = prune(clean)
        self.assertEqual(dropped, []); self.assertEqual(out, clean)
        once, _, _ = prune(fixture()); twice, d2, _ = prune(once)
        self.assertEqual(twice, once); self.assertEqual(d2, [])

    def test_manifest_whitespace_preserved(self):
        out, _, _ = prune(fixture())
        self.assertIn('<script type="__bundler/manifest">\n{', out)

if __name__ == '__main__':
    unittest.main()
