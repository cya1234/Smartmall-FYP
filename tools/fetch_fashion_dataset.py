"""Download the Fashion Product Images (small) parquet shards.

Source: https://huggingface.co/datasets/ashraq/fashion-product-images-small
Public dataset (Apache-2.0 metadata; images from Myntra). Used here only to give
the SmartMall catalog real product photos for CLIP visual search.
"""
import os
import sys
import urllib.request

BASE = "https://huggingface.co/datasets/ashraq/fashion-product-images-small/resolve/main/data"
FILES = [
    "train-00000-of-00002-6cff4c59f91661c3.parquet",
    "train-00001-of-00002-bb459e5ac5f01e71.parquet",
]
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "fashion")
DEST = os.path.normpath(DEST)


def main():
    os.makedirs(DEST, exist_ok=True)
    for name in FILES:
        out = os.path.join(DEST, name)
        if os.path.exists(out) and os.path.getsize(out) > 1_000_000:
            print(f"  already have {name} ({os.path.getsize(out)/1e6:.1f} MB)")
            continue
        url = f"{BASE}/{name}?download=true"
        print(f"  downloading {name} ...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "smartmall-fyp"})

        def hook(blocks, bs, total):
            if total > 0:
                pct = min(100, blocks * bs * 100 / total)
                sys.stdout.write(f"\r    {pct:5.1f}%  {blocks*bs/1e6:7.1f} / {total/1e6:.1f} MB")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, out, reporthook=hook)
        print(f"\r    done: {os.path.getsize(out)/1e6:.1f} MB")
        # verify it is a real parquet file, not an HTML error page
        with open(out, "rb") as fh:
            magic = fh.read(4)
        if magic != b"PAR1":
            print(f"    ERROR: {name} is not a parquet file (got {magic!r})")
            os.remove(out)
            return 1
    print("  dataset ready at", DEST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
