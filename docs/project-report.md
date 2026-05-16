# SO-ARM101 具身智能项目报告

本文档用于把 SO-ARM101 机械臂项目整理成可以给具身智能方向老师阅读的项目材料。它强调完整闭环、关键原理、当前证据、后续推进，而不是只展示单次成功视频。

## 1. 项目动机

本项目目标是在个人 SO-ARM101 机械臂上完成一个低成本真实机器人模仿学习闭环：

```text
teleoperation -> dataset -> training -> checkpoint -> inference -> rollout -> evaluation
```

任务是 `Pick up object and Put down in box`：机械臂从桌面抓取目标物体，移动到固定托盘或盒子上方，停稳后打开夹爪释放物体。

这个项目的价值不在于单纯让机械臂动起来，而在于把真实机器人学习中的关键环节走通：硬件标定、遥操作采集、数据质量控制、视觉-动作策略训练、真机部署、失败分析和下一轮数据改进。

## 2. 系统组成

| 模块 | 当前配置 | 作用 |
|------|----------|------|
| Follower arm | SO-ARM101, `COM3` | 被策略或遥操作控制的执行机械臂 |
| Leader arm | SO-ARM101, `COM4` | 人类遥操作示教输入 |
| Fixed camera | OpenCV camera 0, 640x480, 30fps | 全局俯视视角，观察物体、托盘和机械臂整体状态 |
| Handeye camera | OpenCV camera 2, 640x480, 30fps | 末端视角，补充抓取和释放细节 |
| Collection laptop | Windows, LeRobot environment | 连接硬件，采集数据，部署推理 |
| Training workstation | NVIDIA GPU machine | 训练或微调策略模型 |
| Framework | LeRobot | 统一机器人配置、数据集格式、训练和评估流程 |

核心配置见 `record_config.yaml`。本项目的数据和模型权重均为本地大文件，不纳入 Git：`data/` 保存 LeRobot 数据集，`models/` 保存下载或训练得到的策略 checkpoint。

## 3. 数据采集原理

### 3.1 遥操作示教

数据采集采用 leader-follower 遥操作。人操作 leader arm 完成任务，follower arm 同步执行，系统同时记录每一帧的观测和动作。

训练数据本质上是监督学习样本：

| 字段 | 形状 | 含义 |
|------|------|------|
| `observation.state` | `[6]` | 当前 follower 的 6 自由度关节状态 |
| `observation.images.fixed` | `[480, 640, 3]` | 全局相机 RGB 图像 |
| `observation.images.handeye` | `[480, 640, 3]` | 手眼相机 RGB 图像 |
| `action` | `[6]` | 人类示教产生的下一步目标关节动作 |

相机原始采集为 30fps，训练数据按 `dataset.fps=10` 存储。这样可以减少冗余帧和训练成本，同时保留抓取、搬运、释放的关键时序。

### 3.2 Episode 语义

每条 episode 应该只包含一次干净的抓取-放置尝试：

1. 从统一 home pose 开始。
2. 接近目标物体。
3. 夹爪完全闭合并抓取。
4. 抬起并移动到托盘上方。
5. 末端先停稳。
6. 缓慢打开夹爪 release。
7. 保持静止 0.5-1.0 秒。
8. 物体稳定落入托盘后立即结束。

不要把失败后的补救动作、放置后的回 home、边移动边开爪、多次试探开合混入同一条 episode。对模仿学习来说，模型学习的是数据中的动作分布；如果数据语义混乱，模型也会学习到混乱策略。

### 3.3 数据规模为什么重要

真实机器人数据的规模不仅是 episode 数量，还包括覆盖的状态分布。当前推荐路线是：

| 阶段 | 目标数据 | 目的 |
|------|----------|------|
| Pilot | 5-10 episodes | 验证硬件、相机、episode 语义、数据格式 |
| Left final | 30-50 episodes | 让单一区域任务可稳定训练和部署 |
| Center/right extension | 每区 30-50 episodes | 验证位置泛化和多区域统一策略 |
| Robust set | 更换光照、物体、托盘细节 | 推进泛化能力，而不是只记住一个场景 |

SmolVLA 官方教程建议从约 50 条高质量 episodes 起步，并且每种场景变化都要有足够重复样本。这与本项目先做 left 区域稳定闭环、再扩展 center/right 的路线一致。

