import requests
import json
import time
import os

ACCUWEATHER_API = "fikrPxMEvARvDvYjZ04HsmJfuArj4Fv1"
ACCUWEATHER_ICON = "https://apidev.accuweather.com/developers/Media/Default/WeatherIcons/{0:02d}-s.png"
LOCATION = "60607"
LOCAL_KEY = "2626574"
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/391080178060754956/LxynWpgS1SiTwA2pqyM_kDVtYvpwJzGyRlL4AGoR3eYbBr2lOTQmyGiqmH1Rg0VUnRUE"

os.environ['TZ'] = 'America/Chicago'
time.tzset()

weather = requests.get(url="http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{}?apikey={}&details=False"
                       .format(LOCAL_KEY, ACCUWEATHER_API))
if weather.ok is not True:
    print(weather.content)
    exit(1)

weather_json = json.loads(weather.content.decode())

embeds = []
for hour in weather_json:
    lt = time.localtime(int(hour['EpochDateTime']))
    description = "{}: {}\n".format(time.strftime("%H:%M", lt), hour["IconPhrase"])
    embed = {
        "title": time.strftime("%H:%M", lt),
        "thumbnail": {
            "url": ACCUWEATHER_ICON.format(hour['WeatherIcon'])
        },
        "description": hour['IconPhrase'].encode(),
        "url": hour['Link'].encode()
    }
    embeds.append(embed)

data = {
    "username": "Accuweather",
    "content": "The hourly weather forecast for today is: ",
    "avatar_url": "https://pbs.twimg.com/profile_images/879422659620163584/wudfVGeL_400x400.jpg",
    "embeds": embeds
}
r = requests.post(url=DISCORD_WEBHOOK, json=data, timeout=5)
if r.ok is True:
    print("Successfully sent message")
else:
    print(r.content)
    print(data)

# data = {
#     #"content": "Hello",
#     "username": "Accuweather",
#     "avatar_url": "https://pbs.twimg.com/profile_images/879422659620163584/wudfVGeL_400x400.jpg",
#     "embeds": [
#         {
#             "url": "http://www.accuweather.com/en/us/little-italy-il/60612/hourly-weather-forecast/2626574?day=1&hbhhour=11&lang=en-us",
#             "description": "Mostly cloudy",
#             "thumbnail": {"url": "https://apidev.accuweather.com/developers/Media/Default/WeatherIcons/06-s.png"},
#             "title": "11:00"
#         },
#         {
#             "url": "http://www.accuweather.com/en/us/little-italy-il/60612/hourly-weather-forecast/2626574?day=1&hbhhour=11&lang=en-us",
#             "description": "Mostly cloudy",
#             "thumbnail": {"url": "https://apidev.accuweather.com/developers/Media/Default/WeatherIcons/06-s.png"},
#             "title": "11:00"
#         }
#     ]
# }
#
# r = requests.post(url=DISCORD_WEBHOOK, json=data, timeout=5)
#
# if r.ok is True:
#     print("Successfully sent message")
# else:
#     print(r.content)
#     print(data)

