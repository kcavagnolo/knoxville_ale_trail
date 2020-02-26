import json
import datetime as dt

with open('data/hours.json') as f:
    hours = json.load(f)

print(json.dumps(hours, indent=4))
print("====")

days = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
hours_operation = {'open': None, 'close': None}
weekly_hours = {}
for day in days:
    weekly_hours[day] = hours_operation.copy()

periods = hours['structured']
for period in periods:
    open_time = dt.datetime.strptime(period['start'][1:], '%H%M%S')
    hours, minutes = period['duration'][2:-1].split('H')
    close_time = open_time + dt.timedelta(hours=int(hours), minutes=int(minutes))
    recurrence = dict(x.split(":") for x in period['recurrence'].split(";"))
    for day in recurrence['BYDAY'].split(','):
        weekly_hours[day]['open'] = open_time.time()
        weekly_hours[day]['close'] = close_time.time()
print(weekly_hours)