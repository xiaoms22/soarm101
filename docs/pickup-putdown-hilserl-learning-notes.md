# SO-ARM101 Pickup-and-Putdown 知识点与经验总结

本文档用于总结这次 SO-ARM101 pickup-and-putdown 项目中学到的知识点、工程经验和面试表达。重点不是把任务包装成一次单点成功，而是说明我如何把真实机器人学习拆成数据、模型、部署、评测和失败归因，并进一步理解 HIL-SERL 强化学习如何接入。

## 1. 我学到的核心知识点

### 1.1 LeRobotDataset 的本质

LeRobotDataset 把真实机器人操作记录成统一的 observation-action 数据：

| 字段 | 含义 | 本项目经验 |
|------|------|------------|
| `observation.state` | 当前机器人状态 | SO101 使用 6 维关节状态 |
| `observation.images.fixed` | 全局相机图像 | 判断物体、盒子和机械臂整体关系 |
| `observation.images.handeye` | 手眼相机图像 | 补充夹爪附近细节，尤其是抓取和 release |
| `action` | 人类示教或策略输出动作 | 6 维关节目标动作 |
| task string | 语言任务描述 | 必须保持 `Pick up object and Put down in box` 精确一致 |

学到的经验：

- schema 比模型名字更基础。字段名、shape、相机键名、任务字符串不一致，后面训练和部署都会出问题。
- 数据不是“录了视频就行”，而是每一帧都要对应可学习的状态和动作。
- 真实机器人数据需要可回放、可验证、可追溯，否则很难定位失败原因。

### 1.2 Episode 语义比数量更重要

pickup-and-putdown 的关键不是 episode 数越多越好，而是每条 episode 的动作语义干净：

```text
home -> approach -> grasp -> lift -> transfer -> stop -> release -> hold -> end
```

最重要的经验：

- 一条 episode 只放一次尝试。
- 失败后不要补救后继续录在同一条里。
- release 阶段必须“先停稳，再开爪，再保持”。
- 放置完成后不要回 home，因为这会让模型误学到“完成后还要继续移动”。
- 小批量 pilot 验证通过后再扩大数据规模，能节省大量返工。

### 1.3 双相机视角的分工

| 相机 | 贡献 | 容易出的问题 |
|------|------|--------------|
| fixed | 全局定位，看到物体、盒子和机械臂整体 | 相机移动、遮挡、背景干扰会让策略失配 |
| handeye | 看到夹爪附近细节，帮助抓取和释放 | 运动模糊、夹爪遮挡、视野太局部 |

学到的经验：

- fixed 更像任务地图，handeye 更像末端触觉/近距离视觉的替代。
- 训练和部署时相机键名不能随意改，比如 `fixed` 和 `handeye` 已写进数据和模型输入。
- 后续做 reward classifier 时，成功状态最好同时参考 fixed 和 handeye，否则可能只看局部误判。

## 2. 模仿学习、强化学习与 HIL-SERL

### 2.1 模仿学习在本项目中的作用

模仿学习的目标是拟合人类示教：

```text
observation -> action
```

本项目中 Diffusion Policy、ACT、SmolVLA 都属于这个主线或扩展：

| 模型 | 学到的东西 | 优势 | 风险 |
|------|------------|------|------|
| Diffusion Policy | 从视觉和状态生成连续 action chunk | 适合连续控制和多峰动作分布 | 推理较慢，受 `num_inference_steps` 影响 |
| ACT | 直接预测未来动作 chunk | 推理结构清晰，适合作为对照 | 对数据语义和动作分布敏感 |
| SmolVLA | 图像、状态和语言条件下输出动作 | 更接近 VLA 和多任务方向 | 训练和部署成本更高 |

模仿学习的局限：

- 只能学习数据覆盖到的状态。
- 一旦真机 rollout 偏离训练分布，模型很难自己纠正。
- loss 下降不代表真机成功。
- release 这种细节阶段如果数据里不干净，模型会直接学坏。

### 2.2 强化学习解决什么问题

