import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image

import server
from asset_studio import sprite_video_pipeline as video
from asset_studio.local_3d_pipeline import ComfyClient
from tests.helpers.fake_image_provider import FakeImageProvider
from tests.helpers.http_generation_harness import GenerationHttpHarness


def image_url():
    stream = io.BytesIO()
    Image.new('RGBA', (64, 64), '#00FF00').save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()


def request(**kwargs):
    return {'reference_image': image_url(), 'prompt': '  My exact prompt\n[0s-2s] walk SW',
            'model': 'h3_fast', 'duration': 2, 'frame_count': 8, 'fps': 10, 'seed': 123,
            'name': 'walk_SW', **kwargs}


def node_info():
    info = {node: {} for node in video.REQUIRED_NODES}
    for node, field, values in [('UNETLoader', 'unet_name', list(video.MODEL_FILES.values())),
                                ('CLIPLoader', 'clip_name', [video.TEXT_ENCODER]),
                                ('VAELoader', 'vae_name', [video.VIDEO_VAE])]:
        info[node] = {'input': {'required': {field: [values]}}}
    return info


@pytest.mark.parametrize('kwargs', [{'model': 'wan'}, {'duration': float('nan')}, {'frame_count': 57},
                                  {'frame_count': True}, {'fps': 0}, {'prompt': ' '}, {'seed': -1},
                                  {'name': '../escape'}, {'background_color': 'green'}, {'reference_image': 'bad'}])
def test_invalid_request_fails_before_gpu(kwargs):
    with pytest.raises(ValueError):
        video.validate_request(request(**kwargs))


def test_workflow_uses_exact_prompt_and_distinct_models():
    for model, steps in [('h3', 20), ('h3_fast', 8)]:
        settings, _ = video.validate_request(request(model=model))
        graph = video.build_workflow(settings, video.discover_models(node_info())[model], 'input.png', 448, 448, 'abc')
        assert graph['5']['inputs']['prompt'] == request()['prompt']
        assert graph['5']['inputs']['length'] == 56
        assert graph['7']['inputs']['steps'] == steps
        assert graph['1']['inputs']['unet_name'] == video.MODEL_FILES[model]
        assert graph['12']['inputs']['images'] == ['11', 0]
        assert settings['duration'] == 2 and settings['actual_duration'] == 56 / 24
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value, list):
                    assert value[0] in graph


def test_sample_indices_are_exact_distinct_and_include_bounds():
    for count in [8, 25, 56]:
        indices = video.sample_indices(56, count)
        assert len(set(indices)) == count
        assert indices[0] == 0 and indices[-1] == 55
    with pytest.raises(ValueError):
        video.sample_indices(5, 8)


def test_health_reports_missing_model_and_nodes(tmp_path):
    client = ComfyClient(root=tmp_path)
    client.paths.input.mkdir()
    client.paths.output.mkdir()
    with mock.patch.object(client, 'object_info', return_value=node_info()):
        assert video.sprite_video_health(client=client)['available'] is True
    info = node_info()
    del info['MiniMaxH3ImageToVideo']
    with mock.patch.object(client, 'object_info', return_value=info):
        result = video.sprite_video_health(client=client)
        assert result['available'] is False
        assert result['missing_nodes'] == ['MiniMaxH3ImageToVideo']


def test_output_path_rejects_traversal(tmp_path):
    client = ComfyClient(root=tmp_path)
    record = {'outputs': {'12': {'images': [{'type': 'output', 'filename': '../secret.png'}]}}}
    with pytest.raises(RuntimeError, match='경로'):
        client.output_path(record, '12')


