# gridledger/tasks/memo.py

from anthropic import Anthropic
from gridledger.config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
)

def generate_underwriting_memo(metrics, revenue, risk_level, start_date, end_date):
    """
    Generates an underwriting-style memo using Claude.
    """

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in environment.")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
You are an energy infrastructure investment analyst.

Write a concise underwriting memo (under 200 words) summarizing:

Market Metrics:
Average Price: ${metrics['average_price']}/MWh
Min Price: ${metrics['min_price']}
Max Price: ${metrics['max_price']}
Price Range: ${metrics['price_range']}
Volatility: {metrics['volatility']}
Observations: {metrics['observations']}

Revenue Estimates:
Scenario: {revenue['scenario']}
Battery Size: {revenue['battery_size_mwh']} MWh
Efficiency: {revenue['efficiency']}
Cycles per day: {revenue['cycles_per_day']}
Simple Revenue Estimate: ${revenue['simple_revenue_estimate']}
Arbitrage Proxy Revenue: ${revenue['arbitrage_proxy_revenue']}

Risk Level: {risk_level}

Time Window: {start_date} to {end_date}

Requirements:
- Analytical tone
- Investor focused
- Clear risks and opportunities
- No bullet points
- Under 200 words
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    memo_text = response.content[0].text.strip()

    return memo_text
