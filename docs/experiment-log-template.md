# SO-ARM101 实验与演示记录模板

本模板用于把采集、训练、推理、演示视频和失败分析记录成可追溯证据。每次采集、训练或 rollout 后追加一条记录。

## 1. 数据集记录

```markdown
## 数据集记录 YYYY-MM-DD

- 数据集名称：
- 本地路径：
- Hub repo id：
- 区域：left / center / right / mixed
- Episodes：
- FPS：
- 任务字符串：Pick up object and Put down in box
- 目标物：
- 托盘/盒子：
- 相机：fixed=Camera 0, handeye=Camera 2
- Follower port：COM3
- Leader port：COM4
- 验证结果：PASS / FIX BEFORE TRAINING / BLOCKED
- release-tail 抽查结论：
- 主要问题：
- 是否可用于训练：是 / 否
```

## 2. 训练记录

```markdown
## 训练记录 YYYY-MM-DD

- 模型路线：Diffusion Policy / ACT / SmolVLA / LoRA
- 训练数据集：
- Episodes：
- 训练机器：
- GPU：
- 训练命令：
- Batch size：
- Training steps：
- Learning rate：
- Checkpoint 路径：
- 训练耗时：
- 最终 loss：
- 观察到的问题：
- 是否进入真机评估：是 / 否
```

## 3. 推理评估记录

```markdown
## 推理评估 YYYY-MM-DD

- 模型 checkpoint：
- 评估区域：left / center / right
- 评估次数：
- `num_inference_steps`：
- `max_relative_target`：
- 目标 FPS：
- 实际 wall Hz：
- 成功次数：
- 成功率：
- 平均单次耗时：
- 失败模式统计：
  - 抓取失败：
  - 搬运中掉落：
  - 未在托盘上方停稳：
  - release 失败：
  - 动作跳变/安全停止：
- 代表性成功视频：
- 代表性失败视频：
- 结论：
```

## 4. 标准 10 次 Rollout 表

| Trial | Object start | Grasp | Transport | Stable release | Success | Failure note | Video |
|-------|--------------|-------|-----------|----------------|---------|--------------|-------|
| 01 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 02 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 03 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 04 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 05 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 06 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 07 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 08 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 09 | left | TBD | TBD | TBD | TBD | TBD | TBD |
| 10 | left | TBD | TBD | TBD | TBD | TBD | TBD |

## 5. 演示视频清单

| 视频 | 必要性 | 内容要求 | 状态 | 路径/链接 |
|------|--------|----------|------|-----------|
| 成功 rollout | 必须 | 完整抓取、搬运、停稳、release | TBD | TBD |
| 失败 rollout | 必须 | 展示真实失败并解释原因 | TBD | TBD |
| 实时推理工作流 | 必须 | 硬件、相机、终端、机械臂闭环 | TBD | TBD |
| 数据采集过程 | 推荐 | leader-follower 遥操作示教 | TBD | TBD |
| 训练日志说明 | 推荐 | loss 曲线、checkpoint、配置 | TBD | TBD |

## 6. 给老师展示时的 5 分钟叙事

```text
我做的是一个 SO-ARM101 真实机械臂上的模仿学习闭环。
首先通过 leader-follower 遥操作采集双视角视觉和 6 自由度动作数据。
然后用 LeRobot 数据格式训练 Diffusion Policy，使模型根据当前图像和关节状态生成下一段动作。
训练完成后把 checkpoint 部署回笔记本，进行真机 rollout，并用成功率和失败模式评估。
目前重点不是单次成功，而是建立可复现的数据-训练-推理-评估闭环，后续扩展到 SmolVLA、LoRA 和多区域泛化。
```
