import pandas as pd
import requests

df = pd.read_csv('open_potholes.csv')
for address in df.Location:
    address += ' Knoxville TN USA'
    url = 'https://api.mapanything.io/services/core/geocoding/v2?address={}'.format(address)
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': 'nice-try'
    }
    response = requests.request('GET', url, headers=headers, allow_redirects=True)
    response = response.json()
    print(str(response['data']['position']['lat'])+',',
          str(response['data']['position']['lng'])+',',
          str(response['data']['fullAddress']).replace(",", ""))
print('35.963871, -83.917753, 625 South Gay Street Suite 310 Knoxville TN 37902 USA')
