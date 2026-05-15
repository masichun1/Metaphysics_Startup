import json
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from jinja2 import Environment, FileSystemLoader

from core.config_loader import AppConfig, ContentRulesConfig
from core.exceptions import AIError, AIQuotaExceededError, AIResponseParseError
from core.retry import retry_on_failure

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build_system_prompt(rules: ContentRulesConfig) -> str:
    """Compose the global brand voice system prompt from content rules."""
    voice = rules.brand_voice
    audience = voice.get("target_audience", {})
    rules_list = voice.get("language_rules", [])
    forbidden_list = voice.get("forbidden", [])

    parts = [
        f"You are a professional copywriter for '{audience.get('store_name', 'a metaphysical store')}'.",
        f"Brand tone: {voice.get('tone', 'warm, knowledgeable, accessible')}.",
        f"Target audience: {audience.get('demographics', 'women 40-65 in Western countries')}.",
        f"Audience interests: {audience.get('interests', 'spirituality, astrology, tarot, crystals, meditation')}.",
        "",
        "Language rules:",
    ]
    for r in rules_list:
        parts.append(f"- {r}")
    parts.append("")
    parts.append("DO NOT:")
    for f_item in forbidden_list:
        parts.append(f"- {f_item}")

    return "\n".join(parts)


class AIClient:
    """
    Wrapper around Anthropic Claude API for content generation.

    Features:
    - System prompt built from content rules config
    - Jinja2 prompt template rendering
    - Structured (JSON) output via tool use
    - Token usage tracking
    - Automatic retry on transient failures
    """

    def __init__(self, config: AppConfig):
        env_key = config.env.get("ANTHROPIC_API_KEY", "")
        self._api_key = env_key or ""
        if not self._api_key:
            raise AIError(
                "ANTHROPIC_API_KEY not found in environment. "
                "Set it in .env or as an environment variable."
            )
        self._client = Anthropic(api_key=self._api_key)
        self._model = config.env.get(
            "ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-20250514"
        )
        self._default_max_tokens = int(
            config.env.get("ANTHROPIC_MAX_TOKENS_DEFAULT", "4096")
        )
        self._rules = config.content_rules
        self._system_prompt = _build_system_prompt(self._rules)

        # Jinja2 template environment for prompts
        self._jinja = Environment(
            loader=FileSystemLoader(_PROJECT_ROOT),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._total_input_tokens = 0
        self._total_output_tokens = 0

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimated cost in USD based on token usage (Sonnet pricing)."""
        input_cost = (self._total_input_tokens / 1_000_000) * 3.0  # $3/MTok input
        output_cost = (self._total_output_tokens / 1_000_000) * 15.0  # $15/MTok output
        return input_cost + output_cost

    def render_prompt(self, template_rel_path: str, variables: dict[str, Any]) -> str:
        """Render a Jinja2 prompt template with variables."""
        template = self._jinja.get_template(template_rel_path)
        return template.render(**variables)

    @retry_on_failure(
        max_attempts=3,
        base_delay_seconds=2.0,
        retryable_exceptions=(AIError,),
    )
    def generate_text(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate free-form text content.

        Args:
            user_prompt: The main content generation request.
            system_prompt: Override for the default brand voice system prompt.
            temperature: Creativity level (0.0-1.0).
            max_tokens: Max output tokens.

        Returns:
            Generated text string.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._default_max_tokens,
                system=system_prompt or self._system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature,
            )
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "quota" in msg or "exceeded" in msg:
                raise AIQuotaExceededError(f"API quota exceeded: {e}") from e
            raise AIError(f"Claude API call failed: {e}") from e

        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        content = response.content
        for block in content:
            if block.type == "text":
                return block.text
        raise AIResponseParseError("No text block in Claude response")

    @retry_on_failure(
        max_attempts=3,
        base_delay_seconds=2.0,
        retryable_exceptions=(AIError,),
    )
    def generate_structured(
        self,
        user_prompt: str,
        output_schema: dict[str, Any],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Generate structured JSON output using Claude's tool use.

        Args:
            user_prompt: The content generation request.
            output_schema: JSON schema describing the expected output.
            system_prompt: Override for the default brand voice system prompt.
            temperature: Creativity level.
            max_tokens: Max output tokens.

        Returns:
            Parsed JSON dict matching the schema.
        """
        tool_name = output_schema.get("name", "generate_output")
        tool_definition = {
            "name": tool_name,
            "description": output_schema.get("description", "Generate structured output"),
            "input_schema": {
                "type": "object",
                "properties": output_schema.get("properties", {}),
                "required": output_schema.get("required", []),
                "additionalProperties": False,
            },
        }

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._default_max_tokens,
                system=system_prompt or self._system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[tool_definition],
                tool_choice={"type": "tool", "name": tool_name},
                temperature=temperature,
            )
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "quota" in msg or "exceeded" in msg:
                raise AIQuotaExceededError(f"API quota exceeded: {e}") from e
            raise AIError(f"Claude API structured call failed: {e}") from e

        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input

        raise AIResponseParseError(
            f"No tool_use block found for '{tool_name}' in Claude response"
        )

    def generate_product_description(self, product_info: dict) -> dict:
        """Generate a complete English product listing payload."""
        schema = {
            "name": "product_content",
            "description": "SEO-optimized product listing content in English.",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "SEO-optimized product title in English (max 70 chars)",
                },
                "body_html": {
                    "type": "string",
                    "description": "Full product description in HTML with benefits, features, and spiritual significance",
                },
                "meta_description": {
                    "type": "string",
                    "description": "Meta description for SEO (max 160 chars)",
                },
                "seo_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "10-15 SEO keywords in English",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Shopify product tags (5-10 comma-separated values)",
                },
                "vendor": {
                    "type": "string",
                    "description": "Brand/vendor name",
                },
            },
            "required": ["title", "body_html", "meta_description", "seo_keywords", "tags"],
        }

        prompt = f"""Create a complete English product listing for the following metaphysical product:

Product category: {product_info.get('category', 'spiritual product')}
Internal reference name: {product_info.get('source_title', 'mystical item')}
Key features: {product_info.get('features', 'high-quality spiritual tool')}
Materials: {product_info.get('materials', 'natural materials')}
Intended use: {product_info.get('use_case', 'spiritual practice and personal growth')}
Price point: ${product_info.get('price', 'premium')}

Generate compelling, SEO-optimized content that resonates with Western women aged 40+ interested in spirituality.
Do NOT make any medical or health claims."""

        return self.generate_structured(
            user_prompt=prompt,
            output_schema=schema,
            temperature=0.7,
        )

    def generate_review(self, product_info: dict, persona: dict) -> dict:
        """Generate a single authentic-feeling product review."""
        schema = {
            "name": "product_review",
            "description": "An authentic product review from a verified buyer.",
            "properties": {
                "rating": {
                    "type": "integer",
                    "description": "Star rating from 1 to 5",
                    "minimum": 1,
                    "maximum": 5,
                },
                "title": {
                    "type": "string",
                    "description": "Review title, 5-15 words",
                },
                "body": {
                    "type": "string",
                    "description": "Review body, 80-300 words with personal experience",
                },
                "reviewer_name": {
                    "type": "string",
                    "description": "First name + last initial of the reviewer",
                },
                "usage_duration": {
                    "type": "string",
                    "description": "How long the reviewer has used the product (e.g., '2 weeks', '1 month')",
                },
            },
            "required": ["rating", "title", "body", "reviewer_name"],
        }

        prompt = f"""Write an authentic English product review from a verified buyer.

PRODUCT:
- Name: {product_info.get('title', 'spiritual product')}
- Category: {product_info.get('category', 'metaphysical')}
- Price: ${product_info.get('price', 'premium')}

REVIEWER PERSONA:
- Name: {persona.get('name', 'Sarah')}
- Age: {persona.get('age', 50)}
- Location: {persona.get('location', 'United States')}
- Occupation: {persona.get('occupation', 'professional')}
- Spiritual background: {persona.get('spiritual_background', 'intermediate')}
- Writing style: {persona.get('writing_style', 'casual and warm')}
- Pain points: {persona.get('pain_points', 'stress and seeking balance')}

Make this review feel genuine and personal. Include a small personal story or detail about their experience.
Target rating: {persona.get('target_rating', 5)} stars."""

        return self.generate_structured(
            user_prompt=prompt,
            output_schema=schema,
            temperature=0.9,
        )

    def generate_blog_article(
        self,
        topic: str,
        category: str,
        keywords: list[str],
        target_word_count: int = 2000,
        template_vars: dict | None = None,
    ) -> dict:
        """Generate an SEO-optimized blog article."""
        schema = {
            "name": "blog_article",
            "description": "A complete SEO-optimized blog article in English.",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "SEO-optimized article title (50-70 chars), compelling and clickable",
                },
                "meta_description": {
                    "type": "string",
                    "description": "Meta description for SEO (max 155 chars)",
                },
                "body_html": {
                    "type": "string",
                    "description": "Full article body in HTML with H2/H3 headings, paragraphs, and a CTA at the end",
                },
                "excerpt": {
                    "type": "string",
                    "description": "Short excerpt/summary (1-2 sentences) for blog listing pages",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5-10 article tags",
                },
            },
            "required": ["title", "meta_description", "body_html", "excerpt"],
        }

        kw_str = ", ".join(keywords) if keywords else topic
        prompt = f"""Write an SEO-optimized English blog article for a metaphysical/spiritual e-commerce store.

TOPIC: {topic}
CATEGORY: {category}
PRIMARY KEYWORD: {keywords[0] if keywords else topic}
SECONDARY KEYWORDS: {kw_str}
TARGET WORD COUNT: approximately {target_word_count} words

Structure requirements:
- Start with an engaging hook that resonates with women aged 40+
- Use H2 headings to organize major sections (4-6 sections)
- Use H3 sub-headings where appropriate
- Each section should be substantive and valuable
- Include practical tips or actionable insights
- End with a gentle call-to-action linking to relevant products
- Naturally incorporate keywords (1-2% keyword density)
- Maintain a warm, knowledgeable, accessible tone throughout
- Reading level: 9th-10th grade

Additional context: {json.dumps(template_vars) if template_vars else 'None'}"""

        return self.generate_structured(
            user_prompt=prompt,
            output_schema=schema,
            temperature=0.8,
            max_tokens=4096,
        )
