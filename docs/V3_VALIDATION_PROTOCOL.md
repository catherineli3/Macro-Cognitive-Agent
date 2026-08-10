# V3 Validation Protocol — 实验协议

> **Document Type**: Experimental Protocol (Frozen Specification)
> **Version**: 1.0
> **Date**: 2026-07-18
> **Status**: PROTOCOL PHASE — 冻结，此后所有 Validation 必须遵守本协议
> **Constraint**: 不新增任何 Engine / Schema / Framework / 代码模块
> **Relationship**: 本协议是 `V3_SCIENTIFIC_VALIDATION.md` 的执行规范，后者定义"验证什么"，本协议定义"怎么验证"

---

## 总则

### 协议层级

```
V3_SCIENTIFIC_VALIDATION.md    → 验证目标（What）
    ↓
V3_VALIDATION_PROTOCOL.md     → 实验协议（How）  ← 本文档
    ↓
Milestone F0: Readiness Check  → 实验准备检查（数据质量、隔离性原则）
    ↓
Phase 1: Internal Validation   → 内部验证（Agent 有没有学习？）
    ↓
Phase 2: External Validation   → 外部验证（学到的东西有没有价值？）
    ↓
V3_VALIDATION_REPORT.md        → 验证报告
V3_FINAL_ASSESSMENT.md         → 最终判定
```

### 三阶段 + Readiness Check 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Milestone F0: Validation Readiness                              │
│  核心问题: 实验输入是否满足 Protocol 要求？                        │
│  不涉及: 任何学习、任何验证、任何报告                              │
│  操作:                                                           │
│    ① Dataset Integrity     — Lookahead-Free、无重复 Sample       │
│    ② Snapshot Completeness — 四层知识库快照完整                   │
│    ③ Schema Consistency    — Version 一致                        │
│    ④ Seed Verification     — Seed=42 已固定                      │
│    ⑤ Replay Order          — 顺序固定                            │
│    ⑥ Window Integrity      — 窗口长度正确                        │
│    ⑦ Missing Data Audit    — Missing = 0                         │
│                                                                   │
│  PASS 条件: 全部 7 项 PASS → 进入 Phase 1                        │
│  FAIL 条件: 任一项 FAIL → 修复数据问题后重试，禁止边跑边修         │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Internal Validation                                    │
│  核心问题: Agent 有没有学习？                                     │
│  不涉及: 收益、准确率、赚钱                                       │
│  涵盖:                                                            │
│    V1 — Hypothesis Quality 是否提升？                             │
│    V2 — Principle 是否成熟？                                      │
│    V3 — Framework 是否稳定？                                      │
│    V4 — Transmission 是否收敛？                                   │
│    V5 — Belief 是否有生命周期？                                   │
│    V6 — Thesis 是否一致？                                         │
│    V7 — Knowledge 层级是否健康？                                  │
│    V8 — 所有 Prediction 是否可追溯？                              │
│                                                                   │
│  PASS 条件: 全部 8 项 PASS → 进入 Phase 2                        │
│  FAIL 条件: 任一"一票否决项" FAIL → Phase 1 未通过，停止验证      │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: External Validation                                     │
│  核心问题: 学到的东西有没有价值？                                  │
│  此时才涉及: 外部基准、人类对比、泛化、投资意义                     │
│  涵盖:                                                            │
│    V9 — Framework 是否跨 regime 泛化？                            │
│    V10 — 方法论与人类顶级研究员是否可比？                          │
│                                                                   │
│  PASS 条件: 2 项均至少 WEAK PASS → V3 验证通过                    │
│  FAIL 条件: 任一 FAIL → V3 学到的东西无外部价值                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### Validation Isolation Principle（验证隔离原则）

> **这是整个 V3 验证体系最重要的架构约束。**

#### 原则声明

**Validation Layer is read-only. It must never modify the Agent's cognitive state.**

#### 强制约束

Validation 模块必须遵守以下绝对禁止：

| # | 禁止操作 | 原因 |
|:--:|----------|------|
| 1 | **modify Finding** | 污染数据源，不可复现 |
| 2 | **modify Principle** | 破坏知识结构 |
| 3 | **modify Belief** | 改变 weight/confidence |
| 4 | **modify Framework** | 改变认知架构 |
| 5 | **modify Hypothesis Score** | 曲解学习证据 |
| 6 | **modify Transmission** | 改变 edge 状态 |
| 7 | **trigger Evolution** | 隐性学习 |
| 8 | **trigger Diagnosis** | 隐性诊断 |
| 9 | **trigger Replay** | 隐性回放 |
| 10 | **write to ResearchMemory** | 任何形式的写入 |

#### 允许的操作

Validation 模块**只允许**以下操作：

| # | 允许的操作 | 范围 |
|:--:|------------|------|
| 1 | **read** ResearchMemory | 只读所有 Finding, Principle, Belief, Framework |
| 2 | **read** CycleResults | 只读所有 Prediction, Hypothesis, Thesis, Report |
| 3 | **read** snapshot files | 只读导出的 JSON/SQLite 快照 |
| 4 | **compute** statistics | 在内存中计算，不写回 |
| 5 | **generate** charts | 输出到 `validation/output/` |
| 6 | **generate** reports | 输出到 `docs/` |
| 7 | **log** validation results | 输出到 `validation/logs/` |

#### 数据流向（含 Snapshot Layer）

```
Research Cycle (Agent Domain)
     │
     │  Export (auto, each cycle end)
     ▼
Snapshot Layer (snapshot/ directory)     ← STABLE, IMMUTABLE
     │
     │  Read Only
     ▼
Validation Layer (validation/ directory)
     │
     │  COMPUTE
     ├──→ validation/output/    (charts, .png)
     ├──→ docs/                  (reports, .md)
     └──→ validation/logs/      (run logs, .json)
     
     ✗ Validation NEVER reads ResearchMemory directly
     ✗ Validation NEVER reads live Store state
     ✓ Validation ALWAYS reads Snapshot (frozen, hash-verified)
```

**关键变更**: Validation 不再直接读取 ResearchMemory 或 Store。所有验证数据必须来自 `snapshot/day_NNN/` 目录。这确保：
- 验证数据是固定的（不会因为 Agent 继续运行而变化）
- 可复现（任何人拿到 snapshot 都能重新运行验证）
- 隔离（Validation 与 Agent 运行时完全解耦）

#### 架构隔离

```
src/                          ← Agent Domain (Cognitive Architecture)
  ├── engines/                   ✗ Validation NEVER touches
  ├── schemas/                   ✗ Validation NEVER modifies
  ├── research/
  │   └── snapshot/             ← Snapshot Layer (write-once, read-many)
  │       ├── snapshot_writer.py    → Export Agent state to snapshot/
  │       ├── snapshot_reader.py    → Load snapshot for Validation
  │       └── snapshot_manager.py   → Lifecycle management
  └── ...

snapshot/                      ← Immutable research records
  ├── day_001/
  │   ├── principles.json
  │   ├── frameworks.json
  │   ├── beliefs.json
  │   ├── findings_tracker.json
  │   ├── cycle_result.json
  │   └── metadata.json         (hash, seed, versions)
  └── ...

validation/                   ← Validation Domain (Read-Only Analysis)
  ├── readiness_checker.py      ✓ Reads Snapshot only
  ├── metric_calculator.py      ✓ Reads Snapshot only
  ├── statistics_engine.py      ✓ Reads Snapshot only
  ├── curve_generator.py        ✓ Reads Snapshot only
  └── report_builder.py         ✓ Reads Snapshot only
```

#### 验证

在 Milestone F0 中需确认：任一 validation 模块的运行不会触发 Agent 状态的任何变化。通过对比 `validation run before` 和 `validation run after` 的 Agent 状态快照来验证。

---

### Milestone F0 — Validation Readiness

#### 设计哲学

```
"很多 AI 项目不是死在模型，而是死在实验数据。
 不要边跑边修。
 在跑验证之前，先确认一切输入正确。"
```

#### F0 检查清单

| # | 检查项 | 检查内容 | 数据来源 |
|:--:|--------|----------|----------|
| **F0-1** | Lookahead-Free | 任意 prediction at cycle $t$ 的证据不得包含 $> t$ 的数据 | CycleResult 链 |
| **F0-2** | No Duplicate Samples | Cycle → date 映射无重复，Prediction 无重复 ID | CycleResult + Hypothesis |
| **F0-3** | Seed Fixed | `RANDOM_SEED = 42` 已在一个完整 run 中被全局使用 | Agent config + run log |
| **F0-4** | Replay Order Fixed | Phase 1 严格时间顺序，Phase 2 严格 R1→R2→...→R7 | Replay log |
| **F0-5** | Snapshot Completeness | 四层知识库（F/P/B/FW）在 cycle 100 的快照所有字段非空 | Exported snapshot JSON/SQLite |
| **F0-6** | Window Length Correct | Phase 1 恰好 100 个 cycle，每个 cycle 有完整数据 | Cycle count + per-cycle data |
| **F0-7** | Missing Data = 0 | 所有 Schema 字段无 None 或缺失（除合法可选字段外） | Schema validation |
| **F0-8** | Schema Version Consistent | 所有 exported snapshot 使用同一 schema 版本 | Schema _schema_version field |
| **F0-9** | Principle Version Consistent | 同一 principle 在不同 cycle 的版本引用完整 | Principle.version_history |
| **F0-10** | Framework Version Consistent | 同一 framework 的 lineage 链完整，无断裂 | Framework.parent_framework |
| **F0-11** | V8 Sampling Ready | 分层抽样所需的全量 prediction 列表 $\geq 100$ 个 | Prediction pool |
| **F0-12** | Snapshot Immutability | Agent 快照自导出后未被修改（hash 校验） | File hash |
| **F0-13** | Replay Consistency | Snapshot 重新加载后构建的 Research State hash 与原始一致 | Snapshot → rebuild → hash compare |

#### F0 判定

```
全部 13 项 PASS → Milestone F0 = READY
    → 进入 Phase 1

任一项 FAIL → Milestone F0 = NOT READY
    → 禁止进入 Phase 1
    → 必须修复数据问题
    → 重新运行 F0 检查
    → 禁止在修复数据的同时跑验证
```

---

### Milestone F0.5 — Snapshot Layer

#### 设计哲学

