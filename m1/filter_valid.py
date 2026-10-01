import argparse
import glob
import json
import math
import os
import shutil

import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gen_seq", os.path.join(HERE, "gen_seq.py"))
gen_seq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_seq)

Curve = gen_seq.Curve
close = gen_seq._close
reorder_loop = gen_seq.reorder_loop

def _norm(a):
    return a % (2 * math.pi)

def _ang(p, c):
    return _norm(math.atan2(p[1] - c[1], p[0] - c[0]))

def check_loop(curves):
    """返回 [] 表示没问题，否则返回问题列表"""
    errs = []
    if not curves:
        return ["空环"]

    for i, cv in enumerate(curves):
        if cv.start is None or cv.end is None:
            errs.append("第{}条曲线缺端点".format(i))
    if errs:
        return errs

    n = len(curves)
    for i in range(n):
        if not close(curves[i].end, curves[(i + 1) % n].start):
            errs.append("第{}->{}条断链".format(i, (i + 1) % n))

    for i, cv in enumerate(curves):
        if cv.type != "Arc3D" or cv.mid is None:
            continue
        a_s, a_m, a_e = _ang(cv.start, cv.center), _ang(cv.mid, cv.center), _ang(cv.end, cv.center)
        ccw_span, cw_span = _norm(a_e - a_s), _norm(a_s - a_e)
        got = ccw_span if _norm(a_m - a_s) <= ccw_span + 1e-9 else cw_span
        want = cv.src.get("end_angle", 0.0)
        if abs(got - want) > 1e-6 and abs(got - (2 * math.pi - want)) > 1e-6:
            errs.append("第{}条弧 span={:.1f}° 与 end_angle={:.1f}° 不符"
                        .format(i, math.degrees(got), math.degrees(want)))
    return errs

def check_extrudes(ents):
    """检查拉伸特征是否引用了有效剖面

    实测有两类真坏的情况：
      - Extrude 的 profiles 是空列表 [] -> 建实体时直接抛 IndexError
      - Extrude 引用的 sketch/profile 不存在 -> 该特征被静默跳过，几何缺一块
    """
    problems = []
    for eid, e in ents.items():
        if not (isinstance(e, dict) and e.get("type") == "ExtrudeFeature"):
            continue
        refs = e.get("profiles") or []
        name = e.get("name", eid)
        if len(refs) == 0:
            problems.append("'{}': profiles 为空（没引用任何剖面）".format(name))
            continue
        for r in refs:
            if not isinstance(r, dict):
                problems.append("'{}': profiles 项不是字典".format(name))
                continue
            sid, pid = r.get("sketch"), r.get("profile")
            sk = ents.get(sid)
            if not (isinstance(sk, dict) and sk.get("type") == "Sketch"):
                problems.append("'{}': 引用的草图 {} 不存在".format(name, sid))
                continue
            prof = (sk.get("profiles") or {}).get(pid)
            if prof is None:
                problems.append("'{}': 引用的剖面 {}.{} 不存在".format(name, sid, pid))
                continue
            loops = prof.get("loops") or []
            if not loops or any(not L.get("profile_curves") for L in loops):
                problems.append("'{}': 剖面 {} 没有曲线".format(name, pid))
    return problems

def check_file(path, only_used=False):
    """返回 (是否OK, 问题描述列表)"""
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)

    ents = data.get("entities", {})
    problems = check_extrudes(ents)

    used = set()
    if only_used:
        for e in ents.values():
            if isinstance(e, dict) and e.get("type") == "ExtrudeFeature":
                for r in e.get("profiles") or []:
                    if isinstance(r, dict) and r.get("profile"):
                        used.add(r["profile"])

    n_prof = 0
    for eid, e in ents.items():
        if not (isinstance(e, dict) and e.get("type") == "Sketch"):
            continue
        for pn, prof in (e.get("profiles") or {}).items():
            if only_used and pn not in used:
                continue
            n_prof += 1
            for li, loop in enumerate(prof.get("loops", [])):
                curves = [Curve(c) for c in loop.get("profile_curves", [])]
                curves = reorder_loop(curves)
                errs = check_loop(curves)
                for msg in errs:
                    problems.append("{}.loop{}: {}".format(pn, li, msg))

    if n_prof == 0:
        problems.append("没有任何剖面")
    return (len(problems) == 0), problems

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "m1_sample"))
    ap.add_argument("--dst", default=os.path.join(HERE, "m1_sample_cleaned"))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only-used", action="store_true",
                    help="只检查被 Extrude 引用到的剖面（默认检查全部）")
    ap.add_argument("--max", type=int, default=None,
                    help="按文件名排序最多保留前 N 个（默认全部）")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.src, "*.json")))
    if not files:
        print("在 {} 下没找到 json".format(args.src))
        return

    os.makedirs(args.dst, exist_ok=True)
    ok_list, bad_list = [], []

    for f in files:
        try:
            ok, problems = check_file(f, only_used=args.only_used)
        except Exception as exc:
            ok, problems = False, ["读取失败: {}: {}".format(type(exc).__name__, exc)]
        name = os.path.basename(f)
        if ok:
            ok_list.append((name, f))
        else:
            bad_list.append((name, problems))

    ok_list.sort()
    n_valid = len(ok_list)
    if args.max is not None:
        ok_list = ok_list[:args.max]

    for name, f in ok_list:
        shutil.copy2(f, os.path.join(args.dst, name))
        if args.verbose:
            print("OK   {}".format(name))
    for name, problems in bad_list:
        if args.verbose:
            print("BAD  {}   {}".format(name, "; ".join(problems[:3])))

    print()
    print("共 {} 个文件:  有效 {}  剔除 {}  实际保留 {}".format(
        len(files), n_valid, len(bad_list), len(ok_list)))
    print("保留的已拷贝到: {}".format(args.dst))
    if bad_list:
        print()
        print("被剔除的文件（原因）:")
        for name, problems in bad_list:
            print("  {}  <- {}".format(name, problems[0]))
            for p in problems[1:3]:
                print("      {}".format(p))

if __name__ == "__main__":
    main()