强化学习关注的是交互后的结果：

```text
state -> action -> reward -> next state
```

对真实机器人来说，RL 的价值是：

- 可以在真机交互中继续改进，而不是只依赖离线示教。
- 可以用 reward 把“是否完成任务”纳入优化目标。
- 可以通过探索发现示教数据之外的修正动作。

但真实机器人 RL 的风险也更高：

- 样本昂贵，不能无限试错。
- 探索可能损坏硬件或撞到环境。
- reward 很难手写，尤其是视觉操作任务。
- 训练不稳定，需要严格监控。

### 2.3 HIL-SERL 的核心思想

HIL-SERL 全称是 Human-in-the-Loop Sample-Efficient Reinforcement Learning。它把模仿学习、人类介入和在线强化学习结合起来。

核心流程：

```text
offline demonstrations
-> reward classifier
-> SAC actor-learner
-> human intervention
-> online improvement
```

三个关键组件：

| 组件 | 作用 | 对本项目的意义 |
|------|------|----------------|
| Offline demos | 用少量示教启动 replay buffer 和初始策略 | `so101-left-final-50` 可以作为起点 |
| Reward classifier | 从视觉状态判断是否成功 | 解决 pickup-and-putdown reward 难手写的问题 |
| Human intervention | 人在策略危险或偏离时接管 | 让真实机器人探索更安全、更高效 |

需要强调的证据边界：

- 本地日志已经记录了数据采集、Diffusion/ACT/SmolVLA 训练和 smoke test。
- 本地日志尚未记录完整 HIL-SERL actor-learner 成功率、reward classifier 指标或 intervention rate 曲线。
- 因此在 PPT 中应表述为“已具备 HIL-SERL 接入基础，并设计了迁移路径”，而不是虚构已完成在线 RL 收敛结果。

## 3. SAC、Reward Classifier 与 Human Intervention

### 3.1 SAC 学到什么

SAC, Soft Actor-Critic, 是一种 off-policy actor-critic 强化学习算法。

直观理解：

- Actor 学会输出动作。
- Critic 评估动作长期价值。
- Replay buffer 存储历史 transition。
- Entropy 鼓励策略不要太早变得死板。

为什么适合 HIL-SERL：

- Off-policy 可以复用 demonstrations 和 intervention 数据。
- Replay buffer 能把人工纠正轨迹纳入学习。
- 对连续控制任务比较常用。

我需要会解释的点：

- SAC 不是直接模仿人，而是最大化 reward。
- Human intervention 产生的数据可以作为更高质量探索样本。
- 如果 reward classifier 错了，SAC 会优化错误目标，所以 reward 质量很关键。

### 3.2 Reward classifier 的意义

在真实机器人任务里，手写 reward 很难。例如 pickup-and-putdown 的成功并不是某个单一关节角或距离能完全表示的，而是视觉上“物体稳定落入盒子中”。

Reward classifier 的思路：

```text
image/state -> success probability -> reward / termination
```

训练时需要正负样本：

- 正样本：物体已稳定在盒中，夹爪释放完成。
- 负样本：抓空、掉落、未进盒、卡在夹爪上、还在搬运中。

经验：

- reward classifier 的数据要覆盖失败状态，否则很容易误判。
- 成功后继续记录一小段可以增加正样本。
- threshold 需要在真机上验证，不能只看训练集准确率。

### 3.3 Human intervention 的策略

人类介入不是“人一直开”，而是策略偏离时短时修正。

好的介入：

- 在危险动作前接管。
- 只纠正关键阶段。
- 纠正后尽快把控制权交回策略。
- 随训练进展逐渐减少介入。

对 pickup-and-putdown 的介入重点：

| 阶段 | 何时介入 | 目标 |
|------|----------|------|
| Approach | 末端明显偏离物体 | 把末端拉回可抓取区域 |
| Grasp | 夹爪时机不对 | 纠正闭合时机和姿态 |
| Transfer | 路径可能碰撞或掉落 | 稳定抬起和搬运 |
| Release | 未停稳就开爪 | 强制形成停稳再 release 的轨迹 |

