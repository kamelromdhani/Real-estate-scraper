
import requests
from bs4 import BeautifulSoup
import config

headers = config.HEADERS
url = "https://www.tayara.tn/item/appartements/sousse/sahloul/s1-directe-promoteur-sahloul-4/6970dc21181355990924cf66/"
print(f"Fetching {url}...")
response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"Content length: {len(response.content)}")
text = response.text
print(f"Price '260' in text: {'260' in text}")
print(f"Price '260000' in text: {'260000' in text}")

# Dump HTML to file for inspection
with open('debug_listing.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Saved debug_listing.html")



