"""Local image-to-video sprite jobs using ComfyUI's public core node API.

No Sprite Sheep runtime or code is required. Model weights remain in ComfyUI.
"""
from __future__ import annotations

import json
import math
import re
import secrets
import uuid
from pathlib import Path

from PIL import Image, ImageOps, ImageFilter
import numpy as np

from asset_studio.local_3d_pipeline import ComfyClient, _decode_image_data_url

MODEL_FILES = {
    'h3': 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors',
    'h3_fast': 'fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors',
}
TEXT_ENCODER = 'qwen3vl_32b_minimax_h3_int4_convrot.safetensors'
VIDEO_VAE = 'minimax_h3_video_vae_fp16.safetensors'
REQUIRED_NODES = {'UNETLoader', 'CLIPLoader', 'VAELoader', 'LoadImage',
                  'MiniMaxH3ImageToVideo', 'KSamplerSelect', 'BasicScheduler',
                  'BasicGuider', 'RandomNoise', 'SamplerCustomAdvanced', 'VAEDecode', 'SaveImage'}


def _number(data, key, default, low, high, *, integer=False):
    value = data.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f'{key} must be a number')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{key} must be a number') from None
    if not math.isfinite(number) or not low <= number <= high or (integer and number != int(number)):
        raise ValueError(f'{key} must be between {low} and {high}')
    return int(number) if integer else number


def validate_request(data):
    if not isinstance(data, dict):
        raise ValueError('sprite video payload must be an object')
    prompt = data.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
        raise ValueError('prompt must contain 1–20000 characters')
    model = data.get('model', 'h3_fast')
    if model not in MODEL_FILES:
        raise ValueError('model must be h3 or h3_fast')
    color = data.get('background_color', '#00FF00')
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('background_color must be #RRGGBB')
    duration = _number(data, 'duration', 2, 1, 6)
    length = 5 + 17 * math.ceil((math.ceil(duration * 24) - 5) / 17)
    count = _number(data, 'frame_count', 25, 2, 64, integer=True)
    if count > length:
        raise ValueError('frame_count exceeds the generated clip frame count')
    seed = data.get('seed', secrets.randbelow(2**53))
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**53:
        raise ValueError('seed must be an integer from 0 to 2^53-1')
    name = data.get('name', 'animation')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise ValueError('name must contain 1–64 letters, digits, underscores or hyphens')
    image = _decode_image_data_url(data.get('reference_image'), 'reference_image')
    return dict(prompt=prompt, model=model, duration=duration, clip_frame_count=length,
                actual_duration=length / 24, frame_count=count,
                fps=_number(data, 'fps', 12, 1, 60), seed=seed, name=name,
                background_color=color.upper()), image


def _listed(info, node, field):
    value = info.get(node, {}).get('input', {}).get('required', {}).get(field, [[]])[0]
    return value if isinstance(value, list) else []


def discover_models(info):
    def find(node, field, preferred):
        return next((name for name in _listed(info, node, field)
                     if str(name).replace('\\', '/').rsplit('/', 1)[-1] == preferred), None)
    encoder = find('CLIPLoader', 'clip_name', TEXT_ENCODER)
    vae = find('VAELoader', 'vae_name', VIDEO_VAE)
    return {key: {'diffusion': find('UNETLoader', 'unet_name', filename),
                  'text_encoder': encoder, 'vae': vae}
            for key, filename in MODEL_FILES.items()}


def sprite_video_health(*, client=None):
    client = client or ComfyClient(timeout_seconds=1800)
    try:
        info = client.object_info()
        missing = sorted(REQUIRED_NODES - info.keys())
        paths_ready = client.paths.input.is_dir() and client.paths.output.is_dir()
        models = [{ 'id': key, 'label': 'H3 Fast' if key == 'h3_fast' else 'H3',
                    'available': not missing and paths_ready and all(files.values()),
                    'files': files} for key, files in discover_models(info).items()]
        return {'available': any(m['available'] for m in models), 'models': models,
                'missing_nodes': missing, 'paths_ready': paths_ready, 'url': client.url,
                'provider': 'local-comfyui', 'generation_fps': 24}
    except Exception as exc:
        return {'available': False, 'models': [], 'missing_nodes': [],
                'provider': 'local-comfyui', 'error': str(exc)}


