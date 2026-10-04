import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from save_image_jpg import SaveImageJpg


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'folder_paths', SimpleNamespace(
        get_output_directory=lambda: str(tmp_path),
        get_save_image_path=lambda prefix, folder, w, h: (folder, prefix, 1, '', prefix)))
    import comfy.model_management as mm
    monkeypatch.setattr(mm, 'throw_exception_if_processing_interrupted', lambda: None)
    return tmp_path


@pytest.mark.parametrize('channels', [1, 3, 4])
def test_save_preview_batch_and_no_overwrite(output_dir, channels):
    images = torch.ones(2, 12, 16, channels)
    node = SaveImageJpg()
    result = node.save_images(images)
    assert result['result'][0] is images
    assert len(result['ui']['images']) == 2
    for entry in result['ui']['images']:
        assert entry['type'] == 'output'
        with Image.open(output_dir / entry['filename']) as im:
            assert im.format == 'JPEG' and im.size == (16, 12) and im.mode == 'RGB'
    again = node.save_images(images)
    assert again['ui']['images'][0]['filename'] != result['ui']['images'][0]['filename']
    assert len(list(output_dir.glob('*.jpg'))) == 4


def test_alpha_white_and_validation(output_dir):
    result = SaveImageJpg().save_images(torch.zeros(1, 8, 8, 4))
    with Image.open(output_dir / result['ui']['images'][0]['filename']) as im:
        assert im.getpixel((0, 0)) == (255, 255, 255)
    with pytest.raises(ValueError): SaveImageJpg().save_images(torch.zeros(1, 8, 8, 2))
    with pytest.raises(ValueError): SaveImageJpg().save_images(torch.zeros(1, 8, 8, 3), quality=101)
