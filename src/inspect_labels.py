import pandas as pd
import glob
import os

files = glob.glob(r"datasets\CIC-IDS2018\*.parquet")

print("LABEL DISTRIBUTIONS")
print("=" * 80)

for f in files:
    print()
    print(os.path.basename(f))

    labels = pd.read_parquet(
        f,
        columns=["Label"]
    )["Label"]

    print(labels.value_counts().to_string())