```
Store = Runtime. Snapshot = Experiment.

不要 save()/load()。
要 export_snapshot()/import_snapshot().

含义完全不同:
  - Store 负责运行时查询
  - Snapshot 负责实验可复现
```

#### 命名约定

| 概念 | 动词 | 目录 | 用途 |
|------|------|------|------|
| Store (PrincipleStore, FrameworkStore) | save/get | N/A (内存) | 运行时查询 |
| Snapshot (SnapshotWriter) | export_snapshot | `snapshot/day_NNN/` | 实验记录 |
| SnapshotReader | load_snapshot | `snapshot/day_NNN/` | 验证读取 |

#### Snapshot 目录结构

```
snapshot/
  day_001/
    principles.json          # 全部 Principle（active + retired）
    frameworks.json          # 全部 Framework（active + retired）+ FrameworkSet
    beliefs.json             # 全部 BeliefRecord
    findings_tracker.json    # FindingLifecycle 索引
    cycle_result.json        # 当前 cycle 的 CycleResult 摘要
    metadata.json            # hash, seed, schema_version, timestamp
  day_002/
    ...
  run_manifest.json          # 全部 snapshot 索引
```

#### metadata.json 结构

```json
{
  "snapshot_version": "1.0",
  "cycle_number": 42,
  "cycle_id": "cycle-0042",
  "seed": 42,
  "exported_at": "2026-07-18T...",
  "schema_version": "v3.1",
  "principle_version": 15,
  "framework_version": 4,
  "snapshot_hash": "sha256:...",
  "file_hashes": {
    "principles.json": "sha256:...",
    "frameworks.json": "sha256:...",
    "beliefs.json": "sha256:...",
    "findings_tracker.json": "sha256:...",
    "cycle_result.json": "sha256:..."
  },
  "content_summary": { ... }
}
```

#### Snapshot Immutability Rule

- 一旦写入，snapshot 目录下的文件禁止手动修改
- F0-12 通过 hash 校验确保不可变性
- 如需修正数据，必须重新运行 Agent 生成新的 snapshot，不得修改已有 snapshot

#### Replay Consistency（F0-13）

```
1. 读取 snapshot/day_NNN/ 全部 JSON
2. 用 snapshot_reader 反序列化为内存对象
3. 对反序列化结果重新计算 content hash
4. 与 metadata.json 中的 snapshot_hash 对比
5. 100% 一致 → PASS
   不一致 → FAIL（snapshot 无法可靠复现）
```

#### Snapshot 写入时机

- 每个 Research Cycle 结束（`run_cycle()` 返回前）自动调用
- `SnapshotManager.capture(cycle_number, cycle_result)` 
- 由 CycleEngine 在设置 `result.status = "completed"` 后触发
- Snapshot 导出失败不影响 cycle 结果（写入 warnings）

#### 与 Validation 的关系

```
Before (F0 v1):
    Validation → ResearchMemory / beliefs.json / predictions.db (live data)

After (F0.5):
    Research Cycle → Snapshot → Validation → Report
    
    Validation NEVER reads Agent Stores directly.
    Validation ALWAYS reads Snapshot files.
```

---

### 冻结声明

本协议一旦定稿，以下全部冻结：

- **Part 1**: 10 项 Metric 的完整数学定义
- **Part 2**: 所有 Sampling Rule（样本量）
- **Part 3**: 所有 Window Definition（窗口大小）
- **Part 4**: 所有 Statistical Test（统计方法）
- **Part 5**: 所有 Significance 阈值
- **Part 6**: 所有 Failure Rule
- **Part 7**: 所有 Dataset Rule（数据允许列表）
- **Part 8**: 所有 Benchmark Rule（外部基准）
- **Part 9**: 所有 Reproducibility Seed
- **Part 10**: 报告模板
- **总则**: Validation Isolation Principle（只读隔离）
- **总则**: Milestone F0 Readiness Check（13 项检查清单）
- **总则**: Milestone F0.5 Snapshot Layer（snapshot/ 目录结构、写入时机、格式）

**以后任何版本不得修改本协议中的公式、窗口、阈值、测试方法。如需变更，必须新建 `V4_VALIDATION_PROTOCOL.md`。**

---

## Part 1 — Metric Definition

> **要求**: 每个 Metric 必须给出数学公式，不允许纯文字描述。

---

### V1 — Hypothesis Quality（假设质量）

#### V1.1 单日综合质量

对第 $t$ 个 cycle，所有活跃的 hypothesis 集合 $\mathcal{H}_t$：

$$
HQ_{mean}(t) = \frac{1}{|\mathcal{H}_t|} \sum_{h \in \mathcal{H}_t} S_{total}(h, t)
$$

其中 $S_{total}$ 为 `HypothesisScore.total_score`。

#### V1.2 子维度分解

| 子维度 | 字段 | 权重 $\omega$ |
|--------|------|:---:|
| $S_{pred}$ — Prediction Accuracy | `HypothesisScore.prediction_accuracy` | 0.30 |
| $S_{evid}$ — Evidence Quality | `HypothesisScore.evidence_quality` | 0.25 |
| $S_{cal}$ — Calibration | `HypothesisScore.calibration_score` | 0.20 |
| $S_{cons}$ — Consistency | `HypothesisScore.consistency_score` | 0.15 |
| $S_{learn}$ — Learning History | `HypothesisScore.learning_history` | 0.10 |

$$S_{total}(h, t) = 0.30 \cdot S_{pred} + 0.25 \cdot S_{evid} + 0.20 \cdot S_{cal} + 0.15 \cdot S_{cons} + 0.10 \cdot S_{learn}$$

#### V1.3 分维度均值曲线

对每个子维度 $d \in \{\text{pred, evid, cal, cons, learn}\}$：

$$HQ_{d}(t) = \frac{1}{|\mathcal{H}_t|} \sum_{h \in \mathcal{H}_t} S_{d}(h, t)$$

#### V1.4 聚合分位数

$$HQ_{median}(t) = \text{median}\left(\{S_{total}(h, t) \mid h \in \mathcal{H}_t\}\right)$$

$$HQ_{top3}(t) = \frac{1}{3} \sum_{k=1}^{3} S_{total}^{(k)}(t) \quad \text{（}S_{total}^{(k)}\text{为第 }k\text{ 大值）}$$

$$HQ_{bottom3}(t) = \frac{1}{3} \sum_{k=1}^{3} S_{total}^{(|\mathcal{H}_t| - k + 1)}(t)$$

#### V1.5 按 Dimension 分组

对每个 dimension $d \in \mathcal{D}$（liquidity / growth / inflation / risk_appetite / credit）：

$$\mathcal{H}_t^d = \{h \in \mathcal{H}_t \mid h.\text{dimension} = d\}$$

$$HQ_{mean}^d(t) = \frac{1}{|\mathcal{H}_t^d|} \sum_{h \in \mathcal{H}_t^d} S_{total}(h, t) \quad \text{（若 } |\mathcal{H}_t^d| > 0 \text{，否则 NaN）}$$

#### V1.6 最终指标

| 符号 | 定义 |
|------|------|
| $Q_{trend}$ | $HQ_{mean}(t)$ 线性回归斜率（详见 Part 4） |
| $Q_{sub\_improve}$ | 5 个子维度中斜率为正的个数 |
| $Q_{variance\_down}$ | $HQ_{mean}(t)$ 后半段 vs 前半段方差比 < 1 则 TRUE |
| $Q_{p}$ | 斜率显著性 p-value |

---

### V2 — Principle Evolution（原则演化）

#### V2.1 生命周期分布

定义 Principle 状态集合 $\{\text{CANDIDATE, VALIDATED, MATURE, FOUNDATIONAL}\}$，来源 `ResearchPrinciple.strength`。

$$N_{state}(t) = |\{\,p \mid p.\text{strength} = state \;\land\; p.\text{created\_at\_cycle} \leq t \;\land\; (p.\text{retired\_at\_cycle} > t \;\lor\; p.\text{retired\_at\_cycle} = \text{None})\,\}|$$

补充退休状态：

$$N_{retired}(t) = |\{\,p \mid p.\text{retired\_at\_cycle} \leq t\,\}|$$

#### V2.2 晋升率

$$\text{PromotionRate}(t) = \frac{\Delta \text{VALIDATED}(t) + \Delta \text{MATURE}(t)}{\max(1,\; |\text{CANDIDATE}(t-1)|)}$$

其中 $\Delta$ 表示 $t$ cycle 内新晋升的数量。

#### V2.3 退休率

$$\text{RetirementRate}(t) = \frac{\Delta \text{RETIRED}(t)}{\max(1,\; N_{active}(t-1))}$$

其中 $N_{active}(t) = N_{candidate}(t) + N_{validated}(t) + N_{mature}(t) + N_{foundational}(t)$。

#### V2.4 垃圾率

$$\text{JunkRate} = \frac{|\{\,p \mid p.\text{status} = \text{RETIRED} \;\land\; p.\text{validated\_at\_cycle} = \text{None}\,\}|}{\max(1,\; |\{\,p \mid p.\text{status} = \text{RETIRED}\,\}|)}$$

#### V2.5 存活时间

$$\text{Lifetime}(p) = p.\text{retired\_at\_cycle} - p.\text{created\_at\_cycle}$$

$$\overline{L}_{validated} = \text{mean}\left(\{\text{Lifetime}(p) \mid p.\text{strength} \geq \text{VALIDATED} \;\land\; p.\text{status} = \text{RETIRED}\}\right)$$

$$\overline{L}_{candidate} = \text{mean}\left(\{\text{Lifetime}(p) \mid p.\text{strength} = \text{CANDIDATE} \;\land\; p.\text{status} = \text{RETIRED}\}\right)$$

#### V2.6 矛盾率

$$\text{ContradictionRate}(t) = \frac{1}{|P_{active}(t)|} \sum_{p \in P_{active}(t)} p.\text{contradiction\_count}$$

#### V2.7 最终指标

| 符号 | 定义 |
|------|------|
| $N_{mature\_final}$ | 最终 cycle 的 MATURE 数量 |
| $R_{junk}$ | JunkRate |
| $R_{promo\_final}$ | 最后 20 cycle 的平均 PromotionRate |
| $R_{retire\_final}$ | 最后 20 cycle 的平均 RetirementRate |
| $\overline{L}_{val}$ | 已验证原则的平均存活时间 |
| $\overline{L}_{can}$ | 候选原则的平均存活时间 |

