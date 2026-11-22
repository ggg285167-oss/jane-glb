"""USDZ -> GLB（Blender 无头），导出静态绑定姿态"""
import bpy, os, sys

def log(m):
    print(f"[usdz2glb] {m}", flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath="Kei.usdz")
log(f"导入完成：物体 {len(bpy.data.objects)} / 网格 {len(bpy.data.meshes)} / 材质 {len(bpy.data.materials)}")

# 关键：把所有骨架切回绑定姿态，避免停在动画帧上
for ob in bpy.data.objects:
    if ob.type == 'ARMATURE':
        try:
            ob.data.pose_position = 'REST'
            log(f"骨架 {ob.name} 设为 REST")
        except Exception as e:
            log(f"骨架 {ob.name} 设置失败: {e}")

# 清掉动画数据，避免导出后姿态又被动画覆盖
for ob in bpy.data.objects:
    if ob.animation_data:
        ob.animation_data_clear()
        log(f"清除 {ob.name} 的动画数据")

for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)
log("已清空所有 action")

for ob in bpy.data.objects:
    if ob.type == 'MESH':
        log(f"  网格 {ob.name}: {len(ob.data.vertices)} 顶点")

out = os.path.abspath("Kei.glb")
bpy.ops.export_scene.gltf(
    filepath=out,
    export_format='GLB',
    use_selection=False,
    export_animations=False,
    export_skins=True,
    export_yup=True,
    export_apply=False,
)
log(f"导出 {os.path.getsize(out)/1048576:.1f} MB")
