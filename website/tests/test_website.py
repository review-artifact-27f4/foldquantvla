"""Evidence, anonymity, progressive enhancement, and publishing-path checks."""
from html.parser import HTMLParser
import importlib.util
import math
from pathlib import Path
from urllib.parse import urlsplit
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('website_build', ROOT / 'build.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class EvidenceTests(unittest.TestCase):
    def test_campaign_population_and_missing_measurements(self):
        data = site.load('libero')
        models = data['models']
        self.assertEqual([len(m['rows']) for m in models], [12, 16, 8, 9])
        self.assertEqual(sum(len(m['rows']) for m in models) * data['episodes_per_run'], 36000)
        self.assertEqual(data['comparison_count'], 41)
        self.assertEqual(data['significant_loss_count'], 0)
        self.assertEqual([m['key'] for m in models], ['n17', 'n16', 'n15', 'pi05'])
        for model in models:
            self.assertEqual(len({r['key'] for r in model['rows']}), len(model['rows']))
            self.assertLessEqual(model['k'], model['chunk_length'])
            for row in model['rows']:
                self.assertLessEqual(abs(row['rate'] - row['successes'] / 8), 0.00501)
                # Independently check the descriptive intervals against counts.
                n, z = 800, 1.959964
                p = row['successes'] / n
                center = (p + z*z/(2*n)) / (1+z*z/n)
                half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)) / (1+z*z/n)
                self.assertAlmostEqual(row['ci_low'], 100*(center-half), delta=0.055)
                self.assertAlmostEqual(row['ci_high'], 100*(center+half), delta=0.055)

    def test_headline_denominators_and_failure_cases(self):
        jetson = {r['key']: r for r in site.load('jetson')['rows']}
        self.assertEqual((jetson['float']['e2e_ms'], jetson['int4']['e2e_ms']), (150,125))
        self.assertEqual((jetson['float']['engine_mb'], jetson['int4']['engine_mb']), (5325,2525))
        self.assertEqual(jetson['float']['e2e_ms']/jetson['int4']['e2e_ms'], 1.2)
        desktop = {r['key']: r for r in site.load('desktop')['rows']}
        self.assertEqual((desktop['n16']['eager'],desktop['n16']['compiled'],desktop['n16']['int4']), (74.2,44.1,33.9))
        self.assertEqual(desktop['smol']['compiled_share_pct'], 99.9)
        self.assertIn('fails fidelity',desktop['smol']['note'])
        self.assertGreater(desktop['evo']['int4'],desktop['evo']['int8'])
        self.assertIn('unresolved',desktop['evo']['note'])


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = site.build(Path(cls.temp.name)/'site','https://example.github.io/project/')
        cls.html = (cls.output/'index.html').read_text()
        cls.doc = Document(cls.html)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_internal_links_and_complete_assets(self):
        ids = [a['id'] for _,a in self.doc.elements if 'id' in a]
        self.assertEqual(len(ids),len(set(ids)))
        for tag, attrs in self.doc.elements:
            if tag == 'a':
                if attrs['href'] == './':
                    continue
                if attrs['href'].startswith('https://'):
                    # The only external link is the anonymized code repository.
                    self.assertTrue(attrs['href'].startswith('https://anonymous.4open.science/'), attrs['href'])
                    continue
                self.assertTrue(attrs['href'].startswith('#'))
                self.assertIn(attrs['href'][1:], ids)
            if tag in ('img','script','link'):
                path = attrs.get('src', attrs.get('href',''))
                if path and not path.startswith(('https:', '#')):
                    self.assertTrue((self.output/urlsplit(path).path).is_file(),path)
        self.assertTrue((self.output/'.nojekyll').is_file())
        self.assertEqual((self.output/'robots.txt').read_text(), 'User-agent: *\nDisallow: /\n')
        self.assertFalse(any(self.output.rglob('*.pdf')))
        css = (self.output/'assets/styles.css').read_text()
        for url in re.findall(r"url\(['\"]?([^)'\"]+)",css):
            self.assertTrue((self.output/'assets'/url).is_file(),url)

    def test_anonymous_metadata_and_project_subpath(self):
        self.assertIn('https://example.github.io/project/assets/social-card.png',self.html)
        self.assertIn('author = {{Anonymous Authors}}',self.html)
        self.assertNotRegex(self.html,r'/home/|Downloads|accepted at|accepted to|44 comparisons|35\.3 ms')
        for tag,attrs in self.doc.elements:
            if tag == 'meta' and attrs.get('name') == 'author':
                self.assertEqual(attrs['content'],'Anonymous Authors')
        self.assertNotIn('fonts.googleapis.com',self.html)
        self.assertIn('name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex"', self.html)
        self.assertIn('name="referrer" content="no-referrer"', self.html)
        self.assertIn('92.5<span>%</span>', self.html)
        self.assertIn('Real-robot success rate', self.html)

    def test_all_evidence_readable_without_javascript(self):
        panels = [a for _,a in self.doc.elements if a.get('id') in ('jetson','desktop','libero')]
        self.assertEqual(len(panels),3)
        self.assertTrue(all('hidden' not in p for p in panels))
        self.assertEqual(sum(a.get('data-family-group') == 'desktop' and 'family-panel' in a.get('class','') for _,a in self.doc.elements),4)
        self.assertIn('prefers-reduced-motion:reduce',(self.output/'assets/styles.css').read_text())
        benchmark_panels = [a for _,a in self.doc.elements if a.get('id') in ('benchmark-n17','benchmark-pi05')]
        self.assertEqual(len(benchmark_panels), 2)
        self.assertTrue(all('hidden' not in panel for panel in benchmark_panels))
        self.assertIn('DuQuant', self.html)
        self.assertIn('HoloQ-VLA', self.html)
        self.assertIn('Median cos ↑', self.html)
        self.assertIn('0.99817', self.html)
        self.assertIn('0.99942', self.html)
        self.assertNotIn('class="sr-cell"', self.html)
        self.assertIn('id="simpler"', self.html)
        self.assertLess(self.html.index('id="libero"'), self.html.index('id="simpler"'))
        self.assertIn('<td><strong>64.2%</strong></td>', self.html)

    def test_real_robot_reel_is_ready_without_publishing_private_media(self):
        data = site.load('real_robot')
        self.assertEqual(len(data['trials']), 4)
        self.assertEqual([trial['platform'] for trial in data['trials']], ['ALOHA', 'SO101', 'SO101', 'SO101'])
        self.assertTrue(all(len(trial['views']) == 1 for trial in data['trials']))
        self.assertIn('id="robot-demos"', self.html)
        self.assertEqual(self.html.count('class="robot-card"'), 0)
        tabs = re.findall(r'data-task-panel="task-([a-z0-9-]+)"', self.html)
        self.assertEqual(tabs, ['so101-blue-on-red', 'so101-banana', 'so101-blocks-cup', 'aloha-banana', 'pi05-so101-blue-on-red'])
        self.assertEqual(self.html.count('class="benchmark-panel robot-compare"'), 2)
        self.assertEqual(self.html.count('class="compare-scene-tabs"'), 5)
        self.assertEqual(self.html.count('<button type="button" data-scene='), 25)
        media = self.output / 'media'
        published = sorted(x.relative_to(media).as_posix() for x in media.rglob('*') if x.is_file()) if media.exists() else []
        clip = re.compile(r'real-robot/[a-z0-9-]+/(scene-[0-9]+/)?[a-z0-9-]+\.mp4')
        self.assertTrue(all(p == 'overview.mp4' or clip.fullmatch(p) for p in published), published)
        # Raw LeRobot recordings (parquet, meta, per-camera episodes) never reach the site.
        self.assertFalse(any(x.suffix in ('.parquet', '.jsonl', '.json') for x in media.rglob('*')) if media.exists() else False)
        self.assertNotIn('FoldQuantVLA_ALOHA', self.html)

    def test_real_robot_media_paths_are_confined(self):
        for value in ('../private.mp4', '/tmp/private.mp4', 'https://example.com/demo.mp4', 'demo.mov'):
            with self.assertRaises(ValueError):
                site.safe_media_path(value, set(site.VIDEO_TYPES))

    def test_build_rejects_source_overwrite(self):
        with self.assertRaises(ValueError):
            site.build(ROOT)


if __name__ == '__main__':
    unittest.main()