---

### V3 — Framework Stability（框架稳定性）

#### V3.1 Top Framework 持续性

对每对相邻 cycle $(t-1, t)$，定义指示函数：

$$\mathbf{1}_{top\_same}(t) = \begin{cases} 1 & \text{if } \text{top\_framework}(t-1) = \text{top\_framework}(t) \\ 0 & \text{otherwise} \end{cases}$$

$$\text{TopStability} = \frac{1}{T-1} \sum_{t=2}^{T} \mathbf{1}_{top\_same}(t)$$

其中 $T = 100$ 为总 cycle 数。

#### V3.2 Principle 成员 Jaccard 稳定性（整体）

对 framework $f$ 在时间 $t$ 的 principle 集合 $\mathcal{P}_f(t)$：

$$J_f(t) = \frac{|\mathcal{P}_f(t) \cap \mathcal{P}_f(t-1)|}{|\mathcal{P}_f(t) \cup \mathcal{P}_f(t-1)|} \quad \text{（若分母 > 0，否则 0）}$$

$$\overline{J}(t) = \frac{1}{|F_{active}(t) \cap F_{active}(t-1)|} \sum_{f \in F_{active}(t) \cap F_{active}(t-1)} J_f(t)$$

$$\text{JaccardFinal} = \overline{J}(T)$$

#### V3.3 单框架 Jaccard 稳定性

$$\text{JaccardStability}(f) = \frac{1}{|cycles(f)| - 1} \sum_{t \in cycles(f),\, t > t_0} J_f(t)$$

其中 $cycles(f)$ 是 $f$ 处于 active 状态的 cycle 集合。

#### V3.4 Principle 权重变化

对 framework $f$ 在时间 $t$ 的权重向量 $\mathbf{w}_f(t) = [w_1, w_2, \ldots, w_k]$：

$$\Delta_w(f, t) = \frac{1}{|\mathcal{P}_f(t) \cap \mathcal{P}_f(t-1)|} \sum_{i \in \mathcal{P}_f(t) \cap \mathcal{P}_f(t-1)} |w_i(t) - w_i(t-1)|$$

$$\overline{\Delta_w}(t) = \frac{1}{|F_{active}(t) \cap F_{active}(t-1)|} \sum_{f} \Delta_w(f, t)$$

$$\text{WeightDeltaFinal} = \text{mean}\left(\{\overline{\Delta_w}(t) \mid t \in [81, 100]\}\right)$$

#### V3.5 Framework 生命周期

$$\overline{L}_{fw} = \frac{1}{|F_{retired}|} \sum_{f \in F_{retired}} (f.\text{retired\_at\_cycle} - f.\text{created\_at\_cycle}) \quad \text{（若 } F_{retired} \neq \emptyset \text{）}$$

#### V3.6 Framework 复用率

$$R_{reuse} = \frac{|\{\,f \mid f \text{ 在 } \geq 2 \text{ 个不同 regime 中活跃}\,\}|}{\max(1,\; |F_{all}|)}$$

#### V3.7 Framework 替换率

$$R_{replace} = \frac{|\{\text{新创建的 framework}\}|}{\max(1,\; |F_{all}|)}$$

#### V3.8 谱系深度

$$\text{LineageDepth}(f) = \text{沿 } parent\_framework \text{ 链上溯的代数}$$

$$\overline{D}_{lineage} = \frac{1}{|F_{all}|} \sum_{f \in F_{all}} \text{LineageDepth}(f)$$

#### V3.9 最终指标

| 符号 | 定义 |
|------|------|
| $S_{top}$ | TopStability |
| $J_{final}$ | JaccardFinal |
| $\overline{J}_{trend}$ | $\overline{J}(t)$ 线性回归斜率 |
| $\overline{L}_{fw}$ | 平均框架存活时间 |
| $R_{reuse}$ | Framework 复用率 |
| $R_{replace}$ | Framework 替换率 |
| $\overline{D}_{lineage}$ | 平均谱系深度 |

---

### V4 — Transmission Stability（传输稳定性）

#### V4.1 Channel Reliability

对第 $t$ 个 cycle，channel $c$ 在窗口 $W$ 内的方向准确率：

$$R_c(t; W) = \frac{1}{|W|} \sum_{\tau = t-W+1}^{t} \mathbf{1}_{correct}(c, \tau)$$

其中 $W$ 为窗口大小（详见 Part 3），$\mathbf{1}_{correct}(c, \tau)$ 来自 `AdaptiveBelief.version_history` 中的实际方向记录。

#### V4.2 Reliability 标准差

对 channel $c$ 在全时间序列上的可靠性标准差：

$$\sigma_R(c) = \sqrt{\frac{1}{T-1} \sum_{t=1}^{T} \left(R_c(t; W) - \overline{R_c}\right)^2}$$

$$\overline{\sigma}_R = \frac{1}{|C|} \sum_{c \in C} \sigma_R(c)$$

其中 $C$ 是所有 channel 的集合，$\overline{R_c} = \frac{1}{T} \sum_{t} R_c(t; W)$。

#### V4.3 末尾收敛度量

$$\sigma_R^{\text{tail}}(c) = \sqrt{\frac{1}{20} \sum_{t=T-20+1}^{T} \left(R_c(t; W) - \overline{R_c}^{\text{tail}}\right)^2}$$

其中 $\overline{R_c}^{\text{tail}} = \frac{1}{20} \sum_{t=T-20+1}^{T} R_c(t; W)$。

$$\text{ConvergedChannels} = |\{\,c \in C \mid \sigma_R^{\text{tail}}(c) < 0.08\,\}|$$

#### V4.4 Channel Weight 收敛

对 channel $c$，其 weight（来源 `AdaptiveBelief.version_history[].weight`）：

$$w_c(t) = \text{belief } b \text{ 的 weight，其中 } b.\text{transmission\_channel} = c$$

$$\sigma_w^{\text{tail}}(c) = \sqrt{\frac{1}{20} \sum_{t=T-20+1}^{T} \left(w_c(t) - \overline{w_c}^{\text{tail}}\right)^2}$$

#### V4.5 故障恢复率

$$\text{RecoveryRate}(c) = \frac{c.\text{recovery\_count}}{\max(1,\; c.\text{recovery\_count} + |\{\,c \mid c.\text{status} = \text{deprecated}\,\}|)}$$

#### V4.6 Deprecation 正确率

$$\text{DeprecationCorrectness} = \frac{|\{\,c \mid c.\text{status} = \text{deprecated} \;\land\; \overline{R_c} < 0.50\,\}|}{\max(1,\; |\{\,c \mid c.\text{status} = \text{deprecated}\,\}|)}$$

#### V4.7 最终指标

| 符号 | 定义 |
|------|------|
| $N_{conv}$ | ConvergedChannels |
| $\overline{\sigma}_R^{tail}$ | mean($\sigma_R^{\text{tail}}(c)$) across all $c$ |
| $\overline{\sigma}_w^{tail}$ | mean($\sigma_w^{\text{tail}}(c)$) across all $c$ |
| $\text{DepCorrect}$ | DeprecationCorrectness |

---

### V5 — Belief Evolution（信念演化）

#### V5.1 状态定义与转移矩阵

Belief 状态集 $\mathcal{S} = \{\text{BORN}, \text{ACTIVE}, \text{STRENGTHENING}, \text{WEAKENING}, \text{DORMANT}, \text{DEPRECATED}\}$。

判定规则：

$$\text{state}(b, t) = \begin{cases}
\text{BORN}     & \text{if } b.\text{created\_at\_cycle} = t \\
\text{STRENGTHENING} & \text{if } \exists \text{ version at } t \text{ with } w(t) > w(t-1) \text{ and } conf(t) > conf(t-1) \\
\text{WEAKENING} & \text{if } \exists \text{ version at } t \text{ with } w(t) < w(t-1) \text{ and } conf(t) < conf(t-1) \\
\text{DORMANT}   & \text{if belief 存在但 } t - \text{last\_activation\_cycle} > 10 \\
\text{DEPRECATED} & \text{if } b.\text{status} = \text{deprecated} \\
\text{ACTIVE}     & \text{otherwise}
\end{cases}$$

转移概率矩阵：

$$\mathbf{P}_{ij} = \frac{|\{\text{transitions from state } i \text{ to state } j \text{ at consecutive cycles}\}|}{|\{\text{total transitions from state } i\}|}$$

#### V5.2 Weight Trajectory 聚类

对每个 belief $b$，其 weight 序列 $\mathbf{w}_b = [w_b(1), w_b(2), \ldots, w_b(T_b)]$。

使用 k-means 聚类（$k = 4$），将 belief 分为：

$$\text{cluster}(b) \in \{A_{\text{上升}}, B_{\text{稳定}}, C_{\text{下降}}, D_{\text{震荡}}\}$$

聚类特征提取：

- $c_{slope}$ = $\mathbf{w}_b$ 线性回归斜率
- $c_{std}$ = $\mathbf{w}_b$ 标准差
- $c_{final}$ = 末尾 10 cycle 均值 vs 前 10 cycle 均值之比

#### V5.3 Calibration Error

$$\text{CalibrationError}(b) = \frac{1}{|V_b|} \sum_{v \in V_b} \left(v.\text{confidence} - \frac{b.\text{correct\_count}}{\max(1,\; b.\text{cycle\_count})}\right)$$

其中 $V_b$ 是 belief $b$ 的所有版本。

全局校准误差：

$$CE(t) = \frac{1}{|B_{active}(t)|} \sum_{b \in B_{active}(t)} |\text{CalibrationError}(b)|$$

#### V5.4 Precondition Narrowing

$$\text{PrecondGrowth}(b) = \frac{\text{最后版本 preconditions 数}}{\max(1,\; \text{首版本 preconditions 数})}$$

#### V5.5 最终指标

| 符号 | 定义 |
|------|------|
| $P_{AB}$ | 簇 A + 簇 B 的 belief 占比 |
| $CE_{final}$ | 最后 20 cycle 的 CE(t) 均值 |
| $CE_{trend}$ | CE(t) 线性回归斜率 |
| $\overline{P}_{narrow}$ | $\text{PrecondGrowth}(b)$ 均值 |
| $\mathbf{P}_{act \to str}$ | ACTIVE → STRENGTHENING 转移概率 |
| $\mathbf{P}_{act \to weak}$ | ACTIVE → WEAKENING 转移概率 |

