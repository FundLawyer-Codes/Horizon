"""Source recommendation using AI."""

import json
from typing import List
from collections import Counter

from .client import AIClient
from .prompts import SOURCE_RECOMMENDATION_SYSTEM, SOURCE_RECOMMENDATION_USER
from ..models import ContentItem, SourceRecommendation, SourceType


class SourceRecommender:
    """Recommends new information sources based on high-quality content."""

    def __init__(self, ai_client: AIClient):
        """Initialize source recommender.

        Args:
            ai_client: AI client for making completions
        """
        self.client = ai_client

    async def recommend_sources(
        self,
        items: List[ContentItem],
        min_score: float = 8.0
    ) -> List[SourceRecommendation]:
        """Recommend new sources based on high-scoring items.

        Args:
            items: All analyzed content items
            min_score: Minimum score to consider for recommendations

        Returns:
            List[SourceRecommendation]: Recommended sources
        """
        # Filter high-quality items
        high_quality = [item for item in items if item.ai_score and item.ai_score >= min_score]

        if len(high_quality) < 3:
            # Not enough high-quality content to make recommendations
            return []

        # Analyze source patterns
        source_stats = self._analyze_source_patterns(high_quality)

        # Prepare items for AI analysis
        items_data = []
        for item in high_quality[:20]:  # Limit to top 20 to avoid token limits
            items_data.append({
                "title": item.title,
                "score": item.ai_score,
                "source_type": item.source_type.value,
                "author": item.author,
                "url": str(item.url),
                "tags": item.ai_tags
            })

        items_json = json.dumps(items_data, indent=2)

        # Get recommendations from AI
        user_prompt = SOURCE_RECOMMENDATION_USER.format(items_json=items_json)

        try:
            response = await self.client.complete(
                system=SOURCE_RECOMMENDATION_SYSTEM,
                user=user_prompt,
                temperature=0.4,
                max_tokens=4096
            )

            # Parse response
            result = self._parse_recommendations_response(response)
            recommendations = result.get("recommendations", [])

            # Convert to SourceRecommendation objects
            return [
                SourceRecommendation(
                    source_type=SourceType(rec["source_type"]),
                    identifier=rec["identifier"],
                    reason=rec["reason"],
                    confidence=rec["confidence"],
                    sample_content=rec.get("sample_content", [])
                )
                for rec in recommendations
                if rec["confidence"] >= 0.6  # Only high-confidence recommendations
            ]

        except Exception as e:
            print(f"Error generating source recommendations: {e}")
            return []

    def _analyze_source_patterns(self, items: List[ContentItem]) -> dict:
        """Analyze patterns in high-quality content sources.

        Args:
            items: High-quality content items

        Returns:
            dict: Statistics about sources
        """
        author_counts = Counter()
        source_type_counts = Counter()

        for item in items:
            if item.author:
                author_counts[item.author] += 1
            source_type_counts[item.source_type.value] += 1

        return {
            "top_authors": author_counts.most_common(10),
            "source_distribution": dict(source_type_counts)
        }

    def _parse_recommendations_response(self, response: str) -> dict:
        """Parse AI recommendation response.

        Args:
            response: AI response text

        Returns:
            dict: Parsed recommendations
        """
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            else:
                return {"recommendations": []}
