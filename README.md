# 环境
 - OS: Ubuntu 26.04
 - GPU: NVIDIA RTX 4060 Laptop
 - NVIDIA 驱动 595.91.07
 - CUDA 12.8

# 安装
```bash
conda env create -f environment.yml
conda activate deepcad
```

# 获取官方代码

官方 DeepCAD 代码仓库不随本仓库分发，需自行克隆到当前目录：

```bash
git clone https://github.com/rundiwu/DeepCAD.git
```

- 论文：https://arxiv.org/abs/2105.09492
- 数据集与预训练权重：见下方，或官方仓库 README

# 数据与预训练权重

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

# 获取真实点云

```bash
cd dataset
python json2pc.py --only_test
```

# M1 数据处理与问题理解

## 目录

| 路径 | 内容 |
| --- | --- |
| `m1_sample/` | 原始样本 30 个（`m1.sh` 生成） |
| `m1_sample_cleaned/` | 清洗后保留的 20 个（统计只用这个目录） |
| `m1_sample_step/` | `m1_sample/` 导出的 STEP |
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
| `m1.sh` | 全流程：取样 → 导 STEP → 清洗 → 统计 → 生成 `cmd_seq.md` | 是 |
| `show.sh` | 弹窗显示 3D 模型，手动截图成 `.png` | 是 |

## 从零复现

```bash
cd m1
./m1.sh
```

3 张 `.png` 是 `show.sh` 手动截图，需要图形界面（纯 ssh 跑不了），不在 `m1.sh` 里：

```bash
conda run -n deepcad python ../DeepCAD/utils/show.py --src . --form json --num 3
```

# M2 CAD 自动重建

## 目录

| 路径 | 内容 |
| --- | --- |
| `m2_data/train_val_test_split.json` | 固定 100 个样本的名单 |
| `m2_data/cad_vec/` | 100 个输入 h5 |
| `results/` | 100 个重建结果 `*_vec.h5` |
| `results_step/` | 导出的 STEP，97 个 |

## 脚本

| 脚本 | 作用 | 需要 deepcad 环境 |
| --- | --- | --- |
| `get_sample.py` | 从官方 `test` 名单抽 100 个（种子 114514），写名单并打印 id | 否 |
| `m2.sh` | 抽样本 → 拷 h5 → 官方推理 → 导出 STEP | 是 |

```bash
cd m2 && ./m2.sh
```

## 结论

- 用官方 `test.py`，靠 `--data_root` 指向 `m2_data/` 只跑自选 100 个，不改官方源码
- 100 个全部推理成功，导出 STEP 97 个
- 3 个建不出：`00231240`、`00770426` 真值本身就建不出；`00823562` 是模型失败
- 自检（非 M3 正式指标）：`ACC_cmd 99.19%`、`ACC_param 97.17%`

# M3 质量评价

## 目录

| 路径 | 内容 |
| --- | --- |
| `m3_data/` | `--data_root`：自制名单、`cad_json/`、`cad_vec/`，以及生成的 `pc_cad/` |
| `results/` | 重建结果 `*_vec.h5` |
| `m3.csv` | 按短/中/长 + 总体的指标表 |

## 脚本

| 脚本 | 作用 | 需要 deepcad 环境 |
| --- | --- | --- |
| `get_sample.py n` | 从官方 `test` 抽 n 个（种子 114514），写名单并打印 id | 否 |
| `json2pc.py` | 官方点云脚本的副本，`DATA_ROOT` 指到 `m3_data` | 是 |
| `m3.py n_points` | 读 `results/` 算指标，写 `m3.csv` | 是 |
| `m3.sh n n_points` | 抽样本 → 生成真值点云 → 推理 → 评价 | 是 |

## 流程

```bash
cd m3
./m3.sh 1000 2000
```

第一个参数是样本数，第二个是每个模型采的点数（Chamfer Distance 用）

## 指标

| 指标 | 规则 |
| --- | --- |
| `ACC_cmd` | 命令类型对的命令数 / 总命令数 |
| `ACC_param` | 只统计命令类型对的命令、且只取该命令用到的参数，容差 3（Arc 的 `f`、Ext 的 `b,u` 严格相等）|
| `Generation_Success_Rate` | 建出**非空**实体算成功（`vec2CADsolid` 不报错且包围盒非空）|
| CD | mean / 去掉最大最小各 10% 的 mean / median，只对能算出 CD 的样本 |
| 分组 | 短 ≤20、中 21–40、长 >40 |

## 结论

- 三组趋势一致：短最好、长最差（ACC、成功率、CD 都是）
- 1000 个样本的结果见 `m3.csv`
- CD 只对能算出 CD 的样本统计，失败样本不参与；表里的 `count` 是样本数，不是 CD 的分母
- CD 的覆盖率、5 个代表案例放在报告 / PPT 里讲
