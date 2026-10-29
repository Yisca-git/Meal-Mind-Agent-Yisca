# USD per million tokens. Cache write is the 1.25x premium on input; cache read is the discounted rate.
PRICES = {"claude-opus-5-5": {"input": 4.0, "cache_write": 5.0, "cache_read": 0.20, "output": 20.0}}


def cost_usd(model, tokens):
    price = PRICES[model]
    return sum(tokens[k] * price[k] for k in ("input", "cache_read", "cache_write", "output")) / 1_000_000
