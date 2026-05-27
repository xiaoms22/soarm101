# HIL-SERL 使用教程与面试介绍指南

本文档专门面向 SO-ARM101 pickup-and-putdown 项目，讲清楚 HIL-SERL 的内容细节、在 LeRobot 中怎么使用、迁移到本项目时需要准备什么，以及面试时怎么介绍。写法保持证据边界：本项目已经完成的数据采集、IL 训练和部署 smoke test 写成事实；HIL-SERL 在线 RL 的 reward classifier 指标、actor-learner 成功率和 intervention rate 还没有落库，面试时要表述为下一步可验证路线。

## 1. 一句话理解 HIL-SERL

HIL-SERL 是 Human-in-the-Loop Sample-Efficient Reinforcement Learning，也就是“人类在环的样本高效强化学习”。

它解决的问题是：纯模仿学习只能学示教数据里出现过的状态；一旦真实 rollout 偏离训练分布，策略可能不会自我纠正。HIL-SERL 用少量 demonstration 启动，再通过 reward classifier、SAC 在线训练和人类短时介入，让策略在真实机器人交互中继续变好。

核心链路：

```text
offline demonstrations
-> reward classifier
-> SAC actor-learner
-> human intervention
-> online rollout improvement
```

对应到本项目：

```text
so101-left-final-50 demos
-> 判断物体是否稳定入盒的 reward classifier
-> SAC learner 更新策略
-> actor 控制 SO101 真机 rollout
-> 人在 approach/grasp/release 出问题时短时接管
```

## 2. HIL-SERL 和已有 SO101 工作的关系

本项目已经走通的是 imitation learning 和真机部署链路：

| 已完成环节 | 本项目证据 |
|------------|------------|
| 自采 demonstration | `so101-left-pilot` 5 条，`so101-left-final-pilot` 10 条，`so101-left-final-50` 50 条 |
| 数据格式验证 | fixed/handeye 视频、`observation.state`、`action`、task string、NaN 检查 |
| IL 模型训练 | Diffusion Policy、ACT、SmolVLA 训练摘要 |
| 真机部署检查 | local smoke 和 live smoke timing |
| 待补齐 | 10 次标准 rollout 成功率、HIL-SERL reward classifier 和 actor-learner 指标 |

HIL-SERL 不是替代 OpenPI/π0/π0.5，也不是替代 Diffusion/ACT/SmolVLA。它是示教和部署之后的一层在线改进路线：

- Diffusion/ACT/SmolVLA/π0/π0.5：更偏策略模型和推理部署。
- HIL-SERL：更偏真实交互中的 RL 训练框架。
- 两者关系：先有可运行策略和数据，再用 HIL-SERL 让策略从真实反馈中继续优化。

面试里可以这样说：

> 我把 SO101 项目分成两层：第一层是 IL/VLA 部署闭环，包括 LeRobotDataset、Diffusion/ACT/SmolVLA、OpenPI π0/π0.5 接入和真机 smoke；第二层是 HIL-SERL 扩展，把已有 demonstrations 作为 replay buffer 和 reward classifier 数据来源，通过 SAC actor-learner 和 human intervention 做在线强化学习。

## 3. HIL-SERL 的四个关键模块

### 3.1 Offline demonstrations

作用：给 RL 一个合理起点，避免从零随机探索真实机器人。

在 SO101 项目中可以使用：

- `so101-left-final-50`：50 条高质量 left 区域示教。
- `so101-left-final-pilot`：10 条 final object/final tray pilot，可用于初始检查。

注意事项：

- episode 语义必须干净，尤其 release 阶段要“停稳 -> 开爪 -> 保持 -> 结束”。
- 不要把失败后补救动作混入 demonstration。
- HIL-SERL 需要的不只是成功视频，而是能支撑 reward、action 和安全边界的结构化数据。

面试解释：

> Offline demos 的价值是减少真实机器人 RL 的盲目探索。我的 SO101 数据已经验证了双相机、6DoF state/action 和 task string，这些数据可以作为 HIL-SERL 的 replay buffer 初始化，也可以为 reward classifier 提供正负样本。

### 3.2 Reward classifier

作用：把视觉状态转成 reward 或 success signal。

为什么需要：

- pickup-and-putdown 的成功很难用单个距离或关节角手写。
- 成功状态是视觉语义：物体稳定在盒中，夹爪已释放，机器人动作安全。
- reward classifier 能从 fixed/handeye 图像判断是否成功，给 SAC 提供奖励。

输入建议：

