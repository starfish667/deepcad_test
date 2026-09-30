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
- 数据集与预训练权重：见官方仓库 README（`data.tar` / `pretrained.tar`）
