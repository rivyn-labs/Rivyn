"""
AETHER LogHub Dataset Download CLI.

Supports both:
  1. Full Parallel Download of all 16 LogHub datasets organized by domain:
     python scripts/download_datasets.py --all
  2. Quick Sample Bootstrap for core hackathon demo datasets (HDFS, BGL, Linux, OpenStack):
     python scripts/download_datasets.py --quick
"""

import os
import sys
import argparse
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_URL = "https://raw.githubusercontent.com/logpai/loghub/master"
CORE_DATASETS = {
    "hdfs": f"{BASE_URL}/HDFS/HDFS_2k.log",
    "bgl": f"{BASE_URL}/BGL/BGL_2k.log",
    "linux": f"{BASE_URL}/Linux/Linux_2k.log",
    "openstack": f"{BASE_URL}/OpenStack/OpenStack_2k.log"
}


def download_quick_samples(target_dir: str = "data/samples"):
    """Quickly ensure core 4 sample datasets exist in data/samples/."""
    os.makedirs(target_dir, exist_ok=True)
    for name, url in CORE_DATASETS.items():
        out_path = os.path.join(target_dir, f"{name}_sample.log")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            logging.info(f"Dataset '{name}' already present at {out_path}")
            continue
        logging.info(f"Downloading {name} from {url}...")
        try:
            urllib.request.urlretrieve(url, out_path)
            logging.info(f"Saved {name} ({os.path.getsize(out_path)} bytes) to {out_path}")
        except Exception as e:
            logging.error(f"Failed to download {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download and organize LogHub benchmark datasets.")
    parser.add_argument("--all", action="store_true", default=True, help="Download and organize all 16 LogHub datasets in parallel (default)")
    parser.add_argument("--quick", action="store_true", help="Download only the 4 core sample datasets into data/samples/")
    parser.add_argument("--workers", type=int, default=8, help="Number of concurrent download threads (default: 8)")
    args = parser.parse_args()

    # Always ensure quick samples are ready
    download_quick_samples()

    if args.quick and not args.all:
        logging.info("Quick sample setup complete.")
        return

    # Run full parallel download across all 16 datasets
    try:
        from scripts.download_loghub_parallel import download_all_parallel, cleanup_temp_directories
        download_all_parallel(max_workers=args.workers)
        cleanup_temp_directories()
    except ImportError:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.download_loghub_parallel import download_all_parallel, cleanup_temp_directories
        download_all_parallel(max_workers=args.workers)
        cleanup_temp_directories()


if __name__ == "__main__":
    main()
