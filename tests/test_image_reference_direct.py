import base64,io,json,hashlib
from unittest.mock import Mock
import pytest
from PIL import Image
import server

@pytest.fixture
def backend(tmp_path,monkeypatch):
    generated=tmp_path/'generated';generated.mkdir()
    output=tmp_path/'output.png';Image.new('RGBA',(72,96),(20,50,80,128)).save(output)
    provider=Mock();provider.generate.return_value={'success':True,'image':str(output),'provider':'codex_oauth'}
    monkeypatch.setattr(server,'load_provider',lambda:provider);monkeypatch.setattr(server,'GENERATED',generated)
    return provider,generated

def request(**extra):
    return dict(asset_family='image',asset_type='image',prompt_mode='direct',prompt='  형태만 바꿔줘\n',**extra)

def reference():
    stream=io.BytesIO();Image.new('RGBA',(80,64),(80,30,10,180)).save(stream,format='PNG')
    raw=stream.getvalue();return 'data:image/png;base64,'+base64.b64encode(raw).decode(),raw

def test_reference_forwards_exact_snapshot_and_preserves_native_result(backend):
    provider,root=backend;ref,raw=reference()
    result=server.generate_direct_asset(request(reference_image=ref,mask_image_url='unused mask'))
    provider.generate.assert_called_once_with('  형태만 바꿔줘\n',aspect_ratio='landscape',image_url=ref)
    assert (result['width'],result['height'])==(72,96)
    saved=root/result['reference_url'].split('/')[-1];assert saved.read_bytes()==raw
    metadata=json.loads((root/(result['url'].split('/')[-1]+'.json')).read_text(encoding='utf-8'))
    assert metadata['reference_sha256']==hashlib.sha256(raw).hexdigest()

def test_text_only_does_not_attach_current_image(backend):
    provider,_=backend
    result=server.generate_direct_asset(request())
    provider.generate.assert_called_once_with('  형태만 바꿔줘\n',aspect_ratio='square')
    assert result['reference_url'] is None

@pytest.mark.parametrize('bad',['https://example.com/image.png','data:image/png;base64,bm90YW5pbWFnZQ==','data:text/plain;base64,YQ==',17])
def test_invalid_reference_never_calls_provider(backend,bad):
    provider,_=backend
    with pytest.raises(ValueError):server.generate_direct_asset(request(reference_image=bad))
    provider.generate.assert_not_called()
