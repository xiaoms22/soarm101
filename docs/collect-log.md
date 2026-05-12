# 采集日志

> 记录每次数据采集的参数、问题和进展。

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
| Handeye 相机 | Camera 1 | 640×480, 30fps |

### 软件配置

- **lerobot 版本**：0.5.1 (本地源码 D:\lerobot\upstream\lerobot)
- **Python 版本**：3.14.4 (miniforge3 环境 lerobot-so101)
- **视频编码**：h264 (CPU，无 NVIDIA GPU)

### 数据格式验证

- ✅ observation.state: [6] 关节角度
- ✅ action: [6] 目标角度
- ✅ observation.images.fixed: video [480,640,3]
- ✅ observation.images.handeye: video [480,640,3]
- ✅ 回放验证通过

### 遇到的问题

1. **draccus 版本兼容性** - Python 3.14 与 draccus 0.10.0 不兼容，降级后解决
2. **COM3 端口占用** - 遥操作程序未正确释放串口，需重启 PowerShell 或关闭占用程序
3. **从臂电机锁定** - `disable_torque_on_disconnect=True` 导致断开后电机锁定，改为 `False`
4. **GPU 编码错误** - 无 NVIDIA GPU，改用 h264 CPU 编码
5. **校准文件不匹配** - 每次启动都需要重新校准，使用 `calibration_dir` 和 `id` 参数指定校准文件

### 下一步计划

- [ ] 采集更多数据（扩展到 33 条）
- [ ] 尝试 center 和 right 分区数据采集
- [ ] 将数据传输到台式机进行 Diffusion Policy 微调

---
