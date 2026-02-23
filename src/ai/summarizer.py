"""Daily summary generation — pure programmatic rendering."""

from typing import List, Dict
from collections import defaultdict

from ..models import ContentItem


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "highlights": "Today's Highlights",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "tags": "Tags",
        "sections": {
            "ai": "AI / Machine Learning",
            "ml": "AI / Machine Learning",
            "machine-learning": "AI / Machine Learning",
            "deep-learning": "AI / Machine Learning",
            "llm": "AI / Machine Learning",
            "nlp": "AI / Machine Learning",
            "systems": "Systems & Infrastructure",
            "infrastructure": "Systems & Infrastructure",
            "performance": "Systems & Infrastructure",
            "linux": "Systems & Infrastructure",
            "kernel": "Systems & Infrastructure",
            "security": "Security",
            "programming": "Programming & Tools",
            "rust": "Programming & Tools",
            "python": "Programming & Tools",
            "golang": "Programming & Tools",
            "tools": "Programming & Tools",
            "open-source": "Open Source",
        },
        "other": "Other Updates",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "highlights": "今日精选",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "tags": "标签",
        "sections": {
            "ai": "AI / 机器学习",
            "ml": "AI / 机器学习",
            "machine-learning": "AI / 机器学习",
            "deep-learning": "AI / 机器学习",
            "llm": "AI / 机器学习",
            "nlp": "AI / 机器学习",
            "systems": "系统与基础设施",
            "infrastructure": "系统与基础设施",
            "performance": "系统与基础设施",
            "linux": "系统与基础设施",
            "kernel": "系统与基础设施",
            "security": "安全",
            "programming": "编程与工具",
            "rust": "编程与工具",
            "python": "编程与工具",
            "golang": "编程与工具",
            "tools": "编程与工具",
            "open-source": "开源",
        },
        "other": "其他动态",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
}


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items.

    No AI call needed — all data (score, summary, background, tags)
    is already produced by the analyzer and enricher stages.
    """

    def __init__(self):
        """Initialize daily summarizer."""
        pass

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are split into highlights (score >= 9) and sections grouped by tag.

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = f"""# {labels['header']} - {date}

> From {total_fetched} items, {len(items)} important content pieces were selected

---

"""
        sections = []

        # Split into highlights and regular
        highlights = [i for i in items if (i.ai_score or 0) >= 9.0]
        regular = [i for i in items if (i.ai_score or 0) < 9.0]

        if highlights:
            sections.append(f"## {labels['highlights']}\n")
            for item in highlights:
                sections.append(self._format_item(item, labels, language))

        # Group regular items by primary tag
        grouped = self._group_by_tag(regular, labels)
        for section_title, group_items in grouped.items():
            sections.append(f"## {section_title}\n")
            for item in group_items:
                sections.append(self._format_item(item, labels, language))

        return header + "\n".join(sections)

    def _format_item(self, item: ContentItem, labels: dict, language: str) -> str:
        """Format a single ContentItem into Markdown."""
        title = item.title.replace("[", "(").replace("]", ")")
        url = str(item.url)
        score = item.ai_score or "?"
        meta = item.metadata

        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )
        background = meta.get(f"background_{language}") or meta.get("background") or ""
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        source = item.source_type.value
        if meta.get("subreddit"):
            source += f"/r/{meta['subreddit']}"
        source += f"/{item.author or 'unknown'}"

        # Build item block
        lines = [
            f"### [{title}]({url}) ⭐️ {score}/10",
            "",
            summary,
            "",
            f"*{labels['source']}: {source}*",
        ]

        if background:
            lines.append("")
            lines.append(f"**{labels['background']}**: {background}")

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        # Tags
        if item.ai_tags:
            tags_str = ", ".join([f"`#{t}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        return "\n".join(lines) + "\n\n---\n\n"

    def _group_by_tag(self, items: List[ContentItem], labels: dict) -> Dict[str, List[ContentItem]]:
        """Group items by their primary tag into named sections."""
        tag_sections = labels["sections"]
        other_label = labels["other"]

        grouped: Dict[str, List[ContentItem]] = defaultdict(list)
        for item in items:
            section = other_label
            for tag in (item.ai_tags or []):
                tag_lower = tag.lower()
                if tag_lower in tag_sections:
                    section = tag_sections[tag_lower]
                    break
            grouped[section].append(item)

        return dict(grouped)

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> Analyzed {total_fetched} items, but none met the importance threshold.\n\n"
            + labels["empty_body"]
        )
