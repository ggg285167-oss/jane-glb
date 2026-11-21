"""Blender 无头导出 glTF (.glb)

用法：
    blender -b model.blend --python export_glb.py

做的事：
1. 遍历所有材质，补一个 Principled BSDF，把贴图连到 Base Color
   （Goo Engine 的自定义节点在无头版 Blender 里不认，不补的话导出会是灰模）
2. 导出模型 + 骨骼 + 动画到 Jane.glb
"""
import bpy
import os
import sys


def log(msg):
    print(f"[export] {msg}", flush=True)


def find_image_node(node_tree):
    """挑一张最像 albedo 的贴图"""
    best = None
    for n in node_tree.nodes:
        if n.type != 'TEX_IMAGE' or n.image is None:
            continue
        name = (n.name + " " + (n.image.name or "")).lower()
        if any(k in name for k in ("base", "albedo", "diffuse", "color", "skin", "face", "hair")):
            return n
        if best is None:
            best = n
    return best


def fix_materials():
    fixed = 0
    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes or mat.node_tree is None:
            continue
        nt = mat.node_tree

        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)

        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')
            out.location = (600, 0)

        if bsdf is None:
            bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (300, 0)
            fixed += 1

        if not out.inputs['Surface'].is_linked:
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        img = find_image_node(nt)
        if img is not None and not bsdf.inputs['Base Color'].is_linked:
            nt.links.new(img.outputs['Color'], bsdf.inputs['Base Color'])
            try:
                img.image.alpha_mode = 'CHANNEL_PACKED'
            except Exception:
                pass

        # 半透明/头发这类，把 alpha 也接上
        if img is not None and 'Alpha' in bsdf.inputs and not bsdf.inputs['Alpha'].is_linked:
            try:
                blend = getattr(mat, 'blend_method', 'OPAQUE')
            except Exception:
                blend = 'OPAQUE'
            if blend in {'BLEND', 'HASHED', 'CLIP'}:
                nt.links.new(img.outputs['Alpha'], bsdf.inputs['Alpha'])

    log(f"材质处理完成，新建 BSDF 数量：{fixed}")


def main():
    log(f"已打开：{bpy.data.filepath}")
    log(f"物体数：{len(bpy.data.objects)}，材质数：{len(bpy.data.materials)}")

    fix_materials()

    out_path = os.path.abspath("Jane.glb")
    kwargs = dict(
        filepath=out_path,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_animations=True,
        export_skins=True,
        export_yup=True,
        export_image_format='AUTO',
    )

    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError as e:
        # 某些版本的参数名不同，退回到最小参数集
        log(f"参数不兼容，退回默认设置：{e}")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format='GLB',
            use_selection=False,
            export_animations=True,
        )

    if os.path.exists(out_path):
        log(f"导出成功：{out_path}  大小 {os.path.getsize(out_path)/1048576:.1f} MB")
    else:
        log("导出失败：文件不存在")
        sys.exit(1)


main()
