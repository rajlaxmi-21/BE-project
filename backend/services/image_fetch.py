import subprocess
import os
import time
import re

KEY = "C:/Users/Shreya/Downloads/s2dr3-keypair.pem"
SAVE_PATH = "C:/Users/Shreya/Desktop/results"
HOST = "ubuntu@18.225.177.179"


# -------------------------------
# WAIT FOR FILE ON REMOTE SERVER
# -------------------------------
def wait_for_file(remote_path, timeout=300):
    start = time.time()

    while True:
        check_cmd = f'test -f {remote_path} && echo "FOUND" || echo "WAIT"'

        result = subprocess.run(
            ["ssh", "-i", KEY, HOST, check_cmd],
            capture_output=True,
            text=True
        )

        if "FOUND" in result.stdout:
            return True

        if time.time() - start > timeout:
            raise Exception(f"Timeout waiting for {remote_path}")

        time.sleep(5)


# -------------------------------
# SAFE SCP DOWNLOAD
# -------------------------------
def download_file(remote_path, local_path):
    for attempt in range(5):
        try:
            subprocess.run([
                "scp",
                "-i", KEY,
                remote_path,
                local_path
            ], check=True)
            return
        except subprocess.CalledProcessError:
            print(f"Retrying download... attempt {attempt+1}")
            time.sleep(5)

    raise Exception(f"Failed to download {remote_path}")


# -------------------------------
# MAIN FETCH FUNCTION
# -------------------------------
def fetch_images(lat, lon):
    os.makedirs(SAVE_PATH, exist_ok=True)

    print("🚀 Running remote fetch...")

    remote_cmd = (
        f'cd ~ && '
        f'source ~/s2env/bin/activate && '
        f'python3 -c "from fetch import get_images; get_images({lat}, {lon})"'
    )

    result = subprocess.run(
        ["ssh", "-i", KEY, HOST, remote_cmd],
        capture_output=True,
        text=True
    )

    output = result.stdout
    print("SSH OUTPUT:\n", output)

    # -------------------------------
    # ✅ EXTRACT DATES FROM OUTPUT
    # -------------------------------
    current_date = None
    previous_date = None

    match1 = re.search(r"First image date:\s*(\d+)", output)
    match2 = re.search(r"Second image date:\s*(\d+)", output)

    if match1:
        current_date = match1.group(1)

    if match2:
        previous_date = match2.group(1)

    # -------------------------------
    # WAIT FOR FILES
    # -------------------------------
    print("⏳ Waiting for files...")

    wait_for_file("/home/ubuntu/results/current.tif")
    wait_for_file("/home/ubuntu/results/previous.tif")

    # -------------------------------
    # DOWNLOAD FILES
    # -------------------------------
    print("⬇️ Downloading files...")

    download_file(
        f"{HOST}:/home/ubuntu/results/current.tif",
        SAVE_PATH
    )

    download_file(
        f"{HOST}:/home/ubuntu/results/previous.tif",
        SAVE_PATH
    )

    print("✅ Download complete")

    return {
        "current": f"{SAVE_PATH}/current.tif",
        "previous": f"{SAVE_PATH}/previous.tif",
        "current_date": current_date,
        "previous_date": previous_date
    }