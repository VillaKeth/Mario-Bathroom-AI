"""Fly brain: a whole-CNS spiking simulation of the MaleCNS v1.0 fruit fly connectome.

  connectome   download + preprocess MaleCNS into one cached .npz
  engine       leaky integrate-and-fire kernel (numba)
  populations  named sensory inputs / motor readouts, resolved by cell type
  worker       the subprocess that owns the engine (JSON lines on stdio)
  client       async server-side handle on that subprocess
  senses       party event -> stimulus
  behavior     readout rates -> one behavior
  words        behavior -> at most six grounded words
  voice        Edge speech + wing-buzz ring mod, takeoff buzz
  fly          the character: ties it all together

Connectome: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0.
Model: Shiu et al., "A Drosophila computational brain model reveals
sensorimotor processing", Nature 634, 210-219 (2024).
Design: docs/superpowers/specs/2026-09-25-fly-brain-design.md
"""
