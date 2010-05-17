
import os.path
import unittest
from PIL import Image
from fixcity import exif_utils

HERE = os.path.abspath(os.path.dirname(__file__))

class TestExifUtils(unittest.TestCase):

    def _make_image(self, filename):
        path = os.path.join(HERE, 'files', filename)
        return Image.open(path)
    
    def test_exif_info__no_info(self):
        img = self._make_image('test_no_exif.jpg')
        info = exif_utils.get_exif_info(img)
        self.assertEqual(info, {})

    def test_exif_info(self):
        img = self._make_image('test_exif.jpg')
        info = exif_utils.get_exif_info(img)
        self.assertEqual(info['Make'], 'Apple')
        self.assertEqual(info['DateTime'], '2009:11:07 10:49:33')
        self.assertEqual(info['Orientation'], 6)

    def test_rotate_image_by_exif__no_info(self):
        img = self._make_image('test_no_exif.jpg')
        self.assertEqual(img, exif_utils.rotate_image_by_exif(img))

    def test_rotate_image_by_exif(self):
        img = self._make_image('test_exif.jpg')
        rotated = exif_utils.rotate_image_by_exif(img)
        self.failIfEqual(img, rotated)
        # Unfortunately PIL doesn't save exif info on new images...
        self.assertEqual(exif_utils.get_exif_info(rotated), {})
        
    