def test_complete_job_preserves_frames_metadata_and_alpha(tmp_path):
    client = ComfyClient(root=tmp_path / 'comfy')
    client.paths.input.mkdir(parents=True)
    client.paths.output.mkdir()
    entries = []
    for index in range(56):
        frame = Image.new('RGB', (448, 448), '#00FF00')
        frame.paste((30, 20, 10), (100 + index, 100, 160 + index, 200))
        name = f'{index:03d}.png'
        frame.save(client.paths.output / name)
        entries.append({'type': 'output', 'filename': name, 'subfolder': ''})
    with mock.patch.object(client, 'object_info', return_value=node_info()), mock.patch.object(client, 'run', return_value={'outputs': {'12': {'images': entries}}}):
        result = video.generate_sprite_video(request(), generated_root=tmp_path / 'generated', client=client)
    assert len(result['frames']) == 8
    assert len(result['raw_frames']) == 56
    assert result['seed'] == 123 and result['model'] == 'h3_fast'
    assert result['prompt'] == request()['prompt']
    assert result['actual_duration'] == 56/24
    output = tmp_path / 'generated' / 'sprite-video' / result['run_id']
    assert json.loads((output / 'metadata.json').read_text())['sample_indices'] == result['sample_indices']
    with Image.open(output / 'sheet.png') as sheet:
        assert sheet.size == (1344, 1344)
        assert sheet.getpixel((0, 0))[3] == 0
        assert sheet.getpixel((120, 120)) == (30, 20, 10, 255)
    with Image.open(output / 'preview.gif') as gif:
        assert gif.n_frames == 8
        assert gif.info['duration'] == 100


def test_api_direct_forwards_prompt_without_hidden_contracts(tmp_path):
    provider = FakeImageProvider(tmp_path / 'provider')
    harness = GenerationHttpHarness(provider, tmp_path / 'generated')
    result = harness.post_json('/api/generate', {'prompt_mode': 'direct', 'asset_family': 'object',
                    'asset_type': 'interactable', 'prompt': '  only THIS prompt\n',
                    'style': 'never appended', 'output': {'width': 32, 'height': 48}})
    assert result.status == 200
    assert provider.calls[0]['prompt'] == '  only THIS prompt\n'
    assert result.json()['width'] == 32
    assert result.json()['height'] == 48
    bad = harness.post_json('/api/generate', {'prompt_mode': 'direct', 'asset_family': 'sprite', 'asset_type': 'character', 'prompt': 'walk'})
    assert bad.status == 400
    assert len(provider.calls) == 1


def test_sprite_api_and_health_dispatch(tmp_path):
    harness = GenerationHttpHarness(None, tmp_path)
    with mock.patch.object(server, 'generate_sprite_video', return_value={'success': True, 'frames': ['a']}) as generate:
        assert harness.post_json('/api/sprite-video', request()).status == 200
        assert generate.call_args.args[0]['seed'] == 123
    with mock.patch.object(server, 'sprite_video_health', return_value={'available': True}):
        assert harness.get_json('/api/sprite-video-health').json()['available']


@pytest.mark.parametrize('route', ['pixelize-3d-frame', 'local-3d-action-sheet', 'local-3d-model', 'local-3d-motion'])
def test_retired_routes_not_exposed_or_queued(tmp_path, route):
    assert GenerationHttpHarness(None, tmp_path).post_json('/api/' + route, {}).status == 404
    with pytest.raises(ValueError, match='unsupported'):
        server.create_generation_job('/api/' + route, {}, runner=lambda *a: None)

def test_chroma_despills_edges_without_changing_interior_palette():
    frame = Image.new('RGBA', (40, 40), '#00FF00')
    frame.paste((30, 20, 10, 255), (5, 5, 35, 35))
    frame.putpixel((5, 12), (20, 180, 10, 255))
    frame.putpixel((6, 12), (90, 55, 20, 255))
    frame.putpixel((20, 20), (20, 180, 10, 255))
    result = video.chroma_key(frame, '#00FF00')
    assert result.getpixel((0, 0)) == (0, 0, 0, 0)
    r, g, b, a = result.getpixel((5, 12))
    assert g <= max(r, b) and 0 < a < 255
    assert result.getpixel((6, 12)) == (90, 55, 20, 255)
    assert result.getpixel((10, 10)) == (30, 20, 10, 255)
    assert result.getpixel((20, 20)) == (20, 180, 10, 255)
