import requests
import os
from urllib.parse import urlparse, unquote

def download_file(url, folder):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get filename from Content-Disposition if available
        filename = ''
        if "Content-Disposition" in response.headers:
            cd = response.headers["Content-Disposition"]
            if 'filename=' in cd:
                filename = unquote(cd.split('filename=')[1].strip('"'))
        
        # Fallback to URL path
        if not filename:
            path = urlparse(url).path
            filename = unquote(os.path.basename(path))
        
        # Default if still empty
        if not filename:
            filename = 'unknown_file_' + url.replace('/', '_')[-20:]  # Shortened for safety
        
        filepath = os.path.join(folder, filename)
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Downloaded {url} as {filename}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

# Create folder
folder = 'mario_assets'
os.makedirs(folder, exist_ok=True)

# Read links from the attached file
file_name = "mario_asset_links.txt"
try:
    with open(file_name, 'r') as f:
        links = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print(f"File '{file_name}' not found. Please ensure it's in the current directory.")
    links = []

for link in links:
    download_file(link, folder)

print("Download complete. Check the 'mario_assets' folder. Note: For links that are web pages (e.g., Sketchfab, DeviantArt), the script will download the HTML content. For actual downloads from those sites, you may need to visit them manually and click the download buttons, as they often require interaction or login.")