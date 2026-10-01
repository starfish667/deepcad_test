mkdir -p m1_sample
ls ../DeepCAD/data/cad_json/0000 | head -30 | while read -r file; do
    cp ../DeepCAD/data/cad_json/0000/$file m1_sample/
done
export PYTHONPATH=$PYTHONPATH:$(pwd)/../DeepCAD
conda run -n deepcad python ../DeepCAD/utils/export2step.py --src m1_sample --form json --num -1