def build_workflow(settings, models, input_name, width, height, run_id):
    def node(kind, **inputs):
        return {'class_type': kind, 'inputs': inputs}
    return {
        '1': node('UNETLoader', unet_name=models['diffusion'], weight_dtype='default'),
        '2': node('CLIPLoader', clip_name=models['text_encoder'], type='minimax', device='default'),
        '3': node('VAELoader', vae_name=models['vae']),
        '4': node('LoadImage', image=input_name),
        '5': node('MiniMaxH3ImageToVideo', clip=['2', 0], vae=['3', 0], first_frame=['4', 0],
                  prompt=settings['prompt'], width=width, height=height, length=settings['clip_frame_count']),
        '6': node('KSamplerSelect', sampler_name='res_multistep'),
        '7': node('BasicScheduler', model=['1', 0], scheduler='simple',
                  steps=8 if settings['model'] == 'h3_fast' else 20, denoise=1.0),
        '8': node('BasicGuider', model=['1', 0], conditioning=['5', 0]),
        '9': node('RandomNoise', noise_seed=settings['seed']),
        '10': node('SamplerCustomAdvanced', noise=['9', 0], guider=['8', 0],
                   sampler=['6', 0], sigmas=['7', 0], latent_image=['5', 1]),
        '11': node('VAEDecode', samples=['10', 0], vae=['3', 0]),
        '12': node('SaveImage', images=['11', 0], filename_prefix=f'asset_studio/{run_id}/frame'),
    }


def sample_indices(total, count):
    if not 2 <= count <= total:
        raise ValueError('Cannot extract the requested number of distinct frames')
    return [round(i * (total - 1) / (count - 1)) for i in range(count)]


