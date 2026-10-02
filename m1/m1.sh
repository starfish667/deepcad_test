mkdir -p m1_sample
ls ../DeepCAD/data/cad_json/0000 | head -30 | while read -r file; do
    cp ../DeepCAD/data/cad_json/0000/$file m1_sample/
done
export PYTHONPATH=$PYTHONPATH:$(pwd)/../DeepCAD
conda run -n deepcad python ../DeepCAD/utils/export2step.py --src m1_sample --form json --num -1
mkdir -p m1_sample_cleaned
grep -L '"profiles": \[\]' m1_sample/*.json | sort | head -20 | xargs -I{} cp {} m1_sample_cleaned/
python3 analyze.py
cp m1_sample/00000061.json m1_sample/00000069.json m1_sample/00000070.json .
python3 gen_seq.py
conda run -n deepcad python ../DeepCAD/utils/export2step.py --src . --form json --num -1 -o .
