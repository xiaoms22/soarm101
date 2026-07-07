# SO-ARM101 Pickup-and-Putdown HIL-SERL 任务步骤整理

本文档整理 SO-ARM101 上 `Pick up object and Put down in box` 任务从真机采集、训练、部署到 HIL-SERL 强化学习扩展的完整步骤。写法采用证据边界：已经在本地文档和日志中记录的内容写为完成证据；HIL-SERL/RL 部分写为基于 LeRobot HIL-SERL 工作流的迁移设计和后续验证项。

## 1. 任务目标与成功标准

### 1.1 任务定义

任务字符串必须保持一致：

```text
Pick up object and Put down in box
```

机器人需要完成一次干净的 pickup-and-putdown：

1. 从统一 home pose 开始。
2. 接近桌面目标物体。
3. 闭合夹爪并稳定抓起物体。
4. 抬起并搬运到固定盒子或托盘上方。
5. 末端先停稳。
6. 打开夹爪释放物体。
7. 保持静止约 `0.5-1.0s`。
8. 物体稳定落入盒中后立即结束 episode。

### 1.2 成功标准

| 阶段 | 判定标准 | 失败例子 |
|------|----------|----------|
| Approach | 末端接近目标物体且姿态可抓取 | 末端偏离物体、相机视野判断错误 |
| Grasp | 夹爪完全闭合并稳定抓起物体 | 抓空、夹偏、物体滑落 |
| Transfer | 物体被搬运到盒子上方，中途不掉落 | 搬运中碰撞或掉落 |
| Stable release | 末端停稳后开爪，物体落入盒中 | 边移动边开爪、开爪后物体仍挂在夹爪上 |
| Full success | 以上阶段全部通过且无危险动作 | 任何阶段失败都不计完整成功 |

### 1.3 证据口径

本地已记录的自采数据：

| 日期 | 数据集 | 条数 | 状态 |
|------|--------|------|------|
| 2026-05-12 | `so101-left-pilot` | 5 episodes | 回放验证通过 |
| 2026-05-16 | `so101-left-final-pilot` | 10 episodes | validator PASS |
| 2026-05-16/17 | `so101-left-final-50` | 50 episodes | validator PASS |

合计：`5 + 10 + 50 = 65` 条本地自采 SO101 episodes。

外部或参考数据需要单独标注：

- `Full-Stack-Entity/so101-pickup-putdown-60`：外部 pickup-putdown 参考数据集。
- `Full-Stack-Entity/so101-grasp-99`：外部 grasp 参考数据集，曾用于训练或初始化对照。
- PPT 或报告中如果出现更大的 episode 数字，需要说明是否包含外部参考数据，不能混写成本地自采数据。

## 2. 硬件与软件准备

### 2.1 硬件组成

| 设备 | 当前配置 | 作用 |
|------|----------|------|
| Follower arm | SO-ARM101, `COM3` | 被策略或遥操作控制的执行臂 |
| Leader arm | SO-ARM101, `COM4` | 人类遥操作示教输入 |
| Fixed camera | OpenCV Camera 0, 640x480, 30fps | 全局视角，观察目标、盒子和机械臂整体状态 |
| Handeye camera | OpenCV Camera 2, 640x480, 30fps | 腕部/夹爪视角，观察抓取和 release 细节 |
| Laptop | Windows + LeRobot 环境 | 采集、部署、真机控制 |
| GPU workstation | NVIDIA GPU 机器 | 策略训练或微调 |

### 2.2 LeRobot 数据字段

训练和部署中必须保持字段名一致：

| 字段 | 形状 | 含义 |
|------|------|------|
| `observation.state` | `[6]` | follower 的 6 自由度关节状态 |
| `observation.images.fixed` | `[3, 480, 640]` 或视频帧 | 全局相机 RGB |
| `observation.images.handeye` | `[3, 480, 640]` 或视频帧 | 手眼相机 RGB |
| `action` | `[6]` | 下一步目标关节动作 |

关键配置：

