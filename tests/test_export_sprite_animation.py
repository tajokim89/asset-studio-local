import importlib.util
from pathlib import Path

import pytest
from PIL import Image


spec = importlib.util.spec_from_file_location('sprite_export', Path(__file__).parents[1] / 'scripts/export_sprite_animation.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def test_real_frames_and_separate_review_timing(tmp_path):
    source = tmp_path / 'raw'
    source.mkdir()
    for i in range(12):
        frame = Image.new('RGBA', (32, 32), (0, 255, 0, 255))
        frame.paste((120, 50, 20, 255), (i, 10, i + 5, 20))
        frame.save(source / f'{i:03}.png')
    out = tmp_path / 'export'
    meta = exporter.export(source, out, count=12, fps=30, green=True)
    assert meta['sample_indices'] == list(range(12))
    assert meta['duration_ms'] == 400
    assert meta['preview_duration_ms'] == 1800
    with Image.open(out / 'animation.gif') as gif:
        assert gif.n_frames == 12
        durations = []
        for i in range(12):
            gif.seek(i)
            durations.append(gif.info['duration'])
            assert gif.convert('RGBA').getpixel((31, 31))[3] == 0
        assert sum(durations) == 400
    with Image.open(out / 'frame_003.png') as frame:
        assert frame.getpixel((3, 10)) == (120, 50, 20, 255)
    assert len(list(source.glob('*.png'))) == 12


def test_export_keeps_green_by_default(tmp_path):
    source = tmp_path / 'raw'
    source.mkdir()
    for i in range(2):
        frame = Image.new('RGBA', (16, 16), '#00FF00')
        frame.putpixel((i, i), (200, 0, 0, 255))
        frame.save(source / f'{i}.png')
    exporter.export(source, tmp_path / 'out')
    with Image.open(tmp_path / 'out/frame_000.png') as image:
        assert image.getpixel((15, 15)) == (0, 255, 0, 255)


@pytest.mark.parametrize('indices', [[0, 0], [3, 1], [-1, 1], [0, 5]])
def test_rejects_fake_or_invalid_frame_selection(indices):
    with pytest.raises(ValueError):
        exporter.select_indices(5, indices=indices)


def test_refuses_overwriting_an_existing_export(tmp_path):
    source = tmp_path / 'raw'
    source.mkdir()
    for i in range(2):
        Image.new('RGBA', (8, 8), (i * 100, 0, 0, 255)).save(source / f'{i}.png')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'keep.txt').write_text('keep')
    with pytest.raises(ValueError, match='empty output'):
        exporter.export(source, out)
    assert (out / 'keep.txt').read_text() == 'keep'
