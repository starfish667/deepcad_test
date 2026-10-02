import sys
import json
import random
n=int(sys.argv[1])
with open("../DeepCAD/data/train_val_test_split.json", "r") as f:
    rng=random.Random(114514)
    dataset=json.load(f)
    files=dataset['test']
    files=rng.sample(files, n)
    with open("m3_data/train_val_test_split.json", "w") as w:
        json.dump({"train":[], "validation":[], "test":files}, w)
    for file in files:
        print(file)