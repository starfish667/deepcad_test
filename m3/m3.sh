mkdir -p m3_data
conda run -n deepcad python get_sample.py $1 | while read it; do
dir=${it%%/*}
mkdir -p m3_data/cad_vec/$dir
mkdir -p m3_data/cad_json/$dir
cp ../DeepCAD/data/cad_vec/$it.h5 m3_data/cad_vec/$dir/
cp ../DeepCAD/data/cad_json/$it.json m3_data/cad_json/$dir/
done
echo "sample copy accomplished"

export PYTHONPATH=$PYTHONPATH:$(pwd)/../DeepCAD

conda run -n deepcad python json2pc.py --only_test
echo "points cloud generation accomplished"

conda run -n deepcad python ../DeepCAD/test.py --exp_name pretrained --mode rec --ckpt 1000 -g 0 --data_root m3_data -o results --proj_dir ../DeepCAD/proj_log
# conda run -n deepcad python ../DeepCAD/utils/export2step.py --src results --num -1
echo "reconstruction accomplished"

conda run -n deepcad python m3.py $2
echo "evaluation accomplished"