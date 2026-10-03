import os
import sys
sys.path.append('../DeepCAD')
import csv
import h5py
import numpy as np
import pandas as pd
from cadlib.visualize import vec2CADsolid
from OCC.Core.Bnd import Bnd_Box                                                                                                                       
from OCC.Core.BRepBndLib import brepbndlib 
from joblib import Parallel, delayed
from scipy.spatial import cKDTree as KDTree
from utils import read_ply
from cadlib.visualize import CADsolid2pc
import random

cols=['count', 'ACC_cmd', 'ACC_param', 'Generation_Success_Rate', 'Average_Chamfer_Distance', 'Trimmed_Average_Chamfer_Distance', 'Median_Chamfer_Distance']
statistic_cols=['cmds', 'cor_cmds', 'params', 'cor_params', 'files', 'suc_files']
cats=['short', 'middle', 'long', 'total']

sta=np.zeros((len(cats), len(statistic_cols)), dtype=np.float64)
stacd=[[] for i in range(len(cats))]
res=np.zeros((len(cats), len(cols)), dtype=np.float64)

cmd_param=(
    (1, 2), 
    (1, 2, 3, 4), 
    (1, 2, 5), 
    (), 
    (), 
    tuple(range(6, 17))
)
N_POINTS=int(sys.argv[1])
ITA=3

def chamfer_dist(gt_pc, out_pc):
    gt_kdt=KDTree(gt_pc)
    d1,_=gt_kdt.query(out_pc)
    a1=np.mean(np.square(d1))

    out_kdt=KDTree(out_pc)
    d2,_=out_kdt.query(gt_pc)
    a2=np.mean(np.square(d2))

    return  a1+a2

def normalize_pc(pc):
    scale=np.max(np.abs(pc))
    pc=pc/scale
    return pc

def proc(id):
    h5_file='results/'+id+'_vec.h5'
    gt_pc_file='m3_data/pc_cad/'+id[:4]+'/'+id+'.ply'
    with h5py.File(h5_file, 'r') as f:
        out_vec=f['out_vec'][:].astype(np.float64)
        gt_vec=f['gt_vec'][:].astype(np.float64)
    res,cd=np.zeros((len(statistic_cols))),0
    res[0]=gt_vec.shape[0]
    res[4]=1
    for i in range(gt_vec.shape[0]):
        if gt_vec[i][0]==out_vec[i][0]:
            res[1]+=1
            res[2]+=len(cmd_param[int(gt_vec[i][0])])
            for j in cmd_param[int(gt_vec[i][0])]:
                if gt_vec[i][j]==out_vec[i][j] or ((j not in (4, 15, 16)) and abs(gt_vec[i][j]-out_vec[i][j])<ITA):
                    res[3]+=1
    ok=False
    try:
        shape=vec2CADsolid(out_vec)
        if shape is not None:
            b=Bnd_Box()
            brepbndlib.Add(shape, b)
            ok=not b.IsVoid()
    except Exception:
        ok=False
        return res, None
    if ok:
        res[5]=1
    if not os.path.exists(gt_pc_file):
        return res, None
    gt_pc=read_ply(gt_pc_file)
    idx=random.sample(list(range(gt_pc.shape[0])), N_POINTS)
    gt_pc=gt_pc[idx]

    try:
        out_pc=CADsolid2pc(shape, N_POINTS, id)
    except Exception:
        return res, None
    if np.max(np.abs(out_pc)) > 2:
        out_pc = normalize_pc(out_pc)
    cd=chamfer_dist(gt_pc, out_pc)
    return res, cd

ls=Parallel(n_jobs=-1)(delayed(proc)(x[:8]) for x in os.listdir('results'))
for arr, cd, in ls:
    cat=0
    if arr[0]<=20:
        cat=0
    elif arr[0]<=40:
        cat=1
    else:
        cat=2
    sta[cat]+=arr
    if cd!=None:
        stacd[cat].append(cd)

for i in range(len(cats)-1):
    sta[-1]+=sta[i]
    stacd[-1]+=stacd[i]
for i in range(len(cats)):
    res[i][0]=sta[i][4]
    res[i][1]=sta[i][1]/sta[i][0]
    res[i][2]=sta[i][3]/sta[i][2]
    res[i][3]=sta[i][5]/sta[i][4]
    arr=np.array(stacd[i])
    arr=np.sort(arr)
    n=len(arr)
    k=int(n*0.1)
    res[i][4]=np.mean(arr)
    res[i][5]=np.mean(arr[k:-k])
    res[i][6]=np.median(arr)

df=pd.DataFrame(res, columns=cols)
df.insert(0, 'category', cats)
df.to_csv('m3.csv', index=False, encoding='utf-8-sig')