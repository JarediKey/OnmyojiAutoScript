import cv2
import numpy as np

from numpy import float32, int32, uint8, fromfile
from pathlib import Path

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr


def load_image(file: str):
    file = Path(file)
    img = cv2.imdecode(fromfile(file, dtype=uint8), -1)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    height, width, channels = img.shape
    if height != 720 or width != 1280:
        logger.error(f'Image size is {height}x{width}, not 720x1280')
        return None
    return img


def detect_image(file: str, targe: RuleImage) -> bool:
    img = load_image(file)
    return targe.match(img)

def detect_ocr(file: str, target: RuleOcr):
    img = load_image(file)
    return target.ocr(img)



# 图片文件路径 可以是相对路径
IMAGE_FILE = './log/error/1707301227880/error1707301227880.png'
if __name__ == '__main__':
    from tasks.KekkaiActivation.assets import KekkaiActivationAssets
    targe = KekkaiActivationAssets.I_CARDS_KAIKO_5
    print(detect_image(IMAGE_FILE, targe))
    # from tasks.KekkaiActivation.assets import KekkaiActivationAssets
    # target = KekkaiActivationAssets.O_CARD_ALL_TIME
    # print(detect_ocr(IMAGE_FILE, target))


