import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
UI = (ROOT / "src" / "pixel-pipeline.js").read_text(encoding="utf-8")
VIEWER = (ROOT / "src" / "pixel-pipeline-viewer.js").read_text(encoding="utf-8")
CORE = ROOT / "src" / "pixel-pipeline-core.js"
CORE_TEXT = CORE.read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "pixel-pipeline.css").read_text(encoding="utf-8")


def node_json(source: str):
    result = subprocess.run(
        ["node", "-e", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
















def test_pipeline_ui_persists_state_gates_steps_and_polls_generation_job():
    for token in (
        "asset-studio.3d-pixel-workflow/v2",
        "localStorage.getItem",
        "localStorage.setItem",
        "Core.canEnterStep",
        "Core.completeStep",
        "Core.directionProgress",
        "Core.reviewComplete",
        "generateSingleDirection",
        "generateAllDirections",
        "normalizePipelineState",
        "mergeDirectionArtifactQa",
        'fetch("/api/local-3d-pipeline-health"',
        'requestJson("/api/generation-jobs"',
        'job.status === "succeeded"',
        '30 * 60 * 1000',
        '자동 재생성/검증 포함',
        '"pipelineApproveSingle").disabled = !state.singleDirectionReady || state.directionArtifacts?.S?.accepted !== true',
        "requestAnimationFrame(animateTimeline)",
        "dragover",
        "drop",
        "prefers-reduced-motion",
    ):
        assert token in UI or token in CSS or token in CORE_TEXT




def test_core_normalization_stage_gating_direction_progress_and_review_gate():
    data = node_json(
        """
const C=require('./src/pixel-pipeline-core.js');
let state=C.createState();
const start={available:C.availableStep(state),can0:C.canEnterStep(state,0),can1:C.canEnterStep(state,1)};
for(let step=0;step<3;step++) state=C.completeStep(state,step);
state.directionArtifacts.S={url:'/assets/generated/proof.png',artifactDigest:'abc',provider:'fake',model:'fake',resolution:64,paletteColors:24};
state.singleDirectionReady=true;
state.directions.S='ready';
for(let step=3;step<5;step++) state=C.completeStep(state,step);
for(const direction of C.DIRECTIONS) state.directions[direction]='ready';
const directions=C.directionProgress(state);
for(const key of C.REVIEW_KEYS) state.review[key]=true;
state=C.completeStep(state,5);
const finished={progress:C.workflowProgress(state),review:C.reviewComplete(state),step:state.currentStep};
const normalized=C.normalizeState({schema:C.SCHEMA,currentStep:99,completedSteps:[0,0,7,'bad'],action:'fly',selectedDirection:'X',directions:{S:'ready'},review:{identity:true}});
console.log(JSON.stringify({start,directions,finished,normalized}));
"""
    )
    assert data["start"] == {"available": 0, "can0": True, "can1": False}
    assert data["directions"] == {"ready": 8, "total": 8, "percent": 100}
    assert data["finished"] == {
        "progress": {"complete": 6, "total": 6, "percent": 100},
        "review": True,
        "step": 5,
    }
    assert data["normalized"]["currentStep"] == 0
    assert data["normalized"]["completedSteps"] == [0]
    assert data["normalized"]["action"] == "idle"
    assert data["normalized"]["selectedDirection"] == "S"
    assert data["normalized"]["finalApproved"] is False


def test_pipeline_layout_has_desktop_mobile_and_reduced_motion_contracts():
    assert "grid-template-columns: minmax(300px, 350px) minmax(420px, 1fr) minmax(230px, 270px)" in CSS
    assert "@media (max-width: 1180px)" in CSS
    assert "@media (max-width: 820px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert ".pipeline-direction-grid" in CSS
    assert "grid-template-columns: repeat(3" in CSS


def test_removed_workspace_is_not_loaded_by_the_application():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for removed in ["motionStudioWorkspace", "pixelPipelineWorkspace", "src/motion-studio", "src/pixel-pipeline", "styles/motion-studio", "styles/pixel-pipeline"]:
        assert removed not in html
