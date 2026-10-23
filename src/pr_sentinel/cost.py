"""Model token pricing and review cost estimation."""
from __future__ import annotations

# (input_usd_per_million, output_usd_per_million)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI Flagship & General Models
    "gpt-5.4": (2.50, 10.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gpt-4o-2024-05-13": (5.00, 15.00),
    # Mini Models
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    # Reasoning Models
    "o1": (15.00, 60.00),
    "o1-preview": (15.00, 60.00),
    "o1-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    # Legacy Models
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}

DEFAULT_PRICING = (2.50, 10.00)


def find_pricing(model: str | None) -> tuple[float, float] | None:
    """Find pricing tuple (input_per_m, output_per_m) for a model name."""
    if not model:
        return None
    m = model.strip().lower()
    if m in MODEL_PRICING:
        return MODEL_PRICING[m]

    for key, price in MODEL_PRICING.items():
        if m.startswith(key):
            return price

    if "4o-mini" in m:
        return MODEL_PRICING["gpt-4o-mini"]
    if "4o" in m:
        return MODEL_PRICING["gpt-4o"]
    if "o3-mini" in m:
        return MODEL_PRICING["o3-mini"]
    if "o1-mini" in m:
        return MODEL_PRICING["o1-mini"]
    if "o1" in m:
        return MODEL_PRICING["o1"]
    if "gpt-5" in m:
        return MODEL_PRICING["gpt-5.4"]
    if "gpt-4" in m:
        return MODEL_PRICING["gpt-4-turbo"]
    if "gpt-3.5" in m:
        return MODEL_PRICING["gpt-3.5-turbo"]

    return DEFAULT_PRICING


def estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate total USD cost based on token counts and model pricing."""
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    pricing = find_pricing(model)
    if not pricing:
        return None
    inp_per_m, out_per_m = pricing
    return (max(input_tokens, 0) * inp_per_m + max(output_tokens, 0) * out_per_m) / 1_000_000.0


def format_cost(cost: float | None) -> str | None:
    """Format USD cost with appropriate precision."""
    if cost is None or cost < 0:
        return None
    if cost >= 1.0:
        return f"${cost:.2f}"
    if cost >= 0.01:
        return f"${cost:.3f}"
    if cost >= 0.0005:
        return f"${cost:.4f}"
    if cost > 0:
        return f"${cost:.4f}"
    return "$0.00"