- `dataset.fps=10`：训练数据频率。
- `dataset.video=true`：图像以视频形式存储。
- `dataset.vcodec=h264`：LeRobot 0.5.x 参数，当前笔记本使用 CPU 编码，避免无 NVIDIA GPU 时触发 `nvcuda.dll` 错误；升级 LeRobot main/0.6 前需要同步迁移到 `dataset.rgb_encoder.vcodec`。
- `robot.disable_torque_on_disconnect=false`：避免断开后电机锁定。

## 3. 真机任务执行步骤

### Step 1: 采集前安全检查

目的：确认机器人、相机、环境和脚本都处于可采集状态。

操作：

1. 检查 follower 在 `COM3`、leader 在 `COM4`。
2. 检查 fixed camera 为 Camera 0，handeye camera 为 Camera 2。
3. 盒子或托盘固定不动。
4. 目标物只在当前 left 区域内小范围扰动。
5. follower 回到统一 home pose。
6. 相机无遮挡、画面稳定、光照尽量一致。
7. 手边保留断电或急停方式。

检查相机：

```powershell
cd <repo-root>
conda activate lerobot-so101
python .\scripts\collect\check_cameras.py
```

预期至少看到：

```text
Camera 0: available
Camera 2: available
```

### Step 2: 遥操作采集 pilot 数据

目的：先用少量数据验证硬件、schema、episode 语义和视频编码，而不是一开始就录满大数据集。

推荐顺序：

1. `so101-left-pilot`：先录 5 条，检查流程是否跑通。
2. `so101-left-final-pilot`：录 10 条最终物体/盒子 pilot。
3. `so101-left-final-50`：pilot 通过后扩展到 30-50 条。

采集命令示例：

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_final_pilot_collection.ps1
```

扩展 left-final 数据：

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_left_final_50_collection.ps1 -Resume
```

### Step 3: 控制每条 episode 的语义

每条 episode 只包含一次干净尝试：

1. Home pose。
2. Approach object。
3. Close gripper。
4. Lift。
5. Move above tray/box。
6. Stop end effector。
7. Open gripper。
8. Hold still。
9. End episode。

不要混入：

- 抓取失败后的补救动作。
- 放置后回 home。
- 边移动边开爪。
- 多次试探性开合夹爪。
- 盒子、相机或桌面布局变化。

release 是最关键阶段。正确节奏是：

```text
停稳末端 -> 缓慢开爪 -> 确认物体脱离 -> 保持静止 -> 结束 episode
```

### Step 4: 采集后验证数据

目的：训练前先验证数据格式和视频可读性，避免把坏数据送入训练。

验证 final pilot：

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\collect\validate_final_pilot.ps1
```

验证内容包括：

- episode 数量。
- `observation.state` 和 `action` shape。
- fixed/handeye 视频存在且可解码。
- task string 精确匹配。
- action 和 state 无 NaN。
- gripper action 有足够变化。
- release-tail review frames 是否可人工复核。

`PASS` 才进入训练；`FIX BEFORE TRAINING` 需要人工检查；`BLOCKED` 不应训练。

### Step 5: Diffusion/ACT/SmolVLA 训练与微调

已记录训练路线：

| 日期 | 数据集 | 模型 | 训练记录 |
|------|--------|------|----------|
| 2026-05-17 | `so101-left-final-50` | Diffusion Policy scratch | 10k steps, batch size 4 |
| 2026-05-17 | `so101-left-final-50` | Diffusion Policy fine-tune | from `006000`, 4k steps, batch size 4 |
| 2026-05-17 | `so101-left-final-50` | ACT baseline | 10k steps, batch size 4 |
| 2026-05-19 | `so101-left-final-50` | SmolVLA fine-tune | 200k steps, batch size 4 |

训练阶段记录要素：

- 数据集版本和 episode 数。
- 模型路线。
- 训练命令。
- batch size、steps、learning rate。
- GPU 和训练耗时。
- checkpoint 路径。
- loss 曲线。
- 是否进入真机评估。

注意：训练 loss 下降只说明模型拟合训练数据，不等于真机任务完成。

### Step 6: 本地部署 smoke test

目的：验证模型能加载、相机能读、机器人能收动作、控制循环能跑通。smoke test 不要求完成任务。

Diffusion 本地部署 smoke：

```powershell
cd <repo-root>
.\scripts\deploy\run_diffusion_left_sota_smoke.ps1
```

实时控制循环 smoke：

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\run_live_diffusion_left_sota_smoke.ps1
```

