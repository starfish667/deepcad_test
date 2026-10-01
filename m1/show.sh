export PYTHONPATH=$PYTHONPATH:$(pwd)/../DeepCAD
conda run -n deepcad python ../DeepCAD/utils/show.py --src m1_sample --form json --num 5