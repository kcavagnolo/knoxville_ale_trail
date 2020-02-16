import json

with open('data/hours.json') as f:
    hours = json.load(f)

print(json.dumps(hours, indent=4))
print("====")

hours = hours['structured']
for h in hours:
    open_hour = h['start']
    close_hour = h['duration']
    days = h['recurrence'].split(';')[1].split(':')[1].split(',')
    print(days, open_hour, close_hour)