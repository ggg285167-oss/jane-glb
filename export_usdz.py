"""USDZ -> GLB（Blender 无头）"""
import bpy, os, sys

def log(m):
    print(f"[usdz2glb] {m}", flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
log("场景已清空")

bpy.ops.wm.usd_import(filepath="Kei.usdz")
log(f"导入完成：物体 {len(bpy.data.objects)} / 网格 {len(bpy.data.meshes)} / 材质 {len(bpy.data.materials)}")

# 打印网格顶点数，确认不是平面
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        log(f"  {ob.name}: {len(ob.data.vertices)} 顶点")

out = os.path.abspath("Kei.glb")
bpy.ops.export_scene.gltf(
    filepath=out,
    export_format='GLB',
    use_selection=False,
    export_animations=True,
    export_skins=True,
    export_yup=True,
    export_apply=False,
)
log(f"导出 {os.path.getsize(out)/1048576:.1f} MB")