| 输入 | 用途 |
|------|------|
| `observation.images.fixed` | 判断物体和盒子的全局关系 |
| `observation.images.handeye` | 判断夹爪是否释放、物体是否还挂在末端附近 |
| `observation.state` | 辅助判断机械臂是否处于合理姿态 |

标签设计：

| 标签 | 例子 |
|------|------|
| success | 物体稳定落入盒中，夹爪打开，末端停稳 |
| failure | 抓空、掉落、未进盒、卡爪、边移动边开爪 |

LeRobot 中的关键配置思想：

```json
{
  "env": {
    "processor": {
      "reward_classifier": {
        "pretrained_path": "path_to_reward_classifier",
        "success_threshold": 0.7,
        "success_reward": 1.0
      },
      "reset": {
        "terminate_on_success": true
      }
    }
  }
}
```

训练 reward classifier 需要先采集标注数据。LeRobot 文档建议：训练 reward classifier 数据集时可以把 `terminate_on_success` 设为 `false`，这样成功后继续保留一小段正样本；真正 HIL-SERL 训练时再设回 `true`，让成功自动终止 episode。

面试解释：

> reward classifier 是 HIL-SERL 中把“任务是否完成”自动化的模块。对 pickup-and-putdown，成功不是简单距离，而是物体稳定入盒这个视觉语义。所以我会用 fixed 视角判断全局位置，用 handeye 视角补充 release 细节，再用 threshold 转成 reward 和终止信号。

### 3.3 SAC actor-learner

作用：在线更新策略。

LeRobot HIL-SERL 使用 actor-learner 架构：

| 组件 | 做什么 |
|------|--------|
| learner | 维护 replay buffer，运行 SAC 更新 actor/critic，定期推送策略参数 |
| actor | 连接真实机器人，执行当前策略，采集 transitions，发给 learner |
| gRPC | actor 和 learner 之间传输 transitions、interactions 和模型参数 |

启动顺序：

```powershell
python -m lerobot.rl.learner --config_path path\to\train_config_hilserl_so101.json
python -m lerobot.rl.actor --config_path path\to\train_config_hilserl_so101.json
```

训练循环：

```text
actor rollout
-> collect transition
-> send transition to learner
-> learner updates SAC
-> learner pushes new actor weights
-> actor continues rollout with fresher policy
```

SAC 关键点：

- SAC 是 off-policy，可以复用 demonstrations 和 intervention 数据。
- actor 输出动作，critic 估计动作价值。
- entropy 让策略保持一定探索，不要过早僵化。
- `temperature_init` 控制早期探索强度；LeRobot 文档给的经验起点是 `1e-2`。

关键超参数：

| 参数 | 含义 | 面试说法 |
|------|------|----------|
| `policy.temperature_init` | SAC 初始 entropy temperature | 太高会探索过猛，让 human intervention 不容易发挥作用 |
| `policy.actor_learner_config.policy_parameters_push_frequency` | learner 多久给 actor 推一次新权重 | 默认约 4s，可降到 1-2s 获得更及时策略 |
| `policy.storage_device` | learner 参数放 CPU 还是 GPU | GPU 充足时放 `cuda`，减少传输开销 |

面试解释：

> actor-learner 的意义是把真机交互和梯度更新解耦。actor 负责安全地跑机器人并发 transitions，learner 在后台用 SAC 更新策略，再把新权重推回 actor。这样真机不会因为每一步训练阻塞，同时还可以持续吸收人类介入产生的数据。

### 3.4 Human intervention

作用：人在策略出错或危险时短时接管，提供更安全、更有信息量的探索数据。

LeRobot 中的动作处理管线会记录 teleop events 和 intervention 信息。actor 侧会统计：

- episode 是否发生 intervention。
- intervention steps。
- total steps。
- intervention rate。

对 pickup-and-putdown，推荐介入点：

| 阶段 | 什么时候接管 | 目标 |
|------|--------------|------|
| Approach | 末端偏离物体或靠近危险区域 | 把末端拉回可抓取区域 |
| Grasp | 夹爪闭合时机错 | 示范正确闭合时机 |
| Transfer | 物体快掉或路径会碰撞 | 稳定搬运路径 |
| Release | 未停稳就开爪 | 强制形成停稳后 release 的动作 |
| Safety | 动作跳变、卡住、接近边界 | 立即接管或停止 |

好的 intervention 策略：

- 不要一上来全程接管。
- 初期允许策略探索，但安全边界要清楚。
- 接管要短，只纠正关键错误。
- 策略变好后逐渐减少介入。
- 理想结果是 intervention rate 下降，success rate 上升。

