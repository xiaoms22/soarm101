# SO-ARM101 项目 AI 操作指南

> 本文档用于让 AI 助手理解本项目的结构、工作流程和操作方法。

---

## 项目概述

**项目名称**：SO-ARM101 机械臂数据采集与训练

**目标**：基于 HuggingFace 的 SO-ARM101 预训练模型（Diffusion Policy），通过采集真机示教数据进行微调，实现 pickup-and-putdown 任务。

**任务描述**：机械臂抓取桌面物体并放入盒中

**GitHub 仓库**：https://github.com/xiaoms22/soarm101

**分支**：`main`

---

## 目录结构

```
D:/lerobot/soarm101/
├── docs/                           # 文档目录
│   ├── data-collection-protocol.md # 数据采集协议
│   ├── collect-log.md              # 采集、训练、部署日志
│   ├── final-pilot-data-collection.md
│   ├── local-deployment-smoke-test.md
│   ├── live-deployment-smoke-test.md
│   └── AI_REPOSITORY_GUIDE.md      # 本文档
├── data/                           # 数据采集目录（不上传 GitHub）
│   ├── so101-left-final-pilot/     # 10 条 final pilot 数据集
│   └── so101-left-final-50/        # 50 条 left final 数据集
├── soarm101_lab/                   # 实验室相关文件
│   └── calibrations/               # 机械臂校准文件
│       ├── so101_follower_01.json  # 从臂校准
│       └── so101_leader_01.json    # 主臂校准
├── upstream/                       # 上游源码（lerobot 本地副本）
│   └── lerobot/
├── record_config.yaml              # 数据采集配置文件（不上传 GitHub，已 ignore）
└── README.md                       # 项目说明
```

---

## 硬件配置

| 设备 | 端口 | 说明 |
|------|------|------|
| 从臂 (follower) | COM3 | SO-ARM101 被控制臂 |
| 主臂 (leader) | COM4 | SO-ARM101 主控臂（遥操作用） |
| Fixed 相机 | Camera 0 | 全局俯视，640×480 |
| Handeye 相机 | Camera 2 | 手眼相机，640×480 |

**记忆规则**：主臂 COM4，从臂 COM3

---

## 软件环境

### Python 环境

- **环境管理器**：Miniforge3
- **环境名称**：`lerobot-so101`
- **Python 版本**：3.12.13
- **脚本选择 Python 的顺序**：`-Python` 参数 → `SOARM101_PYTHON` → 当前 conda 环境 → `PATH` 中的 `python`

### 激活环境命令（PowerShell）

```powershell
conda activate lerobot-so101
cd D:\lerobot\soarm101
$env:SOARM101_PYTHON = (Get-Command python).Source
```

### 关键包

- **lerobot**：0.5.1（本地源码位于 `D:\lerobot\upstream\lerobot`）
- 使用 `python -m lerobot.scripts.xxx` 运行命令

---

## Git 操作规范

### 配置（已设置）

```bash
cd D:/lerobot/soarm101
git config user.email "xiaoms22@users.noreply.github.com"
git config user.name "xiaoms22"
```

### 常用操作

```bash
# 查看状态
git status

# 添加文件
git add docs/collect-log.md

# 提交
git commit -m "描述信息"

# 推送
git push origin main
```

### 提交消息格式

```
类型: 简短描述

详细说明（可选）
```

类型示例：
- `docs:` - 文档更新
- `data:` - 数据相关
- `config:` - 配置更新
- `fix:` - 问题修复

---

## 数据采集流程

### 1. 配置文件

位置：仓库根目录的 `record_config.yaml`。该文件包含本机串口、相机编号和校准目录，只保留在本地，不提交 GitHub。

**关键参数**：
- `robot.port: COM3` - 从臂串口
- `teleop.port: COM4` - 主臂串口
- `dataset.fps: 10` - 录制帧率
- `dataset.video: true` - 启用视频
- `dataset.vcodec: h264` - CPU 编码（当前笔记本无 NVIDIA GPU）
- 采集脚本传入 `--display_data=false` - 避免当前环境缺少 Rerun Viewer 可执行文件时报错
- `robot.disable_torque_on_disconnect: false` - 防止电机锁定

### 2. 采集命令

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_final_pilot_collection.ps1

