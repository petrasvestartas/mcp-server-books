"""Cross-platform regeneration and optional upload of LIBRARY.md from Cloudflare R2.

    python3 -I tools/r2_library_map.py [--upload]

Downloads README.md and INDEX.md of each book prefix in s3://brg-books/ plus PROCESSED.md into a temporary
directory, runs tools/library_map.py, writes LIBRARY.md beside tools/, and uploads s3://brg-books/LIBRARY.md
when --upload is given. Uses AWS CLI profile R2_PROFILE (default: r2-books).
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

TOOLS = pathlib.Path(__file__).resolve().parent


def r2_cmd(profile: str, endpoint: str, *args: str) -> list[str]:
    return ["aws", "--profile", profile, "--region", "auto", "--endpoint-url", endpoint, *args]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()

    bucket = os.environ.get("R2_BUCKET", "brg-books")
    endpoint = os.environ.get("R2_ENDPOINT", "https://7a0d8a20a1daaaab0534f11839b6a552.r2.cloudflarestorage.com")
    profile = os.environ.get("R2_PROFILE", "r2-books")

    ls_res = subprocess.run(r2_cmd(profile, endpoint, "s3", "ls", f"s3://{bucket}/"), capture_output=True, text=True, check=True)
    prefixes = []
    for line in ls_res.stdout.splitlines():
        m = re.match(r"^\s*PRE\s+([^/]+)/\s*$", line)
        if m and m.group(1) not in ("RAW", "tools"):
            prefixes.append(m.group(1))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        for b in prefixes:
            rc = subprocess.run(
                r2_cmd(profile, endpoint, "s3", "cp", f"s3://{bucket}/{b}/README.md", str(tmp / b / "README.md"), "--only-show-errors"),
                capture_output=True, text=True, check=False,
            ).returncode
            if rc != 0:
                continue
            subprocess.run(
                r2_cmd(profile, endpoint, "s3", "cp", f"s3://{bucket}/{b}/INDEX.md", str(tmp / b / "INDEX.md"), "--only-show-errors"),
                capture_output=True, text=True, check=False,
            )
        subprocess.run(
            r2_cmd(profile, endpoint, "s3", "cp", f"s3://{bucket}/PROCESSED.md", str(tmp / "PROCESSED.md"), "--only-show-errors"),
            capture_output=True, text=True, check=False,
        )
        (tmp / "tools").mkdir(exist_ok=True)
        shutil.copy2(TOOLS / "library_map.py", tmp / "tools" / "library_map.py")
        subprocess.run([sys.executable, "-I", "-X", "utf8", str(tmp / "tools" / "library_map.py")], cwd=tmp, check=True)
        out_lib = TOOLS.parent / "LIBRARY.md"
        shutil.copy2(tmp / "LIBRARY.md", out_lib)
        print(f"saved {out_lib}")
        if args.upload:
            subprocess.run(
                r2_cmd(profile, endpoint, "s3", "cp", str(tmp / "LIBRARY.md"), f"s3://{bucket}/LIBRARY.md", "--only-show-errors"),
                check=True,
            )
            print("uploaded LIBRARY.md")


if __name__ == "__main__":
    main()
