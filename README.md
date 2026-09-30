### 环境
 - OS: Ubuntu 26.04
 - GPU: NVIDIA RTX 4060 Laptop
 - NVIDIA 驱动 595.91.07
 - CUDA 12.1

### 安装
```bash
conda env create -f environment.yml
conda activate deepcad
```

### 获取官方代码（本仓库不包含）

官方 DeepCAD 代码仓库不随本仓库分发，需自行克隆到当前目录：

```bash
git clone https://github.com/rundiwu/DeepCAD.git
```

- 论文：https://arxiv.org/abs/2105.09492
- 数据集与预训练权重：见下方，或官方仓库 README

### 数据与预训练权重

官方仓库不包含数据，需自行下载解压。**以下命令均在 `DeepCAD/` 目录下执行**：

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

