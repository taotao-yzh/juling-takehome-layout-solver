# TakeHome Layout Solver

这是一个二维房间物品摆放题的求解器。

## 1. 问题理解

题目给定：

- 房间轮廓 `boundary`
- 门的位置 `door`
- 门是否内开 `isOpenInward`
- 若干待摆放物品 `algoToPlace`

目标是把每个矩形物品放进不规则房间内，并满足：

- 不超出房间边界
- 物品之间不重叠
- 不遮挡门
- 内开门要额外预留 `N x N` 空间
- 物体允许旋转，但只允许与房间边平行或垂直
- 空间充足时尽量贴墙放置
- 冰箱需要预留开门侧空间

## 2. 核心实现思路

本项目采用的是 **候选点生成 + 启发式排序 + 回溯搜索** 的方式，而不是求全局最优。

流程如下：

1. 读取 JSON 输入，解析房间轮廓、门、物品尺寸。
2. 构造房间多边形和门的禁放区域。
3. 如果门是内开，则额外构造门扇占用区域。
4. 沿着房间边界生成贴墙候选位置。
5. 按照约束强度和面积对物品排序，优先放冰箱等难放物体。
6. 对每个物品逐个尝试候选位置。
7. 每次尝试时检查：
   - 是否完全在房间内
   - 是否和已放物体重叠
   - 是否挡门
   - 是否进入内开门区域
   - 是否触碰冰箱开门预留区
8. 如果当前顺序放不下，就回溯尝试别的候选点。

这样做的优点是：

- 实现简单
- 容易解释
- 调试方便
- 适合 take-home 交付

## 3. 数据结构

- `RoomInput`：保存题目输入
- `ItemSpec`：保存物品名称和尺寸
- `Placement`：保存最终输出的中心点和旋转角度
- `SolveResult`：保存是否可行、摆放结果和失败原因

## 4. 运行环境

- Python 3.9+
- Shapely
- Matplotlib

## 5. 安装依赖

```bash
pip install -r requirements.txt
```

## 6. 运行方式

```bash
python -m src.main examples/example1.json
```

运行后会生成：

- `outputs/example1_output.json`
- `outputs/example1.png`

## 7. 输出格式

输出 JSON 包含：

- `feasible`：是否成功摆放
- `reason`：失败原因（如果有）
- `placements`：每个物品的结果

示例：

```json
{
  "feasible": true,
  "reason": null,
  "placements": [
    {
      "name": "fridge",
      "center": [5423.4423, 31841.7939],
      "rotation": 90.0,
      "length": 1220,
      "width": 1330
    }
  ]
}
```

## 8. 样例说明

项目已对题目提供的 4 个样例进行了验证：

- `example1.json`
- `example2.json`
- `example3.json`
- `example4.json`

每个样例都会输出对应的 JSON 和 PNG 图。

## 9. 目录结构

```text
juling-takehome-layout-solver/
├── README.md
├── requirements.txt
├── examples/
│   ├── example1.json
│   ├── example2.json
│   ├── example3.json
│   └── example4.json
├── outputs/
│   ├── example1_output.json
│   ├── example1.png
│   ├── example2_output.json
│   ├── example2.png
│   ├── example3_output.json
│   ├── example3.png
│   ├── example4_output.json
│   └── example4.png
└── src/
    ├── main.py
    ├── models.py
    ├── geometry.py
    ├── solver.py
    └── visualize.py
```

## 10. 方案取舍

本项目没有使用复杂的全局优化算法，而是选择了更容易交付的启发式搜索。这样做的原因是：

- 题目重点是布局约束处理，不是最优解证明
- 输入规模较小，回溯搜索足够用
- 代码更容易解释
- 更适合面试展示

局限性：

- 不保证数学意义上的全局最优
- 候选点步长会影响搜索结果
- 极端复杂场景下可能需要更强的搜索策略

## 11. AI 使用说明

本项目在需求拆解、算法设计、README 结构组织阶段使用了 Claude Code 辅助。

AI 主要帮助了：

- 题意拆解
- 代码结构设计
- README 组织
- 方案表达优化

以下关键逻辑由我自己理解后完成：

- 候选点生成策略
- 物品排序策略
- 门区域和内开门区域建模
- 冰箱开门侧禁放区处理
- 最终结果解释和取舍
