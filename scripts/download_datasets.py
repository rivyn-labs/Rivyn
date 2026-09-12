"""
Download and prepare LogHub sample datasets for testing and demonstrations.
Supported datasets from logpai/loghub:
- HDFS (Hadoop Distributed File System)
- BGL (BlueGene/L Supercomputer)
- Linux (Linux System / Auth logs)
- OpenStack (OpenStack Cloud Infrastructure)
"""

import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_URL = "https://raw.githubusercontent.com/logpai/loghub/master"
DATASETS = {
    "hdfs": f"{BASE_URL}/HDFS/HDFS_2k.log",
    "bgl": f"{BASE_URL}/BGL/BGL_2k.log",
    "linux": f"{BASE_URL}/Linux/Linux_2k.log",
    "openstack": f"{BASE_URL}/OpenStack/OpenStack_2k.log"
}

def download_samples(target_dir: str = "data/samples"):
    os.makedirs(target_dir, exist_ok=True)
    for name, url in DATASETS.items():
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

if __name__ == "__main__":
    download_samples()
