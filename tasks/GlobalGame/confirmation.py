"""Shared plain confirmation buttons for explicitly expected task dialogs."""

from module.atom.image import RuleImage
from tasks.GlobalGame.assets import GlobalGameAssets


class DialogConfirmation(RuleImage):
    """Match complete button variants while keeping one click cooldown identity."""

    def __init__(self):
        sources = (
            GlobalGameAssets.I_UI_CONFIRM,
            GlobalGameAssets.I_UI_CONFIRM_SAMLL,
            GlobalGameAssets.I_UI_CONFIRM_SMALL,
            GlobalGameAssets.I_UI_CONFIRM_PLAIN,
            GlobalGameAssets.I_UI_CONFIRM_BLUE,
            GlobalGameAssets.I_UI_CONFIRM_WIDE,
        )
        super().__init__(sources[0].roi_front, (350, 300, 600, 400),
                         'Template matching', 0.8, sources[0].file)
        self.name = 'UI_CONFIRM_DIALOG'
        self.variants = tuple(
            RuleImage(source.roi_front, self.roi_back, source.method,
                      source.threshold, source.file)
            for source in sources
        )

    def match(self, image, threshold=None):
        self.last_score = -1.0
        for rule in self.variants:
            matched = rule.match(image, threshold=threshold)
            self.last_score = max(self.last_score, rule.last_score)
            if matched:
                self.roi_front = list(rule.roi_front)
                return True
        return False
