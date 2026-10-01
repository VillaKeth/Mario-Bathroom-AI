"""Download MaleCNS v1.0 (~1.1 GB) and build the fly-brain cache. Run once per machine.

    python scripts/fetch_connectome.py [--dir DIR] [--rebuild]

Data: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from server.brain import connectome  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=None, help="data dir (default ~/.cache/mario_ai/connectome/malecns_v1)")
    ap.add_argument("--rebuild", action="store_true", help="rebuild net_v1.npz from the raw feathers")
    args = ap.parse_args()
    d = connectome.resolve_dir(args.dir)
    if args.rebuild and os.path.isfile(connectome.cache_path(d)):
        os.remove(connectome.cache_path(d))

    def progress(stage, frac):
        print(f"\r{stage:6s} {frac * 100:5.1f}%", end="", flush=True)

    net = connectome.ensure(d, auto_fetch=True, progress=progress)
    print(f"\nready: {net.n_neurons:,} neurons, {net.n_connections:,} connections, "
          f"{net.n_synapses:,} synapses -> {connectome.cache_path(d)}")


if __name__ == "__main__":
    main()
