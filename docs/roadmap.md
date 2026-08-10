# Release Roadmap — Macro Research Agent

> **Status**: FROZEN | Architecture Freeze — 2026-07-15 (Revision 2)
>
> Sprint S0–S8 已完成。此后不再使用 Sprint 编号，改为 Release Roadmap：**MVP → V1 → V2**。
> 所有后续开发严格按此 Roadmap 执行，不新增 Sprint。

---

## 已完成（Sprint 0–8）

| Sprint | 重点 | 产出 |
|--------|------|------|
| S0 | 工程基础 | 目录结构、配置、CI、Docker |
| S1 | 数据管道 | Collector (Yahoo) + Normalizer + Validation + Repository |
| S2 | 信号引擎 | Rule Engine + Signal Generator + SignalSnapshot API |
| S3 | 规划器 | RuleBasedPlanner + Planning Rules YAML |
| S4 | 执行器 | AgentExecutor + ExecutionContext + 5 SimpleHandlers |
| S5 | 工具层 | BaseTool + ToolRegistry + ToolManager + YahooMacroTool |
| S6 | 推理引擎 | HypothesisEngine + Generator + Aggregator + Confidence |
| S7 | 反思引擎 | ReflectionEngine + Reviewer + BeliefScorer |
| S8 | 信念记忆 | BeliefMemoryStore + Builder + MemoryHandler |

**已废弃**: `src/analyzer/` — 职责由 Observation Layer (V1) + Signal Engine 覆盖。

---

## Schema 链（全栈统一契约）

> DDR-010: Schema First Architecture — 所有认知模块仅通过类型化 Schema 交换数据。
> 内部实现可变，契约不可变。

```
Collector        → MacroDataSchema
    ↓
Normalizer       → MacroDataSchema (canonicalized)
    ↓
Signal Engine    → SignalSnapshot
    ↓
HypothesisEngine → HypothesisSet
    ↓
ReflectionEngine → ReflectionSet
    ↓
BeliefMemory     → BeliefRecord[]
    ↓
Narrative Engine → MacroNarrative
```

**规则**:
- 模块间通信 **必须使用 Pydantic Schema**，禁止 `dict | tuple | list[Any]` 跨模块传递。
- 每个模块的 `input → output` 类型在 Schema 层显式声明。
- Presentation（Markdown/HTML/PDF）是外部消费层的职责，不属于认知模块的 Schema 契约。

---

## Release 0.2.0 — MVP

> **目标**: 系统完成一次端到端宏观研究，输出 `MacroNarrative`（结构化宏观叙事）。
> **非目标**: 数据质量增强、自主规划、实时监控、Web Dashboard。

### 优先级排列（按交付依赖）

| # | 模块 | 目标 | 关键交付物 |
|---|------|------|-----------|
| **1** | **架构债务修复** | memory 导出、SignalHandler 注册、planning_rules.yaml 更新为真实 capability | `src/memory/__init__.py`, `src/handlers/__init__.py`, `configs/planning_rules.yaml` |
| **2** | **MacroResearchPipeline** | 系统唯一统一入口，组装完整 DAG | `src/pipeline.py` (`MacroResearchPipeline.run()`) |
| **3** | **Narrative Engine** | 消费完整认知链输出 → `MacroNarrative` Schema | `src/narrative/`, `MacroNarrative` Schema, `NarrativeHandler` |
| **4** | **CLI 入口** | 命令行交互入口，调用 `pipeline.run()` | `src/cli/main.py` |
| **5** | **API 扩展** | `POST /analyze` 触发管道，`GET /report/{id}` 返回 MacroNarrative | `src/api/routes.py` 扩展 |
| **6** | **端到端集成测试** | 验证完整链路 | `tests/integration/test_e2e_mvp.py` |

### MVP 架构图

```
CLI / API / (Future: Scheduler)
            │
            ▼
     MacroResearchPipeline.run()
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │              Fixed DAG (Planner)              │
   │                                              │
   │  collect ──► normalize ──► signal            │
   │                              │                │
   │                              ▼                │
   │                          hypothesis           │
   │                              │                │
   │                              ▼                │
   │                          reflection           │
   │                              │                │
   │                              ▼                │
   │                           memory              │
   │                              │                │
   │                              ▼                │
   │                    NARRATIVE ENGINE           │
   │              (消费全部认知链输出)               │
   └──────────────────────────────────────────────┘
            │
            ▼
      MacroNarrative      ← 结构化 Schema（非 Markdown）
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
   CLI     API    Dashboard    ← 各自消费 MacroNarrative 做展示
 (Markdown) (JSON) (HTML)
```

### MacroNarrative Schema（MVP 核心契约）

```python
class MacroNarrative(BaseModel):
    """The canonical structured output of a macro research run.
    
    This is the ONLY contract between the Agent and all presentation layers.
    CLI, API, Dashboard, PDF — all consume MacroNarrative, not raw Markdown.
    """
    summary: str                     # 一句话宏观判断
    macro_story: str                 # 宏观叙事（2-3 段结构化英文/中文）
    liquidity: DimensionNarrative    # 流动性维度
    credit: DimensionNarrative       # 信用维度
    growth: DimensionNarrative       # 增长维度
    inflation: DimensionNarrative    # 通胀维度
    belief_changes: list[BeliefChangeNote]  # 信念变化追踪
    risks: list[RiskItem]            # 风险提示
    action_items: list[str]          # 待关注事项
    confidence: float                # 综合置信度 0–1
    generated_at: datetime
```

### MVP 不包含