def chroma_key(image, color, tolerance=40):
    """Remove the matte and unmix primary-key spill only near transparent edges.

    Interior colors are untouched. Retaining a shared canvas avoids frame jitter.
    """
    rgba = np.array(image.convert('RGBA'))
    key = np.array(tuple(bytes.fromhex(color[1:])), dtype=np.float32)
    rgb = rgba[:, :, :3].astype(np.float32)
    distance = np.max(np.abs(rgb - key), axis=2)
    clear = (distance <= tolerance) | (rgba[:, :, 3] == 0)
    rgba[clear, 3] = 0
    dominant = int(np.argmax(key))
    others = [channel for channel in range(3) if channel != dominant]
    key_excess = float(key[dominant] - max(key[others]))
    if key_excess >= 128:
        # A narrow band, not a global hue replacement: keep green clothing intact.
        edge = np.array(Image.fromarray(clear.astype('uint8') * 255).filter(ImageFilter.MaxFilter(11))) > 0
        neutral = np.max(rgb[:, :, others], axis=2)
        excess = rgb[:, :, dominant] - neutral
        spill = edge & ~clear & (excess > 8)
        matte = np.clip(excess / key_excess, 0, 1)
        alpha = np.maximum(1 - matte, 0.001)
        recovered = np.clip((rgb - matte[:, :, None] * key) / alpha[:, :, None], 0, 255)
        rgba[spill, :3] = np.rint(recovered[spill]).astype('uint8')
        rgba[spill, 3] = np.rint(rgba[spill, 3] * alpha[spill]).astype('uint8')
        rgba[spill & (alpha < 0.1), 3] = 0
    rgba[rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(rgba)


def _save_gif(frames, path, fps):
    # Reserve palette index 255 for transparency on every frame.
    paletted = []
    for frame in frames:
        image = frame.convert('RGB').quantize(colors=255, dither=Image.Dither.NONE)
        image.paste(255, mask=frame.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        image.info['transparency'] = 255
        paletted.append(image)
    paletted[0].save(path, save_all=True, append_images=paletted[1:], loop=0,
                     duration=max(20, round(100 / fps) * 10), disposal=2, transparency=255, optimize=False)


def generate_sprite_video(data, *, generated_root, client=None):
    settings, source = validate_request(data)
    client = client or ComfyClient(timeout_seconds=1800)
    info = client.object_info()
    missing = sorted(REQUIRED_NODES - info.keys())
    models = discover_models(info)[settings['model']]
    if missing or not all(models.values()):
        raise ValueError(f'H3 nodes or weights are missing: {missing or models}')
    if not client.paths.input.is_dir() or not client.paths.output.is_dir():
        raise ValueError('ComfyUI input/output folders are unavailable')
    run_id = uuid.uuid4().hex
    output = Path(generated_root) / 'sprite-video' / run_id
    output.mkdir(parents=True, exist_ok=False)
    source.save(output / 'source.png')
    # Fit the entire reference without cropping; one shared canvas for every frame.
    ratio = source.width / source.height
    width = 448 if ratio >= 1 else max(128, round(448 * ratio / 32) * 32)
    height = 448 if ratio <= 1 else max(128, round(448 / ratio / 32) * 32)
    prepared = Image.new('RGBA', (width, height), settings['background_color'])
    fitted = ImageOps.contain(source, (width, height), Image.Resampling.NEAREST)
    prepared.alpha_composite(fitted, ((width-fitted.width)//2, (height-fitted.height)//2))
    input_name = f'asset_studio_{run_id}.png'
    prepared.convert('RGB').save(client.paths.input / input_name)
    workflow = build_workflow(settings, models, input_name, width, height, run_id)
    (output / 'request.json').write_text(json.dumps({**settings, 'models': models}, indent=2), encoding='utf-8')
    (output / 'workflow.json').write_text(json.dumps(workflow, indent=2), encoding='utf-8')
    record = client.run(workflow)
    entries = record.get('outputs', {}).get('12', {}).get('images', [])
    if len(entries) != settings['clip_frame_count']:
        raise RuntimeError(f'Expected {settings["clip_frame_count"]} decoded frames, received {len(entries)}')
    indices = sample_indices(len(entries), settings['frame_count'])
    frames = []
    raw_urls = []
    base = f'/assets/generated/sprite-video/{run_id}'
    (output / 'raw').mkdir()
    for index, entry in enumerate(entries):
        path = client.output_path({'outputs': {'12': {'images': [entry]}}}, '12')
        with Image.open(path) as opened:
            frame = opened.convert('RGBA')
        if frame.size != (width, height):
            raise RuntimeError('ComfyUI returned inconsistent frame dimensions')
        frame.save(output / 'raw' / f'{index:03d}.png')
        raw_urls.append(f'{base}/raw/{index:03d}.png')
        if index in indices:
            frames.append(chroma_key(frame, settings['background_color']))
    columns = math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames)/columns)
    sheet = Image.new('RGBA', (columns*width, rows*height))
    urls = []
    for index, frame in enumerate(frames):
        filename = f'frame_{index:03d}.png'
        frame.save(output / filename)
        urls.append(f'{base}/{filename}')
        sheet.paste(frame, ((index % columns)*width, (index//columns)*height))
    sheet.save(output / 'sheet.png')
    _save_gif(frames, output / 'preview.gif', settings['fps'])
    metadata = {**settings, 'success': True, 'provider': 'local-comfyui', 'models': models,
                'url': f'{base}/sheet.png', 'gif_url': f'{base}/preview.gif',
                'metadata_url': f'{base}/metadata.json', 'source_url': f'{base}/source.png',
                'frames': urls, 'raw_frames': raw_urls, 'sample_indices': indices,
                'columns': columns, 'rows': rows, 'cell_width': width, 'cell_height': height,
                'generation_fps': 24, 'run_id': run_id}
    (output / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata
