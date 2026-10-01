#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成「建模命令序列」文件（Markdown，内容用 ``` 套起来）

扫描本脚本所在目录下的 *.json（DeepCAD 的 cad_json 格式），
按 sequence 的顺序逐步输出：草图（含曲线与坐标）→ 拉伸（含参数）。

★ 关于顺序：json 里一个 loop 的曲线是「无序集合」，方向和顺序都不保证。
  官方 cadlib/sketch.py 的 Loop.reorder() 会重排成
  「从左下角起点开始 + 逆时针」的连续链条，本脚本移植了同样的逻辑。
  想对照原始顺序，用 --raw。

用法:
    python3 gen_seq.py                 # 合并输出 cmd_seq.md
    python3 gen_seq.py --split         # 每个 json 一个 <名字>_seq.md
    python3 gen_seq.py --raw           # 不做重排，照 json 原样输出（对照用）
    python3 gen_seq.py --dir m1_sample # 扫别的目录
    python3 gen_seq.py --unit m        # 长度用米（默认 mm）

只依赖标准库。
"""
import argparse
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CMD_LETTER = {"Line3D": "L", "Arc3D": "A", "Circle3D": "R"}
OP_SHORT = {
    "NewBodyFeatureOperation": "NewBody",
    "JoinFeatureOperation": "Join",
    "CutFeatureOperation": "Cut",
    "IntersectFeatureOperation": "Intersect",
}
EXT_SHORT = {
    "OneSideFeatureExtentType": "OneSide",
    "SymmetricFeatureExtentType": "Symmetric",
    "TwoSidesFeatureExtentType": "TwoSides",
}


# ----------------------------------------------------------------------
# 小工具
# ----------------------------------------------------------------------
def _xy(p):
    return None if not p else (p["x"], p["y"])


def _close(a, b, atol=1e-8, rtol=1e-5):
    """两点是否视为重合。

    容差对齐官方的 np.allclose 默认值(atol=1e-8, rtol=1e-5)。
    json 里相邻曲线的公共端点可能存在 ~1e-9 米的微小差异，
    容差太严(比如 1e-9)会把正常的环误判成断链。
    """
    if a is None or b is None:
        return False
    return (abs(a[0] - b[0]) <= atol + rtol * abs(b[0]) and
            abs(a[1] - b[1]) <= atol + rtol * abs(b[1]))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


class Curve(object):
    """一条曲线（可反转方向），字段与 json 对应"""

    def __init__(self, src):
        self.src = src
        self.type = src.get("type")
        self.center = None
        self.mid = None
        if self.type == "Line3D":
            self.start = _xy(src.get("start_point"))
            self.end = _xy(src.get("end_point"))
        elif self.type == "Arc3D":
            self.start = _xy(src.get("start_point"))
            self.end = _xy(src.get("end_point"))
            self.center = _xy(src.get("center_point"))
            r = src.get("radius", 0.0)
            # ★ mid 必须按官方的算法：用 reference_vector + (start_angle+end_angle)/2 旋转，
            #   不能拿 start_point 去算。因为 reference_vector 不一定指向 start_point
            #   （实测有指向 end_point 的情况），拿 start_point 算会跑到互补的另一条弧上。
            ref = src.get("reference_vector")
            if ref:
                a_ref = math.atan2(ref["y"], ref["x"])
                mid_ang = a_ref + (src.get("start_angle", 0.0) + src.get("end_angle", 0.0)) / 2.0
            elif self.start is not None:
                a0 = math.atan2(self.start[1] - self.center[1], self.start[0] - self.center[0])
                mid_ang = a0 + src.get("end_angle", 0.0) / 2.0
            else:
                mid_ang = 0.0
            self.mid = (self.center[0] + r * math.cos(mid_ang),
                        self.center[1] + r * math.sin(mid_ang))
        elif self.type == "Circle3D":
            self.center = _xy(src.get("center_point"))
            r = src.get("radius", 0.0)
            self.start = (self.center[0] - r, self.center[1])   # 与官方 Circle.start_point 一致
            self.end = self.start
        else:
            self.start = self.end = None

    @property
    def is_circle(self):
        return self.type == "Circle3D"

    def reverse(self):
        if self.type in ("Line3D", "Arc3D"):
            self.start, self.end = self.end, self.start
        # 圆反向没有意义

    def direction(self, from_start=True):
        if self.type == "Line3D":
            return _sub(self.end, self.start)
        if self.type == "Arc3D":
            return _sub(self.mid, self.start) if from_start else _sub(self.end, self.mid)
        if self.type == "Circle3D":
            return _sub(self.center, self.start)
        return (0.0, 0.0)


# ----------------------------------------------------------------------
# 重排（移植自官方 cadlib/sketch.py 的 Loop.reorder / Profile.reorder）
# ----------------------------------------------------------------------
def _is_chain(cs):
    """这组曲线是否首尾相接并闭合"""
    if not cs:
        return False
    n = len(cs)
    for i in range(n):
        if cs[i].start is None or cs[i].end is None:
            return False
        if not _close(cs[i].end, cs[(i + 1) % n].start):
            return False
    return True


def _walk_chain(curves):
    """图遍历强接：从最左下起点出发，逐段找能接上的曲线（不够就反向）。接不上返回 None。"""
    cs = [Curve(c.src) for c in curves]        # 拷贝，避免改动原对象
    n = len(cs)
    if n == 0:
        return None
    used = [False] * n
    si = min(range(n), key=lambda i: (cs[i].start[0], cs[i].start[1]))
    used[si] = True
    order = [cs[si]]
    for _ in range(n - 1):
        tip = order[-1].end
        for j in range(n):
            if used[j]:
                continue
            if _close(cs[j].start, tip):
                used[j] = True
                order.append(cs[j])
                break
            if _close(cs[j].end, tip):
                cs[j].reverse()
                used[j] = True
                order.append(cs[j])
                break
        else:
            return None
    return order if _is_chain(order) else None


def reorder_loop(curves):
    """从左下角起点开始 + 逆时针。

    先跑官方那套启发式（与官方一致）；如果结果仍然断链，
    再用图遍历强接（官方启发式遇到顺序很乱的环会失败）。
    """
    out = _reorder_loop_official(curves)
    if _is_chain(out):
        return out
    walk = _walk_chain(curves)
    if walk is not None:
        return _ensure_ccw(walk)
    return out


def _ensure_ccw(curves):
    if not curves or curves[0].is_circle or curves[-1].is_circle:
        return curves
    start_vec = curves[0].direction(from_start=True)
    end_vec = curves[-1].direction(from_start=False)
    if _cross(end_vec, start_vec) <= 0:
        for cv in curves:
            cv.reverse()
        curves.reverse()
    return curves


def _reorder_loop_official(curves):
    """从左下角起点开始 + 逆时针（移植自官方 cadlib/sketch.py）"""
    if len(curves) <= 1:
        return curves
    start_idx, sx, sy = 0, float("inf"), float("inf")

    # 1) 修正第一条的方向
    if _close(curves[0].start, curves[1].start) or _close(curves[0].start, curves[1].end):
        curves[0].reverse()

    # 2) 逐条把方向接上；同时找 start_point 最左下的曲线
    for i, cv in enumerate(curves):
        if i < len(curves) - 1 and _close(cv.end, curves[i + 1].end):
            curves[i + 1].reverse()
        if cv.start is None:
            continue
        if cv.start[0] < sx or (_close((cv.start[0], 0), (sx, 0)) and cv.start[1] < sy):
            start_idx, sx, sy = i, cv.start[0], cv.start[1]

    # 3) 旋转到 start_idx 开头
    curves = curves[start_idx:] + curves[:start_idx]

    # 4) 保证逆时针（首尾是圆时跳过）
    if curves[0].is_circle or curves[-1].is_circle:
        return curves
    start_vec = curves[0].direction(from_start=True)
    end_vec = curves[-1].direction(from_start=False)
    if _cross(end_vec, start_vec) <= 0:
        for cv in curves:
            cv.reverse()
        curves.reverse()
    return curves


def loop_bbox_min(curves):
    xs, ys = [], []
    for cv in curves:
        for p in (cv.start, cv.end, cv.mid, cv.center):
            if p is not None:
                xs.append(p[0])
                ys.append(p[1])
    return (min(xs), min(ys)) if xs else (0.0, 0.0)


def reorder_profile(loops):
    """多个环按包围盒左下角排序（先 x 后 y）"""
    if len(loops) <= 1:
        return loops
    return sorted(loops, key=lambda cv: loop_bbox_min(cv))


# ----------------------------------------------------------------------
# 排版
# ----------------------------------------------------------------------
def fmt_pt(p, scale, nd=2):
    if p is None:
        return "(?, ?)"
    return "({:.{n}f}, {:.{n}f})".format(p[0] * scale, p[1] * scale, n=nd)


def curve_text(cv, scale, idx):
    src = cv.src
    t = cv.type
    letter = CMD_LETTER.get(t, "?")
    head = "[{:>2d}] {}  {:<9s}".format(idx, letter, t)

    if t == "Line3D":
        body = "{} -> {}".format(fmt_pt(cv.start, scale), fmt_pt(cv.end, scale))
    elif t == "Arc3D":
        body = "{} -> {}".format(fmt_pt(cv.start, scale), fmt_pt(cv.end, scale))
        body += "  center={} r={:.2f}".format(fmt_pt(cv.center, scale),
                                              src.get("radius", 0) * scale)
        body += " sweep={:.1f}\u00b0".format(math.degrees(src.get("end_angle", 0.0)))
    elif t == "Circle3D":
        body = "center={} r={:.2f}".format(fmt_pt(cv.center, scale),
                                           src.get("radius", 0) * scale)
    else:
        body = "(未知类型)"
    return "        " + head + "  " + body


def sketch_block(ent, scale, reorder):
    out = []
    profiles = ent.get("profiles") or {}
    if not profiles:
        out.append("    (该草图没有剖面)")
        return out
    for pid, prof in profiles.items():
        loops = []
        for loop in prof.get("loops", []):
            curves = [Curve(c) for c in loop.get("profile_curves", [])]
            if reorder:
                curves = reorder_loop(curves)
            loops.append(curves)
        if reorder:
            loops = reorder_profile(loops)
        for li, curves in enumerate(loops):
            out.append("    profile {}  loop{}: {} 条曲线".format(pid, li, len(curves)))
            for ci, cv in enumerate(curves):
                out.append(curve_text(cv, scale, ci))
    return out


def fmt_vec(v, nd=3):
    def f(x):
        x = v.get(x, 0.0)
        return 0.0 if x == 0 else x      # 去掉 -0.0
    return "({:.{n}f}, {:.{n}f}, {:.{n}f})".format(f("x"), f("y"), f("z"), n=nd)


def extrude_block(ent, scale, ents):
    """ExtrudeFeature -> 若干行（参数 + 草图平面 transform）"""
    op = OP_SHORT.get(ent.get("operation"), ent.get("operation"))
    et = EXT_SHORT.get(ent.get("extent_type"), ent.get("extent_type"))

    def dist(key):
        d = (ent.get(key) or {}).get("distance") or {}
        v = d.get("value")
        return None if v is None else v * scale

    e1, e2 = dist("extent_one"), dist("extent_two")
    parts = ["{} / {}".format(op, et)]
    if e1 is not None:
        parts.append("e1={:.2f}".format(e1))
    if ent.get("extent_type") == "TwoSidesFeatureExtentType" and e2 is not None:
        parts.append("e2={:.2f}".format(e2))

    refs = []
    for r in ent.get("profiles") or []:
        if isinstance(r, dict):
            refs.append("{}.{}".format(r.get("sketch"), r.get("profile")))
    if refs:
        parts.append("拉 " + ", ".join(refs))

    lines = ["        " + "  ".join(parts)]

    # 草图平面 transform（json 里存在 Sketch 上，被 Extrude 引用）
    seen = []
    for r in ent.get("profiles") or []:
        if isinstance(r, dict) and r.get("sketch") not in seen:
            seen.append(r.get("sketch"))
    for sid in seen:
        t = (ents.get(sid) or {}).get("transform")
        if not t:
            continue
        o = t.get("origin", {})
        lines.append("        平面 transform (来自 {}):".format(sid))
        lines.append("            原点 (px,py,pz) = ({:.2f}, {:.2f}, {:.2f}) mm".format(
            o.get("x", 0) * scale, o.get("y", 0) * scale, o.get("z", 0) * scale))
        lines.append("            法向 z_axis = {}   x_axis = {}   y_axis = {}".format(
            fmt_vec(t.get("z_axis", {})), fmt_vec(t.get("x_axis", {})), fmt_vec(t.get("y_axis", {}))))
    return lines


def json_to_text(path, scale, unit_name, reorder):
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)

    ents = data.get("entities", {})
    seq = data.get("sequence", [])
    lines = ["# 操作序列: 共 {} 步   (长度单位: {})".format(len(seq), unit_name),
             "# 曲线顺序: {}".format("已重排(左下角起点+逆时针)" if reorder else "json 原始顺序"),
             ""]

    for i, step in enumerate(seq):
        ent = ents.get(step.get("entity")) or {}
        typ = step.get("type") or ent.get("type")
        lines.append("[{}] {:<9s} {!r}".format(i, typ, ent.get("name", "")))
        if typ == "Sketch":
            lines.extend(sketch_block(ent, scale, reorder))
        elif typ == "ExtrudeFeature":
            lines.extend(extrude_block(ent, scale, ents))
        else:
            lines.append("        (未知操作类型)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=HERE, help="要扫描的目录（默认=本脚本所在目录）")
    ap.add_argument("--unit", default="mm", choices=["mm", "m"], help="长度单位")
    ap.add_argument("--split", action="store_true", help="每个 json 输出一个单独文件")
    ap.add_argument("--raw", action="store_true", help="不做重排，照 json 原样输出")
    ap.add_argument("--out", default=None, help="合并模式的输出文件名（默认 cmd_seq.md）")
    args = ap.parse_args()

    scale = 1000.0 if args.unit == "mm" else 1.0
    unit_name = "mm" if args.unit == "mm" else "m"
    reorder = not args.raw

    files = sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not files:
        print("在 {} 下没找到 *.json".format(args.dir))
        return

    print("找到 {} 个 json".format(len(files)))
    combined = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        text = json_to_text(f, scale, unit_name, reorder)
        if args.split:
            out_path = os.path.join(args.dir, "{}_seq.md".format(stem))
            with open(out_path, "w", encoding="utf-8") as fp:
                fp.write("`{}`\n\n```\n{}```\n".format(os.path.basename(f), text))
            print("  -> {}".format(os.path.basename(out_path)))
        else:
            combined.append("`{}`\n\n```\n{}```\n".format(os.path.basename(f), text))

    if not args.split:
        out_path = os.path.join(args.dir, args.out or "cmd_seq.md")
        with open(out_path, "w", encoding="utf-8") as fp:
            fp.write("\n".join(combined))
        print("  -> {}".format(os.path.basename(out_path)))


if __name__ == "__main__":
    main()