## 4. 模型原理

### 4.1 Diffusion Policy 主线

Diffusion Policy 把机器人动作序列看作需要生成的连续轨迹。训练时，模型学习如何从加噪动作中逐步去噪，条件是当前视觉和机器人状态；推理时，模型根据当前观测生成一个 action chunk，再由控制循环逐步执行。

本项目优先选择 Diffusion Policy，原因是：

- 已经下载并完成 `diffusion-left-sota` 本地部署 smoke test。
- 它适合连续控制和多模态动作分布。
- 通过 `num_inference_steps` 可以在动作质量和实时延迟之间做权衡。

当前本地延迟测试显示，CPU 推理时主要瓶颈在 diffusion action chunk 生成帧，而不是相机读取或串口发送。因此训练后需要比较 `num_inference_steps=2/4/6/8` 的成功率和实时性。

### 4.2 ACT 对照路线

ACT, Action Chunking Transformer, 也生成动作 chunk。它通过 transformer 预测未来一段动作，常用于低频人类示教数据中的模仿学习。ACT 的优势是推理结构直接、实时性通常较好；风险是对数据质量和动作分布也很敏感。

本项目可以把 ACT 作为对照：如果 Diffusion Policy 在 release 阶段不稳定，ACT 可以作为另一种 action chunking 基线。

### 4.3 SmolVLA 和 LoRA 扩展

SmolVLA 是视觉-语言-动作模型路线，输入可以包含图像、状态和语言任务描述，适合未来扩展到多任务和语言指令。它比纯 Diffusion Policy 更适合展示具身智能方向的潜力，但对数据、算力和调参要求更高。

LoRA 是参数高效微调方法。它冻结主模型权重，只训练低秩增量矩阵，使大模型适配新任务。对于 VLA 或大 backbone 模型，LoRA 的价值是降低显存和训练成本，同时保留预训练知识。

### 4.4 模型对比

| 路线 | 输入 | 输出 | 优势 | 风险 | 本项目定位 |
|------|------|------|------|------|------------|
| Diffusion Policy | 图像 + 关节状态 | 连续动作 chunk | 适合连续控制，多峰动作分布 | 推理较慢，需要调 inference steps | 主线 |
| ACT | 图像 + 关节状态 | 动作 chunk | 推理直接，结构清晰 | 对数据语义敏感 | 对照路线 |
| SmolVLA | 图像 + 状态 + 语言 | 机器人动作 | 支持语言和多任务扩展 | 训练成本更高 | 加分扩展 |
| LoRA/PEFT | 依附于大模型 | 低秩微调参数 | 省显存，保留预训练能力 | 不适合所有小模型结构 | VLA 扩展方法 |

## 5. 训练与微调

训练的目标是学习从观测到动作的映射。对当前任务来说，模型需要学会：

- 从 fixed camera 判断物体和托盘的全局位置。
- 从 handeye camera 捕捉末端附近的抓取和释放细节。
- 从 `observation.state` 理解当前关节构型。
- 在 release 阶段执行“先停稳，再开爪，再保持”的动作节奏。

训练方案按优先级推进：

| 优先级 | 方案 | 说明 |
|--------|------|------|
| P0 | Diffusion Policy on left-final | 主线，先做单区域稳定闭环 |
| P1 | Diffusion Policy center/right extension | 验证跨位置泛化 |
| P2 | ACT baseline | 与 Diffusion 的 action chunking 行为对比 |
| P3 | SmolVLA + LoRA | 面向具身智能展示语言条件和参数高效微调 |

训练日志必须记录：数据集版本、episode 数、训练步数、batch size、GPU、训练耗时、checkpoint 路径、loss 曲线和是否成功部署。

## 6. 训练模型 vs 推理模型

训练阶段和推理阶段关注的问题不同：

| 阶段 | 输入 | 输出 | 目标 | 关键风险 |
|------|------|------|------|----------|
| 训练 | 数据集中的完整轨迹 | loss 和 checkpoint | 拟合人类示教动作分布 | loss 下降但真机失败 |
| 推理 | 当前实时观测 | 下一段动作或单步动作 | 在真实硬件上完成任务 | 延迟、动作跳变、相机偏移、安全限幅 |

