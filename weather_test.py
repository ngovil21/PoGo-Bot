import requests
import json
import time
import os

ACCUWEATHER_API = "fikrPxMEvARvDvYjZ04HsmJfuArj4Fv1"
ACCUWEATHER_ICON = "https://developer.accuweather.com/sites/default/files/{}-s.png"
LOCATION = "60607"
LOCAL_KEY = "2626574"
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/391080178060754956/LxynWpgS1SiTwA2pqyM_kDVtYvpwJzGyRlL4AGoR3eYbBr2lOTQmyGiqmH1Rg0VUnRUE"

os.environ['TZ'] = 'America/Chicago'
time.tzset()

weather = requests.get(url="http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{}?apikey={}&details=False"
                       .format(LOCAL_KEY, ACCUWEATHER_API))
weather_json = json.loads(weather.content.decode())

embeds = []
headers = {'Content-Type': 'application/json'}
for hour in weather_json:
    lt = time.localtime(int(hour['EpochDateTime']))
    description = "{}: {}\n".format(time.strftime("%H:%M", lt), hour["IconPhrase"])
    embed = {
        'title': time.strftime("%H:%M", lt),
        'thumbnail': ACCUWEATHER_ICON.format(hour['WeatherIcon']),
        'description': hour['IconPhrase'],
        'url': hour['Link']
    }

    data = {
        'username': 'Accuweather',
        'avatar_url': 'https://pbs.twimg.com/profile_images/879422659620163584/wudfVGeL_400x400.jpg',
        'embed': embed
    }
    r = requests.post(url=DISCORD_WEBHOOK, data=data, headers=headers)
    if r.status_code == 400:
        print(r.content)
        print(data)


