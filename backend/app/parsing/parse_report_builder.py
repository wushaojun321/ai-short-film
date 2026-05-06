from __future__ import annotations


class ParseReportBuilder:
    """Build the result payload returned by the parse task."""

    def build(self, *, episodes: list[dict], assets: dict, series: dict, blueprint_id: str, continuity_report: dict) -> dict:
        return {
            "episodes": episodes,
            "assets": assets,
            "series": series,
            "blueprint_id": blueprint_id,
            "continuity_report": continuity_report,
            "parse_report": {
                "episode_count": len(episodes),
                "asset_count": sum(len(v) for v in assets.values()) if isinstance(assets, dict) else 0,
                "dialogue_count": sum(int(ep.get("dialogue_count", 0) or 0) for ep in episodes),
                "source_integrity": "original" if all(ep.get("source_integrity") == "original" for ep in episodes) else "partial",
            },
        }
