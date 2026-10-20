"""Content tests for the Spelling Bee rotation. Run from the repo root:  python3 -m unittest discover -s edit -v"""
import json, re, sys, unittest, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'edit'))
from bundle import enc, split

SRC = (ROOT / 'edit/template.html').read_text()
DEFAULT = json.loads(re.search(r'/\*DEFAULT\*/(.*?)/\*END\*/', SRC, re.S).group(1))
SCHEDULE = json.loads(re.search(r'/\*SCHEDULE\*/(.*?)/\*END\*/', SRC, re.S).group(1))
ALL = [DEFAULT] + SCHEDULE

def pick(today):
    """Python mirror of pickWeek() in the template."""
    p = DEFAULT
    for w in SCHEDULE:
        if w['start'] <= today: p = w
    return p

class Puzzles(unittest.TestCase):
    def test_every_word_is_playable(self):
        for w in ALL:
            L = set(w['outer'] + [w['center']])
            self.assertEqual(len(L), 7, w['title']); self.assertEqual(len(w['outer']), 6)
            for x in w['words']:
                self.assertGreaterEqual(len(x), 4, x); self.assertIn(w['center'], x, x); self.assertLessEqual(set(x), L, x)

    def test_no_duplicates_and_has_pangram(self):
        for w in ALL:
            self.assertEqual(len(w['words']), len(set(w['words'])), w['title'])
            self.assertTrue([x for x in w['words'] if len(set(x)) == 7], w['title'])

    def test_october_default_unchanged(self):
        self.assertEqual(DEFAULT['center'], 'E'); self.assertIn('STRENGTH', DEFAULT['words'])

class Rotation(unittest.TestCase):
    def test_weekly_mondays_in_order(self):
        ds = [datetime.date.fromisoformat(w['start']) for w in SCHEDULE]
        self.assertEqual(len(ds), 16)
        for a, b in zip(ds, ds[1:]): self.assertEqual((b - a).days, 7)
        self.assertTrue(all(d.weekday() == 0 for d in ds))

    def test_pick_boundaries(self):
        first, last = SCHEDULE[0]['start'], SCHEDULE[-1]['start']
        self.assertIs(pick('2026-10-20'), DEFAULT)               # before the first Monday
        day_before = str(datetime.date.fromisoformat(first) - datetime.timedelta(days=1))
        self.assertIs(pick(day_before), DEFAULT)                 # Sunday night
        self.assertIs(pick(first), SCHEDULE[0])                  # Monday it switches
        self.assertIs(pick('2026-12-31'), SCHEDULE[9])           # mid-week
        self.assertIs(pick(last), SCHEDULE[-1])
        self.assertIs(pick('2027-06-01'), SCHEDULE[-1])          # after the plan ends, last week stays

    def test_template_wiring(self):
        for s in ['WEEK = this.pickWeek();', 'ALL_WORDS = this.WEEK.words;', '{{ title }}', '{{ banner }}', '{{ outerLine }}', "/^\\d{4}-\\d{2}-\\d{2}$/"]:
            self.assertIn(s, SRC)
        self.assertNotIn('Letters: S · T · R', SRC)

class Fields(unittest.TestCase):
    def test_every_constant_used_is_defined(self):
        """Catches a field dropped while editing (e.g. HEX_POSITIONS): every this.UPPER_CASE must be declared."""
        used = set(re.findall(r'this\.([A-Z][A-Z_]+)\b', SRC))
        declared = set(re.findall(r'^  ([A-Z][A-Z_]+) = ', SRC, re.M))
        self.assertEqual(used - declared, set())

class Bundle(unittest.TestCase):
    def test_index_matches_template(self):
        s = (ROOT / 'index.html').read_text(); m = split(s)
        self.assertEqual(json.loads(m.group(2)), SRC)
        self.assertEqual(enc(json.loads(m.group(2))), m.group(2))
        self.assertNotIn('</script', m.group(2))

if __name__ == '__main__':
    unittest.main()
