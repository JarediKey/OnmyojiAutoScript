"""Replay independent incident crops against the configured story nameplate."""

import ast
import json
from pathlib import Path
import unittest

import cv2


ROOT = Path(__file__).resolve().parents[1]


class WantedStoryAssetsTests(unittest.TestCase):
    def test_shantu_template_matches_both_independent_incidents_not_courtyard(self):
        rules = json.loads((ROOT / 'tasks/WantedQuests/story/image.json').read_text(encoding='utf-8'))
        rule = next(item for item in rules if item['itemName'] == 'secret_story_shantu')
        template = cv2.imread(str(ROOT / 'tasks/WantedQuests/story' / rule['imageName']))
        for name, expected in [('shantu_second', True), ('shantu_third', True), ('courtyard', False)]:
            with self.subTest(name=name):
                image = cv2.imread(str(ROOT / 'tests/fixtures/wanted_story' / (name + '.png')))
                self.assertEqual((image.shape[1], image.shape[0]), (196, 72))
                score = cv2.minMaxLoc(cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED))[1]
                self.assertEqual(score > rule['threshold'], expected, f'{name}: {score:.4f}')

    def test_generated_nameplate_rule_matches_source_json(self):
        rules = json.loads((ROOT / 'tasks/WantedQuests/story/image.json').read_text(encoding='utf-8'))
        tree = ast.parse((ROOT / 'tasks/WantedQuests/assets.py').read_text(encoding='utf-8'))
        assignments = {node.targets[0].id: node.value for node in ast.walk(tree)
                       if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
        for rule in rules:
            with self.subTest(name=rule['itemName']):
                call = assignments['I_' + rule['itemName'].upper()]
                values = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
                self.assertEqual(values['roi_front'], tuple(map(int, rule['roiFront'].split(','))))
                self.assertEqual(values['roi_back'], tuple(map(int, rule['roiBack'].split(','))))
                self.assertEqual(values['threshold'], rule['threshold'])
                self.assertTrue(values['file'].endswith('/' + rule['imageName']))


if __name__ == '__main__':
    unittest.main()