---

### V6 — Research Consistency（研究一致性）

#### V6.1 Dimension 熵

对窗口 $W$ 内的 thesis dimension 分布：

$$H_{dim}(t; W) = -\sum_{d \in \mathcal{D}} \hat{p}_d(t; W) \cdot \log_2\left(\hat{p}_d(t; W)\right)$$

其中 $\hat{p}_d(t; W) = \frac{|\{\,\tau \in [t-W+1, t] \mid thesis\_dimension(\tau) = d\,\}|}{W}$。若 $\hat{p}_d = 0$，则对应项为 0。

$\mathcal{D} = \{\text{liquidity}, \text{growth}, \text{inflation}, \text{risk\_appetite}, \text{credit}, \text{monetary\_policy}\}$。

#### V6.2 Framework 熵

$$H_{fw}(t; W) = -\sum_{f \in \mathcal{F}} \hat{p}_f(t; W) \cdot \log_2\left(\hat{p}_f(t; W)\right)$$

其中 $\mathcal{F}$ 是所有可能的 framework ID。

#### V6.3 最大可能熵（归一化基准）

$$H_{dim}^{max} = \log_2(|\mathcal{D}|) \approx \log_2(6) \approx 2.585$$

$$H_{fw}^{max} = \log_2(|F_{all}|)$$

归一化：$H'_{dim}(t) = \dfrac{H_{dim}(t)}{H_{dim}^{max}}$。

#### V6.4 文本连贯性

$$\text{ThesisCoherence}(t) = \cos\left(\text{embed}(\text{thesis}_t.\text{core\_belief}),\; \text{embed}(\text{thesis}_{t-1}.\text{core\_belief})\right)$$

使用 `sentence-transformers/all-MiniLM-L6-v2` 嵌入模型（固定版本）。

#### V6.5 分段主导维度

将 100 cycle 均分为 4 段 $S_1[1,25], S_2[26,50], S_3[51,75], S_4[76,100]$。

对每段 $k$，主导维度：

$$d^*_{S_k} = \arg\max_{d \in \mathcal{D}} \sum_{t \in S_k} \mathbf{1}[thesis\_dimension(t) = d]$$

#### V6.6 最终指标

| 符号 | 定义 |
|------|------|
| $H'_{dim}^{final}$ | 最后 25 cycle 的 $H'_{dim}(t)$ 均值 |
| $H'_{fw}^{final}$ | 最后 25 cycle 的 $H'_{fw}(t)$ 均值 |
| $H'_{dim}^{trend}$ | $H'_{dim}(t)$ 线性回归斜率 |
| $\text{Coherence}^{avg}$ | 全体 $\text{ThesisCoherence}(t)$ 均值 |
| $N_{same\_dom}$ | 4 段主导维度相同的段数 |
| $L_{dominant}$ | 连续使用同一主维度的最大连续 cycle 数 |

---

### V7 — Knowledge Growth（知识增长）

#### V7.1 四层存量

对 $t = 1, 2, \ldots, T$：

$$N_F(t) = |\{\text{ResearchFinding at cycle } t\}|$$

$$N_P(t) = |\{\text{ResearchPrinciple at cycle } t\}|$$

$$N_B(t) = |\{\text{AdaptiveBelief at cycle } t\}|$$

$$N_{FW}(t) = |\{\text{ResearchFramework at cycle } t\}|$$

#### V7.2 金字塔比例

$$\text{PyramidRatio}(t) = N_F(t) : N_P(t) : N_B(t) : N_{FW}(t)$$

理想基准：$100 : 30 : 10 : 3$。

平衡度量：

$$\text{PyramidBalance}(t) = \frac{1}{3} \left[ \left|\frac{N_F(t)}{N_P(t)} - \frac{100}{30}\right| + \left|\frac{N_P(t)}{N_B(t)} - \frac{30}{10}\right| + \left|\frac{N_B(t)}{N_{FW}(t)} - \frac{10}{3}\right| \right]$$

注意：若分母为 0，对应项用最大值替代。

#### V7.3 增长速度

对每层 $L \in \{F, P, B, FW\}$，10-cycle 窗口增长率：

$$G_L(t) = \frac{N_L(t)}{\max(1,\; N_L(t-10))}$$

#### V7.4 转化漏斗

$$\text{Conv}_{F \to P} = \frac{|\{\text{promoted findings}\}|}{\max(1,\; |F_{all}|)}$$

$$\text{Conv}_{P \to B} = \frac{|\{\text{principles referenced in beliefs}\}|}{\max(1,\; |P_{all}|)}$$

$$\text{Conv}_{B \to FW} = \frac{|\{\text{beliefs referenced in frameworks}\}|}{\max(1,\; |B_{all}|)}$$

#### V7.5 最终指标

| 符号 | 定义 |
|------|------|
| $\text{PB}_{final}$ | PyramidBalance(T) |
| $G_F^{final}, G_P^{final}, G_B^{final}, G_{FW}^{final}$ | 最后 20 cycle 的平均增长率 |
| $\text{Conv}_{F \to P}, \text{Conv}_{P \to B}, \text{Conv}_{B \to FW}$ | 各层转化率 |
| $N_L^{trend}$ form | 四层增长率顺序是否满足 $F > P > B > FW$ |

---

### V8 — Explainability Audit（可追溯性审计）

#### V8.1 抽样集合

从全部 prediction 集合 $\mathcal{P}$（$\approx$ 300 个）中抽取样本 $\mathcal{S}$，$|\mathcal{S}| = 100$。

抽样为**分层抽样（stratified sampling）**：

每 10 个连续 cycle 为一层（共 10 层），每层抽取 10 个，且每层内部按 outcome（correct vs incorrect）配额。

#### V8.2 五问追溯链

对每个 $p \in \mathcal{S}$，定义布尔函数：

$$\mathbf{1}_{Q1}(p) = \begin{cases} 1 & \text{if } p.\text{evidence} \neq \text{None} \;\land\; p.\text{rationale} \neq \text{""} \\ 0 & \text{otherwise} \end{cases}$$

$$\mathbf{1}_{Q2}(p) = \begin{cases} 1 & \text{if } p.\text{source\_hypothesis\_id} \to \text{Hypothesis} \to \text{Thesis} \text{ 链完整} \\ 0 & \text{otherwise} \end{cases}$$

$$\mathbf{1}_{Q3}(p) = \begin{cases} 1 & \text{if } \text{Thesis}.\text{framework\_used} \to \text{Framework} \text{ 存在且 status} \neq \text{RETIRED} \\ 0 & \text{otherwise} \end{cases}$$

$$\mathbf{1}_{Q4}(p) = \begin{cases} 1 & \text{if } \text{Framework}.\text{principles 每条可验证} \\ 0 & \text{otherwise} \end{cases}$$

$$\mathbf{1}_{Q5}(p) = \begin{cases} 1 & \text{if } \text{Principle}.\text{source findings} \to \text{Finding 可追溯} \\ 0 & \text{otherwise} \end{cases}$$

#### V8.3 完整度

$$\text{TraceCompleteness} = \frac{1}{|\mathcal{S}|} \sum_{p \in \mathcal{S}} \prod_{q=1}^{5} \mathbf{1}_{Qq}(p)$$

即：5 个问题全部为 1 的 prediction 占比。

#### V8.4 断链率

$$\text{BrokenChainRate} = \frac{1}{|\mathcal{S}|} \sum_{p \in \mathcal{S}} \mathbf{1}\left[\sum_{q=1}^{5} \mathbf{1}_{Qq}(p) < 5\right]$$

#### V8.5 平均链深

对每个 $p$，链深 $\text{Depth}(p) = \text{Prediction} \to \text{Hypothesis} \to \text{Thesis} \to \text{Framework} \to \text{Principle} \to \text{Finding} 的跳数$。

$$\overline{\text{Depth}} = \frac{1}{|\mathcal{S}|} \sum_{p \in \mathcal{S}} \text{Depth}(p)$$

标准链深应为 5（6 层实体间 5 跳）。

#### V8.6 最终指标

| 符号 | 定义 |
|------|------|
| TC | TraceCompleteness |
| BCR | BrokenChainRate |
| $\overline{D}$ | avg_chain_depth |
| $N_{circular}$ | 存在循环引用的 prediction 数 |

---

### V9 — Generalization Test（泛化测试）

#### V9.1 Test Regime 固定列表

| 编号 | 名称 | 时间窗口（固定） | 交易日数 |
|:---:|------|:---------------|:------:|
| R1 | 2008 Financial Crisis | 2008-09-01 → 2009-03-31 | ~145 |
| R2 | 2011 Euro Debt Crisis | 2011-07-01 → 2011-12-31 | ~125 |
| R3 | 2015 CNY Devaluation | 2015-08-01 → 2016-01-31 | ~125 |
| R4 | 2018 QT / Trade War | 2018-01-01 → 2019-01-31 | ~275 |
| R5 | 2020 COVID | 2020-02-01 → 2020-08-31 | ~145 |
| R6 | 2022 Inflation / Hikes | 2022-01-01 → 2023-01-31 | ~275 |
| R7 | 2023 AI Bull / Soft Landing | 2023-01-01 → 2024-01-31 | ~260 |

每个 Regime 运行 30 个 cycle（每日一个 cycle）。

#### V9.2 Framework 存活率

$$\text{FrameworkSurvival}(r_A \to r_B) = \frac{|F_{active}(r_A) \cap F_{active}(r_B)|}{\max(1,\; |F_{active}(r_A)|)}$$

**跨 Regime 存活**：若 $f$ 在 $\geq 5$ 个 Regime 中活跃，则判定为"跨 Regime 存活"。

$$N_{survive}^{fw} = |\{\,f \mid |\{\,r \mid f \in F_{active}(r)\,\}| \geq 5\,\}|$$

#### V9.3 Principle 跨 Regime 准确率

$$\text{PrincipleXRAccuracy}(p) = \frac{1}{|R_p|} \sum_{r \in R_p} p.\text{evidence}.\text{accuracy}_r$$

其中 $R_p$ 是 principle $p$ 被验证过的 regime 集合。

