#!/usr/bin/python
# app/services/solvers/recaptcha.py


"""
@author: Maxime Dréan.

Github: https://github.com/maximedrn
Telegram: https://t.me/maximedrn

Copyright © 2022 Maxime Dréan. All rights reserved.
Any distribution, modification or commercial use is strictly prohibited.
"""


# Selenium module imports: pip install selenium
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait as WDW
from selenium.webdriver.common.by import By

# Pyclick module import: pip install pyclick
from pyclick import HumanCurve

# Torch module import: pip install torch
from torch.hub import load

# Real ESRGAN internal module.
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

# Python internal imports.
from ...utils.colors import GREEN, RESET

# Python default imports.
from random import randint, uniform, shuffle
from cv2 import imdecode, IMREAD_COLOR
from os.path import abspath, exists
from shutil import copyfileobj
from itertools import product
from tqdm.auto import tqdm
from numpy import asarray
from requests import get
from json import loads
from time import sleep
from math import ceil


class OCR:
    """
    OCR class: divide reCAPTCHA image and return blocks to select.

    Image recognition using Yolov5 object detection architectures and models
    pretrained on the COCO dataset.
    """

    def __init__(self) -> None:
        """Contains urls and paths of the pre-trained models."""
        self.repository_url = 'https://github.com/maximedrn/' + \
            'opensea-automatic-bulk-upload-and-sale/releases/download/'
        self.model_urls = ['RealESRGAN/RealESRGAN_x4plus.pth',
                           'Yolov5x6/yolov5x6.pt']
        self.model_path = ['realesrgan/RealESRGAN_x4plus.pth',
                           'yolov5/yolov5x6.pt']
        self.models = ['RealESRGAN', 'Yolov5x6']

    def load_models(self) -> None:
        """Load Real-ESRGAN, Yolov5's basic and custom models."""
        self.download_models()
        self.upsampler = RealESRGANer(scale=3, model=RRDBNet(
            scale=4, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23,
            num_grow_ch=32), model_path=abspath(self.model_path[0]))
        self.yolo = load(abspath('yolov5'), 'custom', path=abspath(
            self.model_path[1]), source='local')
        self.specific_classes = []

    def download_models(self) -> None:
        """Download and save models."""
        for url, path, model in zip(
                self.model_urls, self.model_path, self.models):
            if not exists(abspath(path)):
                print(f'Downloading {model} pre-trained file.')
                with get(self.repository_url + url, stream=True) as request:
                    with tqdm.wrapattr(request.raw, 'read', desc='', total=int(
                            request.headers.get('Content-Length'))) as raw:
                        with open(abspath(path), 'wb') as output:
                            copyfileobj(raw, output)
                print(f'{GREEN}Done.{RESET} Saved in {path}')

    def set_class(self) -> str:
        """Return the class name compatible with Yolov5 model."""
        self._class = [key for key, value in loads(open(
            'assets/classes.json', encoding='utf-8').read()).items() if
            web.visible('(//div[contains(@class, "imageselect-desc")])'
                        '[last()]/strong').text in value]
        self._class = self._class[0] if len(self._class) > 0 else ''
        return self._class

    def image_from_url(self, url: str) -> list:
        """Get the image array from its URL."""
        image = imdecode(asarray(bytearray(get(  # Get the image from URL.
            url, stream=True).raw.read()), dtype='uint8'), IMREAD_COLOR)
        try:  # Try to enhance the image using Real ESRGAN.
            return self.upsampler.enhance(image)[0]
        except Exception:  # Something went wrong.
            return image  # Return the default reCAPTCHA image.

    def divide_blocks(self, blocks: int = 3) -> list:
        """Divide an image into blocks with same shape."""
        image = self.image_from_url(web.visible(
            '(//img[contains(@class, "rc-image-tile-33")])[position()=1]'
        ).get_attribute('src'))
        width, height, _ = image.shape  # Dimensions of the image.
        step_row, step_column = ceil(width / blocks), ceil(height / blocks)
        return [image[row:row+step_row, column:column+step_column, :] for row
                in range(0, width, step_column) for column in range(
                    0, height, step_row)]

    def find_object(self, image_list: list, blocks: int = 3) -> list or dict:
        """Find objects using the Yolov5 model and return a list of them."""
        if blocks == 3 and len(self._class) > 0:
            if self._class not in self.specific_classes:
                return [list(loads(self.yolo(image).pandas().xyxy[
                    0].to_json())['name'].values()) for image in image_list]
            return [list(loads(eval(f'self.{self._class.lower()}')(
                image).pandas().xyxy[0].to_json())['name'].values(
            )) for image in image_list]
        elif blocks == 4 and len(self._class) > 0:
            if self._class not in self.specific_classes:
                return self.yolo(image_list).pandas().xyxy[
                    0].to_dict(orient="records")
            return eval(f'self.{self._class.lower()}')(image_list).pandas(
            ).xyxy[0].to_dict(orient="records")
        return []

    def check_blocks(self, result_list: list, _class: str) -> list:
        """Return blocks that have to be clicked by the bot."""
        return [_class in result for result in result_list]

    def object_coordinates(self, chunk_number: int = 4) -> list:
        """Return the chunks that have to be clicked according coordinates."""
        image, _result = self.image_from_url(web.visible(
            '(//img[contains(@class, "rc-image-tile")])[position()=1]'
        ).get_attribute('src')), []
        results = self.find_object(image, 4)
        for coordinates in [[
                result['xmin'] + 25, result['ymin'] + 25, result['xmax']
                - 25, result['ymax'] - 25] for result in results if result[
                    'name'] == self._class]:
            coordinate = [ceil(coordinate / image.shape[0] * chunk_number)
                          for coordinate in coordinates]
            [_result.append(coord) for coord in list(product(
                list(range(coordinate[0], coordinate[2] + 1)),
                list(range(coordinate[1], coordinate[3] + 1))))]
        return [number + 1 in [{(
            1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4, (2, 1): 5, (2, 2): 6,
            (2, 3): 7, (2, 4): 8, (3, 1): 9, (3, 2): 10, (3, 3): 11, (3, 4):
                12, (4, 1): 13, (4, 2): 14, (4, 3): 15, (4, 4): 16}[(
                    y if y != 0 else 1, x if x != 0 else 1)] for x, y in list(
                        set(_result))] for number in range(chunk_number ** 2)]


class Actions:
    """Simulate human movement, random waiting time and select buttons."""

    def sleep(self, min: float = 0.5, max: float = 2.0) -> None:
        """Wait between 1 and 5 seconds."""
        time = uniform(min, max)  # From 1 to 5 seconds.
        web.driver.implicitly_wait(time)  # Selenium webdriver.
        sleep(time)  # Python bot.

    def human_click(self, end, target: int = 25) -> None:
        """Use Bezier curve to simulate human like mouse movements."""
        try:
            start_x, start_y, self.start = (randint(30, 60), randint(30, 60)) \
                if self.start is None else (self.start.location['x'],
                                            self.start.location['y']), end
            for curve_x, curve_y in HumanCurve((start_x, start_y), (
                end.location['x'], end.location['y']), upBoundary=0,
                    downBoundary=0, targetPoints=target).points:
                action = webdriver.ActionChains(web.driver).move_by_offset(
                    curve_x - start_x, curve_y - start_y)
                start_x, start_y = curve_x, curve_y
            action.perform()
        except Exception:  # MoveTargetOutOfBoundsException
            pass  # "Move target out of bounds".
        self.sleep()  # Wait before clicking on the button.
        end.click()  # Finally click on the element.

    def reload(self) -> None:
        """Reload the reCAPTCHA challenge."""
        actions.sleep()  # Wait before clicking.
        token = web.driver.find_element(
            By.XPATH, '//*[@id="recaptcha-token"]').get_attribute('value')
        self.human_click(web.visible('//*[@id="recaptcha-reload-button"]'))
        WDW(web.driver, 5).until(lambda _: token != web.driver.find_element(
            By.XPATH, '//*[@id="recaptcha-token"]').get_attribute('value'))

    def confirm(self) -> None:
        """Verify or skip the reCAPTCHA challenge."""
        actions.sleep()  # Wait before clicking.
        self.human_click(web.visible(
            '(//div[@class="primary-controls"])[position()=1]/div[2]/button'))


class Solver:
    """Solver class: contains every method to complete the reCAPTCHA."""

    def open_challenge(self) -> None:
        """Click on the reCAPTCHA checkbox to open the challenge frame."""
        web.driver.switch_to.frame(web.visible('//iframe[@title="reCAPTCHA"]'))
        actions.human_click(web.visible('//*[@id="recaptcha-anchor"]'))
        web.driver.switch_to.default_content()
        web.driver.switch_to.frame(web.visible(
            '//iframe[contains(@title, "recaptcha challenge")]'))

    def challenge_opened(self) -> bool:
        """Check if the challenge frame is displayed."""
        web.driver.switch_to.default_content()
        if 'visible' in web.visible(
                '(//div[contains(@class, "captcha-bubble")])'
                '[position()=1]/..').get_attribute('style'):
            web.driver.switch_to.frame(web.visible(
                '//iframe[contains(@title, "recaptcha challenge")]'))
            return True
        return False

    def check_error(self) -> None:
        """Check if one the error div of the reCAPTCHA is displayed."""
        for child in web.visible('(//div[@aria-live="polite"])[position'
                                 '()=1]').find_elements(By.XPATH, './/*'):
            if 'none' not in child.get_attribute('style'):
                actions.reload()  # An error is displayed.
                break

    def select_blocks(self) -> bool:
        """Select blocks and return False if no block has to be clicked."""
        self.blocks = int(web.visible('//*[@id="rc-imageselect-target"]/table')
                          .get_attribute('class').split('-')[3][0])
        clicked, element = [], '(//td[contains(@class, "imageselect-tile")])'
        _class, _range = ocr.set_class(), list(range(self.blocks ** 2))
        result = ocr.check_blocks(ocr.find_object(ocr.divide_blocks(
        )), _class) if self.blocks == 3 else ocr.object_coordinates()
        shuffle(_range)  # Shuffle the range.
        for block in _range:  # 9 or 16 loops.
            if result[block]:  # Result is True, element has to be clicked.
                element_ = web.visible(element + f'[position()={block + 1}]')
                actions.human_click(element_)  # Click the element.
                clicked.append(element + f'[position()={block + 1}]')
        if len(clicked) == 0:
            return False  # Class is not detectable by Yolov5.
        while len(clicked) > 0 and self.blocks == 3:
            for _ in range(len(clicked)):  # Check new images.
                _element, _class = clicked.pop(0), ocr.set_class()
                web.visible(_element + '[not(contains(@class, "dynamic"))]')
                if '11' not in web.visible(  # Check if image class has 11.
                        _element + '/div/div/img').get_attribute('class'):
                    continue  # Challenge do not change blocks.
                elif ocr.check_blocks(ocr.find_object([ocr.image_from_url(
                        web.visible(_element + '/div/div/img').
                        get_attribute('src'))]), _class)[0]:
                    actions.human_click(web.visible(_element))
                    clicked.append(_element)
        return True  # Yolov5 successed.

    def solve(self, web: object) -> bool:
        """Call methods to solve the reCAPTCHA."""
        _, _, failed = get_webdriver(web), self.open_challenge(), 0
        while True:
            try:  # Check if the reCAPTCHA is solved.
                if not self.challenge_opened():
                    break  # reCAPTCHA solved.
                actions.start = None  # Reset the last click position.
                actions.sleep()  # Wait a few seconds.
                self.select_blocks()  # Check blocks and new blocks.
                if ocr._class != '':  # Class is defined.
                    actions.confirm()  # Confirm or skip the challenge.
                    self.check_error()  # If errors: reload, else confirm.
                else:  # Class is not defined: reload the challenge.
                    actions.reload()  # Reload challenge.
            except Exception:  # Something went wrong.
                if failed < 2:  # -2 fails during the challenge.
                    try:  # Check if the challenge is opened.
                        if self.challenge_opened():
                            failed += 1
                            continue  # Retry to solve it.
                        break  # It's not opened: solved.
                    except Exception:
                        break  # The reCAPTCHA disapears: solved.
                return False
        return True


def solver() -> object:
    """Init the classes and load the models."""
    global ocr, actions, recaptcha
    ocr, actions, recaptcha = OCR(), Actions(), Solver()
    ocr.load_models()
    return recaptcha


def get_webdriver(_web: object) -> None:
    """Send the instance of the webdriver."""
    global web
    web = _web
