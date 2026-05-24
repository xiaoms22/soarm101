# 采集日志

> 记录每次数据采集的参数、问题和进展。

---

## 训练与部署记录 2026-05-19

- **数据集**：`so101-left-final-50`
- **训练模型**：SmolVLA fine-tune：`smolvla-left-final-50-200k`，200k steps，batch size 4，`rename_map` 将 `observation.images.fixed` 映射到 `camera1`，`observation.images.handeye` 映射到 `camera2`，并启用 1 路 empty camera。
- **部署检查**：完成两轮本地 30s live smoke，日志保存在 `outputs/rollout_logs/left_final_50_smolvla-200k_smoke_20260519_004218.csv` 和 `outputs/rollout_logs/left_final_50_smolvla-200k_smoke_20260519_004610.csv`；这些 CSV 和模型权重只保留本地，不上传 GitHub。
- **控制循环摘要**：
  - 两轮分别记录 204 / 205 steps，实际约 6.8Hz，未达到目标 10Hz。
  - 去掉首帧 warmup 后，p90 loop time 约 5.8-5.9ms，但存在约 2.0s 的周期性长帧，疑似 SmolVLA action chunk 生成开销。
  - clamped actions 分别为 26/203 和 24/204，仍需人工复盘动作幅度和现场表现。
- **脚本更新**：`scripts/deploy/run_live_diffusion_left_final_50_smoke.ps1` 增加 `smolvla-200k` 入口，并将 `smolvla` 默认别名指向 200k checkpoint。
- **当前结论**：SmolVLA 200k checkpoint 可加载并能跑通真实控制循环，但目前只能证明部署链路可运行；还不能作为任务成功率结论。
- **下一步计划**：
  - [ ] 先用最佳 Diffusion checkpoint 做 10 次标准 left rollout，补齐成功率和失败模式。
  - [ ] 再对 SmolVLA 200k 做同样的 10 次对照 rollout，重点观察长帧是否导致动作停顿。
  - [ ] 如果继续评估 SmolVLA，需要把 chunk 长帧、clamp 频率和实际抓取/释放结果放在同一张表里复盘。

---

## 训练与部署记录 2026-05-17

- **数据集**：`so101-left-final-50`
- **训练模型**：
  - Diffusion Policy scratch：`diffusion-left-final-50-scratch-10k`，10k steps，batch size 4
  - Diffusion Policy fine-tune：`diffusion-left-final-50-from-006000-4k`，4k steps，batch size 4
  - ACT baseline：`act-left-final-50-10k`，10k steps，batch size 4
  - Diffusion final-pilot quick check：`diffusion-left-final-pilot-2k`，2k steps，batch size 4
- **部署检查**：已生成多轮 `outputs/rollout_logs/left_final_50_*_smoke_*.csv` 控制日志；这些日志只保留本地，不上传 GitHub。
- **当前结论**：
  - Diffusion Policy 仍是主线，ACT 作为对照 baseline。
  - SmolVLA base 已作为备选方向准备；当日尚未发现 `smolvla-left-final-50` 训练 checkpoint，后续 2026-05-19 已补充 200k smoke 记录。
  - 现有日志主要证明控制循环可运行；还缺少人工标注的 10 次标准 rollout 成功率表。
- **下一步计划**：
  - [ ] 按统一协议复盘 smoke CSV 和现场表现，区分抓取失败、搬运掉落、release 失败和动作跳变。
  - [ ] 为最佳 Diffusion checkpoint 做 10 次标准 left rollout，并补充成功率。
  - [ ] 如果 Diffusion release 不稳，再用 ACT baseline 做同样的 10 次对照评估。

---

## 采集记录 2026-05-16 / 2026-05-17

- **数据集名称**：so101-left-final-50
- **采集条数**：50 episodes
- **总帧数**：15000 frames (300 frames/episode)
- **FPS**：10
- **任务字符串**：Pick up object and Put down in box
- **区域**：left
- **验证时间**：2026-05-17
- **验证结果**：PASS

### 数据格式验证

- episode count: 50
- observation.state: [6]
- action: [6]
- observation.images.fixed: video [480,640,3], h264, 15000 frames @ 10fps
- observation.images.handeye: video [480,640,3], h264, 15000 frames @ 10fps
- data rows: 15000
- action has no NaN
- observation.state has no NaN
- gripper action range: 80.896
- task string matches exactly: `Pick up object and Put down in box`

### 处理规则

- 原始数据位于本地 `data/`，不上传 GitHub。
- review frames 和 rollout CSV 位于本地 ignored 目录，只在本文档中记录摘要。
- 该数据集已经超过最初 33 条 left 目标，可进入 Diffusion Policy 主线训练和 ACT 对照评估。