理想指标：

- intervention rate 随训练下降。
- episode success rate 随训练上升。
- episode length 或完成时间逐渐稳定。
- 安全停止次数减少。

## 4. 工程经验与踩坑

### 4.1 先验证链路，再追求成功率

真实机器人项目里，很多问题不在算法本身，而在链路：

- 串口是否被占用。
- 电机是否锁定。
- 相机编号是否变化。
- 视频编码是否可用。
- 数据字段是否对齐。
- 部署 processor 是否和训练一致。

这次学到的做法：

1. 先用 5 条 pilot 跑通采集。
2. 再用 10 条 final pilot 验证最终物体和盒子。
3. validator PASS 后扩展到 50 条。
4. smoke test 先验证加载、相机、推理和动作发送。
5. 最后才做标准 rollout 成功率。

### 4.2 Release 是 pick-and-place 的关键瓶颈

release 看似只是开爪，但对模型来说是时序语义：

```text
到盒子上方 -> 停稳 -> 开爪 -> 等物体脱离 -> 结束
```

如果数据里出现“边移动边开爪”或“开爪后继续乱动”，模型会学到混乱动作。

经验：

- release-tail review frames 很有价值。
- 每条 episode 最后 0.5-1.0 秒要干净。
- 成功后立即结束，不要把后续动作混入。
- 如果 rollout 总在最后失败，优先检查 release 数据，而不是盲目加训练步数。

### 4.3 Action chunk 与延迟

Diffusion Policy 和 ACT 都会输出一段动作 chunk。

好处：

- 动作更连贯。
- 单次推理可以服务多个控制步。

风险：

- 如果早期 chunk 错了，纠正会慢。
- Diffusion chunk 生成帧较慢，影响实时性。
- `num_inference_steps` 太少可能动作质量下降，太多又会增加延迟。

本项目已记录：

- `num_inference_steps=4` 时约 9.10Hz，policy p90 约 174.3ms。
- `num_inference_steps=2` 时约 9.80Hz，policy p90 约 111.5ms。

学到的判断：

- 不能只问模型准不准，还要看控制频率是否足够。
- 真实部署要同时记录成功率和 wall Hz。
- HIL-SERL 中如果 actor 执行动作太滞后，人类介入也会变难。

### 4.4 Normalization 和 relative action

训练和部署之间最容易隐藏错误的是 preprocessing/postprocessing。

需要一致的内容：

- state normalization。
- action normalization。
- 相机 resize/crop。
- action 是 absolute target 还是 relative delta。
- `max_relative_target` 限幅。
- processor 输入输出键名。

经验：

- 如果动作方向异常或幅度很怪，先查 normalization。
- 如果模型在离线数据上看起来正常但真机乱动，查部署 adapter。
- 限幅不是为了提升性能，而是为了真实硬件安全。

## 5. 我学到的研究方法

### 5.1 用 failure taxonomy 推动下一步

失败不能只写“失败了”，要分阶段：

| 失败阶段 | 下一步 |
|----------|--------|
| Approach 失败 | 补采不同物体起点，检查 fixed 相机和 ROI |
| Grasp 失败 | 补采抓取角度和夹爪闭合时机 |
| Transfer 失败 | 检查动作平滑和搬运高度 |
| Release 失败 | 复核 release-tail 数据，补采停稳再开爪 |
| Latency 失败 | 对比 inference steps、模型大小和运行设备 |

这种分析方式能把项目从“调参玄学”变成可复现实验。

### 5.2 小数据也可以有价值，但要承认证据边界

本项目不是开放世界泛化演示，而是一个真实机器人学习闭环：

```text
采集 -> 验证 -> 训练 -> 部署 -> rollout -> 失败分析 -> 下一轮数据
```

小数据的价值：

- 验证硬件和软件链路。
- 暴露 schema、latency、release 等关键问题。
- 形成后续 RL/HIL-SERL 的 offline demos。

证据边界：

