# The Fly

A party character with no script. Its brain is a spiking simulation of the whole
male fruit fly central nervous system, 166,700 neurons and 25.6 M connections.
Whatever those neurons do, the fly does.

- Sweet words land on its sugar taste neurons. Insults taste bitter.
- Shouting is sound on its antennae. "Swat" is a looming shadow.
- "Blow" is a puff of air on its antennae.

Its words (never more than six) are drawn from a closed fly vocabulary and describe
only what fired.

## Credits (required)

- **Connectome:** MaleCNS v1.0: Janelia FlyEM with the University of Cambridge,
  MRC LMB and Google Research. Licensed CC BY 4.0. This project preprocesses it
  into a signed weight matrix (`server/brain/connectome.py`).
- **Neuron model:** Shiu, P.K. et al. "A Drosophila computational brain model reveals
  sensorimotor processing." *Nature* 634, 210–219 (2024). Its parameters are used
  with one global gain of 0.5, calibrated for MaleCNS; see `brain/calibration.json`.
- **Inferred, not measured:** MaleCNS does not label taste modality. The bitter
  group (LB1a–e) was identified with Shiu's co-activation test.

## Known model behavior

At gain 0.5 the literature pathways fire (sugar → proboscis, looming → giant fiber,
antenna → grooming) and die when the wiring is shuffled. But the network is still
supercritical over longer runs: strong bitter, antenna or looming drive, or even a
few hundred random sensory spikes, can ignite most of the brain (about 16,000
neurons, including the mushroom body), and once ignited the activity never decays.
The real fly avoids this with mechanisms the point-neuron model does not have
(adaptation, synaptic depression, graded inhibition). So each reaction is a
separate 500 ms trial from rest (`brain.persist: false`), as in Shiu et al., and
idle noise is kept below the level that ignites. The brain panel shows the spike
count, so an ignited window is visible.

## Setup

Run `python scripts/fetch_connectome.py` once. It downloads about 1.1 GB into
`~/.cache/mario_ai/connectome/` and builds the cache. With `brain.auto_fetch: true`,
the server also does this on first start; the fly stays still until it finishes.

Design: `docs/superpowers/specs/2026-09-25-fly-brain-design.md`.
