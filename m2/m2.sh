mkdir -p m2_data
conda run -n deepcad python get_sample.py | while read it; do
IFS='/' read -ra arr <<< "${it}"
dir=${arr[0]}
file=${arr[1]}
mkdir -p m2_data/cad_vec/$dir
cp ../DeepCAD/data/cad_vec/$it.h5 m2_data/cad_vec/$dir/
done
export PYTHONPATH=$PYTHONPATH:$(pwd)/../DeepCAD
conda run -n deepcad python ../DeepCAD/test.py --exp_name pretrained --mode rec --ckpt 1000 -g 0 --data_root m2_data -o results --proj_dir ../DeepCAD/proj_log
conda run -n deepcad python ../DeepCAD/utils/export2step.py --src results --num -1