import os
import csv
import json

MAX_N_EXT=10
MAX_N_LOOPS=6
MAX_N_CURVES=15
MAX_TOTAL_LEN=60

cols=['id', 'seq_len', 'line', 'arc', 'circle', 'sol', 'extrude']


def statistic(file_name):
    with open(os.path.join("m1_sample_cleaned", file_name), "r") as f:
        model=json.load(f)
    res={'id':file_name.split('.')[0], 'seq_len':0, 'line':0, 'arc':0, 'circle':0, 'sol':0, 'extrude':0}
    max_loops=0
    max_curves=0
    for element in model['sequence']:
        if element['type']=='Sketch':
            continue
        entity=model['entities'][element['entity']]
        for prof in entity['profiles']:
            sketch=model['entities'][prof['sketch']]
            loops=sketch['profiles'][prof['profile']]['loops']
            if len(loops)>max_loops:
                max_loops=len(loops)
            for loop in loops:
                curves=loop['profile_curves']
                if len(curves)>max_curves:
                    max_curves=len(curves)
                res['sol']+=1
                for curve in curves:
                    ctype=curve['type']
                    if ctype=='Line3D':
                        res['line']+=1
                    elif ctype=='Arc3D':
                        res['arc']+=1
                    elif ctype=='Circle3D':
                        res['circle']+=1
            res['extrude']+=1
    res['seq_len']=res['line']+res['arc']+res['circle']+res['sol']+res['extrude']
    ok=res['extrude']<=MAX_N_EXT and max_loops<=MAX_N_LOOPS and max_curves<=MAX_N_CURVES and res['seq_len']+1<=MAX_TOTAL_LEN
    return res, ok


def total(rows):
    tot={'id':'tot'}
    for c in cols[1:]:
        tot[c]=sum(it[c] for it in rows)
    return tot


rows=[]
kept=[]
for name in sorted(os.listdir('m1_sample_cleaned')):
    res, ok=statistic(name)
    rows.append(res)
    if ok:
        kept.append(res)


with open('m1_all.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows+[total(rows)])

with open('m1_lt60.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(kept+[total(kept)])

print('m1_all.csv', len(rows))
print('m1_lt60.csv', len(kept))
for it in rows:
    if it not in kept:
        print('  drop', it['id'], it['seq_len'])
