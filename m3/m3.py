import os
import sys
sys.path.append('../DeepCAD')
import csv
import h5py
import numpy as np
from cadlib.visualize import vec2CADsolid
from OCC.Core.Bnd import Bnd_Box                                                                                                                       
from OCC.Core.BRepBndLib import brepbndlib 
import warnings
_sw = warnings.showwarning
warnings.showwarning = lambda msg, *a, **k: None if "Call to deprecated" in str(msg) else _sw(msg, *a, **k)

cols=['category', 'count', 'ACC_cmd', 'ACC_param', 'Generation_Success_Rate', 'Average_Chamfer_Distance', 'Trimmed_Average_Chamfer_Distance', 'Median_Chamfer_Distance']
statistic_cols=['cmds', 'cor_cmds', 'params', 'cor_params', 'files', 'suc_files', 'CD']
cats=['short', 'middle', 'long', 'total']

statistic={
    'short':{}, 
    'middle':{}, 
    'long':{}, 
    'total':{}
}
for cat in cats:
    for col in statistic_cols:
        statistic[cat][col]=(0 if col!='CD' else [])
cmd_param=[
    [1, 2], 
    [1, 2, 3, 4], 
    [1, 2, 5], 
    [], 
    [], 
    [i for i in range(6, 17)]
]

# def cd

def analyze(path):
    with h5py.File(path, 'r') as f:
        gt_vec=f['gt_vec'][:]
        out_vec=f['out_vec'][:]
        n,m=gt_vec.shape
        cat=''
        if n<=20:
            cat='short'
        elif n<=40:
            cat='middle'
        else:
            cat='long'
        statistic[cat]['cmds']+=n
        statistic[cat]['files']+=1
        ok=False
        try:
            shape=vec2CADsolid(out_vec)
            if shape is not None:
                b=Bnd_Box()
                brepbndlib.Add(shape, b)
                ok=not b.IsVoid()
        except Exception:
            ok=False
        if ok:
            statistic[cat]['suc_files']+=1
        cor_cmds,params,cor_params=0,0,0
        ita=3
        for i in range(n):
            if gt_vec[i][0]==out_vec[i][0]:
                cor_cmds+=1
                params+=len(cmd_param[gt_vec[i][0]])
                for j in cmd_param[gt_vec[i][0]]:
                    if gt_vec[i][j]==out_vec[i][j] or ((j not in (4, 15, 16)) and abs(gt_vec[i][j]-out_vec[i][j])<ita):
                        cor_params+=1
                    
                
        statistic[cat]['cor_cmds']+=cor_cmds
        statistic[cat]['params']+=params
        statistic[cat]['cor_params']+=cor_params

        statistic[cat]['CD'].append(0)


for file_name in os.listdir('results'):
    path=os.path.join('results', file_name)
    analyze(path)

for cat in cats[0:-1]:
    for col in statistic_cols:
        statistic['total'][col]+=statistic[cat][col]

res=[
    {'category':'short'}, 
    {'category':'middle'}, 
    {'category':'long'}, 
    {'category':'total'}
]
for i in range(len(cats)):
    sta=statistic[cats[i]]
    res[i]['count']=sta['files']
    res[i]['ACC_cmd']=sta['cor_cmds']/sta['cmds']
    res[i]['ACC_param']=sta['cor_params']/sta['params']
    arr=np.array(sta['CD'])
    res[i]['Average_Chamfer_Distance']=np.mean(arr)
    res[i]['Median_Chamfer_Distance']=np.median(arr)
    arr=np.sort(arr)
    k=int(len(arr)*0.1)
    res[i]['Trimmed_Average_Chamfer_Distance']=np.mean(arr[k:len(arr)-k])
    res[i]['Generation_Success_Rate']=sta['suc_files']/sta['files']

with open('m3.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(res)