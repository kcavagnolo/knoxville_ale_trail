# Knoxville Ale Trail

So you want to traverse the [Knoxville Ale Trail](https://knoxvillebrewers.com/ale-trail/) but are uncertain of the best route to take? If your goal is to visit all of the breweries on the trail, and you have a Friday from 5p until Sunday at 8p, then here is the route you need to take.

A pre-computed solution is [available here](data/route.geojson). The marker colors indicate the order (start with red and end at violet) ROYGBIV. Click on the markers to get details of each stop.

Routes are encoded polyline which is [easy to parse in JS](https://github.com/mapbox/polyline), but GeoJSON is more portable. [Some code that decodes polylines](https://gist.github.com/signed0/2031157). Alternatively, I'm using a polyline lib (see credit below).

## Usage

Right now, this is a dumb command line script:

```bash
python3 trail.py --geocode --optimize --geojson -d data/
```

## Code Quality

1. Install and configure [Sonarqube](https://docs.sonarqube.org/latest/).

2. Setup a `sonar-project.properties` file with configurations for scans.

3. Run a scan:

    ```bash
    sonar-scanner \
    -Dsonar.host.url=$SONAR_SERVER \
    -Dsonar.login=$SONARQUBE_TOKEN
    ```

## TODOs

* Add dynamic time handling:

    ```python
    # set dynamic shift
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    now = datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=utc_offset))
    later = now + datetime.timedelta(hours=168)
    ```

* Add support for appointments:

    ```python
     if 'elkmont' in brewery_name:
        appointment = [
            {
                "appointment_start": appt_start,
                "appointment_end": appt_end
            }
        ]
        order['appointments'] = appointment
        order['duration'] = 2.5*3600
    ```

* Add `time_windows` to each location for hours of operation.
* Display intinerary as Gantt.

## Credits

* [MapAnything geocoder and routing optimization engine](https://developer.mapanything.com/)
* [hicsail's `polyline` decoder](https://github.com/hicsail/polyline)
* [jazzband's `geojson` utilities](https://github.com/jazzband/geojson)
* [vaab's `colour` library](https://github.com/vaab/colour)
