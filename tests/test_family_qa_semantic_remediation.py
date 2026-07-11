"""I2 second-remediation adversarial semantic and aggregation tests."""
import copy, json
from PIL import Image
import pytest
import server
from test_family_qa_router import requests, valid_envelope


def save(root, ref, size, painter=None):
    p=root/ref; p.parent.mkdir(parents=True,exist_ok=True)
    im=Image.new('RGBA',size,(0,0,0,0))
    if painter: painter(im)
    im.save(p); return p


def test_actor_motion_cells_must_be_nonempty_and_different(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['actor_motion']
    save(tmp_path,q['artifact_refs'][0],(16,4),lambda im: im.paste((1,2,3,255),(0,0,16,4)))
    out=server.route_family_qa(q); assert out['verdict']=='FAIL'
    assert 'actor_motion_frames_identical' in out['reasons']; assert out['metrics']['nonempty_frame_count']==4
    assert out['metrics']['distinct_frame_count']==1


def test_effect_required_cells_nonempty_progression_and_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['effect_sequence']; ref=q['artifact_refs'][0]
    p=save(tmp_path,ref,(16,4),lambda im: im.paste((9,9,9,255),(0,0,4,4)))
    p.with_suffix('.json').write_text(json.dumps({'frame_count':3,'rows':1,'columns':4,'pivot':{'x':.5,'y':.5}}))
    out=server.route_family_qa(q); assert out['verdict']=='FAIL'
    assert out['metrics']['nonempty_frame_count']==1
    assert 'effect_required_cell_empty:1' in out['reasons']
    assert 'metadata_frame_count_mismatch' in out['reasons']


def test_tile_flat_atlas_cannot_pass_topology_and_seams_are_measured(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['tile_topology_repeat']; ref=q['artifact_refs'][0]
    save(tmp_path,ref,(256,256),lambda im: im.paste((7,7,7,255),(0,0,256,256)))
    out=server.route_family_qa(q); assert out['verdict']=='FAIL'
    assert 'tile_topology_unproven' in out['reasons']; assert out['metrics']['nonempty_tile_count']==64
    assert out['metrics']['seam_comparisons']>0 and out['metrics']['rule_coverage']==0


def test_ui_requires_canonical_metadata_for_multi_state_and_rejects_meaningless(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['ui_nine_slice_state']; ref=q['artifact_refs'][0]
    p=save(tmp_path,ref,(96,32),lambda im: im.paste((2,3,4,255),(0,0,96,32)))
    p.with_suffix('.json').write_text('{}')
    out=server.route_family_qa(q); assert out['verdict']=='FAIL'; assert 'ui_metadata_states_mismatch' in out['reasons']
    assert out['metrics']['content_width']==80 and out['metrics']['content_height']==16


def test_object_1x1_multistate_and_points_outside_alpha_fail(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['object_placement_state']; ref=q['artifact_refs'][0]
    save(tmp_path,ref,(1,1),lambda im: im.putpixel((0,0),(1,1,1,255)))
    out=server.route_family_qa(q); assert out['verdict']=='FAIL'; assert 'object_multistate_footprint_too_small' in out['reasons']
    assert out['metrics']['alpha_bounds_width']==1


def test_normalizer_rejects_fabricated_top_level_aggregation():
    v=valid_envelope(); v['reasons']=['fabricated'];
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(v)
    v=valid_envelope(); v['metrics']={'frame_count':999}
    with pytest.raises(ValueError): server.normalize_family_qa_verdict(v)


def test_result_id_covers_request_and_actual_bytes_and_mixed_refs_partial(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'ROOT',tmp_path); q=requests()['actor_motion']; ref=q['artifact_refs'][0]
    p=save(tmp_path,ref,(16,4),lambda im: im.paste((1,1,1,255),(0,0,16,4)))
    a=server.route_family_qa(q); p.write_bytes(p.read_bytes()+b'x'); b=server.route_family_qa(q)
    assert a['result_id']!=b['result_id'] and q['request_id'] in a['result_id']
    mixed=copy.deepcopy(q); mixed['artifact_refs'].append('https://example.invalid/a.png')
    out=server.route_family_qa(mixed); assert out['deterministic']['status']=='UNAVAILABLE'; assert out['verdict']=='PARTIAL'