$$\overline{XR} = \frac{1}{|P_{mature}|} \sum_{p \in P_{mature}} \text{PrincipleXRAccuracy}(p)$$

#### V9.4 适应速度

$$\text{AdaptSpeed}(r) = \min\{\,t \mid HQ_{mean}(t) \geq HQ_{stable} \text{ 连续 } 5 \text{ 个 cycle}\,\}$$

其中 $HQ_{stable}$ 为 regime 内最后 10 cycle 的 $HQ_{mean}$ 均值。

$$\overline{\text{Adapt}} = \frac{1}{7} \sum_{r=1}^{7} \text{AdaptSpeed}(r)$$

#### V9.5 知识保留率（灾难性遗忘测试）

在 Regime 7 完成后，对 Regime 1 数据重新测试：

$$\text{KnowledgeRetention}(r_1 | r_7) = \frac{HQ_{mean}^{(r_1, \text{after } r_7)}}{HQ_{mean}^{(r_1, \text{during } r_1)}}$$

若比值 $> 1$（迁移学习使旧 regime 表现更好），则截断为 1.0。

#### V9.6 最终指标

| 符号 | 定义 |
|------|------|
| $N_{survive}^{fw}$ | 跨 $\geq 5$ 个 Regime 存活的 Framework 数 |
| $\overline{XR}$ | MATURE Principle 跨 Regime 平均准确率 |
| $\overline{\text{Adapt}}$ | 平均适应 speed（单位：cycles） |
| $\text{Retention}_{r_1}$ | KnowledgeRetention(r1 | r7) |

---

### V10 — Researcher Benchmark（研究员基准）

#### V10.1 固定基准

人类研究员基准（固定，不可更改）：

| ID | 研究员 | 代表机构 | 分析时期（固定） |
|:--:|--------|---------|:---------------:|
| H1 | **Ray Dalio** | Bridgewater | 2018-Q1, 2020-Q2, 2022-Q4 |
| H2 | **Paul Tudor Jones** | Tudor Investment | 2018-Q1, 2020-Q2, 2022-Q4 |
| H3 | **Howard Marks** | Oaktree Capital | 2018-Q1, 2020-Q2, 2022-Q4 |
| H4 | **Stanley Druckenmiller** | Duquesne | 2018-Q1, 2020-Q2, 2022-Q4 |

每个研究员 × 3 个时期 = 12 份基准快照。

基准快照格式化要求：每份包含 `framework_dimensions`, `transmission_chain`, `core_beliefs`, `thesis` 四个结构，与 Agent 输出兼容。

#### V10.2 Framework 维度相似度

对 Agent Framework $f_A$ 和 人类 Framework $f_H$：

$$\text{DimSim}(f_A, f_H) = \frac{|D(f_A) \cap D(f_H)|}{|D(f_A) \cup D(f_H)|}$$

其中 $D(f)$ 是 framework 使用的分析维度集合。

#### V10.3 Transmission 相似度

将双方 transmission chain 表示为有向无环图 $G_A = (V_A, E_A)$ 和 $G_H = (V_H, E_H)$：

$$\text{TransSim} = \frac{|V_A \cap V_H| + |E_A \cap E_H|}{\max(1,\; |V_A \cup V_H| + |E_A \cup E_H|)}$$

节点和边的匹配使用语义等价判定（人工标注）。

#### V10.4 Belief 排序相似度

将双方 top-$N$ belief 按权重排序，计算 Spearman 秩相关系数：

$$\rho_{belief} = 1 - \frac{6 \sum d_i^2}{N(N^2 - 1)}$$

其中 $d_i$ 是第 $i$ 个维度的排序差。

#### V10.5 Thesis 语义相似度

$$\text{ThesisSim}(A, H) = \cos(\text{embed}(\text{thesis}_A),\; \text{embed}(\text{thesis}_H))$$

使用固定嵌入模型 `sentence-transformers/all-MiniLM-L6-v2`。

#### V10.6 综合基准得分

对每位研究员 $h$，计算：

$$\text{ResearcherScore}(h) = 0.35 \cdot \text{DimSim}_h + 0.35 \cdot \text{TransSim}_h + 0.15 \cdot \rho_{belief}^{(h)} + 0.15 \cdot \text{ThesisSim}_h$$

#### V10.7 最终指标

| 符号 | 定义 |
|------|------|
| $\overline{RS}$ | 4 位研究员 ResearcherScore 均值 |
| $N_{pass}$ | ResearcherScore > 0.45 的研究员数量 |
| $\max RS$ | 最高 ResearcherScore |

---

## Part 2 — Sampling Rule

> **要求**: 所有采样规则固定，不可后续调整。

### 整体实验规模

| 参数 | 固定值 | 说明 |
|------|:------:|------|
| **Phase 1 Baseline Cycles** | **100** | 单一 regime 中 agent 运行的 cycle 数 |
| **Phase 2 Regime Cycles per Regime** | **30** | 每个历史 regime 运行的 cycle 数 |
| **Phase 2 Total Regimes** | **7** | 固定 7 个历史阶段 |
| **Total Cycles** | **100 + 7 × 30 = 310** | 整个 agent 生命周期 |

### 各 Validation 样本量

| Validation | 样本量 | 采样策略 |
|:----------:|:------:|----------|
| V1 | 100 (全部 cycle) | 全量 |
| V2 | 100 (全部 cycle) | 全量 |
| V3 | 100 (全部 cycle) | 全量 |
| V4 | 所有 active channel | 全量 |
| V5 | 所有 belief | 全量 |
| V6 | 100 (全部 cycle) | 全量 |
| V7 | 100 (全部 cycle) | 全量 |
| V8 | 100 predictions | 分层抽样（每 10 cycle 为层，每层 10 个，层内 correct/incorrect 配额） |
| V9 | 7 regime × 30 cycle | 全量 |
| V10 | 12 份人类基准 | 固定基准（4 研究员 × 3 时期） |

### V8 抽样方案（详细）

分层抽样结构：

```
层 1:  cycle 1-10   → 抽取 10 个 prediction (correct:incorrect 按层内比例)
层 2:  cycle 11-20  → 抽取 10 个
...
层 10: cycle 91-100 → 抽取 10 个
-------------------------------------------
总计: 100 个 prediction
```

配额规则：若某层内 correct 与 incorrect 比例不在 [0.3, 0.7] 范围，则按 5:5 强制配额。否则按层内自然比例分配。

### 固定 Random Seed

```
V8_SAMPLING_SEED = 42
V5_CLUSTERING_SEED = 42
V9_SHUFFLE_SEED = 42
```

---

## Part 3 — Window Definition

> **要求**: 所有滑动窗口大小固定。

### 全局窗口定义

| 窗口名称 | 大小 | 单位 | 用途 |
|----------|:---:|------|------|
| **$W_{trend}$** | **100** | cycles | V1 Q_trend 回归窗口 |
| **$W_{rolling}$** | **20** | cycles | V4 Channel Reliability 滚动窗口 |
| **$W_{entropy}$** | **25** | cycles | V6 Dimension/Framework 熵窗口 |
| **$W_{tail}$** | **20** | cycles | V4/V5 末尾收敛度量窗口 |
| **$W_{segment}$** | **25** | cycles | V6 分段分析段长 |
| **$W_{growth}$** | **10** | cycles | V7 增长率计算窗口 |

### 窗口使用矩阵

```
Validation 1:
  └─ Q_trend regression → W_trend = 100 (全量)
  └─ 子维度趋势 → W_trend = 100 (全量)

Validation 4:
  └─ R_c(t; W) → W_rolling = 20
  └─ σ_R(c) → W_rolling = 20 (逐步计算各窗口)
  └─ σ_R^tail(c) → W_tail = 20 (末尾 20 cycle)

Validation 6:
  └─ H_dim(t; W) → W_entropy = 25
  └─ 分段 → W_segment = 25 × 4 段

Validation 7:
  └─ G_L(t) → W_growth = 10

所有 "末尾收敛" 相关指标:
  └─ 末尾 20 cycle → W_tail = 20
```

### 禁止行为

- 不得因结果不理想而扩大或缩小窗口。
- 不得对不同 channel 使用不同窗口。
- 不得使用非对称窗口（前后不等）。

---

## Part 4 — Statistical Test

> **要求**: 每个统计测试的方法固定，不可切换。

### 全局统计方法注册表

| 测试编号 | 测试目的 | 固定方法 | 使用参数 |
|:-------:|----------|----------|----------|
| ST1 | 趋势检验 | **OLS Linear Regression** | `scipy.stats.linregress` |
| ST2 | 均值比较 | **Welch's t-test** | `scipy.stats.ttest_ind(equal_var=False)` |
| ST3 | 方差比较 | **F-test** (方差比) | $\dfrac{\text{var}_{tail}}{\text{var}_{head}}$ |
| ST4 | 分布比较 | **Kolmogorov-Smirnov** | `scipy.stats.ks_2samp` |
| ST5 | 相关性 | **Spearman's ρ** | `scipy.stats.spearmanr` |
| ST6 | 聚类 | **k-means (k=4)** | `sklearn.cluster.KMeans(n_clusters=4, random_state=42, n_init=10)` |
| ST7 | 文本嵌入 | **all-MiniLM-L6-v2** | `sentence-transformers/all-MiniLM-L6-v2` |
| ST8 | 趋势方向 | **Mann-Kendall** | `pymannkendall` (辅助确认) |
| ST9 | 正态性检验 | **Shapiro-Wilk** | `scipy.stats.shapiro` |

### 各 Validation 测试分配

| Validation | 指标 | 测试方法 |
|:----------:|------|----------|
| V1 | $Q_{trend}$ | ST1 (OLS slope + p-value) |
| V1 | $Q_{sub\_improve}$ | ST1 (每子维度独立回归) |
| V1 | $Q_{variance\_down}$ | ST3 (后半/前半方差比) |
| V2 | JunkRate | 直接计数，无需检验 |
| V2 | ContradictionRate 趋势 | ST1 |
| V3 | $\overline{J}(t)$ 趋势 | ST1 |
| V3 | $\overline{\Delta_w}(t)$ 趋势 | ST1 |
| V4 | $\sigma_R^{\text{tail}}(c)$ | 阈值判断（< 0.08），无需统计检验 |
| V4 | $\overline{\sigma}_R$ 趋势 | ST1 |
| V5 | CE(t) 趋势 | ST1 |
| V5 | Belief 聚类 | ST6 (k-means, k=4) |
| V6 | $H'_{dim}(t)$ 趋势 | ST1 |
| V6 | ThesisCoherence | ST7 (embedding) + ST5 (cosine) |
| V6 | 分段主导一致性 | 直接比较，无需检验 |
| V7 | 增长率序关系 | 直接比较 |
| V8 | TraceCompleteness | 直接计数 |
| V9 | FrameworkSurvival | 直接计数 |
| V9 | 适应速度 | ST1 (per-regime) |
| V10 | 相似度指标 | ST7 (embedding) + ST5 (Spearman) |

