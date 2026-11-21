"""Blender 无头导出 glTF (.glb)  v3

v3 改动：
- 删掉作者的制作面板（Text / Cube / Panel / 表情控制板），只留角色和武器
- 从全局图片池里强行找贴图，手动建 TEX_IMAGE 节点接到 Base Color
"""
import bpy
import os
import sys


def log(msg):
    print(f"[export] {msg}", flush=True)


KEYWORDS = ("base", "albedo", "diffuse", "color", "skin", "face", "hair",
            "cloth", "body", "tex", "texture", "jane")

DROP = ("text", "cube", "panel", "custom", "mouth", "outfit", "arrow",
        "control", "widget", "ik_", "marker", "empty", "label")


def clean_scene():
    """删掉制作面板、文字、参考方块，只留角色"""
    removed = []
    for obj in list(bpy.data.objects):
        low = (obj.name or "").lower()
        if any(k in low for k in DROP):
            # 但不要误删角色本体
            if "jane" in low or "dagger" in low:
                continue
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    log(f"删除辅助物 {len(removed)} 个：{removed[:12]}{'...' if len(removed) > 12 else ''}")
    return removed


def collect_image_nodes(node_tree, depth=0, seen=None):
    if seen is None:
        seen = set()
    if node_tree is None or depth > 5:
        return []
    if node_tree.name in seen:
        return []
    seen.add(node_tree.name)
    found = []
    for n in node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None:
            found.append(n)
        elif n.type == 'GROUP' and getattr(n, "node_tree", None) is not None:
            found.extend(collect_image_nodes(n.node_tree, depth + 1, seen))
    return found


def score_name(name):
    low = (name or "").lower()
    return sum(1 for k in KEYWORDS if k in low)


def fix_materials():
    changed = 0
    # 全局图片池（.blend 里打包的贴图）
    pool = []
    for img in bpy.data.images:
        try:
            if img.name and img.size[0] >= 8 and img.size[1] >= 8:
                pool.append(img)
        except Exception:
            pass
    log(f"图片池：{[(i.name, tuple(i.size)) for i in pool][:10]}")

    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes or mat.node_tree is None:
            continue
        nt = mat.node_tree

        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')
            out.location = (600, 0)

        link = out.inputs['Surface'].links[0] if out.inputs['Surface'].is_linked else None
        node = link.from_node if link else None
        goo_like = (node is not None and node.type == 'GROUP') or ("goo" in (mat.name or "").lower())

        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (300, 0)
            changed += 1

        if link is not None and (goo_like or node.type != 'BSDF_PRINCIPLED'):
            nt.links.remove(link)
        if not out.inputs['Surface'].is_linked:
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

        if bsdf.inputs['Base Color'].is_linked:
            continue

        # 1) 先在节点树里找
        best = None
        imgs = collect_image_nodes(nt)
        if imgs:
            imgs.sort(key=lambda n: -score_name(n.name + " " + (n.image.name or "")))
            best = imgs[0]

        # 2) 节点树里没有，就从全局图片池按名字猜
        if best is None and pool:
            ranked = sorted(pool, key=lambda i: -score_name(i.name))
            if score_name(ranked[0].name) > 0:
                best = nt.nodes.new('ShaderNodeTexImage')
                best.image = ranked[0]
                best.location = (-300, 0)
                log(f"材质 {mat.name} 用全局图片补上：{ranked[0].name}")

        if best is not None:
            nt.links.new(best.outputs['Color'], bsdf.inputs['Base Color'])
            changed += 1

    log(f"材质处理：改动 {changed}")


def main():
    log(f"打开：{bpy.data.filepath}")
    log(f"物体 {len(bpy.data.objects)} / 材质 {len(bpy.data.materials)} / 图片 {len(bpy.data.images)}")

    clean_scene()

    left = [o.name for o in bpy.data.objects]
    log(f"保留物体 {len(left)}：{left[:15]}")

    fix_materials()

    log("=== 网格顶点统计（应用修改器前）===")
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        base = len(ob.data.vertices)
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
            after = len(me.vertices)
            ev.to_mesh_clear()
        except Exception as e:
            after = f"求值失败:{e}"
        log(f"  {ob.name}: 原始 {base} 顶点 / 求值后 {after}")

    for o in bpy.data.objects:
        o.hide_set(False)
        o.hide_viewport = False
        o.hide_render = False

    out_path = os.path.abspath("Jane.glb")
    kwargs = dict(
        filepath=out_path,
        export_format='GLB',
        use_selection=False,
        export_apply=False,
        export_animations=True,
        export_skins=True,
        export_yup=True,
        export_image_format='AUTO',
    )
    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError as e:
        log(f"参数不兼容：{e}")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format='GLB',
            use_selection=False,
            export_animations=True,
        )

    if os.path.exists(out_path):
        log(f"导出成功 {os.path.getsize(out_path)/1048576:.1f} MB")
    else:
        log("导出失败")
        sys.exit(1)


main()
