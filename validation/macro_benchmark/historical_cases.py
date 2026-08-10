# =============================================================================
# V3.3 Macro Intelligence Validation - Historical Case Library
# 34 real-world macro events across all major regimes
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class HistoricalCase:
    case_id: str
    period: str
    title: str
    macro_regime: dict
    input_data: dict
    dominant_narrative: str
    alternative_narratives: list[str] = field(default_factory=list)
    market_outcome: dict = field(default_factory=dict)
    expert_reasoning: str = ""
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"


def _build_cases() -> list[HistoricalCase]:
    """Construct the 34-case library."""

    C = HistoricalCase  # alias
    cases = []

    # ========== 2008 GFC (3 cases) ==========

    cases.append(C(
        case_id="GFC-001", period="2008-09",
        title="Lehman Brothers Collapse - Global Financial System Freezes",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 1200, "vix": 80, "dxy": 80, "us10y": 3.70, "us2y": 1.80,
                    "hyg_spread": 1800, "ig_spread": 350, "libor_ois": 364, "gold": 870,
                    "oil": 100, "unemployment": 6.1, "gdp_qoq": -0.5, "fed_funds_rate": 2.0,
                    "event": "Lehman bankruptcy, AIG bailout, TARP proposed"},
        dominant_narrative="Systemic banking collapse triggers global credit freeze and forced government bailouts",
        alternative_narratives=["Contained crisis - policy response will stabilize markets quickly",
                                "Deflationary depression - worst since 1930s, years of deleveraging ahead"],
        market_outcome={"direction": "bearish_crash_then_recovery", "spx_6m": 683, "spx_12m": 950,
                        "description": "S&P bottomed at 666 in March 2009 (-57%). TARP and QE stabilized."},
        expert_reasoning="Ray Dalio's Beautiful Deleveraging: classic debt crisis requiring (1) debt restructuring, "
                         "(2) austerity, (3) wealth transfer, (4) central bank printing. Coordinated policy response "
                         "would prevent depression but recovery would be slow and uneven.",
        tags=["crisis", "credit", "systemic"], difficulty="hard"
    ))

    cases.append(C(
        case_id="GFC-002", period="2008-12",
        title="Zero Rates and QE1 Begin - Policy Bazooka Deployed",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 900, "vix": 55, "dxy": 82, "us10y": 2.20, "us2y": 0.65,
                    "hyg_spread": 1200, "ig_spread": 250, "gold": 820, "oil": 40,
                    "unemployment": 7.4, "gdp_qoq": -8.5, "fed_funds_rate": 0.25,
                    "event": "Fed cuts to zero, QE1 launched, TARP deployed"},
        dominant_narrative="Policy bazooka - Fed cuts to zero and launches QE, but recession deepening",
        alternative_narratives=["QE will reinflate assets, risk-on rally ahead",
                                "Liquidity trap - zero rates won't work, Japan-style lost decade"],
        market_outcome={"direction": "bottoming", "spx_6m": 919, "spx_12m": 1115,
                        "description": "S&P bottomed March 2009 then rallied 65% in 9 months. QE worked."},
        expert_reasoning="Bridgewater: when ZIRP+QE deployed, asset prices reflate before real economy. "
                         "Transmission: lower discount rates -> higher P/E -> equity rally even as earnings fall.",
        tags=["crisis", "qe", "monetary_policy"], difficulty="medium"
    ))

    cases.append(C(
        case_id="GFC-003", period="2009-03",
        title="S&P 666 - The Ultimate Bottom, Maximum Pessimism",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 666, "vix": 50, "dxy": 88, "us10y": 2.90, "us2y": 0.90,
                    "hyg_spread": 1600, "ig_spread": 300, "gold": 920, "oil": 42,
                    "unemployment": 8.7, "gdp_qoq": -5.4, "fed_funds_rate": 0.25,
                    "event": "Citi and BofA near nationalization fears, extreme pessimism"},
        dominant_narrative="Capitulation - maximum pessimism, but policy response massive and coordinated",
        alternative_narratives=["Nationalization risk - banks insolvent, more failures coming",
                                "V-shaped recovery - unprecedented stimulus will spark rapid rebound"],
        market_outcome={"direction": "major_bottom", "spx_6m": 1050, "spx_12m": 1140,
                        "description": "Historic bottom. S&P +65% to year-end. Greatest buying opportunity in a generation."},
        expert_reasoning="Paul Tudor Jones: when VIX>40 and policy is 'whatever it takes,' asymmetry favors long. "
                         "Key tell: credit markets began functioning after TARP and CPFF.",
        tags=["crisis", "bottom", "capitulation"], difficulty="hard"
    ))

    # ========== 2011-2012 Eurozone Crisis (2 cases) ==========

    cases.append(C(
        case_id="EZ-001", period="2011-08",
        title="US Debt Downgrade + Eurozone Crisis - Flight-to-Quality Paradox",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "decelerating", "inflation": "stable"},
        input_data={"spx": 1120, "vix": 48, "dxy": 74, "us10y": 2.10, "us2y": 0.20,
                    "hyg_spread": 700, "gold": 1820, "oil": 86, "unemployment": 9.0,
                    "gdp_qoq": 1.3, "fed_funds_rate": 0.25,
                    "event": "S&P downgrades US from AAA, Eurozone sovereign stress intensifies"},
        dominant_narrative="Sovereign credit crisis - US downgrade + Eurozone contagion, safe havens paradoxical",
        alternative_narratives=["Treasuries still safe haven despite downgrade, risk assets oversold",
                                "Crisis of confidence in fiat system, gold the only safe asset"],
        market_outcome={"direction": "bearish_equity_treasury_rally", "spx_6m": 1360, "spx_12m": 1400,
                        "description": "Treasuries rallied despite downgrade. Gold hit $1900. S&P recovered."},
        expert_reasoning="The paradox of the risk-free asset: when the safest asset loses its AAA, everything else "
                         "becomes even riskier by comparison. Reflexivity pattern: fear -> treasuries rally -> lower yields.",
        tags=["sovereign", "credit", "safe_haven"], difficulty="hard"
    ))

    cases.append(C(
        case_id="EZ-002", period="2012-07",
        title="Draghi's 'Whatever It Takes' - ECB Saves the Euro",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "contractionary",
                      "volatility": "high", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 1360, "vix": 20, "dxy": 83, "us10y": 1.50, "us2y": 0.25,
                    "hyg_spread": 500, "italy_10y": 6.5, "spain_10y": 7.2, "gold": 1600,
                    "oil": 88, "unemployment": 8.2, "gdp_qoq": 1.7, "fed_funds_rate": 0.25,
                    "event": "Draghi London speech: 'Within our mandate, ECB is ready to do whatever it takes'"},
        dominant_narrative="Central bank put - Draghi draws line in sand, OMT ends existential eurozone crisis",
        alternative_narratives=["Moral hazard - bailout encourages more fiscal irresponsibility",
                                "Eurozone breakup still inevitable long-term despite ECB backstop"],
        market_outcome={"direction": "bullish", "spx_6m": 1460, "spx_12m": 1650,
                        "description": "S&P rallied 28% in 12 months. Italian/Spanish yields collapsed. Zero OMT bonds bought."},
        expert_reasoning="Textbook example of central bank communication as policy tool. Zero bonds bought under OMT, "
                         "yet credible commitment broke doom loop. Credibility > actual intervention size.",
        tags=["central_bank", "eurozone", "communication"], difficulty="medium"
    ))

    # ========== 2013 Taper Tantrum ==========

    cases.append(C(
        case_id="TT-001", period="2013-05",
        title="Taper Tantrum - Bernanke Hints QE Reduction, Markets Panic",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 1650, "vix": 13, "dxy": 84, "us10y": 1.60, "us2y": 0.25,
                    "hyg_spread": 400, "gold": 1380, "oil": 95, "unemployment": 7.5,
                    "gdp_qoq": 1.3, "fed_funds_rate": 0.25,
                    "event": "Bernanke testifies QE tapering may begin in coming meetings"},
        dominant_narrative="Liquidity withdrawal fears - market addicted to QE, taper means tighter conditions",
        alternative_narratives=["Taper is not tightening - Fed still adding stimulus, just less",
                                "EM crisis - rising US rates will trigger capital flight from emerging markets"],
        market_outcome={"direction": "em_crisis_treasury_selloff", "spx_6m": 1770, "us10y_6m": 2.70,
                        "description": "10Y surged from 1.6% to 3.0%. EM currencies crashed. 'Fragile Five' identified."},
        expert_reasoning="Taper tantrum revealed QE addiction. EM vulnerability: countries with current account deficits "
                         "and high foreign ownership of local bonds most exposed. Established Fragile Five framework.",
        tags=["taper", "fed", "em"], difficulty="medium"
    ))

    # ========== 2014-2016 Oil Collapse (3 cases) ==========

    cases.append(C(
        case_id="OIL-001", period="2014-09",
        title="Oil Collapse - WTI Falls from $107 Toward $40, Dollar Surges",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "falling"},
        input_data={"spx": 1980, "vix": 14, "dxy": 84, "us10y": 2.50, "us2y": 0.55,
                    "hyg_spread": 400, "gold": 1240, "oil": 93, "unemployment": 5.9,
                    "gdp_qoq": 4.6, "fed_funds_rate": 0.25,
                    "event": "US shale boom + Saudi market share war, OPEC refuses to cut"},
        dominant_narrative="Supply shock - US shale boom and Saudi strategy = oil entering structural bear market",
        alternative_narratives=["Demand-driven - global growth slowing, oil decline signals recession risk",
                                "Temporary - OPEC will cut production, oil will stabilize above $80"],
        market_outcome={"direction": "disinflation_bullish_consumers", "spx_6m": 2070, "oil_6m": 48, "dxy_6m": 97,
                        "description": "Oil crashed to $26 by Feb 2016. DXY surged to 100. HY energy stress. Consumer benefited."},
        expert_reasoning="Bridgewater: oil crash is disinflationary not recessionary when supply-driven. US consumer "
                         "(70% GDP) benefits from lower gas. Dollar surge crushes EM - this is the real transmission.",
        tags=["oil", "supply", "dollar"], difficulty="medium"
    ))

    cases.append(C(
        case_id="OIL-002", period="2016-01",
        title="Oil Hits $26 - Deflation Panic, HY Energy Stress Peaks",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 1880, "vix": 28, "dxy": 99, "us10y": 1.70, "us2y": 0.85,
                    "hyg_spread": 850, "ig_spread": 190, "gold": 1100, "oil": 26,
                    "unemployment": 4.9, "gdp_qoq": 0.6, "fed_funds_rate": 0.50,
                    "event": "WTI touches $26, HY energy defaults surge, CNH devaluation fears"},
        dominant_narrative="Deflation scare - oil at $26 threatens inflation expectations, HY energy defaults rising",
        alternative_narratives=["Recession warning - oil decline signaling global demand collapse",
                                "Overblown - oil supply driven, economy fine, fear is opportunity"],
        market_outcome={"direction": "panic_buying_opportunity", "spx_6m": 2100, "oil_6m": 44,
                        "description": "S&P fell 12% to 1820 then rallied to ATHs. Fed cut only once in 2016."},
        expert_reasoning="Dalio: energy is 3% of GDP; HY energy is 15% of HY; default loss is manageable. "
                         "Sector problem being priced as systemic risk - classic opportunity.",
        tags=["oil", "credit", "deflation"], difficulty="hard"
    ))

    cases.append(C(
        case_id="OIL-003", period="2020-04",
        title="Negative Oil - WTI Futures Go Negative for First Time Ever",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "extreme", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 2800, "vix": 42, "dxy": 100, "us10y": 0.60, "us2y": 0.20,
                    "hyg_spread": 800, "gold": 1700, "oil": -37, "unemployment": 14.8,
                    "gdp_qoq": -5.0, "fed_funds_rate": 0.25,
                    "event": "WTI May contract settles at -$37.63, Cushing storage full"},
        dominant_narrative="Demand destruction extreme - COVID lockdowns crush demand, storage fills, negative prices",
        alternative_narratives=["Permanent energy impairment - peak oil demand has arrived",
                                "Temporary distortion - contract expiry technical, physical market will normalize"],
        market_outcome={"direction": "temporary_dislocation", "spx_6m": 3400, "oil_6m": 40,
                        "description": "Oil recovered to $40 within months. Negative prices were contract technicality."},
        expert_reasoning="Paul Tudor Jones: extreme anomalies signal broken market - but maximum opportunity. "
                         "When commodity trades negative, it's forced liquidation, not fair value.",
        tags=["oil", "covid", "extreme"], difficulty="hard"
    ))

    # ========== 2020 COVID Crisis (2 cases) ==========

    cases.append(C(
        case_id="COVID-001", period="2020-03",
        title="COVID Crash - Fastest Bear Market in History (23 trading days)",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "extreme", "growth": "contracting", "inflation": "falling"},
        input_data={"spx": 2400, "vix": 82, "dxy": 103, "us10y": 0.54, "us2y": 0.25,
                    "hyg_spread": 1100, "ig_spread": 300, "gold": 1500, "oil": 20,
                    "unemployment": 14.8, "gdp_qoq": -5.0, "fed_funds_rate": 0.25,
                    "event": "WHO declares pandemic, US national emergency, Fed cuts 150bp in 13 days"},
        dominant_narrative="Pandemic panic - global economy shutting down, historic policy response unfolding",
        alternative_narratives=["Depression risk - economic damage permanent, recovery will take years",
                                "V-shaped recovery - unprecedented stimulus + vaccine = rapid normalization"],
        market_outcome={"direction": "bearish_crash_then_v_recovery", "spx_6m": 3400, "spx_12m": 3950,
                        "description": "S&P fell 34% in 23 days then up 68% for 2020. V-shaped recovery was real."},
        expert_reasoning="Bridgewater: exogenous shock, not endogenous cycle. $5T+ fiscal + $4T+ Fed balance sheet "
                         "largest in history. When fiscal/monetary go all-in, response is mechanical: rates->0 + "
                         "fiscal transfers->massive savings -> equities re-rate and retail flows in.",
        tags=["covid", "crash", "stimulus"], difficulty="hard"
    ))

    cases.append(C(
        case_id="COVID-002", period="2020-08",
        title="Post-COVID Reflation - S&P at ATHs, Dollar Weakens, Gold $2070",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "moderate", "growth": "accelerating", "inflation": "rising"},
        input_data={"spx": 3400, "vix": 22, "dxy": 93, "us10y": 0.65, "us2y": 0.14,
                    "hyg_spread": 450, "gold": 1970, "oil": 42, "unemployment": 8.4,
                    "gdp_qoq": 33.1, "fed_funds_rate": 0.25, "m2_yoy": 25.0,
                    "event": "Gold $2070 ATH, DXY breaks below 93, M2 up 25% YoY"},
        dominant_narrative="Reflation trade - massive stimulus + reopening = growth surge, dollar bear market",
        alternative_narratives=["Sugar high - stimulus-driven growth unsustainable, fiscal cliff coming",
                                "Inflation coming - M2 up 25%, monetary overhang will cause CPI surge"],
        market_outcome={"direction": "bullish_with_inflation_risks", "spx_6m": 3900, "gold_6m": 1850,
                        "description": "Reflation worked. Gold $2070 peak. CPI did surge to 7% by late 2021."},
        expert_reasoning="Dalio MP3 framework: rates at zero + fiscal coordinates with monetary = direct monetization. "
                         "Inflationary for assets first, then goods. M2 at 25% leads CPI by 12-18 months historically.",
        tags=["reflation", "covid", "inflation"], difficulty="medium"
    ))

    # ========== 2022 Inflation & Hiking (4 cases) ==========

    cases.append(C(
        case_id="INF-001", period="2022-01",
        title="Inflation Surges Past 7% - Fed Still at Zero, Behind the Curve",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "rising"},
        input_data={"spx": 4500, "vix": 25, "dxy": 96, "us10y": 1.75, "us2y": 1.00,
                    "hyg_spread": 350, "gold": 1800, "oil": 86, "unemployment": 4.0,
                    "gdp_qoq": 6.9, "fed_funds_rate": 0.25, "cpi_yoy": 7.5,
                    "event": "CPI 7.5% YoY, highest since 1982. Fed still at 0-0.25%."},
        dominant_narrative="Fed behind the curve - inflation at 40-year high, aggressive hikes inevitable",
        alternative_narratives=["Transitory - supply chain normalization will bring inflation down naturally",
                                "Stagflation - growth slowing + inflation surging = worst of both worlds"],
        market_outcome={"direction": "bearish", "spx_6m": 3800, "us10y_6m": 3.00,
                        "description": "S&P fell 23% by Oct 2022. Fed hiked 425bp total. Worst 60/40 year since 1937."},
        expert_reasoning="Paul Tudor Jones called this: most dangerous environment since 1980s. 7% inflation + negative "
                         "real rates = Fed MUST hike aggressively. P/E compression dominates earnings growth.",
        tags=["inflation", "fed", "rate_hikes"], difficulty="medium"
    ))

    cases.append(C(
        case_id="INF-002", period="2022-06",
        title="CPI Peaks at 9.1% - 75bp Super-Sized Hike Era Begins",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "decelerating", "inflation": "rising"},
        input_data={"spx": 3800, "vix": 32, "dxy": 105, "us10y": 3.50, "us2y": 3.10,
                    "hyg_spread": 550, "gold": 1820, "oil": 108, "unemployment": 3.6,
                    "gdp_qoq": -1.6, "fed_funds_rate": 1.75, "cpi_yoy": 9.1,
                    "event": "CPI 9.1% YoY (40-year high). Fed delivers first 75bp hike since 1994."},
        dominant_narrative="Super-sized hiking - inflation at 9.1%, Fed delivers 75bp, more large hikes coming",
        alternative_narratives=["Peak inflation - CPI likely peaked, Fed can slow pace by September",
                                "Hard landing inevitable - this pace of hiking guarantees recession"],
        market_outcome={"direction": "volatile_bear", "spx_6m": 3830, "spx_12m": 4400,
                        "description": "CPI was peak. S&P sideways then rallied on disinflation + AI. Hard call in real time."},
        expert_reasoning="The inflation peak call was correct but markets didn't trust it. Psychology of 'peak' "
                         "requires 2-3 confirming prints. Front-running takes conviction.",
        tags=["inflation", "fed", "peak"], difficulty="hard"
    ))

    cases.append(C(
        case_id="INF-003", period="2022-10",
        title="UK Gilt Crisis - LDI Pension Margin Call, BOE Emergency Intervention",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "contractionary",
                      "volatility": "extreme", "growth": "decelerating", "inflation": "rising"},
        input_data={"spx": 3600, "vix": 33, "dxy": 114, "us10y": 4.20, "us2y": 4.40,
                    "hyg_spread": 550, "uk_30y": 5.0, "gold": 1650, "oil": 85,
                    "unemployment": 3.7, "fed_funds_rate": 4.00, "cable": 1.07,
                    "event": "UK mini-budget triggers gilt crash, LDI margin calls, BOE forced to buy bonds"},
        dominant_narrative="Sovereign stress - UK fiscal credibility crisis, pension system near implosion",
        alternative_narratives=["Contained UK event - BOE backstop limits contagion to global markets",
                                "Systemic risk - LDI is $2T market, global pension crisis brewing"],
        market_outcome={"direction": "temporary_uk_crisis", "spx_3m": 3830, "uk_30y_3m": 3.50,
                        "description": "BOE intervention stabilized gilts. Truss resigned. Crisis UK-specific."},
        expert_reasoning="Bridgewater LDI: when yields rise too fast, leveraged duration faces margin calls -> "
                         "forced selling -> yields rise further -> more margin calls. BOE broke the doom loop. "
                         "Lesson: hidden leverage in 'safe' assets.",
        tags=["sovereign", "uk", "leverage"], difficulty="hard"
    ))

    cases.append(C(
        case_id="INF-004", period="2023-03",
        title="SVB Collapse - Regional Banking Crisis, Fed Emergency Lending",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 3900, "vix": 30, "dxy": 104, "us10y": 3.50, "us2y": 4.10,
                    "hyg_spread": 480, "gold": 1960, "oil": 68, "unemployment": 3.6,
                    "fed_funds_rate": 4.75, "cpi_yoy": 5.0,
                    "event": "SVB fails ($209B), Signature Bank closed, First Republic rescued"},
        dominant_narrative="Banking stress - rapid rate hikes breaking something, Fed may need to pause",
        alternative_narratives=["Contained - large banks well capitalized, SVB is idiosyncratic",
                                "Credit crunch - regional bank pullback will cause lending contraction"],
        market_outcome={"direction": "fed_pivot_banking", "spx_6m": 4450,
                        "description": "Fed created BTFP. Markets bet rate cuts. Tech rallied on lower yields."},
        expert_reasoning="Classic 'something breaks' after fastest hiking in 40 years. SVB actually helped equities: "
                         "(1) rates fell on flight to safety, (2) Fed paused via BTFP, (3) tech benefited from lower "
                         "discount rates. Counterintuitive bullish effect.",
        tags=["banking", "fed", "crisis"], difficulty="medium"
    ))

    # ========== 2023-2024 AI Boom (3 cases) ==========

    cases.append(C(
        case_id="AI-001", period="2023-05",
        title="NVIDIA Blowout Earnings - AI Capex Cycle Begins",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "falling"},
        input_data={"spx": 4150, "vix": 16, "dxy": 104, "us10y": 3.80, "us2y": 4.50,
                    "hyg_spread": 420, "gold": 1960, "oil": 72, "unemployment": 3.4,
                    "gdp_qoq": 2.0, "fed_funds_rate": 5.25, "nvda_fwd_rev": 11.0,
                    "event": "NVDA guides Q2 revenue $11B vs consensus $7B - AI demand exploding"},
        dominant_narrative="AI capex boom - NVIDIA guidance transforms AI from hype to economic reality",
        alternative_narratives=["AI bubble - valuations disconnected from adoption timelines",
                                "Productivity revolution - AI will transform every industry like internet"],
        market_outcome={"direction": "bullish_ai_led", "spx_6m": 4200, "nvda_6m": 500,
                        "description": "NVDA became $1T company. Mag 7 drove entire S&P return. AI capex sustained."},
        expert_reasoning="The AI capex cycle is genuine infrastructure buildout. NVDA at $11B/quarter data center "
                         "revenue means hyperscalers spending $200B+ annually. Capex-led growth cycle.",
        tags=["ai", "tech", "growth"], difficulty="medium"
    ))

    cases.append(C(
        case_id="AI-002", period="2023-10",
        title="Bond Tantrum - 10Y Hits 5%, Term Premium Returns After 15 Years",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "accelerating", "inflation": "falling"},
        input_data={"spx": 4200, "vix": 21, "dxy": 107, "us10y": 5.00, "us2y": 5.10,
                    "hyg_spread": 450, "gold": 1850, "oil": 85, "unemployment": 3.8,
                    "gdp_qoq": 4.9, "fed_funds_rate": 5.50,
                    "event": "10Y touches 5.0% first time since 2007. Term premium returns."},
        dominant_narrative="Higher for longer - strong growth + large deficits = rates staying elevated",
        alternative_narratives=["Treasury oversupply - fiscal deficit is driving yields, not growth",
                                "Peak yields - 5% will attract buyers, rates will decline on recession fears"],
        market_outcome={"direction": "bond_selloff_equity_correction", "spx_3m": 4100, "us10y_6m": 4.20,
                        "description": "10Y fell from 5% to 3.8% in 2 months on dovish pivot. S&P corrected then rallied."},
        expert_reasoning="Treasury term premium is the most important price in global finance. When it returns after "
                         "15 years near zero, 'QE suppression' era is over. Fiscal dominance means structurally higher "
                         "real rates. This is structural, not cyclical.",
        tags=["bonds", "rates", "fiscal"], difficulty="hard"
    ))

    cases.append(C(
        case_id="AI-003", period="2024-04",
        title="Magnificent 7 Divergence - AI Hype vs Interest Rate Reality",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "expansionary",
                      "volatility": "moderate", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 5100, "vix": 15, "dxy": 106, "us10y": 4.60, "us2y": 4.80,
                    "hyg_spread": 350, "gold": 2350, "oil": 85, "unemployment": 3.9,
                    "fed_funds_rate": 5.50, "cpi_yoy": 3.5,
                    "event": "Q1 GDP misses, CPI sticky at 3.5%, Mag 7 earnings season begins"},
        dominant_narrative="Stagflation-lite - growth slowing + inflation sticky + rates high = difficult macro backdrop",
        alternative_narratives=["Goldilocks extreme - soft landing with AI productivity boost",
                                "Recession looming - consumer weakening, rate cuts necessary soon"],
        market_outcome={"direction": "bullish_ai_divergence", "spx_3m": 5450,
                        "description": "AI names continued rallying. Rest of market flat. Divergence extreme."},
        expert_reasoning="Market prices two contradictory narratives: (1) AI productivity boom justifies high P/E, "
                         "(2) sticky inflation means rates stay high. Both can't be right indefinitely. Market "
                         "concentration in 7 stocks is historically dangerous and unsustainable.",
        tags=["ai", "divergence", "stagflation"], difficulty="hard"
    ))

    # ========== Dollar / FX (2 cases) ==========

    cases.append(C(
        case_id="FX-001", period="2015-03",
        title="Dollar Bull Market - DXY Breaks 100, EM FX Crisis Deepens",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 2080, "vix": 15, "dxy": 100, "us10y": 2.00, "us2y": 0.60,
                    "hyg_spread": 440, "gold": 1150, "oil": 47, "unemployment": 5.5,
                    "gdp_qoq": 0.6, "fed_funds_rate": 0.25,
                    "event": "DXY breaks 100 first time since 2003. EM currencies in freefall."},
        dominant_narrative="King dollar - Fed divergence drives USD to 12-year highs, EM under severe pressure",
        alternative_narratives=["Dollar overshoot - rate differentials don't justify DXY at 100+",
                                "EM opportunity - dollar peak means EM assets are historically cheap"],
        market_outcome={"direction": "dollar_strong_then_peak", "dxy_12m": 94,
                        "description": "DXY peaked at 103 in 2016 then entered 2-year decline to 88."},
        expert_reasoning="Dollar cycles last 6-8 years. Fed hiking while rest eases = dollar surge. EM pain is "
                         "transmission: weaker FX -> imported inflation -> CBs can't cut -> growth slows. "
                         "Self-reinforcing until Fed pauses.",
        tags=["dollar", "em", "fx"], difficulty="medium"
    ))

    cases.append(C(
        case_id="FX-002", period="2017-01",
        title="Trump Inauguration - 'Strong Dollar is Killing Us,' Dollar Weakens",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "expansionary",
                      "volatility": "low", "growth": "accelerating", "inflation": "rising"},
        input_data={"spx": 2270, "vix": 12, "dxy": 103, "us10y": 2.45, "us2y": 1.20,
                    "hyg_spread": 370, "gold": 1200, "oil": 53, "unemployment": 4.8,
                    "gdp_qoq": 1.8, "fed_funds_rate": 0.75,
                    "event": "Trump: 'Dollar too strong.' Mnuchin: 'Weak dollar good for trade.'"},
        dominant_narrative="Policy-driven dollar weakness - US administration wants weaker dollar for trade",
        alternative_narratives=["Fed still hiking - rate differentials will support dollar despite rhetoric",
                                "Synchronized global growth - dollar declines as capital flows to EM"],
        market_outcome={"direction": "dollar_weak_global_boom", "dxy_12m": 91, "spx_12m": 2680,
                        "description": "DXY fell 12% in 2017. EM rallied. Global synchronized growth. Best year for risk."},
        expert_reasoning="When Treasury wants weaker dollar, don't fight it. Combined with synchronized global growth "
                         "first time since 2010, ideal conditions for dollar bear + EM rally. FX channel most powerful "
                         "macro transmission mechanism.",
        tags=["dollar", "trump", "global_growth"], difficulty="easy"
    ))

    # ========== EM Crises (2 cases) ==========

    cases.append(C(
        case_id="EM-001", period="2018-08",
        title="Turkey Lira Crisis - Erdogan vs Markets, Contagion Fears",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 2850, "vix": 15, "dxy": 96, "us10y": 2.85, "us2y": 2.60,
                    "hyg_spread": 360, "gold": 1190, "oil": 67, "unemployment": 3.9,
                    "fed_funds_rate": 2.00, "usdtry": 7.0, "turkey_inflation": 17.9,
                    "event": "US sanctions Turkey. Lira collapses 40% in one month."},
        dominant_narrative="EM crisis - strong dollar + idiosyncratic risks = EM contagion spreading",
        alternative_narratives=["Contained - Turkey is unique case of policy error, not systemic",
                                "Contagion spreading - Argentina, South Africa, India all under pressure"],
        market_outcome={"direction": "em_contagion_contained", "spx_3m": 2700, "usdtry_3m": 5.5,
                        "description": "Lira stabilized after Turkey hiked to 24%. EM contagion was limited."},
        expert_reasoning="EM crises pattern: (1) strong dollar, (2) idiosyncratic trigger, (3) contagion via "
                         "FX correlation. Turkey unique (Erdogan unorthodox policy) but strong dollar common factor. "
                         "When DXY peaks, EM stress peaks.",
        tags=["em", "turkey", "contagion"], difficulty="hard"
    ))

    cases.append(C(
        case_id="EM-002", period="2024-06",
        title="India Elections Surprise - Modi Loses Majority, Markets Crash",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "accelerating", "inflation": "stable"},
        input_data={"spx": 5300, "vix": 13, "dxy": 104, "us10y": 4.30, "us2y": 4.70,
                    "gold": 2350, "oil": 77, "india_nifty": 23000, "india_10y": 7.0,
                    "event": "Modi BJP loses outright majority, coalition government needed"},
        dominant_narrative="Political risk - Modi reform agenda jeopardized, coalition = fiscal populism risk",
        alternative_narratives=["Overreaction - Modi still PM, coalition partners fiscally conservative",
                                "EM risk premium rising - India joins EM political instability list"],
        market_outcome={"direction": "sharp_correction_then_recovery", "india_nifty_3m": 25000,
                        "description": "Nifty fell 6% election day then recovered to new highs. Reform intact."},
        expert_reasoning="Political shocks in EM: initial panic prices worst-case, then markets realize institutions "
                         "constrain outcomes. India macro story (demographics, digital, manufacturing) is multi-decade "
                         "and doesn't change overnight. Buying opportunity.",
        tags=["em", "india", "political"], difficulty="medium"
    ))

    # ========== Geopolitical (2 cases) ==========

    cases.append(C(
        case_id="GEO-001", period="2022-02",
        title="Russia Invades Ukraine - Commodity Shock, Deglobalization Accelerates",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "expansionary",
                      "volatility": "extreme", "growth": "stable", "inflation": "rising"},
        input_data={"spx": 4300, "vix": 31, "dxy": 97, "us10y": 1.95, "us2y": 1.50,
                    "hyg_spread": 430, "gold": 1910, "oil": 92, "natgas_eu": 90,
                    "unemployment": 3.8, "fed_funds_rate": 0.25,
                    "event": "Russia invades Ukraine Feb 24. SWIFT sanctions. Commodity prices explode."},
        dominant_narrative="War inflation - energy/food prices surge, deglobalization is permanent regime shift",
        alternative_narratives=["Short-lived shock - ceasefire likely within months, energy prices normalize",
                                "WWIII risk - escalation to NATO-Russia conflict possible"],
        market_outcome={"direction": "commodity_super_spike_then_normalize", "spx_3m": 4150, "oil_3m": 120,
                        "description": "Oil hit $130, natgas EUR 300. S&P recovered. Inflation spike temporary."},
        expert_reasoning="Geopolitical shocks hardest to trade. Initial reaction always overshoots. Permanent change "
                         "is deglobalization and energy security investment. Trade is not the event but the structural "
                         "shifts it accelerates.",
        tags=["geopolitical", "russia", "commodities"], difficulty="hard"
    ))

    cases.append(C(
        case_id="GEO-002", period="2023-10",
        title="Israel-Hamas War - Middle East Risk Premium Returns Temporarily",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "moderate", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 4350, "vix": 18, "dxy": 106, "us10y": 4.80, "us2y": 5.00,
                    "hyg_spread": 400, "gold": 1860, "oil": 85, "unemployment": 3.8,
                    "fed_funds_rate": 5.50, "cpi_yoy": 3.7,
                    "event": "Hamas attacks Israel Oct 7. Oil and gold spike on geopolitical risk."},
        dominant_narrative="Middle East risk premium - wider regional conflict could disrupt oil supplies",
        alternative_narratives=["Contained conflict - Iran not directly involved, oil supply safe",
                                "Oil shock risk - Strait of Hormuz closure could spike oil to $150"],
        market_outcome={"direction": "contained_geopolitical_risk", "spx_3m": 4770, "oil_3m": 75,
                        "description": "Geopolitical premium faded quickly. Oil actually fell. S&P rallied strongly."},
        expert_reasoning="Middle East conflicts have diminishing macro impact unless they threaten oil supply. "
                         "Gold and oil initial spike was noise-trading. The macro backdrop (Fed hiking, strong "
                         "dollar) dominated the geopolitical overlay.",
        tags=["geopolitical", "middle_east", "oil"], difficulty="medium"
    ))

    # ========== Japan / BOJ (2 cases) ==========

    cases.append(C(
        case_id="BOJ-001", period="2022-12",
        title="BOJ Surprises - YCC Band Widened, Last Dovish Central Bank Capitulates",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "stable", "inflation": "rising"},
        input_data={"spx": 3850, "vix": 22, "dxy": 104, "us10y": 3.50, "us2y": 4.20,
                    "hyg_spread": 440, "gold": 1800, "oil": 76, "usdjpy": 137,
                    "japan_cpi": 3.8, "boj_rate": -0.10, "japan_10y": 0.25,
                    "event": "BOJ widens YCC band from +/-0.25% to +/-0.50%, shocking global markets"},
        dominant_narrative="BOJ tightening - last dovish central bank capitulating, global rate shock incoming",
        alternative_narratives=["Symbolic move - BOJ still easing, just adjusting YCC parameters marginally",
                                "Yen carry trade unwind - BOJ normalization triggers massive capital flows"],
        market_outcome={"direction": "global_rate_shock", "spx_1m": 3850, "usdjpy_1m": 130,
                        "description": "JGB 10Y spiked to 0.50%. Yen surged 5%. Global bonds sold off. Then stabilized."},
        expert_reasoning="Most important CB signal of 2022. End of 'last dovish central bank.' Implications: "
                         "(1) yen carry trade unwinds, (2) JGBs sell off, (3) Japanese investors repatriate, "
                         "(4) global duration supply increases. Multi-year trend.",
        tags=["boj", "japan", "ycc"], difficulty="hard"
    ))

    cases.append(C(
        case_id="BOJ-002", period="2024-07",
        title="BOJ Hikes, Carry Trade Unwinds - Nikkei Falls 12% in One Day",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "extreme", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 5200, "vix": 23, "dxy": 103, "us10y": 3.80, "us2y": 3.90,
                    "hyg_spread": 370, "gold": 2450, "oil": 75, "usdjpy": 143,
                    "japan_cpi": 2.8, "boj_rate": 0.25, "japan_10y": 1.05,
                    "event": "BOJ hikes to 0.25%, signals more. USDJPY crashes from 161 to 143. Nikkei -12%."},
        dominant_narrative="Carry trade unwind - BOJ hikes + US recession fears = historic yen carry trade liquidation",
        alternative_narratives=["Japan renaissance - stronger yen + higher rates = return to normal monetary policy",
                                "Global risk-off - BOJ tightening removing world's marginal liquidity provider"],
        market_outcome={"direction": "sharp_vix_spike_then_calm", "spx_1m": 5300, "usdjpy_1m": 146,
                        "description": "Nikkei recovered 75% of losses in weeks. Carry trade unwind was positioning event."},
        expert_reasoning="Largest single-day move in Nikkei history. But positioning, not macro crisis: (1) VIX spiked "
                         "then collapsed, (2) credit markets barely moved, (3) unwind was in levered FX/equity positions. "
                         "BOJ normalization story is multi-year but extreme move was transient.",
        tags=["boj", "carry_trade", "yen"], difficulty="hard"
    ))

    # ========== China (2 cases) ==========

    cases.append(C(
        case_id="CN-001", period="2015-08",
        title="China Devaluation - PBOC Surprises Markets, Global Deflation Wave",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 2080, "vix": 28, "dxy": 97, "us10y": 2.15, "us2y": 0.70,
                    "hyg_spread": 510, "gold": 1110, "oil": 45, "usdcnh": 6.45,
                    "shanghai": 3500, "china_gdp": 6.9,
                    "event": "PBOC devalues yuan 2% in single day. Chinese stocks down 30% from June peak."},
        dominant_narrative="China hard landing - yuan devaluation confirms growth panic, global deflation wave",
        alternative_narratives=["Managed depreciation - PBOC maintaining control, not a crisis",
                                "Global risk-off - China weakness spreads to commodities and EM"],
        market_outcome={"direction": "china_selloff_contagion", "spx_3m": 2060, "usdcnh_3m": 6.35,
                        "description": "S&P fell 12% from peak. Fed delayed hiking. China intervened to stabilize yuan."},
        expert_reasoning="China's 2015 devaluation was a watershed: first time China exported deflation rather than "
                         "demand. Transmission: weaker CNY -> lower import prices -> disinflation -> CBs can't "
                         "normalize. Fundamentally changed Fed's 2015-2016 hiking path.",
        tags=["china", "yuan", "devaluation"], difficulty="hard"
    ))

    cases.append(C(
        case_id="CN-002", period="2024-09",
        title="China Stimulus Bazooka - PBoC/Finance Ministry Go 'All-In'",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 5700, "vix": 15, "dxy": 100, "us10y": 3.70, "us2y": 3.55,
                    "hyg_spread": 330, "gold": 2650, "oil": 68, "usdcnh": 7.01,
                    "shanghai": 3000, "china_30y": 2.20, "china_gdp": 4.6,
                    "event": "PBoC cuts RRR/MLF/LPR simultaneously. Fiscal stimulus >$280B announced."},
        dominant_narrative="China policy bazooka - coordinated monetary + fiscal stimulus to revive growth and housing",
        alternative_narratives=["Too little too late - deflation psychology entrenched, stimulus insufficient",
                                "Commodity super-cycle - China reflation will drive global commodity demand"],
        market_outcome={"direction": "china_rally_then_fade", "csi300_3m": 4200, "iron_ore_3m": 105,
                        "description": "Chinese stocks rallied 25% then gave back half. Iron ore bounced. Uncertain path."},
        expert_reasoning="China stimulus 2024 is different: (1) housing deflation structural not cyclical, (2) "
                         "demographics headwind, (3) fiscal multipliers lower than property era. Will stabilize "
                         "not reflate. Key bet: China growth floor, not ceiling.",
        tags=["china", "stimulus", "deflation"], difficulty="hard"
    ))

    # ========== Fed / Monetary Policy (2 cases) ==========

    cases.append(C(
        case_id="FED-001", period="2019-07",
        title="Fed Cuts with S&P at ATHs - Insurance Cut, Don't Fight the Fed",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "low", "growth": "stable", "inflation": "stable"},
        input_data={"spx": 3020, "vix": 12, "dxy": 97, "us10y": 2.00, "us2y": 1.80,
                    "hyg_spread": 370, "gold": 1420, "oil": 57, "unemployment": 3.7,
                    "gdp_qoq": 2.0, "fed_funds_rate": 2.50, "cpi_yoy": 1.8,
                    "event": "Fed cuts 25bp, calls it 'mid-cycle adjustment.' Market wants more."},
        dominant_narrative="Insurance cut - Fed easing with strong economy is uniquely bullish for risk assets",
        alternative_narratives=["Last cut before recession - cutting at cycle highs signals late-cycle danger",
                                "Political pressure - Trump bullying Fed into unnecessary easing"],
        market_outcome={"direction": "bullish", "spx_6m": 3330,
                        "description": "S&P rallied 12% in 6 months. Fed cut 3 times. 2019 was >30% S&P total return."},
        expert_reasoning="Insurance cuts are most bullish Fed action: (1) economy still growing, (2) P/E expands "
                         "on lower rates, (3) recession probability falls. 2019 is template: when they ease without "
                         "a recession, risk assets rally strongly.",
        tags=["fed", "rate_cut", "insurance"], difficulty="easy"
    ))

    cases.append(C(
        case_id="FED-002", period="2024-09",
        title="Fed Cuts 50bp - First Cut of Cycle, Soft Landing or Recession Signal?",
        macro_regime={"monetary_policy": "easing", "fiscal_stance": "expansionary",
                      "volatility": "moderate", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 5700, "vix": 17, "dxy": 100, "us10y": 3.65, "us2y": 3.55,
                    "hyg_spread": 330, "gold": 2650, "oil": 70, "unemployment": 4.2,
                    "fed_funds_rate": 5.00, "cpi_yoy": 2.5, "cpi_core": 3.2,
                    "event": "Fed delivers 50bp cut (not 25bp), signals more. Powell: 'Recalibration.'"},
        dominant_narrative="Soft landing - Fed front-loads cuts, inflation falling, labor cooling not crashing",
        alternative_narratives=["Recession signal - 50bp cut means Fed sees something markets don't",
                                "Too late - labor market cracks appearing, Fed behind again"],
        market_outcome={"direction": "bullish_uncertain", "spx_3m": 6000,
                        "description": "Markets rallied on 50bp cut. Soft landing narrative intact. AI + Fed tailwinds."},
        expert_reasoning="50bp cuts at the start of an easing cycle are historically ambiguous: sometimes recession "
                         "(2001, 2007), sometimes cycle extension (1995, 1998, 2019). Key variable: is labor market "
                         "deteriorating or normalizing? 4.2% UE suggests normalization. The defining macro bet.",
        tags=["fed", "rate_cut", "soft_landing"], difficulty="hard"
    ))

    # ========== Volatility / Positioning (1 case) ==========

    cases.append(C(
        case_id="VOL-001", period="2018-02",
        title="Volmageddon - XIV ETN Collapses, Short-Vol Trade Implodes",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "expansionary",
                      "volatility": "high", "growth": "accelerating", "inflation": "rising"},
        input_data={"spx": 2640, "vix": 37, "dxy": 89, "us10y": 2.85, "us2y": 2.10,
                    "hyg_spread": 330, "gold": 1330, "oil": 62, "unemployment": 4.1,
                    "gdp_qoq": 2.9, "fed_funds_rate": 1.50,
                    "event": "VIX spikes from 17 to 50 in one session. XIV collapses to zero. S&P down 10%."},
        dominant_narrative="Volatility regime change - short-vol trade implodes, rates causing market instability",
        alternative_narratives=["Buy the dip - strong fundamentals, vol spike is technical not fundamental",
                                "End of cycle - wage inflation + rate hikes = recession ahead"],
        market_outcome={"direction": "sharp_correction_then_recovery", "spx_3m": 2720,
                        "description": "S&P recovered in weeks. Volmageddon was positioning unwind, not macro crisis."},
        expert_reasoning="When implied correlation spikes without fundamental catalyst, it's a positioning unwind. "
                         "XIV/VIX complex had become too large. Crowded trade blowup. Macro fundamentals still strong "
                         "- this was a vol event, not an econ event.",
        tags=["volatility", "positioning", "correction"], difficulty="medium"
    ))

    # ========== Style / Factor Rotation (1 case) ==========

    cases.append(C(
        case_id="STYLE-001", period="2022-11",
        title="Growth to Value Rotation - Biggest Factor Rotation in 20 Years",
        macro_regime={"monetary_policy": "tightening", "fiscal_stance": "neutral",
                      "volatility": "high", "growth": "decelerating", "inflation": "falling"},
        input_data={"spx": 3900, "vix": 23, "dxy": 112, "us10y": 4.10, "us2y": 4.60,
                    "hyg_spread": 500, "gold": 1730, "oil": 87, "unemployment": 3.7,
                    "fed_funds_rate": 4.00, "nasdaq_ytd": -32, "energy_xle_ytd": 64,
                    "event": "Oct CPI 7.7% (below 8.0% expected). Massive short-covering rally in growth stocks."},
        dominant_narrative="Peak hawkishness - inflation data softening, Fed pivot pricing begins, risk-on rotation",
        alternative_narratives=["Head fake - one CPI print doesn't make a trend, Fed still hawkish",
                                "Factor regime change - growth repricing just getting started"],
        market_outcome={"direction": "growth_recovery", "spx_6m": 4150, "nasdaq_6m": 13500,
                        "description": "Nasdaq rallied 40% in 7 months. AI excitement followed CPI peak narrative."},
        expert_reasoning="Nov 2022 CPI was the single most important data point of the cycle. It confirmed inflation "
                         "peak and opened path to Fed pause. From Nov 2022 to Jul 2023, growth massively outperformed "
                         "value. Ultimate 'bad news is good news' regime change.",
        tags=["rotation", "growth", "cpi"], difficulty="medium"
    ))

    return cases


CASES: list[HistoricalCase] = _build_cases()


def get_case_by_id(case_id: str) -> HistoricalCase | None:
    """Retrieve a specific case by its ID."""
    for c in CASES:
        if c.case_id == case_id:
            return c
    return None


def get_cases_by_tag(tag: str) -> list[HistoricalCase]:
    """Filter cases by tag."""
    return [c for c in CASES if tag in c.tags]


def get_cases_by_difficulty(difficulty: str) -> list[HistoricalCase]:
    """Filter cases by difficulty level."""
    return [c for c in CASES if c.difficulty == difficulty]


def get_cases_by_regime(regime_key: str, regime_value: str) -> list[HistoricalCase]:
    """Filter cases by regime dimension value."""
    return [c for c in CASES if c.macro_regime.get(regime_key) == regime_value]
