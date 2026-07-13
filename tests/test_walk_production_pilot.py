from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

import server

from asset_studio.output_profiles import action_recipe_for_profile, load_output_profile_by_id
from tests.helpers.fake_image_provider import FakeImageProvider, deterministic_png
from tests.helpers.http_generation_harness import GenerationHttpHarness
from tests.helpers.js_runtime_harness import JavaScriptRuntimeHarness


ROOT = Path(__file__).resolve().parents[1]
JS_HARNESS = JavaScriptRuntimeHarness(ROOT / "src" / "main.js")


def data_url(raw: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


class WalkProductionPilotTests(unittest.TestCase):
    def make_harness(self, root: Path):
        provider = FakeImageProvider(root / "provider")
        return provider, GenerationHttpHarness(provider, root / "generated")

    def test_profile_and_blueprint_endpoint_use_canonical_walk_contract(self):
        profile = load_output_profile_by_id("generic-pixel-actor-v1")
        walk = action_recipe_for_profile(profile, "walk")
        self.assertEqual(walk["id"], "walk")
        self.assertEqual(walk["frame_count"], 4)
        self.assertEqual(walk["beats"], ["N", "L", "N", "R"])
        self.assertNotRegex(walk["id"], r"\d$")

        with tempfile.TemporaryDirectory() as directory:
            _provider, harness = self.make_harness(Path(directory))
            response = harness.get_json("/api/actor-walk-blueprints")
            self.assertEqual(response.status, 200)
            payload = response.json()
            self.assertEqual(payload["action"], "walk")
            self.assertEqual(payload["beats"], ["N", "L", "N", "R"])
            self.assertEqual(payload["generated_frame_indices"], [1, 3])
            self.assertEqual([item["frame_index"] for item in payload["blueprints"]], [1, 3])

    def test_numeric_walk_suffixes_are_not_normalized_or_accepted_at_request_boundary(self):
        profile = load_output_profile_by_id("generic-pixel-actor-v1")
        self.assertEqual(server.normalize_animation_action("walk"), "walk")
        self.assertEqual(server.normalize_animation_action("attack"), "attack")
        for legacy in ("walk4", "walk6"):
            with self.subTest(legacy=legacy):
                self.assertEqual(server.normalize_animation_action(legacy), legacy)
                with self.assertRaisesRegex(ValueError, "Unknown actor action"):
                    server.resolve_actor_action_recipe(profile, legacy)
                payload = {
                    "asset_family": "sprite", "asset_type": "character",
                    "sprite": {
                        "output_profile_id": "generic-pixel-actor-v1",
                        "animation_mode": legacy, "direction_mode": "single",
                        "target_direction": "S", "reference_direction": "AUTO",
                    },
                }
                with self.assertRaisesRegex(ValueError, "Unknown actor action"):
                    server.normalize_asset_generation_payload(payload)

    def test_actor_codex_responses_payload_contains_every_ordered_visual_reference(self):
        master = data_url(deterministic_png("master"))
        pose = data_url(deterministic_png("pose"))
        detail = data_url(deterministic_png("detail"))
        continuity = data_url(deterministic_png("continuity"))
        payload = server.build_codex_actor_frame_responses_payload(
            "one actor frame", [master, pose, detail, continuity],
            ["direction_master", "pose_guide", "identity_detail", "continuity_reference"],
            provider_module=type("ProviderModule", (), {
                "_CODEX_CHAT_MODEL": "codex-chat", "API_MODEL": "gpt-image",
                "_SIZES": {"square": "1024x1024"},
            }), quality="high",
        )
        content = payload["input"][0]["content"]
        images = [item for item in content if item["type"] == "input_image"]
        labels = [item["text"] for item in content if item["type"] == "input_text" and item["text"].startswith("Reference role:")]
        self.assertEqual([item["image_url"] for item in images], [server.data_url_to_png_data_url(value) for value in (master, pose, detail, continuity)])
        self.assertEqual(labels, [
            "Reference role: direction_master", "Reference role: pose_guide",
            "Reference role: identity_detail", "Reference role: continuity_reference",
        ])
        self.assertEqual(payload["tool_choice"]["mode"], "required")

    def test_codex_plugin_capability_health_never_invents_image_reference_support(self):
        provider = type("OpenAICodexImageGenProvider", (), {
            "name": "openai-codex", "display_name": "Codex",
            "default_model": lambda self: "model", "is_available": lambda self: True,
        })()
        self.assertEqual(server.provider_capabilities(provider), {})

    def test_f2_f4_approval_is_server_bound_and_client_pass_cannot_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider, harness = self.make_harness(root)
            source = deterministic_png("uploaded-transparent-pixel-character")
            blueprints = harness.get_json("/api/actor-walk-blueprints").json()["blueprints"]
            source_digest = hashlib.sha256(source).hexdigest()
            frames = {"0": {"image": data_url(source), "artifact_digest": source_digest}}
            run_id = None
            for blueprint in blueprints:
                request = {
                    "prompt": "preserve uploaded pixel actor",
                    "direction": "S",
                    "action": "walk",
                    "frame_index": blueprint["frame_index"],
                    "direction_master": data_url(source),
                    "pose_blueprint": blueprint,
                    "background_mode": "chroma_green",
                    "output_profile_id": "generic-pixel-actor-v1",
                }
                if run_id is not None:
                    request["run_id"] = run_id
                response = harness.post_json("/api/generate-actor-frame", request)
                self.assertEqual(response.status, 200)
                result = response.json()
                run_id = run_id or result["run_id"]
                self.assertEqual(result["run_id"], run_id)
                self.assertEqual(result["source_digest"], source_digest)
                frames[str(blueprint["frame_index"])] = {
                    "image": data_url(Path(result["path"]).read_bytes()),
                    "artifact_digest": result["artifact_digest"],
                    "visual_qa": "PASS",
                }

            blocked = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_id, "source_digest": source_digest, "frames": frames,
            })
            self.assertEqual(blocked.status, 400)
            self.assertIn("server-bound visual approval", blocked.json()["error"])

            approvals = {}
            for index, beat in ((1, "L"), (3, "R")):
                approved = harness.post_json("/api/approve-actor-walk-frame", {
                    "run_id": run_id, "source_digest": source_digest,
                    "artifact_digest": frames[str(index)]["artifact_digest"],
                    "frame_index": index,
                    "beat": beat,
                    "decision": "APPROVED",
                })
                self.assertEqual(approved.status, 200)
                approvals[str(index)] = approved.json()["approval_token"]

            stale = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_id, "source_digest": source_digest,
                "frames": frames,
                "approvals": {**approvals, "1": approvals["3"]},
            })
            self.assertEqual(stale.status, 400)

            assembled = harness.post_json("/api/assemble-actor-walk", {
                "run_id": run_id, "source_digest": source_digest,
                "frames": frames,
                "approvals": approvals,
                "cell_size": 64,
                "padding": 4,
            })
            self.assertEqual(assembled.status, 200)
            result = assembled.json()
            self.assertEqual(result["action"], "walk")
            self.assertEqual(result["beats"], ["N", "L", "N", "R"])
            self.assertTrue(result["export_ready"])
            provenance = result["approval_provenance"]
            self.assertEqual(provenance["schema_version"], "asset-studio.walk-assembly-provenance/v1")
            self.assertEqual(provenance["route"], "/api/assemble-actor-walk")
            self.assertRegex(provenance["assembly_token"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                [(item["frame_index"], item["beat"], item["approval_token"]) for item in provenance["approvals"]],
                [(1, "L", approvals["1"]), (3, "R", approvals["3"])],
            )
            self.assertEqual(len(result["frame_urls"]), 4)
            self.assertEqual(len(provider.calls), 2)
            frame_bytes = [(root / "generated" / Path(url).name).read_bytes() for url in result["frame_urls"]]
            self.assertEqual(frame_bytes[0], frame_bytes[2])
            self.assertNotEqual(frame_bytes[1], frame_bytes[3])
            with Image.open(BytesIO(source)) as uploaded, Image.open(BytesIO(frame_bytes[0])) as exported_f1:
                self.assertEqual(exported_f1.size, uploaded.size)
                self.assertEqual(exported_f1.convert("RGBA").tobytes(), uploaded.convert("RGBA").tobytes())
            for raw in frame_bytes:
                with Image.open(BytesIO(raw)) as frame:
                    self.assertEqual(frame.format, "PNG")
                    self.assertEqual(frame.mode, "RGBA")
            self.assertEqual(set(result["proof_urls"]), {"strip", "walk_gif", "f2_f4_gif"})
            for url in result["proof_urls"].values():
                self.assertTrue((root / "generated" / Path(url).name).is_file())
            with Image.open(root / "generated" / Path(result["proof_urls"]["strip"]).name) as strip:
                self.assertEqual(strip.format, "PNG")
                with Image.open(BytesIO(source)) as uploaded:
                    self.assertEqual(strip.width, uploaded.width * 4 * 4)
            with Image.open(root / "generated" / Path(result["proof_urls"]["f2_f4_gif"]).name) as gif:
                self.assertEqual(gif.format, "GIF")
                self.assertEqual(getattr(gif, "n_frames", 1), 2)
            with Image.open(root / "generated" / Path(result["proof_urls"]["walk_gif"]).name) as gif:
                self.assertEqual(gif.format, "GIF")
                self.assertEqual(getattr(gif, "n_frames", 1), 4)

            forged = harness.post_json("/api/export-actor-walk", {"assembly_token": "0" * 64})
            self.assertEqual(forged.status, 400)
            exported = harness.post_json("/api/export-actor-walk", {
                "assembly_token": provenance["assembly_token"],
            })
            self.assertEqual(exported.status, 200)
            self.assertEqual(exported.headers["Content-Type"], "application/zip")
            with zipfile.ZipFile(BytesIO(exported.body)) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"manifest.json", "atlas.png", "frames/walk-000.png", "frames/walk-001.png",
                     "frames/walk-002.png", "frames/walk-003.png", "proofs/strip.png",
                     "proofs/walk.gif", "proofs/f2-f4.gif", "provenance.json"},
                )
                manifest = __import__("json").loads(archive.read("manifest.json"))
                self.assertEqual(manifest["action"], "walk")
                self.assertEqual(manifest["beats"], ["N", "L", "N", "R"])
                self.assertEqual(archive.read("frames/walk-000.png"), archive.read("frames/walk-002.png"))

    def test_ui_is_profile_walk_flow_not_a_walk4_lab_island(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        js = (root / "src/main.js").read_text(encoding="utf-8")
        self.assertIn('id="actorWalkWorkflow"', html)
        self.assertIn('id="actorWalkProofStrip"', html)
        self.assertIn('id="actorWalkProofGif"', html)
        self.assertIn('id="actorWalkF2F4Gif"', html)
        self.assertIn("activeSpriteTarget()", js)
        self.assertIn("imageObjectDataUrl", js)
        self.assertIn("/api/approve-actor-walk-frame", js)
        self.assertIn("/api/assemble-actor-walk", js)
        self.assertNotIn("/api/assemble-actor-walk4", js)
        self.assertNotIn("actorWalk4Workflow", html)

    def test_normal_actor_walk_trigger_routes_to_pilot_and_assembly_adopts_result(self):
        routed = JS_HARNESS.run_json(
            names=("isActorWalkProductionRequest", "generateAiAsset"),
            prelude="""
let assetGenerationInFlight = null;
const source = { type:'image', id:'uploaded-character' };
const isRecipeRegistryReady = () => true;
const blockAssetGeneration = () => new Error('blocked');
const currentAssetFamily = () => 'sprite';
const currentAssetSubtype = () => 'character';
const effectivePixelAnimationPreset = () => 'walk';
const activeSpriteTarget = () => source;
let calls = 0;
const generateActorWalk = async () => { calls += 1; return { workflow:'walk' }; };
""",
            script="""
(async () => {
  const value = await generateAiAsset();
  console.log(JSON.stringify({calls, value}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertEqual(routed, {"calls": 1, "value": {"workflow": "walk"}})

        direction_guard = JS_HARNESS.run_json(
            names=("actorWalkDirectionSupported", "syncActorWalkControls", "generateActorWalk"),
            prelude="""
const controls = {
  pixelDirectionMode:{value:'single'}, pixelTargetDirection:{value:'W'},
  actorWalkStart:{disabled:false,title:''}, actorWalkRetry:{disabled:false,title:''},
  actorWalkApprove:{disabled:false}, actorWalkAssemble:{disabled:false},
};
const $ = id => controls[id] || null;
const isRecipeRegistryReady = () => true;
const ACTOR_WALK_SOUTH_ONLY_MESSAGE = '제작용 walk 워크플로우는 현재 단일 방향 S(정면)만 지원합니다. 방향 모드를 1방향으로 설정하고 S를 선택하세요.';
let actorWalkState = null, actorWalkGenerationId = 0, actorWalkGenerationInFlight = null;
let actorWalkApprovalInFlight = null, actorWalkAssemblyInFlight = null;
""",
            script="""
(async () => {
  syncActorWalkControls();
  let message='';
  try { await generateActorWalk(); } catch (error) { message=error.message; }
  controls.pixelTargetDirection.value='S';
  const southSupported=actorWalkDirectionSupported();
  console.log(JSON.stringify({message,southSupported,disabled:controls.actorWalkStart.disabled,title:controls.actorWalkStart.title}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertIn("S(정면)만 지원", direction_guard["message"])
        self.assertTrue(direction_guard["southSupported"])
        self.assertTrue(direction_guard["disabled"])
        self.assertIn("S(정면)만 지원", direction_guard["title"])

        single_flight = JS_HARNESS.run_json(
            names=("isActorWalkProductionRequest", "generateAiAsset"),
            prelude="""
let assetGenerationInFlight = null;
const source = { type:'image', id:'uploaded-character' };
const isRecipeRegistryReady = () => true;
const blockAssetGeneration = () => new Error('blocked');
const currentAssetFamily = () => 'sprite';
const currentAssetSubtype = () => 'character';
const effectivePixelAnimationPreset = () => 'walk';
const activeSpriteTarget = () => source;
let calls = 0, release;
const gate = new Promise(resolve => { release = resolve; });
const generateActorWalk = () => { calls += 1; return gate.then(() => ({workflow:'walk'})); };
""",
            script="""
(async () => {
  const first = generateAiAsset();
  const second = generateAiAsset();
  const samePromise = first === second;
  release();
  const values = await Promise.all([first, second]);
  await Promise.resolve();
  console.log(JSON.stringify({calls, samePromise, values, cleared:assetGenerationInFlight===null}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertEqual(single_flight["calls"], 1)
        self.assertTrue(single_flight["samePromise"])
        self.assertTrue(single_flight["cleared"])
        self.assertEqual(single_flight["values"], [{"workflow": "walk"}] * 2)

        adopted = JS_HARNESS.run_json(
            names=("effectConcatBytes", "tileCanonical", "tileJson", "tileSha256", "ACTOR_EXPORT_LIMITS", "normalizeActorProductionContract", "actorArtifactDigest", "validateActorWalkServerProvenance", "buildActorWalkProductionArtifact", "actorWalkAssemblyAdoptions", "adoptActorWalkAssembly"),
            prelude="""
global.window = {};
const added = [], selected = [], adopted = [], stored = new Map();
const assetResultFromGeneration = (payload, generation, source) => ({id:'result-walk', payload, generation, source, adopted:false});
const assetResultStore = {
  add: value => { added.push(value); stored.set(value.id,value); },
  get: id => stored.get(id) || null,
  select: id => selected.push(id),
};
let failAdoptionOnce = true;
const adoptResult = async (id, mode) => {
  adopted.push([id, mode]);
  if (failAdoptionOnce) { failAdoptionOnce=false; throw new Error('forced post-store adoption failure'); }
  stored.get(id).adopted=true;
};
let loadCount=0;
const makeFrame = index => { const data=new Uint8ClampedArray(16*16*4); for(let y=3;y<13;y++)for(let x=5;x<11;x++)data[(y*16+x)*4+3]=255; if(index===1)data[(11*16+4)*4+3]=255; if(index===3)data[(11*16+12)*4+3]=255; return {width:16,height:16,data}; };
const loaded=[makeFrame(0),makeFrame(1),makeFrame(0),makeFrame(3)];
const frameLoader = async (_url,index) => { loadCount += 1; return loaded[index]; };
""",
            script="""
(async () => {
  const source = {id:'uploaded-character'};
  const state = {sourceObject:source};
  const assembly = {
    generation_stage:'actor-walk-assembly', action:'walk', beats:['N','L','N','R'],
    export_ready:true, sheet_url:'/walk.png', frame_urls:['/f1.png','/f2.png','/f3.png','/f4.png'],
    package_url:'/assets/generated/actor_walk_package_0123456789abcdef0123456789abcdef.zip',
    proof_urls:{strip:'/proof.png',walk_gif:'/walk.gif',f2_f4_gif:'/feet.gif'},
    approval_provenance:{schema_version:'asset-studio.walk-assembly-provenance/v1',route:'/api/assemble-actor-walk',action:'walk',sheet_digest:'f'.repeat(64),assembly_token:'a'.repeat(64),approvals:[
      {frame_index:1,beat:'L',artifact_digest:'b'.repeat(64),approval_token:'c'.repeat(64)},
      {frame_index:3,beat:'R',artifact_digest:'d'.repeat(64),approval_token:'e'.repeat(64)}
    ]}
  };
  let firstError='';
  try { await adoptActorWalkAssembly(assembly, state, 'character', frameLoader); }
  catch(error) { firstError=error.message; }
  const result = await adoptActorWalkAssembly(assembly, state, 'character', frameLoader);
  const repeated = await adoptActorWalkAssembly(assembly, state, 'character', frameLoader);
  const art=window.__actorProductionArtifact;
  console.log(JSON.stringify({result,repeated,firstError,loadCount,added,selected,adopted,artifact:art,packageFrames:art.frames.length,exportToken:art.serverExportToken}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertEqual(adopted["firstError"], "forced post-store adoption failure")
        self.assertEqual(adopted["loadCount"], 4)
        self.assertEqual(len(adopted["added"]), 1)
        self.assertEqual(adopted["selected"], ["result-walk", "result-walk", "result-walk"])
        self.assertEqual(adopted["adopted"], [["result-walk", "new-layer"], ["result-walk", "new-layer"]])
        self.assertEqual(adopted["result"]["id"], adopted["repeated"]["id"])
        result = adopted["added"][0]
        self.assertEqual(result["payload"]["sprite"]["animation_mode"], "walk")
        self.assertEqual(result["payload"]["sprite"]["beats"], ["N", "L", "N", "R"])
        self.assertTrue(result["generation"]["export_ready"])
        self.assertEqual(result["generation"]["qa"]["status"], "HUMAN_APPROVED")
        self.assertEqual(adopted["artifact"]["contract"]["actions"][0]["beats"], ["N", "L", "N", "R"])
        self.assertEqual(adopted["packageFrames"], 4)
        self.assertEqual(adopted["exportToken"], "a" * 64)
        self.assertEqual(adopted["artifact"]["serverPackageUrl"], "/assets/generated/actor_walk_package_0123456789abcdef0123456789abcdef.zip")
        self.assertEqual(result["generation"]["artifacts"][0]["kind"], "package")
        self.assertEqual(adopted["artifact"]["serverApprovalProvenance"]["route"], "/api/assemble-actor-walk")

    def test_walk_browser_generation_and_review_operations_are_single_flight(self):
        generated = JS_HARNESS.run_json(
            names=("actorWalkDirectionSupported", "syncActorWalkControls", "actorWalkRunIsCurrent", "generateActorWalk"),
            prelude="""
const controls = Object.fromEntries(['actorWalkStart','actorWalkRetry','actorWalkApprove','actorWalkAssemble','familyGenerateAi','generateBtn','generatePixelAsset','actorWalkProofs','actorWalkProofStrip','actorWalkProofGif','actorWalkF2F4Gif'].map(id => [id,{disabled:false,classList:{add(){},remove(){}}}]));
const $ = id => controls[id] || null;
const isRecipeRegistryReady = () => true;
let selected = {type:'image', id:'source-A'};
const activeSpriteTarget = () => selected;
const actorActionRecipe = () => ({id:'walk',frame_count:4,beats:['N','L','N','R']});
const refreshProviderHealth = async () => ({available:true});
const imageObjectDataUrl = async object => `data:${object.id}`;
const imageDigest = async source => `digest:${source}`;
const srcToDataUrl = async url => `data:${url}`;
const setStatus = () => {};
const renderActorWalkReview = () => {};
let actorWalkState = null, actorWalkGenerationId = 0, actorWalkGenerationInFlight = null;
let actorWalkApprovalInFlight = null, actorWalkAssemblyInFlight = null;
const calls = [];
const actorApi = async (path, payload) => {
  calls.push({path, source:payload?.direction_master || null, frame:payload?.frame_index ?? null});
  await new Promise(resolve => setTimeout(resolve, 2));
  if (path.endsWith('blueprints')) return {blueprints:[{frame_index:1},{frame_index:3}]};
  if (path.endsWith('generate-actor-frame')) return {url:`/${payload.direction_master}/${payload.frame_index}.png`,artifact_digest:`artifact-${payload.frame_index}`,run_id:'run-A',source_digest:'digest:data:source-A'};
  return {proof_urls:{strip:'/strip',walk_gif:'/walk',f2_f4_gif:'/feet'}};
};
""",
            script="""
(async () => {
  const first = generateActorWalk();
  selected = {type:'image', id:'source-B'};
  const second = generateActorWalk();
  const samePromise = first === second;
  await Promise.all([first,second]);
  console.log(JSON.stringify({samePromise,calls,state:{source:actorWalkState.source,runId:actorWalkState.runId,frame1:actorWalkState.frames[1].url,frame3:actorWalkState.frames[3].url},disabled:Object.fromEntries(Object.entries(controls).filter(([id])=>id.startsWith('actorWalk')).map(([id,value])=>[id,value.disabled]))}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertTrue(generated["samePromise"])
        self.assertEqual([call["path"] for call in generated["calls"]].count("/api/generate-actor-frame"), 2)
        self.assertTrue(all(call["source"] in (None, "data:source-A") for call in generated["calls"]))
        self.assertEqual(generated["state"]["source"], "data:source-A")
        self.assertEqual(generated["state"]["runId"], "run-A")
        self.assertIn("source-A", generated["state"]["frame1"])
        self.assertIn("source-A", generated["state"]["frame3"])
        self.assertFalse(generated["disabled"]["actorWalkStart"])
        self.assertFalse(generated["disabled"]["actorWalkRetry"])

        reviewed = JS_HARNESS.run_json(
            names=("actorWalkDirectionSupported", "syncActorWalkControls", "approveActorWalkCurrent", "assembleActorWalk"),
            prelude="""
const controls = Object.fromEntries(['actorWalkStart','actorWalkRetry','actorWalkApprove','actorWalkAssemble','familyGenerateAi','generateBtn','generatePixelAsset','actorWalkProgress'].map(id => [id,{disabled:false,title:'',textContent:'',classList:{add(){},remove(){}}}]));
controls.pixelDirectionMode={value:'single'};
controls.pixelTargetDirection={value:'S'};
const $ = id => controls[id] || null;
const isRecipeRegistryReady = () => true;
const ACTOR_WALK_SOUTH_ONLY_MESSAGE = 'south only';
const setStatus = () => {};
const renderActorWalkReview = () => {};
const addGallery = () => {};
let actorWalkGenerationInFlight = null, actorWalkApprovalInFlight = null, actorWalkAssemblyInFlight = null;
let actorWalkState = {generationId:7,runId:'run',sourceDigest:'digest',sourceObject:{},beats:['N','L','N','R'],frames:{1:{artifact_digest:'f1'},3:{artifact_digest:'f3'}},approvals:{}};
let approveCalls = 0, assembleCalls = 0;
const actorApi = async path => {
  await new Promise(resolve => setTimeout(resolve, 2));
  if (path.includes('approve')) { approveCalls += 1; return {approval_token:'token-1'}; }
  assembleCalls += 1; return {sheet_url:'/sheet'};
};
const adoptActorWalkAssembly = async () => {};
""",
            script="""
(async () => {
  const approve1=approveActorWalkCurrent(), approve2=approveActorWalkCurrent();
  const sameApprove=approve1===approve2;
  await Promise.all([approve1,approve2]);
  actorWalkState.approvals['3']='token-3';
  const assemble1=assembleActorWalk(), assemble2=assembleActorWalk();
  const sameAssemble=assemble1===assemble2;
  await Promise.all([assemble1,assemble2]);
  controls.pixelTargetDirection.value='W';
  syncActorWalkControls();
  let approveBlocked='', assembleBlocked='';
  try { await approveActorWalkCurrent(); } catch(error) { approveBlocked=error.message; }
  try { await assembleActorWalk(); } catch(error) { assembleBlocked=error.message; }
  console.log(JSON.stringify({sameApprove,sameAssemble,approveCalls,assembleCalls,approval:actorWalkState.approvals['1'],blocked:{approveBlocked,assembleBlocked},buttons:{start:controls.actorWalkStart.disabled,retry:controls.actorWalkRetry.disabled,approve:controls.actorWalkApprove.disabled,assemble:controls.actorWalkAssemble.disabled}}));
})().catch(error => { console.error(error); process.exit(1); });
""",
        )
        self.assertTrue(reviewed["sameApprove"])
        self.assertTrue(reviewed["sameAssemble"])
        self.assertEqual(reviewed["approveCalls"], 1)
        self.assertEqual(reviewed["assembleCalls"], 1)
        self.assertEqual(reviewed["approval"], "token-1")
        self.assertEqual(reviewed["blocked"], {"approveBlocked": "south only", "assembleBlocked": "south only"})
        self.assertEqual(reviewed["approveCalls"], 1)
        self.assertEqual(reviewed["assembleCalls"], 1)
        self.assertTrue(all(reviewed["buttons"].values()))

    def test_synthetic_walk_remains_non_exportable_even_with_browser_style_approval(self):
        result = JS_HARNESS.run_json(
            names=("uint16LE", "uint32LE", "effectConcatBytes", "crc32Table", "crc32Bytes", "effectPngChunk", "encodeEffectFramePng", "tileCanonical", "tileJson", "tileSha256", "TILE_EXPORT_LIMITS", "tileZipBytes", "ACTOR_EXPORT_LIMITS", "normalizeActorProductionContract", "actorArtifactDigest", "validateActorVisualApproval", "validateActorWalkServerProvenance", "evaluateActorProductionQA", "buildActorExportPackage", "resetActorVisualApproval", "buildActorSyntheticArtifact"),
            prelude="""
global.window = {};
const controls = {actorVisualApproval:{checked:false},exportActorPackageZip:{disabled:false},actorQaSummary:{textContent:''}};
const $ = id => controls[id] || null;
const cancelAnimationFrame = () => {};
const renderActorProductionFrame = () => {};
""",
            script="""
buildActorSyntheticArtifact();
const art=window.__actorProductionArtifact;
const browserApproval={status:'APPROVED',reviewer:'local-user',source:'manual-browser-review',timestamp:new Date().toISOString(),artifact_digest:actorArtifactDigest(art.frames,art.contract)};
let blocked=false, message='';
try { buildActorExportPackage(art.frames,art.contract,browserApproval,art.serverApprovalProvenance); }
catch(error) { blocked=true; message=error.message; }
console.log(JSON.stringify({blocked,message,exportable:art.exportable,provenance:art.serverApprovalProvenance||null}));
""",
        )
        self.assertTrue(result["blocked"])
        self.assertIn("server export endpoint", result["message"])
        self.assertFalse(result["exportable"])
        self.assertIsNone(result["provenance"])

    def test_active_walk_contract_has_no_frame_count_suffix_aliases(self):
        active = "\n".join((
            (ROOT / "server.py").read_text(encoding="utf-8"),
            (ROOT / "src" / "main.js").read_text(encoding="utf-8"),
            (ROOT / "index.html").read_text(encoding="utf-8"),
            (ROOT / "profiles" / "generic-pixel-actor-v1.json").read_text(encoding="utf-8"),
        ))
        self.assertNotRegex(active, r"walk(?:4|6)")

    def test_walk_pixel_balance_cannot_claim_semantic_alternation_or_exportability(self):
        result = JS_HARNESS.run_json(
            names=("effectConcatBytes", "tileCanonical", "tileJson", "tileSha256", "ACTOR_EXPORT_LIMITS", "normalizeActorProductionContract", "actorArtifactDigest", "validateActorVisualApproval", "validateActorWalkServerProvenance", "evaluateActorProductionQA"),
            script="""
const contract={subtype:'character',directions:{mode:'1dir',requested:['S'],row_order:['S']},actions:[{id:'walk',frame_count:4,fps:10,loop:true,beats:['N','L','N','R']}],grid:{cell:{width:16,height:16},gap:0},sourceSize:{width:16,height:16},anchors:{pivot:{x:.5,y:.75},root:{x:.5,y:.75},contact:{x:.5,y:.75}}};
const frame=(i)=>{const data=new Uint8ClampedArray(16*16*4);for(let y=3;y<13;y++)for(let x=6;x<10;x++)data[(y*16+x)*4+3]=255;if(i===1)for(let y=10;y<13;y++)data[(y*16+4)*4+3]=255;if(i===3)for(let y=10;y<13;y++)data[(y*16+11)*4+3]=255;return{direction:'S',action:'walk',index:i,beatId:['N','L','N','R'][i],imageData:{width:16,height:16,data},root:{x:.5,y:.75},contact:{x:.5,y:.75}}};
const frames=[frame(0),frame(1),frame(0),frame(3)],qa=evaluateActorProductionQA(frames,contract);
console.log(JSON.stringify(qa));
""",
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["evidence"]["motion_read"]["status"], "HUMAN_REVIEW_REQUIRED")
        self.assertIn("visual alternation", result["evidence"]["motion_read"]["note"].lower())
        self.assertFalse(any(reason["code"] == "SUPPORT_ALTERNATION" for reason in result["reasons"]))
        self.assertFalse(any("support_balance" in sequence for sequence in result["evidence"]["motion_read"]["metrics"]["sequences"]))


if __name__ == "__main__":
    unittest.main()