因此不能只用训练 loss 判断项目成功。最终必须做真机 rollout，并记录成功率和失败类型。

推理部署还需要考虑：

- `robot.max_relative_target`：限制单步动作幅度，避免危险跳变。
- `num_inference_steps`：影响 Diffusion Policy 质量和实时性。
- 控制频率：目标约 10Hz，但实际频率要用 live smoke test 记录。
- 失败保护：手边保留断电或急停方式，先在无障碍区域验证动作。

## 7. 实验结果记录

当前已经完成的基础证据：

| 证据 | 状态 | 位置 |
|------|------|------|
| 硬件连接 | 已完成 | `record_config.yaml` |
| 双摄像头配置 | 已完成 | `record_config.yaml` |
| Pilot 数据采集 | 已完成 10 episodes final pilot，且扩展到 50 episodes left-final | `docs/collect-log.md` |
| Diffusion checkpoint 下载 | 已完成 | `scripts/deploy/download_diffusion_left_sota.py` |
| 本地 dataset-style smoke test | 已完成 | `docs/local-deployment-smoke-test.md` |
| live control-loop smoke test | 已完成 | `docs/live-deployment-smoke-test.md` |
| final pilot 采集协议 | 已完成 | `docs/final-pilot-data-collection.md` |
| Diffusion/ACT 训练 | 已完成本地 checkpoint 摘要记录，权重不入 Git | `docs/collect-log.md` |

下一步实验表应按以下格式补齐：

| 日期 | 数据集 | 模型 | 训练步数 | 推理配置 | 成功/总数 | 主要失败模式 | 视频 |
|------|--------|------|----------|----------|-----------|--------------|------|
| TBD | `so101-left-final-50` | Diffusion Policy | 10k / 4k | steps=2/4/6/8 | TBD/10 | TBD | TBD |

评价标准：

- 抓取成功：夹爪稳定抓起物体。
- 搬运成功：物体移动到托盘上方，中途不掉落。
- 释放成功：末端停稳后打开夹爪，物体稳定落入托盘。
- 完整成功：以上三项都满足，且无危险动作。

## 8. 后续扩展

### 8.1 数据扩展

先把 left 区域做稳，再扩展：

1. `left-final`: 30-50 条高质量 episodes。
2. `center-pilot`: 10 条，验证 left-only 模型泛化。
3. `center-final`: 30-50 条，训练多区域模型。
4. `right-pilot/final`: 视 center 结果决定。
5. 加入物体位置、光照、背景、托盘轻微变化。

### 8.2 模型扩展

建议顺序：

1. Diffusion Policy 主线完成稳定 rollout。
2. ACT baseline 做轻量对比。
3. SmolVLA 尝试语言条件训练。
4. SmolVLA 或其他 VLA 模型上使用 LoRA/PEFT。

### 8.3 研究问题

可向老师展示的后续问题：

- 数据规模和成功率之间的关系是什么？
- release 语义是否是 pick-and-place 任务的关键瓶颈？
- 双视角相机中 fixed 和 handeye 各贡献什么信息？
- Diffusion Policy 的 inference steps 如何影响成功率和实时性？
- left-only 数据能否泛化到 center/right？
- LoRA 能否用更少参数完成任务适配？

## 展示材料清单

给老师看的材料建议包括：

- 本报告。
- 1 页项目概览图。
- 1 个成功 rollout 视频。
- 1 个失败 rollout 视频和失败分析。
- 1 个硬件/实时推理工作流视频。
- 数据集统计和验证结果。
- 训练配置、loss 曲线、checkpoint 说明。
- 10 次标准评估成功率表。
- 后续 4-6 周推进路线。

## 参考资料

- Hugging Face LeRobot real-world robot workflow: https://huggingface.co/docs/lerobot/main/getting_started_real_world_robot
- SO101 left SOTA pack: https://huggingface.co/datasets/Full-Stack-Entity/so101-left-sota-pack
- Diffusion Policy paper: https://huggingface.co/papers/2303.04137
- SmolVLA LeRobot docs: https://huggingface.co/docs/lerobot/v0.4.3/en/smolvla
- LoRA paper: https://arxiv.org/abs/2106.09685
