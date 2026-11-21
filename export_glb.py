"""Blender 无头导出 glTF (.glb)

用法：
    blender -b model.blend --python export_glb.py

v2 改进：
- 递归进节点组（Goo Engine 的贴图藏在 group 里），把贴图挖出来
- 对 GooEngine_ToonShader 这类自定义材质，强制换成 Principled BSDF 再连贴图
"""
import bpy
import os
import sys


def log(msg):
    print(f"[export] {msg}", flush=True)


KEYWORDS = ("base", "albedo", "diffuse", "color", "skin", "face", "hair",
            "cloth", "body", "tex", "texture")


def collect_image_nodes(node_tree, depth=0, seen=None):
    """递归收集节点树（含节点组内部）里的图像纹理节点"""
    if seen is None:
        seen = set()
    if node_tree is None or depth > 5:
        return []
    key = node_tree.name
    if key in seen:
        return []
    seen.add(key)

    found = []
    for n in node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None:
            found.append(n)
        elif n.type == 'GROUP' and getattr(n, "node_tree", None) is not None:
            found.extend(collect_image_nodes(n.node_tree, depth + 1, seen))
    return found


def pick_best(images):
    """从候选贴图里挑最像 albedo 的一张"""
    if not images:
        return None
    scored = []
    for n in images:
        name = ((n.name or "") + " " + (n.image.name or "")).lower()
        score = sum(1 for k in KEYWORDS if k in name)
        scored.append((score, n))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def fix_materials():
    changed = 0
    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes or mat.node_tree is None:
            continue
        nt = mat.node_tree

        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')
            out.location = (600, 0)

        # 找出当前接到 Surface 上的东西
        surface_link = out.inputs['Surface'].links[0] if out.inputs['Surface'].is_linked else None
        surface_node = surface_link.from_node if surface_link else None

        goo_like = (surface_node is not None and surface_node.type == 'GROUP') or \
                   ("goo" in (mat.name or "").lower())

        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)

        if goo_like:
            # 断开自定义着色器，换标准 BSDF，否则 glTF 导出器认不出来
            if surface_link:
                nt.links.remove(surface_link)
            if bsdf is None:
                bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
                bsdf.location = (300, 0)
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            changed += 1

        if bsdf is None:
            bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (300, 0)
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            changed += 1

        # 递归找贴图
        imgs = collect_image_nodes(nt)
        best = pick_best(imgs)

        if best is not None:
            if not bsdf.inputs['Base Color'].is_linked:
                nt.links.new(best.outputs['Color'], bsdf.inputs['Base Color'])
            # 粗糙度用不上，保持默认
            if 'Alpha' in bsdf.inputs and not bsdf.inputs['Alpha'].is_linked:
                try:
                    method = getattr(mat, "blend_method", "OPAQUE")
                except Exception:
                    method = "OPAQUE"
                if method in {"BLEND", "HASHED", "CLIP"}:
                    nt.links.new(best.outputs['Alpha'], bsdf.inputs['Alpha'])

    log(f"材质处理完成，改动 {changed} 个")


def main():
    log(f"已打开：{bpy.data.filepath}")
    log(f"物体 {len(bpy.data.objects)} / 材质 {len(bpy.data.materials)} / 贴图 {len(bpy.data.images)}")

    fix_materials()

    # 统计一下有多少材质终于带上贴图了
    with_tex = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.node_tree is None:
            continue
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].is_linked:
                with_tex += 1
                break
    log(f"带贴图的材质：{with_tex}")

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
        log(f"参数不兼容，退回默认：{e}")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format='GLB',
            use_selection=False,
            export_animations=True,
        )

    if os.path.exists(out_path):
        log(f"导出成功：{out_path}  {os.path.getsize(out_path)/1048576:.1f} MB")
    else:
        log("导出失败")
        sys.exit(1)


main()