### 下一步计划

- [ ] 人工抽查 release-tail review frames，确认每条 episode 都是停稳后开爪。
- [ ] 固定 10 次 rollout 评估协议，补齐成功率和失败模式。
- [ ] 根据评估结果决定是否采集 center-pilot 或补采 left hard cases。

---

## 采集记录 2026-05-16

- **数据集名称**：so101-left-final-pilot
- **采集时间**：2026-05-16 17:05-17:11
- **采集条数**：10 episodes
- **总帧数**：3000 frames (300 frames/episode)
- **FPS**：10
- **任务字符串**：Pick up object and Put down in box
- **区域**：left
- **验证结果**：PASS

### 硬件配置

| 设备 | 端口/编号 | 说明 |
|------|----------|------|
| 从臂 (follower) | COM3 | SO-ARM101 follower_01 |
| 主臂 (leader) | COM4 | SO-ARM101 leader_01 |
| Fixed 相机 | Camera 0 | 顶部/全局视角，640×480, 30fps |
| Handeye 相机 | Camera 2 | 腕部/夹爪视角，640×480, 30fps |

### 采集前处理

1. 发现主臂部分姿态可达但从臂不可达，停止第一次采样。
2. 重新标定 active ids：`leader_01` 和 `follower_01`。
3. 低速遥操作检查通过后重新开始采集。
4. 禁用 `display_data`，避免缺少 Rerun Viewer 导致 `lerobot_record` 启动失败。

### 数据格式验证

- ✅ episode count: 10
- ✅ observation.state: [6]
- ✅ action: [6]
- ✅ observation.images.fixed: video [480,640,3]
- ✅ observation.images.handeye: video [480,640,3]
- ✅ data rows: 3000
- ✅ action has no NaN
- ✅ observation.state has no NaN
- ✅ gripper action range: 48.267
- ✅ fixed video decodes: 3000 frames @ 10fps
- ✅ handeye video decodes: 3000 frames @ 10fps

### 验证产物

- release-tail review frames: `data/so101-left-final-pilot/validation_review/`
- fixed overview: `data/so101-left-final-pilot/validation_review/overview_fixed_release_tail.jpg`
- handeye overview: `data/so101-left-final-pilot/validation_review/overview_handeye_release_tail.jpg`

### 下一步计划

- [ ] 人工复核 release-tail overview，确认每条 episode 都是停稳后开爪。
- [ ] 将 `so101-left-final-pilot` 同步到训练机。
- [ ] 用 diffusion-left-sota 做快速微调验证。
- [ ] 如果微调/rollout 方向正确，将 left 数据扩展到 30-50 条。

---

## 采集记录 2026-05-12

- **数据集名称**：so101-left-pilot
- **采集时间**：2026-05-12 19:15
- **采集条数**：5 episodes
- **总帧数**：1500 frames (300 frames/episode)
- **FPS**：10

### 硬件配置

| 设备 | 端口/编号 | 说明 |
|------|----------|------|
| 从臂 (follower) | COM3 | SO-ARM101 follower_01 |
| 主臂 (leader) | COM4 | SO-ARM101 leader_01 |
| Fixed 相机 | Camera 0 | 640×480, 30fps |
| Handeye 相机 | Camera 1 | 640×480, 30fps（历史 pilot 记录；当前 final 配置已切到 Camera 2） |

### 软件配置

- **lerobot 版本**：0.5.1 (本地源码 D:\lerobot\upstream\lerobot)
- **Python 版本**：3.12.13 (miniforge3 环境 lerobot-so101)
- **视频编码**：h264 (CPU，无 NVIDIA GPU)

### 数据格式验证

- ✅ observation.state: [6] 关节角度
- ✅ action: [6] 目标角度
- ✅ observation.images.fixed: video [480,640,3]
- ✅ observation.images.handeye: video [480,640,3]
- ✅ 回放验证通过

### 遇到的问题

1. **draccus 版本兼容性** - Python 3.12 环境中 draccus 版本不兼容，降级后解决
2. **COM3 端口占用** - 遥操作程序未正确释放串口，需重启 PowerShell 或关闭占用程序
3. **从臂电机锁定** - `disable_torque_on_disconnect=True` 导致断开后电机锁定，改为 `False`
4. **GPU 编码错误** - 无 NVIDIA GPU，改用 h264 CPU 编码
5. **校准文件不匹配** - 每次启动都需要重新校准，使用 `calibration_dir` 和 `id` 参数指定校准文件

### 下一步计划

- [ ] 采集更多数据（扩展到 33 条）
- [ ] 尝试 center 和 right 分区数据采集
- [ ] 将数据传输到台式机进行 Diffusion Policy 微调

---
