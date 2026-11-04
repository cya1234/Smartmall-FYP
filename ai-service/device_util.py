"""Pick the best available torch device: CUDA, then Apple Silicon MPS, then CPU.

The AI services were written against a single RTX 4070, so `cuda` was assumed
everywhere. Running the same code on a MacBook needs three things:

  1. a device chosen at runtime instead of hard-coded,
  2. MPS-safe dtype handling (float16 works on Apple GPUs, bfloat16 mostly does not),
  3. a CPU generator for diffusion sampling — torch.Generator("mps") is not
     implemented, so the seed has to live on the CPU and the latents get moved.

Import this from the service before touching torch.
"""
import os


def torch_module():
    import torch  # noqa: PLC0415 - imported lazily so --help works without torch
    return torch


def pick_device(torch=None):
    """Return 'cuda', 'mps' or 'cpu' — whichever is actually usable."""
    t = torch or torch_module()
    if t.cuda.is_available():
        return "cuda"
    mps = getattr(t.backends, "mps", None) if hasattr(t, "backends") else None
    if mps is not None and getattr(mps, "is_available", lambda: False)():
        return "mps"
    return "cpu"


def pick_dtype(torch=None, device=None):
    """float16 on GPUs, including Apple's; float32 on CPU."""
    t = torch or torch_module()
    dev = device or pick_device(t)
    if dev in ("cuda", "mps"):
        return t.float16
    return t.float32


def device_name(torch=None, device=None):
    """A human-readable GPU name for /health, or None when there is none."""
    t = torch or torch_module()
    dev = device or pick_device(t)
    try:
        if dev == "cuda":
            return t.cuda.get_device_name(0)
        if dev == "mps":
            import platform
            return f"Apple Silicon GPU ({platform.machine()})"
    except Exception:
        return None
    return None


def memory_gb(torch=None, device=None):
    """Allocated VRAM in GiB where the backend can report it."""
    t = torch or torch_module()
    dev = device or pick_device(t)
    try:
        if dev == "cuda":
            return round(t.cuda.memory_allocated() / 2**30, 2)
        if dev == "mps":
            return round(t.mps.current_allocated_memory() / 2**30, 2)
    except Exception:
        return None
    return None


def generator(torch=None, device=None, seed=0):
    """A seeded generator that works on every backend.

    torch.Generator(device="mps") raises, so the generator always lives on the CPU;
    diffusers moves the sampled latents to the pipeline device itself.
    """
    t = torch or torch_module()
    dev = device or pick_device(t)
    gen = t.Generator(device="cpu" if dev == "mps" else dev)
    gen.manual_seed(int(seed))
    return gen


def enable_mps_fallback():
    """Let unimplemented MPS ops fall back to CPU instead of raising.

    Must run before the first CUDA/MPS allocation, so call it at import time.
    """
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
