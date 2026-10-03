local root = "C:/comfyui/ComfyUI/output/actor_rig/source_black_orc_walk6/"
local output = root .. "source_black_orc_walk6.aseprite"
local sprite = Sprite(384, 384, ColorMode.RGB)
local layer = sprite.layers[1]
layer.name = "Rendered Walk Frames"

for index = 1, 6 do
  if index > 1 then sprite:newEmptyFrame() end
  local path = root .. string.format("walk_%02d.png", index)
  local image = Image{ fromFile=path }
  sprite:newCel(layer, sprite.frames[index], image, Point(0, 0))
  sprite.frames[index].duration = 0.125
end

local tag = sprite:newTag(1, 6)
tag.name = "walk6"
tag.aniDir = AniDir.FORWARD
sprite:saveAs(output)
sprite:close()
