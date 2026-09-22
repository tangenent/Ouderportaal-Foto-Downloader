import os
import requests
from datetime import datetime, timezone
import getpass
import time
import argparse

# ==== CONFIGURATION ====
START = 0
STEP = 6
DOWNLOAD_DIR = "photos"
# =======================

# These will be set later
base_url = None
login_url = None
refresh_url = None
timeline_url = None
session = None
auth_token = None

def get_auth_token(username, password):
    global session, auth_token

    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session = requests.Session()
    session.mount('https://', adapter)
    
    payload = {"username": username, "password": password}
    response = session.put(login_url, json=payload, timeout=20)
    response.raise_for_status()

    data = response.json()
    auth_token = data.get("authToken")

    if not auth_token:
        raise RuntimeError("❌ authToken not found in login response.")

    if not session.cookies.get("__Host-refresh_token"):
        raise RuntimeError("❌ __Host-refresh_token cookie not found in login response.")
    

def refresh_login():
    global auth_token

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = session.put(refresh_url, headers=headers, json={}, timeout=20)
    response.raise_for_status()

    data = response.json()
    auth_token = data.get("authToken")
    
    if not auth_token:
        raise RuntimeError("❌ authToken not found in refresh response.")

    if not session.cookies.get("__Host-refresh_token"):
        raise RuntimeError("❌ __Host-refresh_token cookie not found in refresh response.")

    print("🔄 Token successfully refreshed")


def fetch_json(url):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = session.get(url, headers=headers, timeout=20)

    if response.status_code == 401:
        print("🔐 401 received: Refreshing token")
        refresh_login()
        headers["Authorization"] = f"Bearer {auth_token}"
        response = session.get(url, headers=headers, timeout=20)

    response.raise_for_status()
    return response.json()


def download_photo(url, filepath):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = session.get(url, headers=headers, timeout=30)

    if response.status_code == 401:
        print("🔐 401 received: Refreshing token")
        refresh_login()
        headers["Authorization"] = f"Bearer {auth_token}"
        response = session.get(url, headers=headers, timeout=30)

    response.raise_for_status()

    with open(filepath, "wb") as f:
        f.write(response.content)

    print(f"✅ Saved: {filepath}")
    

def process_data(data):
    if not isinstance(data, list):
        return 0

    days_processed = 0

    for day_entry in data:
        date_ms = day_entry.get("date")
        photos = day_entry.get("photos", [])

        days_processed += 1
        date_str = datetime.fromtimestamp(
            date_ms / 1000, timezone.utc
        ).strftime("%Y%m%d")

        for i, photo in enumerate(photos, start=1):
            url = photo.get("fullSizeUrl")
            if photo.get("mediaType") == "video":
                filename = f"{date_str}-{i:02d}.mp4"
            else:
                filename = f"{date_str}-{i:02d}.jpg"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            download_photo(url, filepath)

    return days_processed


# ==== MAIN ====
print("\nOuderportaal Foto Downloader\n")

try:
    parser = argparse.ArgumentParser(description="Ouderportaal Photo Downloader")

    parser.add_argument("--org", help="Organisation name")
    parser.add_argument("--username", help="Username (email)")
    parser.add_argument("--password", help="Password")
    parser.add_argument("--days", type=int, help="Amount of days to fetch")

    args = parser.parse_args()

    ORG = args.org or input("Enter your Organisation: ").strip()
    USERNAME = args.username or input("Enter your username (email): ").strip()
    PASSWORD = args.password or getpass.getpass("Enter your password (input hidden): ").strip()
    END = args.days if args.days is not None else int(input("Enter the amount of days (e.g. 60): ").strip())
    
    DOWNLOAD_DIR = f"{ORG}_{DOWNLOAD_DIR}"
    base_url = f"https://{ORG}.ouderportaal.nl"
    login_url = f"{base_url}/auth-api/login"
    refresh_url = f"{base_url}/auth-api/token"
    timeline_url = f"{base_url}/restservices-parent/timeline/cards/v2/{{}}"
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
	
    print(f"\n🔒 Authenticating on {login_url}")
    get_auth_token(USERNAME, PASSWORD)
    print("🔓 Authenticated")

    current_step = STEP
    for page in range(START, END + 1, current_step):
        url = timeline_url.format(page)
        print(f"\n🌐 Fetching page {page}")
        data = fetch_json(url)
        processed = process_data(data)
        print(f"📊 Days processed: {processed}")

        if processed == 0:
            break

        current_step = processed

    print("\n✅ All downloads complete!")
except Exception as e:
    print(e)