面试解释：

> HIL-SERL 里的 human intervention 不是重新做 teleoperation 数据采集，而是在策略自己 rollout 的状态分布上进行纠偏。这样收集到的是策略真实会遇到的错误状态，比纯离线示教更能解决 compounding error。

## 4. 在 SO101 上实际使用 HIL-SERL 的步骤

### Step 0: 明确边界

目前可作为事实讲：

- 已完成 SO101 数据采集和验证。
- 已完成 Diffusion/ACT/SmolVLA 训练摘要。
- 已完成本地和 live deployment smoke。
- 已在 PPT 中设计 HIL-SERL 扩展页。

目前不要说成事实：

- reward classifier 已训练完成。
- SAC actor-learner 已在 SO101 上收敛。
- HIL-SERL 已显著提高成功率。
- intervention rate 已下降。

### Step 1: 准备 HIL-SERL 环境

安装 LeRobot 的 HIL-SERL 额外依赖：

```bash
pip install -e ".[hilserl]"
```

在本项目中需要注意版本：

- 当前 SO101 脚本按 LeRobot `0.5.x` 记录。
- HIL-SERL 在上游 LeRobot 中涉及 `lerobot.rl.gym_manipulator`、`lerobot.rl.learner`、`lerobot.rl.actor`。
- 在真正跑之前要确认本地环境是否和上游 HIL-SERL 代码版本一致。

### Step 2: 准备环境配置

核心配置对象是：

```text
GymManipulatorConfig
├── env: HILSerlRobotEnvConfig
│   ├── robot
│   ├── teleop
│   ├── processor
│   ├── name
│   ├── task
│   └── fps
├── dataset: DatasetConfig
├── mode
└── device
```

SO101 迁移时重点字段：

```json
{
  "env": {
    "type": "gym_manipulator",
    "name": "real_robot",
    "fps": 10,
    "processor": {
      "control_mode": "leader",
      "observation": {
        "display_cameras": false
      },
      "image_preprocessing": {
        "crop_params_dict": {},
        "resize_size": [128, 128]
      },
      "gripper": {
        "use_gripper": true,
        "gripper_penalty": 0.0
      },
      "reset": {
        "control_time_s": 20.0,
        "terminate_on_success": true
      }
    },
    "robot": {
      "type": "so101_follower",
      "port": "COM3"
    },
    "teleop": {
      "type": "so101_leader",
      "port": "COM4"
    }
  },
  "dataset": {
    "repo_id": "xiaoms22/so101-hilserl-pickup-putdown",
    "task": "Pick up object and Put down in box",
    "push_to_hub": false
  },
  "device": "cuda"
}
```

说明：

- 这是迁移模板，不是已经验证可直接运行的最终配置。
- SO101 的 end-effector/IK 支持、URDF、action space 需要进一步确认。
- 如果继续使用 joint action，要特别注意 action bounds 和 `max_relative_target`。

### Step 3: 找 workspace bounds

HIL-SERL 在线探索真实机器人，必须先限制工作空间。

要确认：

- 末端 x/y/z 可达范围。
- 盒子和目标物所在区域。
- 最低高度，避免撞桌。
- 最高高度，避免拉扯线缆或相机。
- 单步动作幅度。

为什么重要：

- 减少无意义探索。
- 避免撞桌、撞盒子、撞相机支架。
- 让 RL 在“能解决任务的局部空间”里学习。

面试表达：

> 在真机 RL 中，workspace bounds 不是小细节，而是 reward 之前的安全前提。HIL-SERL 能 sample-efficient，很大一部分来自把探索限制在合理任务空间里。

### Step 4: 用现有 demos 启动

把 `so101-left-final-50` 作为初始 demonstrations。

建议先检查：

- 每条 episode 是否完整。
- release-tail 是否干净。
- fixed/handeye 是否稳定。
- task string 是否一致。
- action/state 是否无 NaN。

可以沿用已有 validator 和 review frames 经验。

### Step 5: 训练 reward classifier

建议先做一个小型 reward classifier 数据集：

| 样本类型 | 采集方式 |
|----------|----------|
| 成功状态 | 成功放入盒中后继续记录 1-2 秒 |
| 抓取失败 | 抓空、夹偏 |
| 搬运失败 | 中途掉落 |
| release 失败 | 未停稳、物体挂爪、未进盒 |
| 边界状态 | 快成功但未完全稳定 |

训练命令形态：

