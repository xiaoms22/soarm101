# SO-ARM101 数据采集协议

> 本协议基于 [Full-Stack-Entity/so101-left-sota-pack](https://huggingface.co/datasets/Full-Stack-Entity/so101-left-sota-pack) 的采集经验整理，面向 Diffusion Policy 微调数据采集。

---

## 任务定义

**任务名称**：pickup-and-putdown（抓取并放入盒子）

**任务描述**：
1. 从桌面抓取目标物体
2. 搬运到固定盒子上方
3. 张开夹爪放置物体
4. 物体稳定落入盒中
5. 立即结束 episode

**任务字符串（必须一致）**：
```
Pick up object and Put down in box
```

---

## 硬件配置要求

### 相机

模型要求两路相机，命名和参数必须严格匹配：

| 键名 | 类型 | 分辨率 | 帧率 | 说明 |
|------|------|--------|------|------|
| `fixed` | 俯视/全局相机 | 640×480 | 30fps | 放在固定支架上，拍摄整个工作台 |
| `handeye` | 手眼相机 | 640×480 | 30fps | 安装在机械臂末端，跟随运动 |

> **注意**：相机键名 `fixed` 和 `handeye` 是硬编码到模型 input_features 中的，不可更改。

### 机械臂

- **型号**：SO-ARM101 follower arm
- **自由度**：6 DOF（状态向量维度 = 6，动作向量维度 = 6）
- **串口**：需确认实际端口（Linux 通常为 `/dev/ttyACM0` 或 `/dev/ttyACM1`）

---

## 数据格式规范

### 模型输入特征

```
observation.state        → shape [6]   — 6 个关节角度
observation.images.fixed → shape [3, 480, 640]  — 全局相机 RGB
observation.images.handeye → shape [3, 480, 640] — 手眼相机 RGB
action                   → shape [6]   — 6 个关节目标角度
```

### 录制参数

| 参数 | 值 | 说明 |
|------|----|------|
| `dataset.fps` | **10** | 训练用 10fps，不是相机原生 30fps |
| `dataset.video` | `true` | 存储为视频格式 |
| `dataset.streaming_encoding` | `true` | 实时编码减少磁盘 IO |
| `dataset.encoder_threads` | `2` | 编码线程数 |
| `dataset.vcodec` | `auto` | 自动选择编解码器 |
| `dataset.push_to_hub` | `false` | 本地保存，不自动上传 |

---

## 采集节奏规划

### 分区策略

按物体位置将工作区分为三个分区，**当前优先采集左侧分区**：

| 分区 | 物体位置 | 优先级 | 目标条数 |
|------|----------|--------|----------|
| left（左侧） | 机械臂左侧工作区 | **优先** | 33 条 |
| center（中间） | 机械臂正前方 | 次优先 | 33 条 |
| right（右侧） | 机械臂右侧工作区 | 待定 | 33 条 |

### 采集步骤

```
第一步：left-pilot（5-10 条）
  → 验证采集质量和 release 语义是否清晰
  → 用 5 条快速训练验证模型能否稳定 release

第二步：left-full（扩展到 33 条）
  → 只有 pilot 验证通过再继续

第三步：根据 left 经验扩展 center / right
```

> **不要一开始就录满 33 条再看结果。** 先用 5-10 条验证协议正确性。

---

## Episode 语义规范

### 一个合法 episode 的完整语义

```
① 起始姿态（follower 对齐到统一 home pose）
② 接近目标物
③ 夹爪闭合抓取
④ 抬起并搬运到盒子上方
⑤ 末端停稳在盒子正上方
⑥ 夹爪明确张开
⑦ 保持末端静止 0.5~1.0 秒
⑧ 物体脱离夹爪稳定落入盒中
⑨ 立即结束 episode（按停止键）
```

### 严禁混入 episode 的行为

- 放置完成后回 home
- 放置后继续摆动或悬停
- 放置失败后的补救动作
- episode 结束前多次试探性开合爪
- 边移动边张爪（应先停稳再张爪）

### release 阶段的节奏要求

```
❌ 错误：边移动边张爪
✅ 正确：先停稳 → 再张爪 → 确认物体脱落 → 结束
```

release 是**最关键的阶段**，建议有意识地放慢操作：

1. 搬运到盒子正上方
2. **先停稳末端**（不要继续移动）
3. 缓慢张开夹爪
4. 目视确认物体脱离夹爪
5. 维持静止 ~1 秒
6. 按键结束 episode

---

## 一致性要求

### 起始姿态

每条 episode 开始前必须：
- follower 回到**同一个 home pose**（关节角度记录下来）
- 相机位置未移动
- 桌面布局未变（盒子固定，无新增遮挡）

### 场景布置

| 要素 | 要求 |
|------|------|
| 盒子位置 | 全程固定不动 |
| 目标物位置 | 在当前分区小范围随机扰动（±3-5cm） |
| 相机位置 | 固定不动 |
| 桌面环境 | 无无关遮挡物 |

### 单次采集的变量控制

**不要同时改变多个变量**。每批次只允许一个维度有扰动：

```
✅ 只扰动目标物横向位置（left 分区内）
❌ 同时扰动目标物位置 + 盒子位置 + 起始姿态
```

---

## 录制命令模板

### 采集命令（需按实际硬件修改的部分已标注）

```bash
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \                          # ← 修改为实际串口
  --robot.id=my_so101_follower \
  --robot.disable_torque_on_disconnect=false \
  --robot.cameras="{ \
    fixed: {type: opencv, index_or_path: 4, width: 640, height: 480, fps: 30}, \
    handeye: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30} \
  }" \                                                 # ← 修改 index_or_path 为实际相机编号
  --dataset.single_task="Pick up object and Put down in box" \
  --dataset.fps=10 \
  --dataset.video=true \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  --dataset.vcodec=auto \
  --dataset.episode_time_s=30 \                        # ← 单 episode 最长时间（秒）
  --dataset.reset_time_s=10 \                          # ← 两条 episode 间 reset 时间
  --dataset.num_episodes=10 \                          # ← pilot 阶段先录 10 条
  --dataset.push_to_hub=false \
  --dataset.root=./data/so101-left-pilot              # ← 数据保存路径
```

### 如何确认相机编号

```bash
# 列出所有可用相机
python -c "
import cv2
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f'Camera {i}: available')
        cap.release()
"
```

### 如何确认串口

```bash
# Linux
ls /dev/ttyACM*
ls /dev/ttyUSB*

# 或者
dmesg | grep tty | tail -5
```

---

## 每条 Episode 操作 Checklist

### 开始前

- [ ] follower 已回到 home pose
- [ ] 盒子位置已固定
- [ ] 目标物在左侧分区允许范围内
- [ ] 两路相机画面正常，无遮挡
- [ ] 按下录制开始键

### 进行中

- [ ] 动作流畅，无明显抖动
- [ ] 抓取时夹爪完全闭合
- [ ] 失败时立刻按键放弃，重新开始

### 结束时

- [ ] 末端已停稳在盒子上方
- [ ] 夹爪已完全张开
- [ ] 物体已脱离夹爪
- [ ] 物体稳定留在盒中
- [ ] 保持静止约 1 秒后按键结束

### Reset 阶段

- [ ] 机械臂回 home pose
- [ ] 目标物取出放回左侧分区随机位置
- [ ] 确认相机视野正常后开始下一条

---

## 采集质量验收标准

pilot（5-10 条）完成后，用以下命令快速验证：

```bash
# 回放 episode 0 检查动作是否流畅
lerobot-replay \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --dataset.root=./data/so101-left-pilot \
  --episode=0
```

**合格标准**：
1. 回放能稳定复现抓取和放置动作
2. release 阶段有明显停顿再张爪
3. 无大幅抖动或异常动作

只有回放验证通过后，再继续录制扩展到 33 条。

---

## 数据目录规范

```
data/
├── so101-left-pilot/     ← pilot 5-10 条
├── so101-left33/         ← 扩展后完整左侧数据 33 条
├── so101-center33/       ← 后续中侧数据（暂缓）
└── so101-right33/        ← 后续右侧数据（暂缓）
```

数据目录**不上传 GitHub**（已在 `.gitignore` 中排除）。

---

## 与上游数据集的关系

本次采集数据将用于微调以下模型：

- **基础模型**：`so101-left-sota-pack/models/diffusion-left-sota`
- **上游参考数据集**：`Full-Stack-Entity/so101-grasp-99`（`so101-grasp-left33` 子集）
- **本次任务**：与上游相同的 pickup-and-putdown，数据格式完全兼容

微调命令参见 `scripts/train/` 目录。
