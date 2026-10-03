# Prompt-first Asset Studio and H3 sprite generation

Approved scope: keep Sprite/UI/Object taxonomy and subtypes; remove motion and 3D workspaces and active APIs; prompt-only generation for UI/Object; selected-image H3/H3 Fast video generation for Sprite with wizard or direct final prompt.

Existing user changes and assets must remain. Do not delete projects, models, generated outputs, reference sources or untracked scripts. Retired source modules may remain on disk but cannot be exposed or loaded by the app.

Order:
1. Preserve targeted regression baseline (53 menu tests passed before this change). Full suite has pre-existing Windows cp949/fcntl collection failures; use UTF-8 for focused runs.
2. Frontend: remove retired menu and workspace mounts; consolidate navigation; reduce primary generation surface; explicit selected source snapshot; wizard/direct prompt and compact execution controls; no legacy walk interception.
3. Backend: independent H3 workflow via local ComfyUI nodes; existing installed model discovery; source and final prompt validation; async job integration; exact output frame count, chroma removal, sheet/GIF/frame artifacts and metadata. UI/Object direct prompt bypasses hidden style/contract augmentation.
4. Reuse result tray and animation preview; keep rendering FPS distinct from generation duration.
5. Run focused API/workflow/prompt/route/DOM tests, JS syntax, Python compile and diff checks. Verify browser menus and source gating. Run one real local H3 Fast sprite job using user-authorized orc source when GPU queue is free, inspect artifacts.

No new dependencies, model downloads, paid cloud generation, commits, or security-setting changes.
