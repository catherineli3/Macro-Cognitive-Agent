"""RegimeClassifier — multi-dimensional macro regime classification.

Classifies across 6 dimensions:
    1. Growth Phase    2. Inflation Regime    3. Monetary Stance
    4. Credit Cycle    5. Dollar Regime       6. Volatility Regime

Integrates: MentalModel outputs, market data, narrative engine, reflexivity engine.
"""

from __future__ import annotations

from typing import Any

from src.regime.schemas import MacroRegime


class RegimeClassifier:
    """Multi-dimensional macro regime classifier."""

    def classify(
        self,
        mental_models: dict[str, Any] = None,
        market_data: dict | None = None,
        narrative_data: dict | None = None,
        reflexivity_data: dict | None = None,
    ) -> MacroRegime:
        mental = mental_models or {}
        market = market_data or {}

        growth = self._classify_growth(mental.get("growth"), market)
        inflation = self._classify_inflation(mental.get("inflation"), market)
        monetary = self._classify_monetary(mental.get("liquidity"), market)
        credit = self._classify_credit(mental.get("credit"), market)
        dollar = self._classify_dollar(mental.get("dollar"), market)
        vol = self._classify_volatility(market)

        regime_label, confidence = self._composite_label(
            growth, inflation, monetary, credit, dollar, vol, reflexivity_data
        )
        trans_prob, trans_dir = self._detect_transition_signals(
            growth, inflation, monetary, credit, dollar, vol, market
        )
        warnings = self._generate_warnings(
            growth, inflation, monetary, credit, dollar, vol, market, reflexivity_data
        )
        hist = self._historical_label(growth, inflation, monetary, credit)

        return MacroRegime(
            regime_id=f"reg_{regime_label}",
            regime_label=regime_label,
            confidence=confidence,
            growth_phase=growth["label"],
            inflation_regime=inflation["label"],
            monetary_stance=monetary["label"],
            credit_cycle=credit["label"],
            dollar_regime=dollar["label"],
            volatility_regime=vol["label"],
            transition_probability=trans_prob,
            transition_direction=trans_dir,
            early_warning_signals=warnings,
            historical_period_label=hist,
        )

    def _classify_growth(self, model_data: Any, market: dict) -> dict:
        if model_data and hasattr(model_data, "status"):
            s = str(getattr(model_data, "status", "")).lower()
            if s in ("expansion", "accelerating", "above_trend"):
                return {"label": "accelerating", "score": 0.8, "desc": "Above-trend growth"}
            if s in ("contraction", "decelerating", "below_trend"):
                return {"label": "decelerating", "score": 0.7, "desc": "Below-trend growth"}
            if s == "stable":
                return {"label": "stable", "score": 0.7, "desc": "Trend growth"}
        yc = market.get("yield_curve", 0)
        return {
            "label": "decelerating" if yc < 0.3 else "stable",
            "score": 0.4,
            "desc": "Market-implied",
        }

    def _classify_inflation(self, model_data: Any, market: dict) -> dict:
        cpi = market.get("cpi_yoy", 2.5)
        if cpi < 2.0:
            return {"label": "disinflation", "score": 0.7, "desc": f"CPI {cpi}%"}
        if cpi < 4.0:
            return {"label": "reflation", "score": 0.6, "desc": f"CPI {cpi}%"}
        growth_label = self._classify_growth(model_data, market)["label"]
        if growth_label == "decelerating":
            return {"label": "stagflation", "score": 0.65, "desc": f"CPI {cpi}% + slowing growth"}
        return {"label": "reflation", "score": 0.5, "desc": f"CPI {cpi}%"}

    def _classify_monetary(self, model_data: Any, market: dict) -> dict:
        change = market.get("rate_change_bps", 0)
        if change < -25:
            return {"label": "easing", "score": 0.8, "desc": "Policy easing"}
        if change > 25:
            return {"label": "tightening", "score": 0.8, "desc": "Policy tightening"}
        return {"label": "neutral", "score": 0.5, "desc": "On hold"}

    def _classify_credit(self, model_data: Any, market: dict) -> dict:
        hy = market.get("hy_spread", 350)
        if hy > 600:
            return {"label": "contraction", "score": 0.7, "desc": f"HY spread {hy}bp"}
        if hy < 300:
            return {"label": "expansion", "score": 0.7, "desc": f"HY spread {hy}bp"}
        if hy < 450:
            return {"label": "peak", "score": 0.5, "desc": f"HY spread {hy}bp"}
        return {"label": "contraction", "score": 0.5, "desc": f"HY spread {hy}bp"}

    def _classify_dollar(self, model_data: Any, market: dict) -> dict:
        trend = market.get("dxy_trend", 0)
        dxy = market.get("dxy", 104)
        if trend > 2:
            return {"label": "strong", "score": 0.7, "desc": "Dollar strengthening"}
        if trend < -2:
            return {"label": "weak", "score": 0.7, "desc": "Dollar weakening"}
        return {"label": "stable", "score": 0.5, "desc": f"DXY {dxy}"}

    def _classify_volatility(self, market: dict) -> dict:
        vix = market.get("vix", 18)
        if vix < 14:
            return {"label": "low_vol", "score": 0.8, "desc": "Complacency regime"}
        if vix < 22:
            return {"label": "normal", "score": 0.7, "desc": f"VIX {vix}"}
        if vix < 35:
            return {"label": "high_vol", "score": 0.7, "desc": f"VIX {vix} elevated"}
        return {"label": "crisis", "score": 0.85, "desc": f"VIX {vix} extreme"}

    def _composite_label(
        self,
        growth: dict,
        inflation: dict,
        monetary: dict,
        credit: dict,
        dollar: dict,
        vol: dict,
        reflexivity: dict | None,
    ) -> tuple:
        if vol["label"] == "crisis":
            return "credit_event", 0.85
        if inflation["label"] == "stagflation" and growth["label"] == "decelerating":
            return "inflation_shock", 0.70
        if monetary["label"] == "tightening" and credit["label"] in ("contraction", "peak"):
            return "policy_tightening", 0.65
        if dollar["label"] == "strong" and vol["label"] in ("high_vol", "crisis"):
            return "liquidity_stress", 0.60
        if growth["label"] == "decelerating" and monetary["label"] == "easing":
            return "recovery", 0.55
        if growth["label"] == "accelerating" and inflation["label"] == "disinflation":
            return "expansion", 0.70
        if growth["label"] == "accelerating" and credit["label"] == "peak":
            return "late_cycle", 0.55
        return "stable_growth", 0.40

    def _detect_transition_signals(
        self,
        growth: dict,
        inflation: dict,
        monetary: dict,
        credit: dict,
        dollar: dict,
        vol: dict,
        market: dict,
    ) -> tuple:
        prob = 0.2
        direction = "stable"
        if market.get("yield_curve", 0.5) < 0:
            prob += 0.20
            direction = "recession_risk"
        if market.get("hy_spread", 350) > 500:
            prob += 0.15
            direction = "credit_stress"
        if market.get("vix", 18) > 28:
            prob += 0.15
            direction = "volatility_regime_change"
        if abs(market.get("dxy_trend", 0)) > 5:
            prob += 0.10
            direction = "dollar_extreme_reversal_risk"
        if growth["label"] == "decelerating" and monetary["label"] != "easing":
            prob += 0.10
            direction = "policy_lag_risk"
        return round(min(prob, 0.9), 2), direction

    def _generate_warnings(
        self,
        growth: dict,
        inflation: dict,
        monetary: dict,
        credit: dict,
        dollar: dict,
        vol: dict,
        market: dict,
        reflexivity: dict | None,
    ) -> list[str]:
        warnings = []
        if market.get("yield_curve", 0.5) < -0.3:
            warnings.append("Deep yield curve inversion — historical recession signal")
        if credit["label"] == "contraction" and monetary["label"] == "tightening":
            warnings.append("Credit contracting while policy tightening — double squeeze")
        if dollar["label"] == "strong" and credit["label"] in ("contraction", "peak"):
            warnings.append("Strong dollar + credit stress = EM funding crisis risk")
        if vol["label"] == "low_vol" and credit["label"] == "peak":
            warnings.append("Low volatility masking credit cycle peak — false calm")
        if inflation["label"] == "stagflation":
            warnings.append("Stagflation regime — worst case for policy, no good options")
        if reflexivity:
            cycles = reflexivity.get("active_cycles", [])
            if cycles:
                warnings.append(
                    f"{len(cycles)} reflexivity cycle(s) active — self-reinforcing dynamics"
                )
        return warnings

    def _historical_label(
        self,
        growth: dict,
        inflation: dict,
        monetary: dict,
        credit: dict,
    ) -> str:
        """Generate historical period label."""
        if growth["label"] == "accelerating" and inflation["label"] == "disinflation":
            return "late-1990s goldilocks"
        if inflation["label"] == "stagflation":
            return "early-1970s stagflation"
        if monetary["label"] == "tightening" and credit["label"] in ("contraction", "peak"):
            return "late-2018 tightening"
        if growth["label"] == "decelerating" and monetary["label"] == "easing":
            return "early-2019 easing cycle"
        if credit["label"] == "contraction":
            return "early-2008 credit stress"
        return "current cycle — no close analog"