已记录的实时性结论：

| 设置 | 结果 |
|------|------|
| `num_inference_steps=4` | 约 9.10Hz，policy p90 约 174.3ms |
| `num_inference_steps=2` | 约 9.80Hz，policy p90 约 111.5ms |

解释：Diffusion Policy 的主要瓶颈是 action chunk 生成帧，不是相机读取或串口发送。

### Step 7: 标准 rollout 评估

目的：用固定协议评估真机行为，不能只展示最好的一次。

建议评估协议：

1. 固定 left 区域。
2. 每个 checkpoint 做 10 次标准 trial。
3. 记录 `num_inference_steps`、`max_relative_target`、目标 FPS、实际 wall Hz。
4. 每次按 Approach、Grasp、Transfer、Stable release、Full success 逐项标注。
5. 保存成功和失败代表性视频。
6. 按失败模式决定补采、调参或换模型。

标准表：

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

当前边界：本地日志主要证明采集、训练和控制链路跑通；还需要补齐标准 10 次 rollout 成功率表，才能把任务成功率写成定量结论。

## 4. HIL-SERL/RL 接入步骤

HIL-SERL 是 Human-in-the-Loop Sample-Efficient Reinforcement Learning。它不是只做离线模仿学习，而是在少量示教的基础上，用在线 RL、人类介入和奖励分类器继续改进策略。

### Step 8: 把自采 demonstration 作为 RL 起点

对应 HIL-SERL 的 offline demonstrations。

已有基础：

- `so101-left-final-50` 提供 50 条高质量 left 区域示教。
- fixed/handeye 双视角和 6DoF state/action 已验证。
- episode 语义强调 release 阶段的“停稳再开爪”。

迁移到 HIL-SERL 时，这些数据可用于：

- 初始化 replay buffer。
- 训练初始 policy。
- 训练 reward classifier 的正负样本来源之一。
- 作为人工介入时的动作风格参考。

### Step 9: 训练 reward classifier

目的：自动判断当前视觉状态是否成功，给 RL 提供 reward，而不是每一步都人工写 reward。

输入建议：

- `observation.images.fixed`
- `observation.images.handeye`
- 必要时加入 `observation.state`

标签建议：

- 成功：物体稳定落入盒中，夹爪已释放。
- 失败：抓空、掉落、未到盒子、release 后物体未脱离。

注意：

- LeRobot HIL-SERL 文档建议 reward classifier 数据采集时可设置 `terminate_on_success=false`，让成功后继续记录一小段，以获得更多正样本。
- 本项目尚未在日志中记录 reward classifier 的训练指标，所以 PPT 中应写成“方法接入/下一步验证”，不能写成已完成定量结果。

### Step 10: 启动 SAC actor-learner 在线训练

HIL-SERL 使用 actor-learner 架构：

| 组件 | 作用 |
|------|------|
| Learner | 维护 replay buffer，运行 SAC 更新策略，定期推送新权重 |
| Actor | 控制真实机器人执行策略，采集 transition，发送给 learner |
| Human intervention | 当策略偏离或危险时，人接管并完成/纠正动作 |
| Reward classifier | 根据视觉状态给成功奖励或终止信号 |

典型命令形态：

```powershell
python -m lerobot.rl.learner --config_path path\to\train_config.json
python -m lerobot.rl.actor --config_path path\to\train_config.json
```

注意：这部分对应 LeRobot main 的 HIL-SERL/source install 工作流，需要单独安装 `hilserl` extra；本仓库当前采集和部署脚本仍按 LeRobot 0.5.x 运行，不能在未迁移前直接混用。

