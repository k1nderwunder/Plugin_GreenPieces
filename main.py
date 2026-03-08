import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YANDEX_API_KEY")

url = "https://static-maps.yandex.ru/v1"
params = {
    "ll": "92.8670,56.0184",   # долгота, широта
    "z": "18",                 # большой зум
    "size": "650,450",
    "lang": "ru_RU",
    "scale": "2",              # увеличивает объекты на карте
    "apikey": API_KEY,
}

response = requests.get(url, params=params, timeout=30)
print(response.status_code)
print(response.url)
response.raise_for_status()

with open("map_zoomed.png", "wb") as f:
    f.write(response.content)

print("Сохранено: map_zoomed.png")