- Observation Layer（→ V1）
- 自主规划 / LLM 任务分解（→ 不做）
- State Manager (LangGraph)（→ V2）
- Scheduler（→ V2）
- Monitoring（→ V2）
- Analyzer 模块（已废弃）

---

## Release 0.5.0 — V1

> **目标**: 提升信号质量和系统可靠性。

| # | 模块 | 目标 |
|---|------|------|
| **1** | **Observation Layer** | 在 Data Pipeline 与 Signal Engine 之间插入 Observation 抽象层。Signal Engine 消费 `Observation[]` 而非原始 `MacroDataSchema` |
| **2** | **Signal Engine 接口升级** | `generate(indicator, current, history)` → `generate(observations: list[Observation])` |
| **3** | **ObservationHandler** | 注册 capability `macro.observation`，上下文构建器 |
| **4** | **ReplanGate** | 当 Reflection 输出 REFUTED 时，触发重规划或降级策略 |
| **5** | **ArtifactKey 枚举** | 消除魔法字符串，类型安全的 artifact key 通信 |
| **6** | **Narrative 多格式导出** | CLI/API/Dashboard 各自从 `MacroNarrative` 渲染 Markdown / JSON / HTML / PDF |

---

## Release 1.0.0 — V2

> **目标**: 生产级可靠性和可观测性。

| # | 模块 | 目标 |
|---|------|------|
| **1** | **State Manager** | LangGraph 状态机，替代当前 ExecutionContext 的简单状态管理 |
| **2** | **Scheduler** | 定时任务编排（每日/每周宏观巡检） |
| **3** | **Monitoring** | 日志、指标、告警、执行追踪 |
| **4** | **API 完备化** | `GET /beliefs`, `GET /analyses`, 分页、搜索、筛选 |
| **5** | **LLM 集成** | 引入 LLM 增强假设生成和反思质量（可选） |
| **6** | **API 认证** | 生产环境安全 |

---

## Future (v2.0, Implemented ✅) — Continuous Learning Agent

> **Status**: ✅ Implemented (July 2026)  
> **Tests**: 62 passing (v2.0 suite) | 86 v1.0 regression tests unaffected  
> **DDR**: [docs/ddr_v2.md](ddr_v2.md)

将 Agent 从 "一次性分析器" 升级为 "持续学习研究者"：

| # | 模块 | 目标 | 交付 |
|---|------|------|------|
| **1** | **Outcome Tracking Engine** | 追踪预测 vs 实际结果，建立反馈闭环 | `src/outcome/engine.py` — OutcomeEvaluator, OutcomeMetrics (hit rate, Brier Score), OutcomeTracker |
| **2** | **Learning Engine** | 基于历史准确度调整维度信念权重 | `src/learning/learning_engine.py` — BeliefUpdater (EMA), ConfidenceDecay, PatternMiner |
| **3** | **Confidence Calibration** | 校准置信度（原始 * 0.50 + 历史 * 0.30 + 维度权重 * 0.20，不超过原始值） | `src/calibration/confidence_calibrator.py` |
| **4** | **Cross-Indicator Reasoning** | 组合信号 → 宏观主题（8 个主题定义） | `src/signal/composite_signal_generator.py` — CompositeSignal, MacroTheme |
| **5** | **Narrative Engine v2** | 叙事加入 "What We Learned"、"Prediction Accuracy"、"Confidence Calibration" 章节 | `src/narrative/engine.py` v2 rewrite |
| **6** | **API v2 Endpoints** | GET /v2/beliefs, /learning, /outcomes, /accuracy, /confidence; POST /v2/relearn | `src/api/v2_routes.py` |

### v2.0 认知闭环

```
Observation → Signal → Hypothesis → Reflection → Memory
                                                    │
                    ┌───────────────────────────────┤
                    ↓                               ↓
              Outcome Tracking               Composite Signals
                    │                               │
                    ↓                               ↓
              Learning Engine                MacroThemes
                    │                               │
                    ↓                               │
           Confidence Calibration                   │
                    │                               │
                    └───────────┬───────────────────┘
                                ↓
                      Narrative Engine v2
                 (含 What We Learned /
                  Prediction Accuracy /
                  Confidence Calibration 章节)
```

---

## Future (v2.1+)

> **方向性规划，不进入当前开发范围。**

| 能力 | 描述 |
|------|------|
| **Outcome Tracking → Learning** | 信念校准：追踪报告预测 vs 实际结果，建立反馈闭环，实现长期学习 |
| **Web Dashboard** | 可视化宏观状态、信号面板、信念网络 |
| **Multi-Agent Debate** | 多个 Agent 独立推理后辩论，投票形成共识信念 |
| **Real-Time Streaming** | WebSocket 推送实时宏观数据更新和信号变化 |

---

## 架构原则（冻结后不变）

1. **Pipeline 是唯一入口**: `MacroResearchPipeline.run()` — CLI、API、Scheduler 全部通过它调用
2. **Planner = 固定 DAG**: 不做自主规划，仅作为任务编排器
3. **Schema First**: 所有认知模块仅通过类型化 Pydantic Schema 交换数据。禁止 `dict | tuple | list[Any]` 跨模块边界传递（DDR-010）
4. **MacroNarrative 是唯一输出契约**: CLI/API/Dashboard/PDF 全部消费 `MacroNarrative`，不直接消费 Markdown
5. **确定性优先**: Signal、Hypothesis、Reflection 均为确定性引擎（MVP 不依赖 LLM）
6. **不修改原始对象**: Hypothesis 由 HypothesisEngine 产出后，Reflection 和 Narrative 均不修改原对象
