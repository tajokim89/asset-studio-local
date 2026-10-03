(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PixelPipelineCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "asset-studio.3d-pixel-workflow/v2";
  const STEP_COUNT = 6;
  const DIRECTIONS = Object.freeze(["S", "SW", "W", "NW", "N", "NE", "E", "SE"]);
  const ACTIONS = Object.freeze(["idle", "walk", "run"]);
  const REVIEW_KEYS = Object.freeze([
    "identity",
    "silhouette",
    "palette",
    "pivot",
    "loop",
    "alpha",
  ]);

  function blankDirections() {
    return Object.fromEntries(DIRECTIONS.map(direction => [direction, "pending"]));
  }

  function blankDirectionArtifacts() {
    return Object.fromEntries(DIRECTIONS.map(direction => [direction, null]));
  }

  function blankReview() {
    return Object.fromEntries(REVIEW_KEYS.map(key => [key, false]));
  }

  function blankMotions() {
    return Object.fromEntries(ACTIONS.map(action => [action, "pending"]));
  }

  function createState() {
    return {
      schema: SCHEMA,
      currentStep: 0,
      completedSteps: [],
      model: null,
      motions: blankMotions(),
      action: "idle",
      poseFrame: 0,
      singleDirectionReady: false,
      selectedDirection: "S",
      directions: blankDirections(),
      directionArtifacts: blankDirectionArtifacts(),
      review: blankReview(),
      finalApproved: false,
    };
  }

  function integer(value, fallback, min, max) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= min && parsed <= max ? parsed : fallback;
  }

  function normalizeState(raw) {
    const base = createState();
    if (!raw || typeof raw !== "object" || raw.schema !== SCHEMA) return base;
    const completedSteps = Array.isArray(raw.completedSteps)
      ? [...new Set(raw.completedSteps.map(value => integer(value, -1, 0, STEP_COUNT - 1)).filter(value => value >= 0))].sort((a, b) => a - b)
      : [];
    const model = raw.model && typeof raw.model === "object" && typeof raw.model.name === "string"
      ? {
          name: raw.model.name.slice(0, 180),
          size: Math.max(0, Number(raw.model.size) || 0),
          type: typeof raw.model.type === "string" ? raw.model.type.slice(0, 40) : "",
          sample: Boolean(raw.model.sample),
          url: typeof raw.model.url === "string" && raw.model.url.startsWith("/assets/")
            ? raw.model.url.slice(0, 1024)
            : "",
          referenceUrl: typeof raw.model.referenceUrl === "string" && raw.model.referenceUrl.startsWith("/assets/")
            ? raw.model.referenceUrl.slice(0, 1024)
            : "",
          blendUrl: typeof raw.model.blendUrl === "string" && raw.model.blendUrl.startsWith("/assets/")
            ? raw.model.blendUrl.slice(0, 1024)
            : "",
          source: ["image", "sample", "upload"].includes(raw.model.source) ? raw.model.source : "upload",
        }
      : null;
    const motions = blankMotions();
    for (const action of ACTIONS) {
      if (["pending", "working", "ready"].includes(raw.motions?.[action])) motions[action] = raw.motions[action];
    }
    const directions = blankDirections();
    for (const direction of DIRECTIONS) {
      if (["pending", "working", "ready", "approved"].includes(raw.directions?.[direction])) {
        directions[direction] = raw.directions[direction];
      }
    }
    const directionArtifacts = blankDirectionArtifacts();
    for (const direction of DIRECTIONS) {
      const artifact = raw.directionArtifacts?.[direction];
      if (!artifact || typeof artifact !== "object" || typeof artifact.url !== "string") continue;
      const url = artifact.url.slice(0, 1024);
      if (!url.startsWith("/assets/generated/")) continue;
      directionArtifacts[direction] = {
        url,
        artifactDigest: typeof artifact.artifactDigest === "string" ? artifact.artifactDigest.slice(0, 128) : "",
        provider: typeof artifact.provider === "string" ? artifact.provider.slice(0, 80) : "",
        model: typeof artifact.model === "string" ? artifact.model.slice(0, 160) : "",
        resolution: integer(artifact.resolution, 64, 1, 4096),
        frameWidth: integer(artifact.frameWidth, integer(artifact.resolution, 64, 1, 4096), 1, 4096),
        frameHeight: integer(artifact.frameHeight, integer(artifact.resolution, 64, 1, 4096) * 2, 1, 4096),
        frameCount: integer(artifact.frameCount, 8, 1, 64),
        frameUrls: Array.isArray(artifact.frameUrls)
          ? artifact.frameUrls.filter(value => typeof value === "string" && value.startsWith("/assets/generated/")).slice(0, 64).map(value => value.slice(0, 1024))
          : [],
        previewUrl: typeof artifact.previewUrl === "string" && artifact.previewUrl.startsWith("/assets/generated/")
          ? artifact.previewUrl.slice(0, 1024)
          : "",
        action: ACTIONS.includes(artifact.action) ? artifact.action : "idle",
        paletteColors: integer(artifact.paletteColors, 24, 1, 256),
      };
    }
    const review = blankReview();
    for (const key of REVIEW_KEYS) review[key] = Boolean(raw.review?.[key]);
    const state = {
      ...base,
      currentStep: integer(raw.currentStep, 0, 0, STEP_COUNT - 1),
      completedSteps,
      model,
      motions,
      action: ACTIONS.includes(raw.action) ? raw.action : "idle",
      poseFrame: integer(raw.poseFrame, 0, 0, 1000),
      singleDirectionReady: Boolean(directionArtifacts.S),
      selectedDirection: DIRECTIONS.includes(raw.selectedDirection) ? raw.selectedDirection : "S",
      directions,
      directionArtifacts,
      review,
      finalApproved: Boolean(raw.finalApproved),
    };
    if (!state.singleDirectionReady) {
      state.completedSteps = state.completedSteps.filter(step => step < 3);
      for (const direction of DIRECTIONS) state.directions[direction] = "pending";
    }
    state.currentStep = Math.min(state.currentStep, availableStep(state));
    if (!reviewComplete(state)) state.finalApproved = false;
    return state;
  }

  function availableStep(state) {
    let next = 0;
    while (next < STEP_COUNT - 1 && state.completedSteps.includes(next)) next += 1;
    return next;
  }

  function canEnterStep(state, step) {
    const target = integer(step, -1, 0, STEP_COUNT - 1);
    return target >= 0 && target <= availableStep(state);
  }

  function completeStep(state, step) {
    const target = integer(step, -1, 0, STEP_COUNT - 1);
    if (target < 0 || !canEnterStep(state, target)) return normalizeState(state);
    const next = normalizeState(state);
    if (!next.completedSteps.includes(target)) next.completedSteps.push(target);
    next.completedSteps.sort((a, b) => a - b);
    next.currentStep = Math.min(target + 1, STEP_COUNT - 1);
    return next;
  }

  function directionProgress(state) {
    const ready = DIRECTIONS.filter(direction => ["ready", "approved"].includes(state.directions?.[direction])).length;
    return { ready, total: DIRECTIONS.length, percent: Math.round((ready / DIRECTIONS.length) * 100) };
  }

  function reviewComplete(state) {
    return REVIEW_KEYS.every(key => state.review?.[key] === true);
  }

  function workflowProgress(state) {
    const complete = new Set(state.completedSteps).size;
    return { complete, total: STEP_COUNT, percent: Math.round((complete / STEP_COUNT) * 100) };
  }

  return Object.freeze({
    SCHEMA,
    STEP_COUNT,
    DIRECTIONS,
    ACTIONS,
    REVIEW_KEYS,
    createState,
    normalizeState,
    availableStep,
    canEnterStep,
    completeStep,
    directionProgress,
    reviewComplete,
    workflowProgress,
  });
});
