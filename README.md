# soarm101

SO-ARM101 机械臂微调与部署项目，基于 HuggingFace 预训练模型进行微调，目标是让模型成功部署到个人 SO-ARM101 机械臂上。

## 项目目标

以 [Full-Stack-Entity/so101-left-sota-pack](https://huggingface.co/datasets/Full-Stack-Entity/so101-left-sota-pack) 中的预训练模型为基础，优先对 **Diffusion Policy** 进行微调，使其适配自有机械臂的任务场景。

## 模型

| 模型 | 状态 | 说明 |
|------|------|------|
| Diffusion Policy | 微调中 | 优先目标 |
| ACT | 待定 | 备选方案 |
| SmolVLA | 待定 | 备选方案 |

## 目录结构

```
soarm101/
├── configs/          # 机器人硬件配置、相机标定等
├── data/             # 采集的演示数据（本地，不上传）
├── models/           # 微调后的模型权重（本地，不上传）
├── scripts/
│   ├── collect/      # 数据采集脚本
│   ├── train/        # 微调训练脚本
│   └── deploy/       # 推理部署脚本
├── notebooks/        # 实验分析与可视化
├── docs/             # 调试记录、实验日志
└── requirements.txt
```

## 环境

- **连接机械臂的设备**：笔记本电脑（直连 SO-ARM101）
- **训练/开发设备**：台式机
- **依赖框架**：[LeRobot](https://github.com/huggingface/lerobot)

## 快速开始

```bash
git clone git@github.com:xiaoms22/soarm101.git
cd soarm101
pip install -r requirements.txt
```

## 工作流

1. **笔记本**：连接机械臂，运行 `scripts/collect/` 采集演示数据
2. **台式机**：运行 `scripts/train/` 微调模型
3. **笔记本**：运行 `scripts/deploy/` 部署推理
