"""Reference token counts; no runtime spatial processing."""
COUNTING_VERSION = "h3rc-latent-v1"

def visual_cost(shape):
    return int(shape[2] * (shape[3] // 2) * (shape[4] // 2))