### Mann-Kendall 辅助确认规则

ST8 仅作为 ST1 的**辅助确认**。规则：

- 若 ST1 (OLS) 与 ST8 (Mann-Kendall) 结论一致 → 取 OLS 结论
- 若 ST1 显著 ($p < 0.05$) 但 ST8 不显著 ($p \geq 0.10$) → 降级为 WEAK PASS
- 若 ST1 不显著 但 ST8 显著 → 不改变结论（OLS 为主）

### 禁止行为

- 不得因结果不理想而切换统计测试方法。
- 不得在 OLS 和 Kendall 之间 cherry-pick 有利结果。
- 不得使用非线性回归除非预注册。
- 不得对同一数据使用多种显著性检验后选最好的报告。

---

## Part 5 — Significance

> **要求**: 何时判定 "Agent 真的学习了" 必须提前定义。

### 全局显著性阈值

| 参数 | 固定值 | 说明 |
|------|:-----:|------|
| **$\alpha$** (Type I Error) | **0.05** | p < 0.05 判定显著 |
| **$R^2_{min}$** | **0.20** | OLS 回归 $R^2$ 最低要求（方向正确但解释力太弱不算） |
| **$\text{slope}_{min}$** | **0.001 / cycle** | 斜率绝对值低于此 → 视为无实质变化 |

### Phase 1 通关判定（Internal Validation）

| 层级 | 判定 | 条件 |
|:----:|:----:|------|
| **层面 1** | 单个 Validation PASS | 该 Validation 达到 Part 6 定义的 PASS 条件 |
| **层面 2** | Phase 1 通关 | **全部 8 项** 均至少 WEAK PASS，且**全部一票否决项** PASS |
| **层面 3** | 进入 Phase 2 | Phase 1 通关 |
| **层面 4** | Phase 1 未通过 | 任一"一票否决项" FAIL → 终止验证，V3 = NO LEARNING |

### Phase 2 通关判定（External Validation）

| 层级 | 判定 | 条件 |
|:----:|:----:|------|
| **层面 1** | V9 PASS | $N_{survive}^{fw} \geq 2$ 且 $\overline{XR} > 0.55$ 且 $\text{Retention}_{r_1} > 0.70$ |
| **层面 2** | V9 WEAK PASS | $N_{survive}^{fw} \geq 1$ 且 $\overline{XR} > 0.50$ |
| **层面 3** | V10 PASS | $N_{pass} \geq 2$ 且 $\overline{RS} > 0.45$ |
| **层面 4** | V10 WEAK PASS | $N_{pass} \geq 1$ |

### "Agent 真的学习了" 完整判定

```
IF Phase 1 通关 AND Phase 2 通关:
    → V3 = LEARNING + VALUABLE（强结论）

IF Phase 1 通关 AND Phase 2 未完全通关 (V9 WEAK + V10 WEAK):
    → V3 = LEARNING, VALUE UNCERTAIN（中等结论）

IF Phase 1 通关 AND Phase 2 FAIL:
    → V3 = LEARNING BUT NOT USEFUL（学到的东西无外部价值）

IF Phase 1 未通关:
    → V3 = NO LEARNING（实验失败，无需进入 Phase 2）
```

### V3 整体评分

延续 `V3_SCIENTIFIC_VALIDATION.md` 的综合评分体系：

$$\text{FinalScore} = \frac{\sum_{i=1}^{10} \text{Score}_i \times \omega_i}{\sum_{i=1}^{10} \omega_i}$$

其中 $\text{Score}_i \in \{0, 0.5, 1.0\}$，$\omega_i$ 为权重：

| V# | 权重 |
|:--:|:----:|
| V1, V2, V7 | 2.0 |
| V3, V4, V8 | 1.5 |
| V5, V6, V9, V10 | 1.0 |

$$\text{Conclusion} = \begin{cases}
\text{PASS (Strong)} & \text{FinalScore } \geq 0.80 \\
\text{PASS (Moderate)} & 0.60 \leq \text{FinalScore} < 0.80 \\
\text{FAIL} & \text{FinalScore} < 0.60
\end{cases}$$

---

## Part 6 — Failure Rule

> **要求**: 何时整个验证判定为 FAIL 必须提前全部定义。

### 一票否决项（任一触发 → 直接 FAIL）

| # | 条件 | 所属 |
|:--:|------|:----:|
| F1 | $Q_{trend}$ slope $\leq 0$ | V1 |
| F2 | $Q_{sub\_improve} = 0$（5 个子维度斜率为正的数量为 0） | V1 |
| F3 | $N_{mature\_final} = 0$（最终无任何 MATURE principle） | V2 |
| F4 | $\text{PyramidBalance}(T) > 5.0$（知识金字塔严重失衡） | V7 |
| F5 | 任意一层知识存量在最后 10 cycle 归零 | V7 |
| F6 | $\text{TraceCompleteness} < 0.95$（可追溯性不达标） | V8 |
| F7 | $N_{circular} > 0$（存在循环引用） | V8 |

### 连续失败规则

| 条件 | 触发规则 | 判定 |
|------|----------|:--:|
| 连续 **3 个** $W_{segment}$（即 75 cycle）内 $HQ_{mean}$ 无改善趋势 | V1 触发警告 | 需人工审核 |
| 连续 **2 个** $W_{segment}$ 内 $R_{junk} > 0.60$ | V2 触发警告 | 需人工审核 |
| 连续 **5 个** cycle 内 top_framework 每天不同 | V3 触发警告 | 需人工审核 |
| 末尾 $W_{tail}$ 内 $\overline{\sigma}_R > 0.20$ | V4 FAIL | 直接 FAIL |

### Phase 1 终止规则

```
如果触发任一 [F1, F2, F3, F4, F5, F6, F7]:
    → Phase 1 直接终止
    → 记录 FAIL 原因
    → 不进入 Phase 2
    → 输出 V3_FINAL_ASSESSMENT.md（结论: NO LEARNING）
```

### Phase 2 终止规则

```
如果 V9 FAIL (N_survive^fw = 0 且 mean_XR ≤ 0.50):
    → 记录: "所学知识无法泛化"
    → 仍执行 V10（因 V10 可独立于 V9）

如果 V10 FAIL (N_pass = 0):
    → 记录: "方法论与人类研究员无相似性"
```

---

## Part 7 — Dataset Rule

> **要求**: 明确定义允许和禁止的数据。

### Lookahead-Free 规则（最高优先级）

**Lookahead 违反 = 整个验证无效。**

#### 禁止

1. **未来数据**: 任何在时间 $t$ 不应可知的数据，不得出现在 $t$ 的 prediction/evidence 中。
   - 例：cycle 50 的 prediction 不得引用 cycle 51 的市场数据。
   
2. **前视偏差**: 训练/校准阶段不得使用验证阶段的数据。
   - Agent 在 Regime A 训练 → 测试 Regime A。但 Agent 在 Regime A 训练 → 测试 Regime B = OK。

3. **信息泄露**: 同一天的不同 prediction 之间不得共享彼此尚未产生的信息。

#### 允许

1. 每个 cycle 仅使用截至该 cycle date 的所有已知历史数据。
2. `replay history` 按时间顺序排列。
3. Agent 的最终快照用于 V9 冷启动 = OK（因为冷启动是从训练完成状态开始，不涉及跨 regime 泄露）。

### 数据准入清单

| 数据类别 | Phase 1 | Phase 2 (V9) | 备注 |
|----------|:------:|:------------:|------|
| Synthetic market data (trending regime) | ✅ | — | Phase 1 baseline |
| 2008 金融危机数据 | — | ✅ | 历史真实数据 |
| 2011 欧债危机数据 | — | ✅ | |
| 2015 人民币汇改数据 | — | ✅ | |
| 2018 QT/Trade War 数据 | — | ✅ | |
| 2020 COVID 数据 | — | ✅ | |
| 2022 Inflation 数据 | — | ✅ | |
| 2023 AI Bull 数据 | — | ✅ | |
| 人类研究员公开材料（Marks memos, Dalio writings, etc.） | — | ✅ (V10) | 仅用于基准对比 |

### 数据排除清单

| 排除项 | 原因 |
|--------|------|
| 未经 publisher 认证的市场数据 | 数据质量不可控 |
| 非公开付费数据 | 不可复现 |
| Agent 自身产生的 future data | 循环论证 |
| 任何人工修正过的 Agent 中间输出 | 破坏自动化 |
| Human benchmark 中未经公开发表的部分 | 数据来源不可核实 |

### V10 基准数据固定

对 V10 Researcher Benchmark，基准数据来源固定为：

| 研究员 | 数据来源（固定） |
|--------|-----------------|
| Ray Dalio | *Principles* (2017), *Big Debt Crises* (2018), Bridgewater Daily Observations (selected) |
| Paul Tudor Jones | Public interviews, Robin Hood Foundation conference letters, public trade letters |
| Howard Marks | Oaktree Memos (public archive), *The Most Important Thing* (2011) |
| Stanley Druckenmiller | Public interviews, USC Marshall School remarks, Sohn Conference transcripts |

---

## Part 8 — Benchmark Rule

> **要求**: 人类研究员基准固定，不可更换。

### V10 基准（已全部固定）

见 Part 7 末尾数据来源 + Part 1 (V10) 中的研究员 × 时期矩阵。

### 基准冻结条款

1. ✅ 4 位研究员 **已固定**：Dalio, PTJ, Marks, Druckenmiller。
2. ✅ 每位研究员 3 个分析时期 **已固定**：2018-Q1, 2020-Q2, 2022-Q4。
3. ✅ 比较的 4 个维度 **已固定**：Framework, Transmission, Belief, Thesis。
4. ✅ 各维度权重 **已固定**：0.35, 0.35, 0.15, 0.15。

