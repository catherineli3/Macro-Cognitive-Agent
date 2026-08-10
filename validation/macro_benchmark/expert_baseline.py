# =============================================================================
# V3.3 Expert Baseline — reference for comparing Agent reasoning vs top investors
# =============================================================================
# Maps each case to expected expert reasoning patterns based on:
#   - Ray Dalio (Bridgewater): debt cycles, beautiful deleveraging, MP3 framework
#   - Paul Tudor Jones: macro asymmetry, risk/reward, rate regime shifts
#   - Bridgewater research style: systematic, regime-aware, multi-dimensional
#
# Each baseline entry defines what a senior macro researcher SHOULD observe.
# The agent is scored on alignment with these expert patterns.
# =============================================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExpertBaseline:
    """Expected expert-level analysis for a macro event."""
    case_id: str
    expert_archetype: str  # "Dalio", "PTJ", "Bridgewater", "Mixed"

    # Core thesis — what the expert would say in one sentence
    core_thesis: str

    # Key signals the expert would notice
    key_signals: list[str] = field(default_factory=list)

    # Causal chain the expert would articulate
    causal_chain: list[str] = field(default_factory=list)

    # Regime classification the expert would use
    regime_classification: str = ""

    # What the expert would be watching (leading indicators)
    watch_items: list[str] = field(default_factory=list)

    # Expert's confidence calibration
    expert_confidence: float = 0.65  # Experts are rarely overconfident

    # What would change the expert's mind
    falsification_conditions: list[str] = field(default_factory=list)

    # Key differentiator — what separates good from great analysis
    differentiator: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# EXPERT BASELINE LIBRARY
# ═══════════════════════════════════════════════════════════════════════════

