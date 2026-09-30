### 环境
 - OS: Ubuntu 26.04
 - GPU: NVIDIA RTX 4060 Laptop
 - NVIDIA 驱动 595.91.07
 - CUDA 12.1

### 安装
```
conda env create -f environment.yml
conda activate deepcad
```

### 获取官方代码（本仓库不包含）

官方 DeepCAD 代码仓库不随本仓库分发（已加入 `.gitignore`），需自行克隆到当前目录：

```bash
git clone https://github.com/rundiwu/DeepCAD.git
```

- 论文：https://arxiv.org/abs/2105.09492
- 数据集与预训练权重：见下方，或官方仓库 README

### 数据与预训练权重

官方仓库不包含数据，需自行下载解压。**以下命令均在 `DeepCAD/` 目录下执行**：

```bash
cd DeepCAD

# 1) 下载（约 208 MB + 80 MB）
curl -LO http://www.cs.columbia.edu/cg/deepcad/data.tar
curl -LO http://www.cs.columbia.edu/cg/deepcad/pretrained.tar

# 2) 解压外层
tar xzf data.tar         # 得到 data/
tar xzf pretrained.tar   # 得到 pretrained/

# 3) 解压内层数据集
tar xzf data/cad_json.tar.gz -C data/   # 得到 data/cad_json/
tar xzf data/cad_vec.tar.gz  -C data/   # 得到 data/cad_vec/

# 4) 预训练权重移到 proj_log/ 下
mkdir -p proj_log && mv pretrained proj_log/pretrained
```

解压后的目录结构：

```
DeepCAD/
├── data/
│   ├── cad_json/                  原始建模记录（*.json，约 21.5 万个，M1 用）
│   ├── cad_vec/                   向量化表示（*.h5，约 17.9 万个，模型输入）
│   ├── train_val_test_split.json  数据划分
│   └── pc_cad/                    真值点云（由 json2pc.py 生成，算 Chamfer 距离用）
└── proj_log/
    └── pretrained/
        ├── model/ckpt_epoch1000.pth              自编码器权重
        └── lgan_1000/model/ckpt_epoch200000.pth  潜在 GAN 权重
```

数据划分：train **161,240** / validation **8,946** / test **8,052**。

### 生成真值点云（评测 Chamfer 距离时需要）

```bash
cd DeepCAD/dataset
python json2pc.py --only_test     # 输出到 DeepCAD/data/pc_cad/
```

> ⚠️ 仓库内脚本使用相对路径（如 `../data`），**必须在对应子目录下运行**，
> 例如 `dataset/json2pc.py` 要在 `dataset/` 里跑、`utils/export2step.py` 要在 `utils/` 里跑。