### 禁止行为

- 不得因某研究员得分低而将其移出基准。
- 不得增加新研究员（V3 生命周期内）。
- 不得更换分析时期。
- 不得调整维度权重。
- 不得用"预测准确率"替代"方法论相似度"。

---

## Part 9 — Reproducibility

> **要求**: 任何人按本协议重新 replay，得到相同结果。

### 完全可复现性清单

#### 9.1 固定 Random Seed

| Seed | 用途 |
|:----:|------|
| `RANDOM_SEED = 42` | V3 Agent 全局随机数 |
| `SAMPLING_SEED = 42` | V8 抽样 |
| `CLUSTERING_SEED = 42` | V5 k-means 聚类 |
| `SHUFFLE_SEED = 42` | V9 Regime 内数据 shuffle |

#### 9.2 固定 Replay Order

Phase 1: baseline regime, 100 cycles，严格时间顺序。

Phase 2:
```
R1 (2008 FC) → R2 (2011 EDC) → R3 (2015 CNY) → R4 (2018 QT) → 
R5 (2020 COVID) → R6 (2022 Inf) → R7 (2023 AI)
```

必须严格按此顺序执行连续迁移测试。冷启动测试可用不同顺序（从快照重置），但需记录顺序。

#### 9.3 固定环境

| 组件 | 固定版本 |
|------|:----------:|
| Python | 3.11.x |
| numpy | 1.26.x |
| scipy | 1.11.x |
| scikit-learn | 1.3.x |
| sentence-transformers | 2.2.x |
| pymannkendall | 1.4.x |
| matplotlib | 3.8.x |

嵌入模型：`sentence-transformers/all-MiniLM-L6-v2`（固定，不随版本变化）。

#### 9.4 固定快照

V9 冷启动快照固定为：**Phase 1 cycle 100 结束后的完整 agent 状态**（包括 HypothesisLibrary, PrincipleLibrary, BeliefLibrary, FrameworkSet 的全部内容）。

快照导出格式：JSON / SQLite dump，包含所有四层知识库的完整状态。

#### 9.5 可复现性验证清单

在验证报告中必须记录：

- [ ] Agent 运行使用的 seed 值
- [ ] 各 Replay Phase 的精确起止时间戳
- [ ] Cycle 编号 → 日历日期映射表
- [ ] 各窗口起止 cycle 范围
- [ ] V8 抽样的完整 prediction ID 列表
- [ ] V10 使用的人类基准数据版本号/日期
- [ ] 所有统计测试的完整输出（p-value, slope, R², test statistic）

---

## Part 10 — Frozen Report Template

> **要求**: 最终报告模板提前冻结，所有版本统一格式。

---

### 报告 1: `V3_VALIDATION_REPORT.md`（冻结模板）

```markdown
# V3 Validation Report

**Version**: [版本号]
**Date**: [日期]
**Agent Cycle Count**: 100 (Phase 1) + 210 (Phase 2)
**Protocol Version**: V3_VALIDATION_PROTOCOL.md v1.0

---

## Executive Summary

| 项目 | 结果 |
|------|:----:|
| Phase 1 (Internal Validation) | [PASS / FAIL] |
| Phase 2 (External Validation) | [PASS / WEAK PASS / FAIL] |
| V3 Final Score | [0.00 - 1.00] |
| V3 Conclusion | [PASS (Strong) / PASS (Moderate) / FAIL] |

---

## Phase 1: Internal Validation

### V1 — Hypothesis Quality Curve
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $Q_{trend}$ slope | [数值] | > 0 | [PASS/FAIL] |
| $Q_{trend}$ p-value | [数值] | < 0.05 | |
| $Q_{trend}$ R² | [数值] | > 0.20 | |
| $Q_{sub\_improve}$ | [0-5] | ≥ 3 | [PASS/WEAK/FAIL] |
| $Q_{variance\_down}$ | [TRUE/FALSE] | TRUE | |
| **V1 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Learning curve chart placeholder]*

### V2 — Principle Evolution
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $N_{mature\_final}$ | [数值] | ≥ 2 | |
| $R_{junk}$ | [0.00] | < 0.30 | |
| $R_{promo\_final}$ | [0.00] | > $R_{retire\_final}$ | |
| $\overline{L}_{val}$ | [数值] | >> $\overline{L}_{can}$ | |
| **V2 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Principle lifecycle stacked area chart placeholder]*

### V3 — Framework Stability
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $S_{top}$ | [0.00] | > 0.60 | |
| $J_{final}$ | [0.00] | > 0.70 | |
| $\overline{L}_{fw}$ | [数值] | > 30 | |
| $R_{replace}$ | [0.00] | < 0.30 | |
| **V3 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Framework stability chart placeholder]*

### V4 — Transmission Stability
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $N_{conv}$ / $|C|$ | [数值] / [数值] | ≥ 60% | |
| $\overline{\sigma}_R^{tail}$ | [0.00] | < 0.08 | |
| $\overline{\sigma}_w^{tail}$ | [0.00] | < 0.05 | |
| DepCorrect | [0.00] | > 0.80 | |
| **V4 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Per-channel reliability convergence chart placeholder]*

### V5 — Belief Evolution
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $P_{AB}$ (A+B cluster %) | [0.00] | > 0.60 | |
| $CE_{trend}$ slope | [数值] | < 0 (converging) | |
| $\mathbf{P}_{act \to str}$ | [0.00] | > $\mathbf{P}_{act \to weak}$ | |
| **V5 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Belief weight trajectory clustering chart placeholder]*

### V6 — Research Consistency
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $H'_{dim}^{final}$ | [0.00] | < 0.58 (归一化后 < 1.5) | |
| $H'_{dim}^{trend}$ slope | [数值] | < 0 (converging) | |
| $L_{dominant}$ | [数值] | ≥ 10 | |
| $N_{same\_dom}$ | [0-4] | ≥ 3 | |
| **V6 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Dimension entropy curve chart placeholder]*

### V7 — Knowledge Growth
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| PyramidBalance(T) | [0.00] | < 5.0 | |
| Growth rate order (F>P>B>FW) | [TRUE/FALSE] | TRUE | |
| $\text{Conv}_{F \to P}$ | [0.00] | [0.10, 0.50] | |
| $\text{Conv}_{P \to B}$ | [0.00] | [0.10, 0.50] | |
| $\text{Conv}_{B \to FW}$ | [0.00] | [0.10, 0.50] | |
| **V7 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Four-layer knowledge growth chart placeholder]*

### V8 — Explainability Audit
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| TraceCompleteness | [0.00] | = 1.00 | |
| BrokenChainRate | [0.00] | = 0.00 | |
| $\overline{D}$ (avg chain depth) | [0.0] | ≥ 3 | |
| $N_{circular}$ | [0] | 0 | |
| **V8 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Trace chain completeness breakdown table placeholder]*

---

## Phase 2: External Validation

### V9 — Generalization Test
| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $N_{survive}^{fw}$ | [数值] | ≥ 2 | |
| $\overline{XR}$ | [0.00] | > 0.55 | |
| $\overline{\text{Adapt}}$ | [数值] cycles | 越小越好 | |
| $\text{Retention}_{r_1}$ | [0.00] | > 0.70 | |
| **V9 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

*[Cross-regime framework survival matrix placeholder]*

### V10 — Researcher Benchmark
| 研究员 | DimSim | TransSim | $\rho_{belief}$ | ThesisSim | Score | > 0.45? |
|--------|:------:|:--------:|:--------------:|:---------:|:-----:|:-------:|
| Dalio | | | | | | |
| PTJ | | | | | | |
| Marks | | | | | | |
| Druckenmiller | | | | | | |
| **Mean** | | | | | [0.00] | |

| 指标 | 值 | 阈值 | 判定 |
|------|:--:|:----:|:----:|
| $\overline{RS}$ | [0.00] | > 0.45 | |
| $N_{pass}$ | [0-4] | ≥ 2 | |
| **V10 Overall** | | | **[PASS/WEAK PASS/FAIL]** |

---

## Final Assessment

| 维度 | Score | Weight | Weighted Score |
|------|:-----:|:------:|:-------------:|
| V1 | | 2.0 | |
| V2 | | 2.0 | |
| V7 | | 2.0 | |
| V3 | | 1.5 | |
| V4 | | 1.5 | |
| V8 | | 1.5 | |
| V5 | | 1.0 | |
| V6 | | 1.0 | |
| V9 | | 1.0 | |
| V10 | | 1.0 | |
| **TOTAL** | | | **[0.00]** |

**Final Conclusion**: [PASS (Strong) / PASS (Moderate) / FAIL]

---

## One-Vote Veto Status

| # | 条件 | 状态 |
|:--:|------|:----:|
| F1 | Q_trend slope ≤ 0 | [OK / **VETO**] |
| F2 | Q_sub_improve = 0 | [OK / **VETO**] |
| F3 | N_mature_final = 0 | [OK / **VETO**] |
| F4 | PyramidBalance(T) > 5.0 | [OK / **VETO**] |
| F5 | Any layer zero at end | [OK / **VETO**] |
| F6 | TraceCompleteness < 0.95 | [OK / **VETO**] |
| F7 | N_circular > 0 | [OK / **VETO**] |

---

## Limitations

1. [具体限制 1]
2. [具体限制 2]
3. [具体限制 3]

## Future Work

1. [未来方向 1]
2. [未来方向 2]
3. [未来方向 3]

---

*Report generated under Protocol v1.0. All metrics, windows, and statistical tests as specified in V3_VALIDATION_PROTOCOL.md.*
```

---

### 报告 2: `V3_LEARNING_CURVES.md`（冻结模板）

```markdown
# V3 Learning Curves

*Protocol: V3_VALIDATION_PROTOCOL.md v1.0*

## 1. Hypothesis Quality Curve (V1)

[Chart: HQ_mean(t), HQ_median(t), HQ_top3(t), HQ_bottom3(t) — 100 cycles]

[Chart: 5 sub-dimension curves — 100 cycles]

[Chart: Per-dimension HQ curves — liquidity, growth, inflation, risk_appetite, credit]

## 2. Transmission Convergence (V4)

[Chart: R_c(t) per channel — 100 cycles, W_rolling overlay]

[Chart: Channel weight convergence σ_w — per channel]

[Chart: Failure/Recovery per channel]

## 3. Belief Lifecycle (V5)

[Chart: Weight trajectory clusters (4 clusters)]

[Chart: Calibration Error CE(t) — 100 cycles]

[Chart: State transition matrix heatmap]

[Chart: Per-belief weight trajectory (top 10 active beliefs)]
```

