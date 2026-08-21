import collections
import json
import pathlib
import re
import unittest

import refresh_data


class RefreshSafetyTests(unittest.TestCase):
    def test_inline_json_cannot_close_the_script_element(self):
        hostile = [[50.8, 4.3, 'water', 'tap', '</script><script>alert(1)</script>', '', 0]]
        encoded = refresh_data.inline_json(hostile)
        self.assertNotIn('<', encoded)
        self.assertNotIn('>', encoded)
        self.assertEqual(json.loads(encoded), hostile)

    def test_every_translation_source_still_exists(self):
        template = (refresh_data.HERE / 'index_template.html').read_text()
        translations = json.loads((refresh_data.HERE / 'i18n_nl.json').read_text())
        for source, _ in translations['pairs']:
            self.assertIn(source, template)

    def test_previous_counts_reads_the_shared_payload(self):
        payload = (refresh_data.ROOT / 'data' / 'pois.js').read_text()
        points = json.loads(re.search(r'const POIS = (\[.*?\]);\n', payload, re.S).group(1))
        self.assertEqual(refresh_data.previous_counts(), collections.Counter(p[2] for p in points))

    def test_generated_pages_have_no_unfilled_placeholders(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        for page in (root / 'index.html', root / 'nl' / 'index.html'):
            rendered = page.read_text()
            self.assertNotRegex(rendered.replace('__DATA__', ''), r'__[A-Z0-9]+__')
            self.assertIn('integrity="sha384-', rendered)

    def test_generated_pages_exactly_match_template_and_current_data(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        template = (refresh_data.HERE / 'index_template.html').read_text()
        english = (root / 'index.html').read_text()
        payload = (root / 'data' / 'pois.js').read_text()
        translations = json.loads((refresh_data.HERE / 'i18n_nl.json').read_text())
        self.assertEqual(refresh_data.render(template, refresh_data.EN), english)
        self.assertEqual(
            refresh_data.render(template, translations['placeholders'], translations['pairs']),
            (root / 'nl' / 'index.html').read_text(),
        )
        self.assertNotIn('const POIS = [', english)
        self.assertIn('<link rel="preload" href="/data/pois.js" as="script"/>', english)
        self.assertIn('<script src="/data/pois.js"></script>', english)


if __name__ == '__main__':
    unittest.main()
