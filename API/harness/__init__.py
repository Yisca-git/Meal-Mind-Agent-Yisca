def trace(component, message):
    """Every runtime action is printed with the harness file that performed it."""
    print(f"[{component}.py] {message}", flush=True)