```bash
lerobot-train --config_path path/to/reward_classifier_train_config.json
```

评估时不要只看 accuracy，还要看：

- 成功状态召回率。
- 失败状态误报率。
- threshold 从 0.5 到 0.9 的行为。
- fixed-only、handeye-only、双相机输入的差异。

### Step 6: 启动 learner 和 actor

先启动 learner：

```bash
python -m lerobot.rl.learner --config_path path/to/train_config_hilserl_so101.json
```

再启动 actor：

```bash
python -m lerobot.rl.actor --config_path path/to/train_config_hilserl_so101.json
```

训练时记录：

| 指标 | 含义 |
|------|------|
| episodic reward | 每个 episode 的奖励 |
| success rate | 成功率 |
| intervention rate | 人类介入步数占比 |
| episode length | 完成任务耗时 |
| safety stop count | 安全停止次数 |
| actor wall Hz | 真机控制频率 |
| learner updates/s | 学习更新速度 |

最理想的趋势：

```text
success rate 上升
intervention rate 下降
episode length 稳定或下降
safety stop count 不增加
```

### Step 7: 做 IL-only vs HIL-SERL 对比

最有说服力的实验不是单独说 HIL-SERL 好，而是做对照：

| 条件 | 说明 |
|------|------|
| IL-only baseline | 用 Diffusion/ACT/SmolVLA 或 π0/π0.5 做固定 10 次 rollout |
| HIL-SERL round 1 | 用 demos + reward classifier + intervention 在线训练一段时间 |
| HIL-SERL round 2 | 减少介入，验证是否仍能保持成功 |

报告方式：

| 模型/阶段 | 10 次成功率 | intervention rate | 主要失败模式 | 结论 |
|-----------|-------------|-------------------|--------------|------|
| IL baseline | TBD | 0 | TBD | 离线策略基础 |
| HIL-SERL early | TBD | 高 | TBD | 人类介入帮助探索 |
| HIL-SERL later | TBD | 下降 | TBD | 如果成功率上升，说明在线 RL 有效 |

## 5. 面试时怎么介绍

### 5.1 30 秒版本

我在 SO-ARM101 上做了 pickup-and-putdown 的真实机器人闭环。前半部分是 IL/VLA 部署：采集 fixed 和 handeye 双视角、6DoF state/action 数据，训练 Diffusion、ACT、SmolVLA，并接入 OpenPI 的 π0/π0.5 推理链路。后半部分我设计了 HIL-SERL 扩展：把已有 demonstrations 作为 replay buffer 和 reward classifier 数据来源，再用 SAC actor-learner 在线更新策略，人类在 approach、grasp、release 出问题时短时接管，目标是让成功率上升、intervention rate 下降。

### 5.2 90 秒版本

HIL-SERL 我理解为示教数据之后的在线强化学习框架。纯模仿学习的问题是只能覆盖 demos 里的状态，真实 rollout 一旦偏离，策略可能不会自纠。HIL-SERL 先用少量 demonstrations 给策略一个安全起点，再训练 reward classifier，把视觉状态转成成功奖励，然后用 SAC actor-learner 在真机上持续更新策略。

在我的 SO101 项目里，已有的 `so101-left-final-50` 可以作为 offline demos。fixed 相机负责看物体和盒子的全局关系，handeye 相机负责看夹爪附近的抓取和 release 细节。reward classifier 会判断物体是否稳定入盒。actor 负责控制真机 rollout，把 transitions 发给 learner；learner 用 SAC 更新 actor/critic，再把新策略推回 actor。

human intervention 是这个方法的关键：它不是重新 teleop 一整条 episode，而是在策略偏离时短时接管，比如 approach 偏离、夹爪时机不对、release 前没有停稳。理想训练结果是前期介入多，后期 intervention rate 下降，同时 success rate 上升。这个部分我现在会明确说成下一步验证计划，不会把未跑完的 reward classifier 指标或 actor-learner 成功率说成已完成。

### 5.3 3 分钟技术版

我会把 HIL-SERL 拆成四块讲。

第一是 offline demonstrations。真实机器人从零 RL 成本太高，而且随机探索危险，所以先用人类示教数据启动。我这里已经有 65 条自采 SO101 episodes，其中 `so101-left-final-50` 是最适合作为初始 demos 的数据。

第二是 reward classifier。pickup-and-putdown 的 reward 不容易手写，因为成功是视觉语义：物体稳定在盒中，夹爪释放，末端停稳。我会用 fixed 和 handeye 两路图像训练一个二分类器，输出 success probability，再通过 threshold 转成 reward 和 termination。训练 reward classifier 时要故意收集失败样本，包括抓空、搬运掉落、release 失败，否则误报率会很高。

