
# Minimal helpers

def clamp(v: float, vmin: float, vmax: float) -> float:
    return max(vmin, min(v, vmax))

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