# 扩展 left-final 数据集时：
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_left_final_50_collection.ps1 -Resume
```

### 3. 校准流程

程序启动时会自动校准（如果校准文件不匹配）：
1. 移动从臂到中间位置，按 Enter
2. 依次移动各关节到最大范围，按 Enter
3. 对主臂重复相同操作

### 4. 录制操作

- 控制主臂，从臂会跟随
- 完成任务后按 `Shift+Space` 结束 episode
- 程序自动开始下一条 episode

### 5. 回放验证

```powershell
python -m lerobot.scripts.lerobot_replay --robot.type=so101_follower --robot.port=COM3 --dataset.repo_id=xiaoms22/so101-left-final-pilot --dataset.root=.\data\so101-left-final-pilot --dataset.episode=0
```

---

## 数据格式规范

### 输入特征（训练用）

| 特征 | 形状 | 说明 |
|------|------|------|
| observation.state | [6] | 6 个关节角度 |
| observation.images.fixed | [3, 480, 640] | 全局相机 RGB |
| observation.images.handeye | [3, 480, 640] | 手眼相机 RGB |
| action | [6] | 6 个关节目标角度 |

### Episode 语义

一个完整的 episode 应包含：
1. 起始姿态（home pose）
2. 接近目标物
3. 夹爪闭合抓取
4. 抬起并搬运
5. 停在盒子上方
6. **先停稳，再张爪**（关键）
7. 保持静止 0.5-1 秒
8. 物体落入盒中
9. 立即结束

### 禁止行为

- 放置后继续移动
- 边移动边张爪
- 失败后的补救动作

---

## 常见问题解决

### COM3 端口被占用

**错误**：`PermissionError(13, '拒绝访问。', None, 5)`

**解决**：
1. 关闭所有 PowerShell 窗口
2. 重新打开并激活环境
3. 或重启从臂电源

### 从臂电机锁定

**现象**：从臂不动或松软

**解决**：
1. 运行遥操作解锁：`python -m lerobot.scripts.lerobot_teleoperate --robot.type=so101_follower --robot.port=COM3 --teleop.type=so101_leader --teleop.port=COM4`
2. 或重启从臂电源

### GPU 编码错误

**错误**：`Cannot load nvcuda.dll`

**解决**：配置中使用 `vcodec: h264`（CPU 编码）

### 目录已存在错误

**错误**：`FileExistsError: 当文件已存在时...`

**解决**：更换新的数据集名称，或确认旧数据已经归档后再删除旧目录
```powershell
Remove-Item -Recurse -Force .\data\DATASET_NAME
```

---

## 数据验证检查清单

采集完成后验证：

```python
import pandas as pd
import json

# 检查 episode 信息
df = pd.read_parquet('data/so101-left-final-pilot/meta/episodes/chunk-000/file-000.parquet')
print(df[['episode_index', 'length']])

# 检查特征
with open('data/so101-left-final-pilot/meta/info.json', 'r') as f:
    info = json.load(f)
print(info['features']['observation.images.fixed'])
print(info['features']['observation.images.handeye'])
```

**预期结果**：
- episodes 数量正确
- 每条 300 帧（10fps × 30秒）
- 图像 shape: [480, 640, 3]

---

## 更新采集日志

位置：`docs/collect-log.md`

**添加记录模板**：

```markdown
## 采集记录 YYYY-MM-DD

- 数据集名称：so101-left-final-pilot
- 采集条数：X
- 总帧数：Y
- 遇到的问题：
- 下一步计划：
```

**提交到 GitHub**：

```bash
git add docs/collect-log.md
git commit -m "docs: add YYYY-MM-DD collection log"
git push origin main
```

---

## 重要提示

1. **data/ 目录不上传 GitHub** - 已在 `.gitignore` 中排除
2. **models/、outputs/、wandb/ 不上传 GitHub** - 只在文档中记录摘要
3. **record_config.yaml 不上传** - 已在 `.gitignore` 中排除，包含本地路径和硬件配置
4. **每次采集前检查**：机械臂上电、相机连接、桌面布置
5. **先小批量验证** - 用 5-10 条验证协议正确性，再扩展到 33-50 条
6. **release 阶段最关键** - 先停稳再张爪，不要边动边开

---

## AI 助手操作建议

当用户需要 AI 帮助时，AI 应该：

1. **先阅读本文档** - 理解项目结构和配置
2. **阅读 `docs/data-collection-protocol.md`** - 了解详细采集协议
3. **阅读 `docs/collect-log.md`** - 了解历史采集、训练、部署记录
4. **检查当前状态** - 运行验证命令确认环境正常
5. **执行操作** - 按照本文档的流程执行
6. **记录日志** - 操作完成后更新 `collect-log.md`

---

## 快速命令参考

```powershell
# 激活环境
conda activate lerobot-so101
cd D:\lerobot\soarm101
$env:SOARM101_PYTHON = (Get-Command python).Source

# 开始采集
powershell -ExecutionPolicy Bypass -File .\scripts\collect\run_final_pilot_collection.ps1

# 回放验证
python -m lerobot.scripts.lerobot_replay --robot.type=so101_follower --robot.port=COM3 --dataset.repo_id=xiaoms22/so101-left-final-pilot --dataset.root=.\data\so101-left-final-pilot --dataset.episode=0

# Git 提交
git add docs/collect-log.md
git commit -m "docs: update collection log"
git push origin main
```