---

### 报告 3: `V3_KNOWLEDGE_GROWTH.md`（冻结模板）

```markdown
# V3 Knowledge Growth Analysis

*Protocol: V3_VALIDATION_PROTOCOL.md v1.0*

## 1. Principle Evolution (V2)

[Chart: Principle lifecycle stacked area — CANDIDATE/VALIDATED/MATURE/FOUNDATIONAL/RETIRED]

[Chart: PromotionRate vs RetirementRate — 100 cycles]

[Chart: Principle lifetime distribution histogram]

[Chart: ContradictionRate trend]

## 2. Knowledge Pyramid (V7)

[Chart: Four-layer cumulative growth curves — Finding/Principle/Belief/Framework]

[Chart: Pyramid ratio bar chart — at t=25, 50, 75, 100]

[Chart: Conversion funnel — F→P, P→B, B→FW]

[Chart: Per-layer growth rate moving average (W_growth=10)]

## 3. Anomaly Detection (V7)

[Table: Anomaly log — timestamp, type, severity, resolution]
```

---

### 报告 4: `V3_FRAMEWORK_ANALYSIS.md`（冻结模板）

```markdown
# V3 Framework Analysis

*Protocol: V3_VALIDATION_PROTOCOL.md v1.0*

## 1. Framework Stability (V3)

[Chart: N_active(t), N_candidate(t), N_retired(t) — 100 cycles]

[Chart: TopFramework identity timeline]

[Chart: Jaccard stability J̄(t) — 100 cycles]

[Chart: Weight delta Δ̄_w(t) — 100 cycles]

[Chart: Framework lineage tree (genealogy graph)]

## 2. Research Consistency (V6)

[Chart: H'_dim(t) and H'_fw(t) — 100 cycles]

[Chart: ThesisCoherence(t) between consecutive thesis pairs]

[Chart: Per-segment dominant dimension — 4 bars]

[Table: Thesis titles by segment]

## 3. Generalization Test (V9)

[Chart: Cross-regime framework survival matrix (7×7 heatmap)]

[Chart: Per-regime adaptation speed]

[Chart: Knowledge retention across regime transitions]

[Table: Principle cross-regime accuracy by principle]
```

---

### 报告 5: `V3_FINAL_ASSESSMENT.md`（冻结模板）

```markdown
# V3 Final Assessment

*Protocol: V3_VALIDATION_PROTOCOL.md v1.0*

## 1. Overall Conclusion

**V3 Learning Status**: [LEARNING + VALUABLE / LEARNING, VALUE UNCERTAIN / LEARNING BUT NOT USEFUL / NO LEARNING]

**Final Score**: [0.00 / 1.00]

**Phase 1**: [PASS / FAIL]
**Phase 2**: [PASS / WEAK PASS / FAIL]

---

## 2. Evidence Summary

### Learning Evidence (Phase 1)
- [V1 conclusion and key numbers]
- [V2 conclusion and key numbers]
- [V3 conclusion and key numbers]
- [V4 conclusion and key numbers]
- [V5 conclusion and key numbers]
- [V6 conclusion and key numbers]
- [V7 conclusion and key numbers]
- [V8 conclusion and key numbers]

### Value Evidence (Phase 2)
- [V9 conclusion and key numbers]
- [V10 conclusion and key numbers]

---

## 3. Researcher Benchmark Detailed Analysis (V10)

Per-researcher breakdown with qualitative notes.

---

## 4. Key Findings

1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

---

## 5. Limitations

[Discussion of what this validation cannot answer]

## 6. Future Work

[Recommendations for V4 or further investigation]

## 7. Reproducibility Statement

| 参数 | 值 |
|------|------|
| Protocol Version | v1.0 |
| Agent Seed | 42 |
| Total Cycles | 310 |
| Phase 1 Cycles | 100 |
| Phase 2 Regimes | 7 |
| Sampling Seed | 42 |
| Clustering Seed | 42 |
| Python Version | 3.11.x |
| Key Libraries | numpy 1.26.x, scipy 1.11.x, sklearn 1.3.x |
| Embedding Model | all-MiniLM-L6-v2 |
| Replay Order | R1→R2→R3→R4→R5→R6→R7 |

*This report was generated under the frozen protocol V3_VALIDATION_PROTOCOL.md v1.0.*
*Any future validation must use the identical protocol or be declared as a new version.*
```

---

## 附录 A — Phase 执行流程

### Milestone F0: Validation Readiness 执行清单

```
□ F0-1.  确认 validation/ 目录存在且独立于 src/
□ F0-2.  确认 Snapshot Layer 已部署（snapshot_writer/reader/manager）
□ F0-3.  确认 Agent 已完成 100 cycle run
□ F0-4.  运行 readiness_checker.py → 全部 13 项检查
□ F0-5.  判定：全部 13 项 PASS → F0 = READY → 进入 Phase 1
□ F0-6.  判定：任一项 FAIL → F0 = NOT READY → 修复后重新运行 F0
```

### Phase 1 执行清单

```
□ 1. 确认 Milestone F0 = READY
□ 2. 确认 Validation Isolation Principle 未违反（validation 未触发任何 Agent 状态变更）
□ 3. 运行 metric_calculator.py → V1 Hypothesis Quality 指标计算
□ 4. 运行 metric_calculator.py → V2 Principle Evolution 指标计算
□ 5. 运行 metric_calculator.py → V3 Framework Stability 指标计算
□ 6. 运行 metric_calculator.py → V4 Transmission Stability 指标计算
□ 7. 运行 metric_calculator.py → V5 Belief Evolution 指标计算
□ 8. 运行 metric_calculator.py → V6 Research Consistency 指标计算
□ 9. 运行 metric_calculator.py → V7 Knowledge Growth 指标计算
□ 10. 运行 metric_calculator.py → V8 Explainability Audit 指标计算
□ 11. 运行 statistics_engine.py → 对 V1-V8 执行统计检验（ST1-ST9）
□ 12. 运行 curve_generator.py → 生成 V1/V4/V5 学习曲线图
□ 13. 运行 report_builder.py → 生成 V3_VALIDATION_REPORT.md（V1-V8）
□ 14. 运行 report_builder.py → 生成 V3_LEARNING_CURVES.md
□ 15. 运行 report_builder.py → 生成 V3_KNOWLEDGE_GROWTH.md
□ 16. 运行 report_builder.py → 生成 V3_FRAMEWORK_ANALYSIS.md
□ 17. 判定 Phase 1 PASS/FAIL
□ 18. 若 FAIL → 输出 V3_FINAL_ASSESSMENT.md（结论: NO LEARNING）→ 终止
□ 19. 若 PASS → 进入 Phase 2
```

### Phase 2 执行清单

```
□ 20. 确认 Milestone F0 快照仍然有效（immutability re-check）
□ 21. 从 Phase 1 cycle 100 导出 Agent 快照
□ 22. 冷启动：用快照依次测试 R1-R7（每个 30 cycle，每次从快照重置）
□ 23. 连续迁移：Agent 连续经历 R1→R7（保留学习痕迹）
□ 24. 灾难性遗忘测试：R7 结束后重新测试 R1 数据
□ 25. 运行 metric_calculator.py → V9 Generalization 指标计算
□ 26. 准备 V10 Human Benchmark 数据（12 份基准快照）
□ 27. 运行 metric_calculator.py → V10 Researcher Benchmark 指标计算
□ 28. 运行 statistics_engine.py → 对 V9-V10 执行统计检验
□ 29. 运行 curve_generator.py → 生成 V9 泛化矩阵图
□ 30. 运行 report_builder.py → 补充 V3_VALIDATION_REPORT.md（V9-V10）
□ 31. 运行 report_builder.py → 补充 V3_FRAMEWORK_ANALYSIS.md（V9）
□ 32. 运行 report_builder.py → 生成 V3_FINAL_ASSESSMENT.md
□ 33. 计算 V3 Final Score
□ 34. 输出全部 5 份验证文档（最终版本）
```

---

## 附录 B — 禁止操作清单

以下操作在 V3 验证生命周期内被明确禁止：

| # | 禁止操作 | 原因 |
|:--:|----------|------|
| 1 | 修改数学公式 | 破坏协议冻结 |
| 2 | 修改窗口大小 | 破坏可比性 |
| 3 | 修改统计测试方法 | cherry-picking 风险 |
| 4 | 修改显著性阈值 | p-hacking |
| 5 | 修改 Failure Rule | 不可复现 |
| 6 | 修改数据集准入规则 | 数据泄露风险 |
| 7 | 更换人类研究员基准 | 基准漂移 |
| 8 | 更换 embedding 模型版本 | 结果不可复现 |
| 9 | 修改 random seed | 不可复现 |
| 10 | 修改 Replay Order | 排序效应 |
| 11 | 在结果不理想后调整任何参数 | 事后优化 |
| 12 | 选择性报告有利的 Validation | 报告偏差 |

---

## 附录 C — 协议修订条款

本协议为 **v1.0 冻结版**。如需修订：

1. 新建 `V4_VALIDATION_PROTOCOL.md`。
2. 在 `V4` 协议中声明与 `V3` 的差异（Change Log）。
3. 不得修改 `V3_VALIDATION_PROTOCOL.md` 原有内容。
4. 新协议应有独立的实验周期，不与 v1.0 结果混合比较。

---

> **Protocol Status**: FROZEN v1.0
> **Effective Date**: 2026-07-18
> **Expiry**: None（实验协议永久有效，直到被新版本协议声明取代）
> **Declared Frozen Parts**: Part 1–10（全部）+ 总则（Validation Isolation Principle + Milestone F0 + Milestone F0.5 Snapshot Layer）
> **Next Step**: 执行 Milestone F0（Validation Readiness Check），确认 Snapshot Layer 已部署且数据质量通过后方可进入 Phase 1
> **Reminder**: 先检查数据，再证明学习，最后证明价值
