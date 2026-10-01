### 环境
 - OS: Ubuntu 26.04
 - GPU: NVIDIA RTX 4060 Laptop
 - NVIDIA 驱动 595.91.07
 - CUDA 12.8

### 安装
```bash
conda env create -f environment.yml
conda activate deepcad
```

### 获取官方代码

官方 DeepCAD 代码仓库不随本仓库分发，需自行克隆到当前目录：

```bash
git clone https://github.com/rundiwu/DeepCAD.git
```

- 论文：https://arxiv.org/abs/2105.09492
- 数据集与预训练权重：见下方，或官方仓库 README

### 数据与预训练权重

官方仓库不包含数据，需自行下载解压。

```bash
cd DeepCAD

curl -LO http://www.cs.columbia.edu/cg/deepcad/data.tar
curl -LO http://www.cs.columbia.edu/cg/deepcad/pretrained.tar

tar xzf data.tar
tar xzf pretrained.tar

tar xzf data/cad_json.tar.gz -C data/
tar xzf data/cad_vec.tar.gz  -C data/

mkdir -p proj_log && mv pretrained proj_log/pretrained
```

### 获取真实点云

```bash
cd dataset
python json2pc.py --only_test
```

# M1 数据处理与问题理解

## 目录

| 路径 | 内容 |
| --- | --- |
| `m1_sample/` | 原始样本 30 个（从 `DeepCAD/data/cad_json/0000` 抽取） |
| `m1_sample_cleaned/` | 清洗后保留的 20 个（统计只用这个目录） |
| `m1_sample_step/` | `m1_sample/` 导出的 STEP 文件 |
| `00000061.json` / `.png` / `.step` | 挑出来讲解的 3 个零件 |
| `00000069.json` / `.png` / `.step` | 同上 |
| `00000070.json` / `.png` / `.step` | 同上 |
| `sketch.md` | 3 个零件的草图曲线清单 |
| `cmd_seq.md` | 3 个零件的完整命令序列（草图 + 拉伸 + 平面 transform） |
| `m1_all.csv` | 20 个样本的命令统计 |
| `m1_lt60.csv` | 其中通过论文四个上限的 17 个 |

## 脚本

| 脚本 | 作用 | 需要 deepcad 环境 |
| --- | --- | --- |
| `m1.sh` | 取 30 个样本，并导出 STEP | 是 |
| `show.sh` | 弹窗显示 3D 模型（手动截图） | 是 |
| `filter_valid.py` | 清洗坏文件 → `m1_sample_cleaned/` | 否 |
| `gen_seq.py` | 生成 `cmd_seq.md` | 否 |
| `analyze.py` | 生成两份统计 CSV | 否 |

## A. 统计流程（20 个样本）

```bash
cd m1

# 1) 取 30 个原始样本，并导出 STEP 到 m1_sample_step/
./m1.sh

# 2) 清洗：剔掉「拉伸没有引用任何剖面」的坏文件，按文件名排序保留前 20 个
python3 filter_valid.py --max 20

# 3) 输出命令统计
python3 analyze.py
```

产物：

| 产物 | 内容 |
| --- | --- |
| `m1_sample/` | 30 个原始 json |
| `m1_sample_step/` | 26 个 STEP |
| `m1_sample_cleaned/` | 清洗后保留的 20 个 json |
| `m1_all.csv` | 20 行命令统计 |
| `m1_lt60.csv` | 17 行命令统计 |

> `00000076` / `00000175` / `00000176` / `00000177` 这 4 个 `profiles` 为空，建不出实体，所以 STEP 只有 26 个；`00000073` 能建出实体但几何不对（有个拉伸是空的，被静默跳过），仍会被清洗掉。

## B. 3 个讲解样本

```bash
cd m1

# 0) 从样本里挑 3 个放到当前目录
cp m1_sample/00000061.json m1_sample/00000069.json m1_sample/00000070.json .

# 1) 弹窗显示 3D 模型，手动截图存成 00000061.png / 00000069.png / 00000070.png
#    需要图形界面，无头环境（纯 ssh）跑不起来
conda run -n deepcad python ../DeepCAD/utils/show.py --src . --form json --num 3

# 2) 导出 STEP
conda run -n deepcad python ../DeepCAD/utils/export2step.py --src . --form json --num -1 -o .

# 3) 生成命令序列
python3 gen_seq.py
```

产物：`cmd_seq.md`、`00000061/69/70.png`、`00000061/69/70.step`

## C. 从零复现

```bash
cd m1
./m1.sh
python3 filter_valid.py --max 20
python3 analyze.py
cp m1_sample/00000061.json m1_sample/00000069.json m1_sample/00000070.json .
python3 gen_seq.py
```

## 结果

`analyze.py` 的口径与论文 / `cad_vec` 一致：每个「拉伸 → 剖面引用 → 环」记 1 个 `SOL` 加该环的曲线数，每个「拉伸 → 剖面引用」记 1 个 `extrude`。

```
seq_len = line + arc + circle + sol + extrude
```

| | 样本数 | seq_len | line | arc | circle | sol | extrude |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `m1_all.csv` | 20 | 536 | 242 | 92 | 39 | 97 | 66 |
| `m1_lt60.csv` | 17 | 186 | 57 | 42 | 19 | 39 | 29 |

被四个上限筛掉的 3 个：

| 文件 | 超限原因 |
| --- | --- |
| `00000062` | `ext=26>10`、`curves=19>15`、`seq_len=204>59` |
| `00000069` | `seq_len=90>59` |
| `00000137` | `loops=18>6` |

清洗掉的 5 个（`profiles` 为空，无法建实体）：

```
00000073  00000076  00000175  00000176  00000177
```
