# Knoxville Ale Trail

So you want to traverse the [Knoxville Ale Trail](https://knoxvillebrewers.com/ale-trail/) but are uncertain of the best route to take? If your goal is to visit all of the breweries on the trail, and you have a Friday from 5p until Sunday at 8p, then here is the route you need to take.

[MapAnything geocoder and routing optimization engine](https://developer.mapanything.com/)

## Code Quality

1. Install and configure [Sonarqube](https://docs.sonarqube.org/latest/).

2. Setup a `sonar-project.properties` file with configurations for scans.

3. Run a scan:

    ```bash
    sonar-scanner \
    -Dsonar.host.url=$SONAR_SERVER \
    -Dsonar.login=$SONARQUBE_TOKEN
    ```

## TODO's

* TODO: Add dynamic time handling:

    ```python
    # set dynamic shift
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    now = datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=utc_offset))
    later = now + datetime.timedelta(hours=168)
    ```

* TODO: Add support for appointments:

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
