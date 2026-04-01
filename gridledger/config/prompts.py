# gridledger/config/prompts.py
"""
Versioned prompt templates for memo generation (AC5).

To add a new prompt version:
1. Add a new key to PROMPT_VERSIONS with a new version string (e.g. "v2")
2. Update ACTIVE_PROMPT_VERSION to point to it
3. Old versions remain in the dict for eval comparison / regression testing
"""

ACTIVE_PROMPT_VERSION = "v1"

PROMPT_VERSIONS = {
    "v1": """You are an energy infrastructure investment analyst.

Write a concise underwriting memo (under 200 words) summarizing:

Market Metrics:
Average Price: ${average_price}/MWh
Min Price: ${min_price}
Max Price: ${max_price}
Price Range: ${price_range}
Volatility: {volatility}
Observations: {observations}

Revenue Estimates:
Scenario: {scenario}
Battery Size: {battery_size_mwh} MWh
Efficiency: {efficiency}
Cycles per day: {cycles_per_day}
Simple Revenue Estimate: ${simple_revenue_estimate}
Arbitrage Proxy Revenue: ${arbitrage_proxy_revenue}

Risk Level: {risk_level}

Time Window: {start_date} to {end_date}

Requirements:
- Analytical tone
- Investor focused
- Clear risks and opportunities
- No bullet points
- Under 200 words
""",
}


def get_prompt(version: str, **kwargs) -> str:
    """
    Returns the formatted prompt for the given version.
    Raises KeyError if version is not found.
    """
    template = PROMPT_VERSIONS[version]
    return template.format(**kwargs)
