"""Which device the detectors run on, when the default is not the one wanted.

Left alone, ultralytics takes a CUDA card if there is one and the CPU if not;
it never takes an Apple GPU unasked. ``analyze --device`` reached only the
overhead stone detector, so on a Mac the end-camera, broom and spin models
stayed on the CPU whatever was asked. `ENV_VAR` names a device for all of
them -- ``mps`` on an Apple GPU -- and ``--device`` sets it.

Opt-in, never detected: an Apple GPU does not compute exactly what a CPU or a
CUDA card does, so a timeline made on one is not byte for byte the other's.
Unset, every call is what it was.
"""

import os

ENV_VAR = "CURLING_SCORE_DEVICE"


def chosen(explicit=None):
    """The device asked for: the caller's own, else `ENV_VAR`'s, else None
    (ultralytics' choice)."""
    if explicit is not None:
        return explicit
    return os.environ.get(ENV_VAR) or None


def kwargs() -> dict:
    """``device=`` for a ``predict`` call, or nothing when none was asked for,
    so an unconfigured run makes the call it always made."""
    device = chosen()
    return {} if device is None else {"device": device}


def use(device) -> None:
    """Make ``device`` the one every detector takes from here on; None leaves
    things as they are."""
    if device is not None:
        os.environ[ENV_VAR] = str(device)
