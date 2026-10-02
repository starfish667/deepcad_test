import json
import random
with open("../DeepCAD/data/train_val_test_split.json", "r") as f:
    rng=random.Random(114514)
    dataset=json.load(f)
    files=dataset['test']
    files=rng.sample(files, 100)
    with open("m2_data/train_val_test_split.json", "w") as w:
        json.dump({"train":[], "validation":[], "test":files}, w)
    for file in files:
        print(file)