第三是 SAC actor-learner。actor 在真机上跑当前策略，收集 observation、action、reward、next observation，然后通过 gRPC 发给 learner；learner 维护 replay buffer，用 SAC 更新 actor 和 critic，并周期性把新 actor 参数推回 actor。SAC 是 off-policy，所以能复用 demonstrations 和 intervention 数据。

第四是 human intervention。人不是全程控制，而是在策略进入坏状态时短时接管，比如末端偏离目标、夹爪时机不对或 release 前未停稳。这个 intervention 数据正好补足 IL 的分布偏移问题。评估时我会同时看 success rate 和 intervention rate：如果成功率上升但 intervention rate 不降，说明还是人在完成；如果成功率上升且 intervention rate 下降，才说明策略真的学到了。

## 6. 面试高频追问与回答

### Q1: HIL-SERL 和普通模仿学习有什么区别？

模仿学习只拟合 demonstrations 中的 `observation -> action`，本质是监督学习。HIL-SERL 在此基础上加入真实交互和 reward，通过 SAC 继续优化策略。它能处理策略 rollout 后遇到的分布外状态，而这正是纯 BC 或普通 IL 容易失败的地方。

### Q2: HIL-SERL 为什么需要 human intervention？

真实机器人 RL 不能像仿真那样无限随机探索。human intervention 可以在策略危险或无效时及时纠正，一方面保护硬件，另一方面提供高价值的 on-policy correction 数据。它让探索更安全，也更接近任务成功区域。

### Q3: reward classifier 会不会不准？

会，所以它是 HIL-SERL 的关键风险点。我的处理思路是：收集多种失败样本，特别是接近成功但还没稳定入盒的边界状态；用 fixed 和 handeye 双视角；调 success threshold；最后在真机 rollout 中观察误报和漏报。如果 reward classifier 错了，SAC 会优化错误目标。

### Q4: 为什么不用手写 reward？

pickup-and-putdown 的成功不只是距离近，而是物体稳定入盒、夹爪释放、末端停稳。手写 reward 很容易漏掉 release、卡爪、掉落等情况。视觉 reward classifier 更适合表达这种任务语义。

### Q5: actor-learner 为什么要分开？

真机控制需要稳定频率，不能每一步都被梯度更新阻塞。actor 负责实时控制和采样，learner 负责后台更新策略，再周期性推送新权重。这样交互和学习可以并行，样本效率更高。

### Q6: 怎么证明 HIL-SERL 比 IL-only 好？

要做对照实验。先固定 IL baseline 的 10 次 rollout 成功率和失败模式，再运行 HIL-SERL，记录 success rate、intervention rate、episode length 和 safety stop。只有当 success rate 上升并且 intervention rate 下降，才能说策略本身变好了。

### Q7: 你现在 HIL-SERL 做到哪一步？

严谨回答：

> 我现在已经完成了 HIL-SERL 的前置基础：SO101 自采 demonstrations、数据验证、IL 策略训练和部署 smoke。HIL-SERL 部分已经完成方法设计和 PPT 结构整理，下一步是训练 reward classifier、启动 SAC actor-learner，并用 10 次 IL baseline 对比 intervention rate 和成功率。reward classifier 指标和 HIL-SERL 成功率我不会提前声称已经完成。

## 7. 自己练习讲述的顺序

面试时可以按这个顺序讲，比较稳：

1. 先讲任务：SO101 pickup-and-putdown。
2. 再讲已有闭环：数据、模型、OpenPI/π0/π0.5、部署 smoke。
3. 再讲问题：IL 偏离分布后难自纠，release 是关键瓶颈。
4. 引出 HIL-SERL：demos + reward classifier + SAC + intervention。
5. 讲四个模块各自作用。
6. 讲你会怎么验证：IL-only vs HIL-SERL，success rate 和 intervention rate。
7. 最后强调边界：在线 RL 指标还待实验补齐，但你知道怎么做、怎么评估、风险在哪里。

一句收尾：

> 我不是把 HIL-SERL 当成一个名词放进 PPT，而是把它拆成能在 SO101 上落地的训练系统：已有 demos 提供起点，reward classifier 定义任务成功，SAC actor-learner 在线更新，人类介入保证安全和样本效率，最后用 success rate 和 intervention rate 验证它是否真的优于 IL-only。