本项目迁移时需要重点配置：

- robot/teleop 硬件配置。
- fixed/handeye 图像输入。
- action space 使用 joint space 还是 end-effector space。
- workspace bounds 和 `max_relative_target`。
- reward classifier path 和 success threshold。
- actor-learner 权重同步频率。
- WandB 或日志指标。

### Step 11: 人类介入策略

HIL-SERL 的关键不是一直人工接管，而是在策略偏离时短时纠正。

推荐介入原则：

1. 初期允许策略探索，但安全边界必须明确。
2. 当末端偏离目标、夹爪时机不对、动作危险时介入。
3. 介入尽量短，只把策略拉回可学习轨迹。
4. 当策略能完成大部分动作后，减少介入频率。
5. 记录 intervention rate，理想趋势是训练过程中逐渐下降。

对 pickup-and-putdown，最值得介入的时刻：

- 接近目标时偏离。
- 夹爪闭合太早或太晚。
- 搬运路径会碰撞或掉落。
- release 前没有停稳。
- release 后物体未脱离。

### Step 12: 安全边界与 workspace 约束

HIL-SERL 在线训练会让策略探索真实机器人动作，因此安全边界比离线模仿学习更重要。

需要确认：

- 机械臂工作空间上下界。
- 单步动作幅度限制。
- gripper 最大开合范围。
- 桌面、盒子、相机支架和人的安全距离。
- 失败时的急停方式。

可考虑从 joint action 逐步迁移到 end-effector action：

- joint space 直接对应 SO101 的 6DoF 动作，但探索难度较高。
- end-effector space 更贴近“上下左右前后 + 开合夹爪”的任务结构，HIL-SERL 文档也强调它对操作任务更容易学习。

## 5. 失败归因与下一步

### 5.1 失败分类

| 类型 | 现象 | 可能原因 | 处理方向 |
|------|------|----------|----------|
| 视觉偏移 | 末端对不准物体或盒子 | 相机位置变化、ROI 不稳定、数据覆盖不足 | 固定相机、裁剪 ROI、补采 hard cases |
| 抓取失败 | 抓空或夹偏 | approach 数据不足、夹爪时机不稳 | 补采抓取阶段、分阶段统计 |
| 搬运掉落 | 抬起或移动中掉落 | 抓取不牢、动作 chunk 跳变 | 限幅、平滑、补采稳定搬运 |
| release 失败 | 物体没落入盒中或挂爪 | episode 语义混乱、未停稳就开爪 | 强化 release-tail 复核和补采 |
| 延迟滞后 | 动作慢、卡顿 | Diffusion chunk 生成慢、CPU 推理瓶颈 | 对比 inference steps、优化硬件或模型 |
| normalization 错误 | 动作方向/幅度异常 | schema 或归一化不一致 | 检查训练和部署 processor |

### 5.2 下一轮验证路线

1. 补齐最佳 Diffusion checkpoint 的 10 次标准 left rollout。
2. 用 ACT baseline 做同样 10 次对照。
3. 分阶段统计 approach/grasp/transfer/release 通过率。
4. 如果 release 是瓶颈，补采高质量 release-tail 数据。
5. 如果 IL 到达上限，再把 `so101-left-final-50` 作为 HIL-SERL offline demos，接入 reward classifier 和 SAC actor-learner。
6. 记录 intervention rate、成功率、episode length 和安全事件，验证 HIL-SERL 是否比纯 imitation 更快提升成功率。

## 6. 可以放进 PPT 的一句话总结

我完成的是一个真实 SO-ARM101 机械臂上的 pickup-and-putdown 闭环：先用 leader-follower 采集双视角示教数据，训练 Diffusion/ACT/SmolVLA 策略并部署到真机，再用 rollout、延迟和失败分类评估；强化学习部分则基于 HIL-SERL，把已有 demonstrations 作为起点，通过 reward classifier、SAC actor-learner 和人类介入继续提升样本效率与安全性。
