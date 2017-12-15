import requests
import json
import time

ACCUWEATHER_API = "fikrPxMEvARvDvYjZ04HsmJfuArj4Fv1"
LOCATION = "60607"
LOCAL_KEY = "2626574"
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/391080178060754956/LxynWpgS1SiTwA2pqyM_kDVtYvpwJzGyRlL4AGoR3eYbBr2lOTQmyGiqmH1Rg0VUnRUE"

weather = requests.get(url="http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{}?apikey={}&details=False"
                       .format(LOCAL_KEY, ACCUWEATHER_API))



weather_json = json.loads(weather.content.decode())

content = "Weather for {}\n".format(LOCATION)
print(weather_json)
for hour in weather_json:
    t = time.localtime(int(hour['EpochDateTime']))
    content += "{}: {}\n".format(time.strftime("%H:%M", t), hour["IconPhrase"])

data = {
    "username": "Accuweather",
    "content": content
}

requests.post(url=DISCORD_WEBHOOK, data=data)

