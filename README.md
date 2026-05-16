# soarm101

SO-ARM101 机械臂微调与部署项目，基于 HuggingFace 预训练模型进行微调，目标是让模型成功部署到个人 SO-ARM101 机械臂上。

## 项目目标

以 [Full-Stack-Entity/so101-left-sota-pack](https://huggingface.co/datasets/Full-Stack-Entity/so101-left-sota-pack) 中的预训练模型为基础，优先对 **Diffusion Policy** 进行微调，使其适配自有机械臂的任务场景。

当前项目按具身智能闭环组织：

```text
teleoperation -> dataset -> training -> checkpoint -> inference -> rollout -> evaluation
```

任务是 `Pick up object and Put down in box`：通过 leader-follower 遥操作采集双视角视觉和 6 自由度动作数据，在台式机上训练或微调策略模型，再部署回笔记本控制真实 SO-ARM101 follower。

## 项目材料

| 文档 | 用途 |
|------|------|
| [项目报告](docs/project-report.md) | 面向课题组老师的完整项目叙事：动机、系统、数据、模型、训练、推理、实验和扩展 |
| [4-6 周推进路线](docs/project-roadmap.md) | 从当前状态推进到可稳定演示的周计划和验收标准 |
| [实验与演示记录模板](docs/experiment-log-template.md) | 记录数据集、训练、推理评估、10 次 rollout 和视频证据 |
| [最终 pilot 采集指南](docs/final-pilot-data-collection.md) | 采集 `so101-left-final-pilot` 的操作步骤和验证方式 |
| [本地部署 smoke test](docs/local-deployment-smoke-test.md) | 使用 Diffusion Policy 跑完整 LeRobot record/eval 流程 |
| [实时部署 smoke test](docs/live-deployment-smoke-test.md) | 不写数据集，只测真实控制循环延迟 |
| [采集日志](docs/collect-log.md) | 历史采集记录和问题复盘 |

## 模型

| 模型 | 状态 | 说明 |
|------|------|------|
| Diffusion Policy | 主线 | 已完成 final-pilot / left-final-50 训练摘要，下一步做 10 次标准真机评估 |
| ACT | 对照路线 | 已有 left-final-50 baseline checkpoint 摘要，用于和 Diffusion 对照 |
| SmolVLA | 扩展路线 | 面向视觉-语言-动作和多任务扩展 |
| LoRA/PEFT | 扩展方法 | 用于 VLA 或大 backbone 的参数高效微调 |

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
- **Follower**：COM3
- **Leader**：COM4
- **Fixed camera**：Camera 0
- **Handeye camera**：Camera 2

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

## 下一步

1. 人工复核 `so101-left-final-50` 的 release-tail review frames，确认“停稳再松爪”的 episode 语义。
2. 用最佳 Diffusion checkpoint 完成 10 次标准 left rollout，记录成功率、失败模式和视频证据。
3. 用 ACT checkpoint 做同样的 10 次对照评估。
4. 根据失败模式决定补采 left hard cases，或推进 center-pilot 10 条泛化测试。
5. 将评估结果追加到 [采集日志](docs/collect-log.md) 和 [实验与演示记录模板](docs/experiment-log-template.md)。
