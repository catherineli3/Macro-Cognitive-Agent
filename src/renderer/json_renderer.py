"""JsonRenderer — Machine-readable JSON output from MacroNarrative.

Consumes: MacroNarrative
Output:  JSON string / dict
"""

from src.schemas.narrative import MacroNarrative


class JsonRenderer:
    """Render MacroNarrative → JSON string."""

    def render(self, narrative: MacroNarrative, indent: int = 2) -> str:
        """Render MacroNarrative as JSON.

        Args:
            narrative: The structured MacroNarrative.
            indent: JSON indentation level.

        Returns:
            JSON string.
        """
        import json
        return json.dumps(narrative.model_dump(mode="json"), indent=indent, ensure_ascii=False)

    def render_dict(self, narrative: MacroNarrative) -> dict:
        """Render MacroNarrative as a Python dict.

        Args:
            narrative: The structured MacroNarrative.

        Returns:
            Nested dict ready for JSON serialization.
        """
        return narrative.model_dump(mode="json")