EXPERT_BASELINES: dict[str, ExpertBaseline] = {

    # ── Global Financial Crisis ──────────────────────────────────────

    "GFC-001": ExpertBaseline(
        case_id="GFC-001",
        expert_archetype="Dalio",
        core_thesis="This is a classic debt crisis requiring coordinated monetary + fiscal response to prevent depression",
        key_signals=["LIBOR-OIS spread 364bp", "VIX 80", "HY spreads 1800bp",
                     "Fed cutting aggressively", "money market funds breaking the buck"],
        causal_chain=[
            "Housing bubble debt accumulation -> Mortgage defaults",
            "-> MBS/CDO losses -> Bank solvency crisis",
            "-> Interbank lending freezes -> Credit markets seize",
            "-> Real economy contracts -> Unemployment spikes",
            "-> Requires: debt restructuring + central bank printing + fiscal support",
        ],
        regime_classification="Depression risk / Debt crisis / Policy response phase",
        watch_items=["TED spread normalization", "CPFF/PDCF usage",
                     "TARP deployment speed", "bank capital raises"],
        expert_confidence=0.75,
        falsification_conditions=[
            "If interbank markets don't normalize within 3 months of TARP",
            "If bank capital raises fail despite government backstops",
        ],
        differentiator="Recognizing this as a solvency crisis (not liquidity) requiring debt restructuring"
    ),

    "GFC-003": ExpertBaseline(
        case_id="GFC-003",
        expert_archetype="PTJ",
        core_thesis="Maximum pessimism + unprecedented policy response = asymmetric risk/reward favoring longs",
        key_signals=["VIX 50 (extreme fear)", "S&P down 57% from peak",
                     "Fed at ZIRP + QE active", "policy response 'whatever it takes'"],
        causal_chain=[
            "Extreme bearish sentiment -> All sellers exhausted",
            "-> Coordinated policy response -> Systemic collapse averted",
            "-> Risk/reward asymmetry -> Upside > downside",
            "-> Asset prices reflate before real economy recovers",
        ],
        regime_classification="Capitulation / Policy Bazooka / V-shaped recovery setup",
        watch_items=["VIX decline below 30", "credit spread compression",
                     "bank CDS normalization", "Fed balance sheet expansion pace"],
        expert_confidence=0.70,
        falsification_conditions=[
            "If bank nationalization risk materializes",
            "If credit markets remain frozen despite QE",
        ],
        differentiator="Seeing the asymmetry: policy response > economic damage at this point"
    ),

    # ── Eurozone ─────────────────────────────────────────────────────

    "EZ-002": ExpertBaseline(
        case_id="EZ-002",
        expert_archetype="Bridgewater",
        core_thesis="Draghi's 'whatever it takes' is policymaker game theory — credible commitment ends doom loop without firing a shot",
        key_signals=["Italian yields 6.5% (unsustainable)", "Spanish yields 7.2%",
                     "Draghi speech", "ECB credibility test"],
        causal_chain=[
            "Sovereign-bank doom loop -> Rising yields threaten solvency",
            "-> ECB draws line (OMT framework) -> Credible commitment breaks feedback",
            "-> Yields collapse without actual bond purchases",
            "-> Sovereign crisis ends -> Risk assets re-rate higher",
        ],
        regime_classification="Central bank put / Credibility restoration / Risk-on pivot",
        watch_items=["Italian/Spanish yield convergence", "ECB OMT legal clarity",
                     "banking union progress", "fiscal reform follow-through"],
        expert_confidence=0.72,
        falsification_conditions=[
            "If German constitutional court blocks OMT",
            "If Italy/Spain fail to implement fiscal reforms",
        ],
        differentiator="Understanding that credibility > actual intervention — the speech itself was the policy tool"
    ),

    # ── Taper Tantrum ────────────────────────────────────────────────

    "TT-001": ExpertBaseline(
        case_id="TT-001",
        expert_archetype="Bridgewater",
        core_thesis="The market is addicted to QE liquidity — taper talk reveals structural vulnerability in EM funding",
        key_signals=["Bernanke taper signal", "10Y 1.6->3.0%", "EM FX collapse",
                     "current account deficit countries most hit"],
        causal_chain=[
            "QE flows into EM -> EM yields compressed, currencies overvalued",
            "-> Taper signal -> US rates rise -> Capital flows reverse",
            "-> EM FX depreciates -> Imported inflation -> Central banks can't cut",
            "-> 'Fragile Five' identified — structural vulnerability exposed",
        ],
        regime_classification="QE withdrawal / EM vulnerability / Rate normalization risk",
        watch_items=["EM current account balances", "foreign ownership of local bonds",
                     "FX reserve adequacy", "Fed dots vs market pricing"],
        expert_confidence=0.68,
        falsification_conditions=[
            "If Fed explicitly commits to no taper for 12+ months",
            "If EM central banks successfully defend currencies",
        ],
        differentiator="Identifying the transmission: QE -> EM inflows -> fragility -> taper = crisis"
    ),

    # ── Oil Collapse ─────────────────────────────────────────────────

    "OIL-001": ExpertBaseline(
        case_id="OIL-001",
        expert_archetype="Dalio",
        core_thesis="Oil crash is supply-driven disinflation, not demand-driven recession — bullish for consumers, bearish for energy credit",
        key_signals=["US shale production surge", "Saudi market share war",
                     "DXY strengthening", "HY energy exposure"],
        causal_chain=[
            "Shale boom + Saudi strategy -> Oil supply glut",
            "-> WTI collapses from $107 -> Disinflation wave",
            "-> Consumer benefits (lower gas) -> HY energy stress (sector, not systemic)",
            "-> DXY strengthens -> EM/commodity producers crushed",
        ],
        regime_classification="Supply-driven disinflation / Dollar bull / Sector stress only",
        watch_items=["OPEC unity", "shale production response",
                     "HY energy default rates", "consumer spending boost"],
        expert_confidence=0.70,
        falsification_conditions=[
            "If demand data (PMIs, trade volumes) also collapse",
            "If HY energy stress spreads to IG credit",
        ],
        differentiator="Distinguishing supply-driven (bullish) from demand-driven (bearish) oil decline"
    ),

    "OIL-002": ExpertBaseline(
        case_id="OIL-002",
        expert_archetype="Mixed",
        core_thesis="Oil at $26 is extreme — the market is pricing depression probability in energy credit, creating buying opportunity",
        key_signals=["WTI $26", "HY spreads 850bp", "V-shaped recovery setup",
                     "energy 3% of GDP", "sector not systemic"],
        causal_chain=[
            "Oil overshoots to $26 -> Deflation panic sets in",
            "-> HY energy priced for depression -> Sector is 15% of HY, 3% of GDP",
            "-> Default losses manageable -> Market over-pricing systemic risk",
            "-> Buying opportunity in risk assets as fear peaks",
        ],
        regime_classification="Deflation scare / Over-priced risk / Contrarian opportunity",
        watch_items=["OPEC production freeze talks", "oil inventory draws",
                     "HY energy distressed exchange offers", "China stimulus"],
        expert_confidence=0.65,
        falsification_conditions=[
            "If oil stays below $30 for 12+ months",
            "If HY energy defaults trigger bank losses (contagion)",
        ],
        differentiator="Seeing sector problem being priced as systemic risk — classic opportunity identification"
    ),

    # ── COVID ────────────────────────────────────────────────────────

    "COVID-001": ExpertBaseline(
        case_id="COVID-001",
        expert_archetype="Bridgewater",
        core_thesis="This is an exogenous shock, not an endogenous cycle — unprecedented policy response will create V-shaped recovery",
        key_signals=["VIX 82", "Fed cuts 150bp in 13 days", "$5T+ fiscal",
                     "$4T+ Fed balance sheet", "banks well capitalized (unlike 2008)"],
        causal_chain=[
            "COVID shutdown -> Demand collapse -> Markets panic",
            "-> Fed responds in days (not months like 2008) -> Fiscal unprecedented",
            "-> Discount rates -> 0 + fiscal transfers -> massive savings",
            "-> Asset prices re-rate -> Retail flows in -> V-shaped recovery",
        ],
        regime_classification="Exogenous shock / All-in policy response / V-shaped recovery",
        watch_items=["vaccine timeline", "fiscal stimulus renewal",
                     "savings rate", "Fed balance sheet path"],
        expert_confidence=0.72,
        falsification_conditions=[
            "If vaccine development fails or takes 3+ years",
            "If fiscal cliff hits before recovery solidifies",
        ],
        differentiator="Distinguishing exogenous shock (recoverable) from endogenous cycle (structural damage)"
    ),

    "COVID-002": ExpertBaseline(
        case_id="COVID-002",
        expert_archetype="Dalio",
        core_thesis="MP3 in action — coordinated fiscal+monetary is inherently inflationary for assets first, goods later",
        key_signals=["M2 +25% YoY", "gold $2070", "DXY breaking down",
                     "MP3 mechanism active", "CPI likely to surge with 12-18 month lag"],
        causal_chain=[
            "Fiscal-monetary coordination (MP3) -> Direct monetization of debt",
            "-> Money supply explodes -> Asset prices inflate first",
            "-> With 12-18 month lag -> Goods/services inflation",
            "-> Gold as canary -> DXY structural decline",
        ],
        regime_classification="MP3 / Reflation / Inflation brewing / Dollar bear market",
        watch_items=["M2 growth trajectory", "fiscal deficit path",
                     "commodity price trends", "wage growth acceleration"],
        expert_confidence=0.70,
        falsification_conditions=[
            "If M2 growth normalizes below 10% rapidly",
            "If fiscal spending is sharply cut before recovery completes",
        ],
        differentiator="Using MP3 framework to see inflation before it appears in CPI data"
    ),

    # ── 2022 Inflation & Hiking ─────────────────────────────────────

    "INF-001": ExpertBaseline(
        case_id="INF-001",
        expert_archetype="PTJ",
        core_thesis="Most dangerous financial environment since 1980s — 7% inflation + negative real rates means aggressive rate hikes are MECHANICAL",
        key_signals=["CPI 7.5%", "Fed at 0%", "real rates deeply negative",
                     "labor market tight (UE 4%)", "P/E at elevated levels"],
        causal_chain=[
            "Inflation at 40-year high + Fed at zero -> Massive policy error",
            "-> Real rates deeply negative -> MUST hike aggressively to catch up",
            "-> Higher discount rates -> P/E compression -> Equities re-price lower",
            "-> P/E compression dominates earnings growth -> Bear market",
        ],
        regime_classification="Behind-the-curve tightening / Asset repricing / Bear market",
        watch_items=["real rates trajectory", "CPI momentum (MoM not YoY)",
                     "labor market slack", "Fed terminal rate pricing"],
        expert_confidence=0.80,
        falsification_conditions=[
            "If CPI falls below 4% within 3 months naturally",
            "If Fed explicitly caps rate hikes at 2%",
        ],
        differentiator="Understanding that 7% inflation + ZIRP = mechanical asset repricing, not optional"
    ),

    "INF-002": ExpertBaseline(
        case_id="INF-002",
        expert_archetype="Mixed",
        core_thesis="CPI 9.1% is likely the peak, but psychology of 'peak' means markets need 2-3 confirming prints before trusting the turn",
        key_signals=["CPI 9.1% (likely peak)", "commodities rolling over",
                     "base effects favor disinflation", "housing leading indicators softening"],
        causal_chain=[
            "CPI surges to 9.1% -> Peak call emerges",
            "-> But one print isn't enough -> Consensus needs 2-3 confirms",
            "-> Front-running the turn requires conviction -> Risk reward favors patience",
            "-> Eventually: disinflation confirmed -> Fed pace slows -> Markets rally",
        ],
        regime_classification="Inflation peak / Turning point / Patience rewarded",
        watch_items=["CPI MoM prints", "shelter/OER lag", "commodity indices",
                     "Fed rhetoric shift from hawkish to data-dependent"],
        expert_confidence=0.60,
        falsification_conditions=[
            "If next 2 CPI prints are above 9%",
            "If wage growth accelerates above 6%",
        ],
        differentiator="Understanding the psychology of 'peak' — it's not enough to be right, you need timing"
    ),

    "INF-003": ExpertBaseline(
        case_id="INF-003",
        expert_archetype="Bridgewater",
        core_thesis="UK gilt crisis reveals hidden leverage in 'safe' assets — LDI margin calls create self-reinforcing doom loop that BOE must break",
        key_signals=["30Y gilt 5%", "LDI margin calls", "BOE forced buyer",
                     "pension system stress", "sterling weakness"],
        causal_chain=[
            "UK mini-budget -> Fiscal credibility crisis -> Gilts sell off",
            "-> Yields spike -> LDI pension funds face margin calls",
            "-> Forced selling -> Yields rise further -> More margin calls",
            "-> BOE intervenes as buyer of last resort -> Doom loop breaks",
        ],
        regime_classification="Hidden leverage crisis / Policy error / Central bank backstop",
        watch_items=["LDI leverage levels globally", "pension fund regulation",
                     "sovereign fiscal credibility metrics", "duration hedging practices"],
        expert_confidence=0.68,
        falsification_conditions=[
            "If BOE intervention fails to stabilize gilts within 2 weeks",
            "If contagion spreads to other sovereign bond markets",
        ],
        differentiator="Identifying the hidden leverage in 'safe' pension assets as the real risk"
    ),

    "INF-004": ExpertBaseline(
        case_id="INF-004",
        expert_archetype="PTJ",
        core_thesis="Something broke — as expected after fastest hiking in 40 years. Counterintuitively bullish: rates fall, Fed pauses, tech benefits",
        key_signals=["SVB failure $209B", "regional bank stress", "Fed creates BTFP",
                     "rate expectations collapse", "flight to safety"],
        causal_chain=[
            "Fastest hikes in 40 years -> Duration mismatch at banks",
            "-> SVB fails -> Contagion fear in regional banks",
            "-> Fed creates BTFP (stealth pause) -> Flight to safety",
            "-> Rates fall -> Tech/growth benefit from lower discount rates",
            "-> Counterintuitive: banking crisis = bullish for equities",
        ],
        regime_classification="Something broke / Fed stealth pivot / Counterintuitive bullish",
        watch_items=["BTFP usage", "regional bank deposit flows",
                     "CRE exposure", "Fed rate path repricing"],
        expert_confidence=0.65,
        falsification_conditions=[
            "If bank stress spreads to systematically important banks",
            "If Fed explicitly continues hiking despite banking stress",
        ],
        differentiator="Seeing the counterintuitive: bank crisis -> lower rates -> tech rally"
    ),

    # ── AI Boom ──────────────────────────────────────────────────────

    "AI-001": ExpertBaseline(
        case_id="AI-001",
        expert_archetype="Mixed",
        core_thesis="The AI capex cycle is genuine infrastructure buildout — NVDA $11B/quarter DC revenue means $200B+ annual hyperscaler spend",
        key_signals=["NVDA revenue $11B vs $7B consensus", "data center capex guide",
                     "hyperscaler AI spend commitments", "semiconductor cycle acceleration"],
        causal_chain=[
            "ChatGPT moment -> AI demand signal -> Hyperscalers commit capex",
            "-> NVDA becomes bottleneck supplier -> Revenue explodes",
            "-> Genuine infrastructure buildout -> Not speculation, real spending",
            "-> Productivity gains may follow -> But spending is real today",
        ],
        regime_classification="Capex-led growth cycle / Technology infrastructure / Productivity bet",
        watch_items=["NVDA data center revenue growth rate", "hyperscaler capex guidance",
                     "AI application revenue", "semiconductor supply chain constraints"],
        expert_confidence=0.70,
        falsification_conditions=[
            "If NVDA data center revenue growth decelerates below 30%",
            "If hyperscalers announce capex cuts",
        ],
        differentiator="Distinguishing real capex cycle from speculative bubble — revenue vs narrative"
    ),

    "AI-003": ExpertBaseline(
        case_id="AI-003",
        expert_archetype="Bridgewater",
        core_thesis="Market prices two contradictory narratives: AI boom (high P/E justified) AND sticky inflation (rates stay high). Both can't persist.",
        key_signals=["S&P 5100 extreme concentration", "Mag 7 = all of S&P return",
                     "CPI sticky at 3.5%", "rates elevated", "breadth narrowing"],
        causal_chain=[
            "AI hype -> Mag 7 P/E expansion -> Drives entire S&P returns",
            "-> Rest of market flat -> Extreme concentration",
            "-> Meanwhile: sticky inflation -> Rates stay high",
            "-> Contradiction: AI justifies high P/E, but high rates compress P/E",
            "-> One must give -> Either AI disappoints OR rates must fall",
        ],
        regime_classification="Extreme divergence / Narrative contradiction / Unsustainable equilibrium",
        watch_items=["market breadth (advance/decline)", "Mag 7 vs S&P 493 performance",
                     "CPI path", "Fed rate cut timeline"],
        expert_confidence=0.62,
        falsification_conditions=[
            "If CPI sustainably falls below 2.5% allowing rate cuts",
            "If Mag 7 earnings growth justifies valuations",
        ],
        differentiator="Identifying the narrative contradiction: two markets pricing incompatible futures"
    ),

    # ── Dollar / FX ──────────────────────────────────────────────────

    "FX-001": ExpertBaseline(
        case_id="FX-001",
        expert_archetype="Dalio",
        core_thesis="Dollar cycles last 6-8 years — DXY at 100+ means EM pain is self-reinforcing until Fed pauses",
        key_signals=["DXY 100+ (12-year high)", "EM FX freefall",
                     "Fed rate divergence", "EM current account stress"],
        causal_chain=[
            "Fed tightening + rest-of-world easing -> Dollar surge",
            "-> EM currencies depreciate -> Imported inflation",
            "-> EM central banks can't cut -> Growth slows more",
            "-> Self-reinforcing: weak EM growth -> more capital outflows -> weaker FX",
            "-> Cycle ends when Fed pauses -> Dollar peak",
        ],
        regime_classification="Dollar bull market / EM stress / Self-reinforcing cycle",
        watch_items=["Fed rate path", "EM current account balances",
                     "FX reserve depletion", "DXY momentum"],
        expert_confidence=0.72,
        falsification_conditions=[
            "If Fed explicitly pauses or cuts",
            "If synchronized global growth resumes",
        ],
        differentiator="Understanding dollar cycles as self-reinforcing EM stress mechanisms"
    ),

    # ── BOJ ──────────────────────────────────────────────────────────

    "BOJ-001": ExpertBaseline(
        case_id="BOJ-001",
        expert_archetype="Bridgewater",
        core_thesis="Most important CB signal of 2022 — last dovish central bank capitulating, yen carry Trade unwinds, global duration supply increases",
        key_signals=["BOJ YCC band widened", "yen surge 5%", "JGB 10Y to 0.50%",
                     "global bond selloff", "carry trade risk"],
        causal_chain=[
            "BOJ YCC change -> Signal: last dovish CB capitulating",
            "-> Yen strengthens -> Carry trade begins unwinding",
            "-> JGBs sell off -> Japanese investors repatriate",
            "-> Global duration supply increases -> Global yields rise",
            "-> Multi-year trend: BOJ normalization is structural",
        ],
        regime_classification="CB regime change / Carry trade unwind / Global duration repricing",
        watch_items=["BOJ further YCC adjustments", "Japanese investor flows",
                     "yen direction", "global term premium"],
        expert_confidence=0.70,
        falsification_conditions=[
            "If BOJ reverses YCC widening within 3 months",
            "If yen carry trade is unaffected by BOJ action",
        ],
        differentiator="Seeing the multi-year implications: Japan normalization is structural, not a one-off"
    ),

    "BOJ-002": ExpertBaseline(
        case_id="BOJ-002",
        expert_archetype="PTJ",
        core_thesis="Largest Nikkei move in history, but it's a positioning unwind, not macro crisis — credit markets stable, VIX spiked and collapsed",
        key_signals=["USDJPY 161->143", "Nikkei -12%", "VIX spike then collapse",
                     "credit spreads stable", "carry trade liquidation"],
        causal_chain=[
            "BOJ hikes + US recession fear -> Perfect storm for yen",
            "-> Levered carry trade positions forced to liquidate",
            "-> Nikkei crashes 12% in one day -> VIX spikes",
            "-> But: credit markets barely move -> Not a macro crisis",
            "-> Position unwind -> prices normalize -> Buying opportunity",
        ],
        regime_classification="Carry trade crash / Positioning event / Temporary dislocation",
        watch_items=["CFTC yen positioning", "Nikkei volume/closing",
                     "JPY vol surface", "carry trade P&L estimates"],
        expert_confidence=0.67,
        falsification_conditions=[
            "If credit spreads widen >100bp (systemic contagion)",
            "If Nikkei doesn't recover 50% of losses within 2 weeks",
        ],
        differentiator="Distinguishing positioning event from macro crisis — credit markets are the tell"
    ),

    # ── China ────────────────────────────────────────────────────────

    "CN-001": ExpertBaseline(
        case_id="CN-001",
        expert_archetype="Dalio",
        core_thesis="China devaluation is a watershed — first time China exports deflation instead of demand, fundamentally altering Fed's hiking path",
        key_signals=["PBOC devalues 2%", "Shanghai Composite -30% from peak",
                     "global disinflation", "Fed hiking path delayed"],
        causal_chain=[
            "China growth panic -> PBOC devalues yuan",
            "-> Weaker CNY -> Lower import prices globally",
            "-> Global disinflation wave -> Central banks can't normalize",
            "-> Fed delays hiking -> Dollar weakens -> EM stabilizes",
        ],
        regime_classification="China hard landing / Deflation export / CB normalization delayed",
        watch_items=["CNY fix", "capital outflow data",
                     "China FX reserves", "global PMIs"],
        expert_confidence=0.68,
        falsification_conditions=[
            "If PBOC reverses devaluation within 3 months",
            "If China growth data stabilizes above 7%",
        ],
        differentiator="Seeing China's role shift: from demand engine to deflation exporter"
    ),

    "CN-002": ExpertBaseline(
        case_id="CN-002",
        expert_archetype="Bridgewater",
        core_thesis="China stimulus 2024 is different — housing deflation is structural, demographics are a headwind, fiscal multipliers lower. Will stabilize, not reflate.",
        key_signals=["coordinated RRR/MLF/LPR cuts", "fiscal $280B+",
                     "housing inventory overhang", "demographic drag"],
        causal_chain=[
            "China growth below target -> Coordinated stimulus deployed",
            "-> But: housing is structural problem, not cyclical",
            "-> Demographics: working-age population declining",
            "-> Fiscal multipliers lower than property boom era",
            "-> Result: stabilization floor, not reflation ceiling",
        ],
        regime_classification="China stabilization / Structural deflation / Growth floor",
        watch_items=["property transaction volumes", "new home prices",
                     "credit impulse", "consumer confidence"],
        expert_confidence=0.63,
        falsification_conditions=[
            "If property transaction volumes recover to 2021 levels",
            "If China credit impulse turns strongly positive for 3+ months",
        ],
        differentiator="Distinguishing cyclical stimulus response from structural deflation — key bet: floor not ceiling"
    ),

    # ── Fed Policy ──────────────────────────────────────────────────

    "FED-001": ExpertBaseline(
        case_id="FED-001",
        expert_archetype="PTJ",
        core_thesis="Insurance cuts are the most bullish Fed action — economy is growing, P/E expands on lower rates, recession probability falls",
        key_signals=["Fed cuts at ATHs", "Powell 'mid-cycle adjustment'",
                     "low VIX (12)", "strong labor market", "moderate inflation"],
        causal_chain=[
            "Trade war uncertainty -> Fed delivers insurance cut",
            "-> Economy still growing -> Easing without recession",
            "-> Lower discount rates -> P/E expansion",
            "-> Lower recession probability -> Risk assets rally",
            "-> 'Don't fight the Fed' in its purest form",
        ],
        regime_classification="Insurance easing / Goldilocks / Don't fight the Fed",
        watch_items=["Fed dot plot", "trade war developments",
                     "ISM/PMI trajectory", "inflation expectations"],
        expert_confidence=0.75,
        falsification_conditions=[
            "If ISM falls below 47 (genuine recession signal)",
            "If trade war escalates to full tariff war",
        ],
        differentiator="Understanding insurance cuts as fundamentally different from recession cuts"
    ),

    "FED-002": ExpertBaseline(
        case_id="FED-002",
        expert_archetype="Mixed",
        core_thesis="50bp cuts at cycle start are historically ambiguous — labor market deterioration vs normalization is the defining macro bet of 2024",
        key_signals=["50bp cut (not 25bp)", "UE 4.2% (not alarming)",
                     "CPI falling to 2.5%", "Powell 'recalibration' language"],
        causal_chain=[
            "Fed delivers 50bp cut -> Markets price more cuts",
            "-> Historically: 50bp cuts precede recession (2001, 2007) OR extend cycle (1995, 1998, 2019)",
            "-> Key variable: labor market deterioration vs normalization?",
            "-> 4.2% UE suggests normalization -> Soft landing bet",
            "-> But uncertainty is high -> Confidence should reflect this",
        ],
        regime_classification="Soft landing bet / Historically ambiguous / High uncertainty",
        watch_items=["initial jobless claims", "UE rate trajectory",
                     "consumer spending", "corporate hiring intentions"],
        expert_confidence=0.60,
        falsification_conditions=[
            "If UE rate rises above 4.5% (labor cracks)",
            "If CPI re-accelerates above 3%",
        ],
        differentiator="Honest uncertainty — the data is genuinely ambiguous, confidence should reflect that"
    ),

    # ── Geopolitical ─────────────────────────────────────────────────

    "GEO-001": ExpertBaseline(
        case_id="GEO-001",
        expert_archetype="Bridgewater",
        core_thesis="Geopolitical shocks always overshoot initially — the permanent change is structural deglobalization and energy security investment",
        key_signals=["Russia invasion", "SWIFT sanctions", "commodity spike",
                     "energy security awakening", "deglobalization acceleration"],
        causal_chain=[
            "Russia invades -> Commodity supply shock -> Prices spike",
            "-> Initial panic pricing -> Always overshoots on geopolitical events",
            "-> Permanent change: deglobalization + energy security investment",
            "-> Trade is not the event but the structural shifts it accelerates",
        ],
        regime_classification="Geopolitical shock / Commodity spike / Deglobalization acceleration",
        watch_items=["ceasefire negotiations", "energy infrastructure investment",
                     "supply chain reconfiguration", "NATO unity"],
        expert_confidence=0.55,
        falsification_conditions=[
            "If ceasefire is reached within 2 months",
            "If energy flows normalize to pre-war levels",
        ],
        differentiator="Trading the structural shift (deglobalization) not the event (invasion)"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Comparison Engine
# ═══════════════════════════════════════════════════════════════════════════

class ExpertComparison:
    """Compare agent output against expert baselines."""

    @staticmethod
    def compare(case_id: str, agent_output: dict) -> dict:
        """Compare agent reasoning vs expert baseline for a case.

        Returns:
            dict with alignment scores and gap analysis
        """
        baseline = EXPERT_BASELINES.get(case_id)
        if not baseline:
            return {"aligned": False, "reason": "No expert baseline for this case"}

        scores = {}

        # 1. Key signal alignment
        agent_signals_mentioned = ExpertComparison._extract_signal_mentions(
            agent_output, baseline.key_signals
        )
        scores["signal_alignment"] = round(agent_signals_mentioned / max(len(baseline.key_signals), 1), 3)

        # 2. Regime classification alignment
        agent_stance = agent_output.get("macro_stance", "").lower()
        scores["regime_alignment"] = 0.5  # neutral default
        if baseline.regime_classification.lower():
            regime_words = set(baseline.regime_classification.lower().replace("/", " ").split())
            all_agent_text = str(agent_output).lower()
            matched = sum(1 for w in regime_words if w in all_agent_text)
            scores["regime_alignment"] = round(min(matched / max(len(regime_words), 1), 1.0), 3)

        # 3. Falsification alignment
        falsification_alignment = ExpertComparison._compare_falsification(
            agent_output, baseline.falsification_conditions
        )
        scores["falsification_alignment"] = round(falsification_alignment, 3)

        # 4. Confidence calibration
        agent_judgments = agent_output.get("judgments", [])
        agent_confs = [j.get("confidence", 0) for j in agent_judgments]
        avg_agent_conf = sum(agent_confs) / len(agent_confs) if agent_confs else 0.5
        conf_diff = abs(avg_agent_conf - baseline.expert_confidence)
        scores["confidence_calibration"] = round(max(0, 1.0 - conf_diff * 2), 3)

        # 5. Core thesis alignment
        agent_text = str(agent_output.get("judgment_convictions", [])).lower()
        agent_text += " " + str(agent_output.get("narrative_titles", [])).lower()
        core_keywords = set(
            w for w in re.findall(r'\b[a-z]{4,}\b', baseline.core_thesis.lower())
            if w not in {"this", "that", "with", "from", "have", "will", "would", "could",
                         "should", "been", "being", "more", "most", "such", "into", "over", "after"}
        )
        matched_keywords = sum(1 for kw in core_keywords if kw in agent_text)
        scores["thesis_alignment"] = round(min(matched_keywords / max(len(core_keywords), 1) * 1.5, 1.0), 3)

        # Overall alignment
        weights = {
            "signal_alignment": 0.25,
            "regime_alignment": 0.20,
            "falsification_alignment": 0.20,
            "confidence_calibration": 0.15,
            "thesis_alignment": 0.20,
        }
        overall = sum(scores[k] * weights[k] for k in weights if k in scores) / sum(
            weights[k] for k in weights if k in scores) if scores else 0

        return {
            "case_id": case_id,
            "expert_archetype": baseline.expert_archetype,
            "overall_alignment": round(overall, 3),
            "dimension_scores": scores,
            "key_gaps": ExpertComparison._identify_gaps(scores),
            "differentiator_check": ExpertComparison._check_differentiator(
                agent_output, baseline.differentiator
            ),
        }

    @staticmethod
    def _extract_signal_mentions(agent_output: dict, key_signals: list[str]) -> int:
        """Count how many expert key signals appear in agent output."""
        all_text = str(agent_output).lower()
        count = 0
        for signal in key_signals:
            sig_lower = signal.lower()
            words = sig_lower.split()
            # Check if most words from the signal appear
            matched = sum(1 for w in words if w in all_text)
            if matched >= len(words) * 0.5:
                count += 1
        return count

    @staticmethod
    def _compare_falsification(agent_output: dict, expert_conditions: list[str]) -> float:
        """Compare agent falsification conditions with expert's."""
        judgments = agent_output.get("judgments", [])
        if not judgments or not expert_conditions:
            return 0.3

        all_agent_falsification = []
        for j in judgments:
            all_agent_falsification.extend(j.get("falsification", []))

        if not all_agent_falsification:
            return 0.0

        # Simple overlap analysis
        agent_text = " ".join(all_agent_falsification).lower()
        expert_text = " ".join(expert_conditions).lower()

        # Count shared key themes (inflation, growth, policy, etc.)
        themes = ["inflation", "cpi", "growth", "gdp", "rate", "fed", "unemployment",
                  "spread", "yield", "dollar", "oil", "credit", "bank", "recession"]
        agent_themes = {t for t in themes if t in agent_text}
        expert_themes = {t for t in themes if t in expert_text}
        overlap = len(agent_themes & expert_themes)

        if overlap >= 3:
            return 0.7
        elif overlap >= 1:
            return 0.4
        else:
            return 0.2

    @staticmethod
    def _identify_gaps(scores: dict[str, float]) -> list[str]:
        """Identify dimensions where agent significantly underperforms."""
        gaps = []
        thresholds = {"signal_alignment": 0.4, "regime_alignment": 0.4,
                      "falsification_alignment": 0.4, "confidence_calibration": 0.3,
                      "thesis_alignment": 0.4}
        for dim, thresh in thresholds.items():
            if scores.get(dim, 0) < thresh:
                gaps.append(f"Gap in {dim.replace('_', ' ')} ({scores[dim]:.0%})")
        return gaps if gaps else ["No significant gaps"]

    @staticmethod
    def _check_differentiator(agent_output: dict, differentiator: str) -> float:
        """Check if agent captures the expert's key differentiator insight."""
        all_text = str(agent_output).lower()
        diff_keywords = set(
            w for w in re.findall(r'\b[a-z]{4,}\b', differentiator.lower())
            if w not in {"this", "that", "with", "from", "have", "will", "the", "and", "not"}
        )
        if not diff_keywords:
            return 0.5
        matched = sum(1 for kw in diff_keywords if kw in all_text)
        return round(matched / len(diff_keywords), 2)
