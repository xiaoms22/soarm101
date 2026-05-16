# SO-ARM101 4-6 周推进路线

目标是在 4-6 周内把项目推进到可稳定展示：有项目报告、数据证据、训练记录、真机 rollout、成功率统计和后续研究路线。

## Week 1: 报告骨架和现状整理

- 完成 `docs/project-report.md` 初稿。
- 汇总当前已完成证据：硬件连接、双摄像头、pilot 数据、本地 smoke test、live smoke test。
- 统一术语：SO-ARM101/SO101、follower、leader、fixed、handeye、episode、rollout、checkpoint。
- 准备 1 张闭环图和 3 张表：数据格式、模型对比、实验结果。
- 整理已有视频和截图，没有就列出待补拍清单。

验收标准：

- 老师能从报告中看懂项目目标和完整闭环。
- 当前完成度、缺口和下一步路线清楚。

## Week 2: 高质量 left-final 数据

- 运行相机检查：`scripts/collect/check_cameras.py`。
- 采集 `so101-left-final-pilot` 10 条 episodes。
- 运行 `scripts/collect/validate_final_pilot.ps1`。
- 抽查 `validation_review` 中 release-tail 图片。
- 如果 10 条通过，扩展到 30-50 条 left-final 数据。

验收标准：

- final 数据集 validator 结果为 `PASS`，或所有 warning 都有明确处理。
- release 阶段语义清楚：先停稳，再开爪，再保持。
- 数据集可用于训练。

## Week 3: Diffusion Policy 主线训练

- 在 GPU 台式机上训练 Diffusion Policy。
- 固定记录训练数据版本、训练命令、训练步数、batch size、GPU、训练耗时、checkpoint 路径。
- 保存 loss 曲线和配置文件。
- 将 checkpoint 同步回笔记本部署目录。

验收标准：

- 有可追溯 checkpoint。
- 能解释训练 loss 的意义和局限。
- 模型进入真机评估阶段。

## Week 4: 真机推理和 10 次评估

- 用训练后的 checkpoint 运行真机 rollout。
- 固定评估协议：left 区域，10 次标准 trial。
- 测试 `num_inference_steps=2/4/6/8`。
- 记录 wall Hz、成功率、失败类型、代表性视频。
- 选择成功率和实时性最平衡的推理配置。

验收标准：

- 至少有 1 个完整成功 rollout 视频。
- 有 10 次标准评估表，不只展示最好结果。
- 能说明主要失败来自抓取、搬运、release 还是实时性。

## Week 5-6: 扩展实验和材料定稿

- 做一个轻量对比：ACT baseline 或 SmolVLA/LoRA 小实验。
- 采集 center-pilot 10 条，测试 left-only 模型泛化。
- 完成项目报告定稿、README 入口、演示视频清单。
- 准备 5 分钟讲述版和 15 分钟追问版材料。

验收标准：

- 项目具有“工程闭环 + 原理理解 + 研究扩展”的结构。
- 能回答数据、模型、训练、推理、失败分析和后续科研问题。

## 展示完成度分级

| 等级 | 内容 | 是否够给老师看 |
|------|------|----------------|
| 最低线 | 10 条 final pilot、validator 通过、复用 checkpoint 推理、有 rollout 视频 | 可以初步展示 |
| 推荐线 | 30-50 条 left 数据、Diffusion 真机成功率统计、失败分析、完整报告 | 推荐展示 |
| 加分线 | ACT/SmolVLA/LoRA 对比、center/right 泛化、消融分析 | 适合科研型交流 |
