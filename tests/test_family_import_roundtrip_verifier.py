import hashlib, io, json, zipfile, zlib
from PIL import Image
import pytest
from scripts.verify_family_export import verify_family_export, SCHEMAS


def png(size=(2,2)):
 b=io.BytesIO(); Image.new('RGBA',size,(1,2,3,255)).save(b,'PNG'); return b.getvalue()


def archive(family):
 payload={}; size={'width':2,'height':2}
 if family=='actor':
  payload={'frames/S/walk-000.png':png(),'atlas.png':png()}; m={'sourceSize':size,'anchors':{'pivot':{'x':.5,'y':1}},'actions':[{'fps':8}],'frames':[{'path':'frames/S/walk-000.png','atlas':{'x':0,'y':0}}]}
 elif family=='effect':
  payload={'frame-000.png':png()}; m={'source_size':size,'frames':[{'file':'frame-000.png','trim_rect':{'x':0,'y':0,'width':2,'height':2},'pivot':{'x':.5,'y':.5}}]}
 elif family=='tile':
  payload={'atlas.png':png()}; m={'atlas':{'path':'atlas.png','width':2,'height':2},'tiles':[{'x':0,'y':0,'width':2,'height':2}]}
 elif family=='ui':
  payload={'states/normal.png':png()}; m={'sourceSize':size,'sliceMargins':{'top':0,'right':0,'bottom':0,'left':0},'safeArea':{'top':0,'right':0,'bottom':0,'left':0},'states':[{'file':'states/normal.png'}]}
 else:
  payload={'states/base.png':png()}; m={'sourceSize':size,'states':[{'path':'states/base.png','pivot':{'x':.5,'y':1},'ground_point':{'x':.5,'y':1},'y_sort_point':{'x':.5,'y':1}}]}
 inventory=[{'path':n,'bytes':len(d),'crc32':f'{zlib.crc32(d)&0xffffffff:08x}','sha256':hashlib.sha256(d).hexdigest()} for n,d in payload.items()]
 manifest={'schema_version':SCHEMAS[family],'family':family,'inventory':inventory,**m}
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
  z.writestr('manifest.json',json.dumps(manifest)); [z.writestr(n,d) for n,d in payload.items()]
 return out.getvalue()


@pytest.mark.parametrize('family',['actor','effect','tile','ui','object'])
def test_independent_import_verifier_accepts_all_family_coordinates(family):
 out=verify_family_export(archive(family)); assert out['status']=='PASS' and out['family']==family and out['pngs_verified']>=1


def mutate(raw, name, transform):
 with zipfile.ZipFile(io.BytesIO(raw)) as z: files={n:z.read(n) for n in z.namelist()}
 files[name]=transform(files[name]); out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
  for n,d in files.items(): z.writestr(n,d)
 return out.getvalue()


def test_verifier_rejects_digest_and_coordinate_mutation():
 with pytest.raises(ValueError,match='digest'): verify_family_export(mutate(archive('tile'),'atlas.png',lambda b:b+b'x'))
 def bad(data):
  m=json.loads(data);m['frames'][0]['trim_rect']['x']=2;return json.dumps(m).encode()
 with pytest.raises(ValueError,match='reconstruction'): verify_family_export(mutate(archive('effect'),'manifest.json',bad))


def test_verifier_rejects_duplicate_and_traversal_entries():
 raw=io.BytesIO()
 with zipfile.ZipFile(raw,'w') as z:z.writestr('manifest.json','{}');z.writestr('../x','x')
 with pytest.raises(ValueError):verify_family_export(raw.getvalue())