- 已完成的是本地自采数据、模型训练摘要和 smoke test。
- 标准 10 次 rollout 成功率还需要补齐。
- HIL-SERL 在线 RL 部分应作为下一步实验路线，而不是已经量化完成的结果。

## 6. 面试表达模板

### 6.1 30 秒版本

我做了一个 SO-ARM101 真实机械臂上的 pickup-and-putdown 闭环。先通过 leader-follower 遥操作采集 fixed 和 handeye 双视角、6DoF state/action 数据，验证 LeRobotDataset schema 后训练 Diffusion Policy、ACT 和 SmolVLA，并部署回真机做 smoke test 和 rollout 评估。这个项目让我重点理解了真实机器人中数据语义、action chunk、normalization、延迟和失败归因的重要性；强化学习上，我把 HIL-SERL 作为下一步路线，用 demonstrations、reward classifier、SAC actor-learner 和 human intervention 继续提升样本效率。

### 6.2 2 分钟版本

这个项目的任务是让 SO-ARM101 从桌面抓起物体并放入盒中。我先搭建真实数据链路：follower 在 `COM3`，leader 在 `COM4`，fixed camera 和 handeye camera 分别记录全局和末端视觉，数据按 LeRobotDataset 保存为 `observation.state`、`observation.images.fixed`、`observation.images.handeye` 和 `action`。

采集上我没有一开始就大规模录，而是先做 5 条 pilot，再做 10 条 final pilot，validator PASS 后扩到 50 条 left-final 数据。这个过程中最重要的经验是 episode 语义必须干净，尤其 release 要先停稳再开爪，否则模型会学到错误时序。

模型上我做了 Diffusion Policy 主线、ACT 对照和 SmolVLA 扩展，并做了本地和 live smoke test。Diffusion 的延迟主要来自 action chunk 生成，所以需要比较 `num_inference_steps` 对成功率和实时性的影响。接下来我会用固定 10 次 rollout 表统计 approach、grasp、transfer 和 release 的阶段成功率。

强化学习部分我理解为在 imitation learning 的基础上接入 HIL-SERL：用已有 demonstrations 初始化，训练 reward classifier 自动判断成功状态，再用 SAC actor-learner 在线更新策略。人在策略偏离或危险时短时介入，目标是让 intervention rate 下降、成功率上升。这个部分我会明确标注为下一步验证，不会把未记录的指标写成已完成结果。

### 6.3 可追问问题回答

**为什么不用纯 RL 从零开始？**

真实机器人样本贵且探索有安全风险。先用示教数据启动策略和 replay buffer，再用 HIL-SERL 做在线改进，比从零探索更安全、更省样本。

**为什么 release 是瓶颈？**

因为 release 不是单个开爪动作，而是“到盒子上方、停稳、开爪、等待物体脱离、结束”的时序。如果示教里混入边移动边开爪或放置后继续乱动，模型会学习到错误动作分布。

**为什么需要 reward classifier？**

pickup-and-putdown 的成功是视觉语义，手写 reward 很难完整覆盖。reward classifier 可以从 fixed/handeye 图像判断物体是否稳定在盒中，为 SAC 提供成功奖励和终止信号。

**为什么要记录失败分类？**

因为不同失败对应不同改进方式。抓取失败要补抓取数据，release 失败要补 release-tail，延迟问题要调 inference steps 或模型部署，不能都归因成“模型不行”。

**怎么证明是真机闭环而不是只训练了模型？**

需要展示数据目录、validator 结果、训练配置、checkpoint、部署命令、live smoke timing、rollout 视频和 10 次标准评估表。训练 loss 只是中间证据，真机 rollout 才是任务证据。

## 7. 一句话经验总结

这次项目最大的收获是：真实机器人学习不是单纯换一个更大的模型，而是把数据语义、schema、训练、部署延迟、安全限幅、rollout 评估和失败归因连成闭环；HIL-SERL 的价值正是在这个闭环上加入 reward、在线更新和人类介入，让策略从“模仿成功样本”进一步走向“在真实交互中变好”。
