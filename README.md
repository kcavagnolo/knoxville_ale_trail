# Knoxville Ale Trail

So you want to traverse the [Knoxville Ale Trail](https://knoxvillebrewers.com/ale-trail/) but are uncertain of the best route to take? If your goal is to visit all of the breweries on the trail, and you have a Friday from 5p until Sunday at 8p, then here is the route you need to take. Existing visualizations:

* A pre-computed solution is [available here](data/route.geojson). The marker colors indicate the order (start with red and end at violet) ROYGBIV. Click on the markers to get details of each stop.
* A draft interactive map is [available here](https://www.kcavagnolo.com/knoxville_ale_trail/). Clone this repo and load that HTML locally to interact with the route.

Note that raw legs of the routing solution from the Optimization API are encoded polyline which is [easy to parse in JS](https://github.com/mapbox/polyline), but GeoJSON is more portable. [Some code that decodes polylines](https://gist.github.com/signed0/2031157). Alternatively, I'm using a polyline lib (see credit below).

version: v0.2.0

## Mapbox Styling HowTo's

* [Loading options for GeoJSON](https://docs.mapbox.com/help/troubleshooting/working-with-large-geojson-data/)
* [Add multiple geometries in GeoJSON](https://docs.mapbox.com/mapbox-gl-js/example/multiple-geometries/)
* [Stylize a GeoJSON line](https://docs.mapbox.com/mapbox-gl-js/example/geojson-line/)
* [Interactively change a map style](https://docs.mapbox.com/mapbox-gl-js/example/setstyle/)
* [Toggle visible layers](https://docs.mapbox.com/mapbox-gl-js/example/toggle-layers/)
* [Display a popup with data](https://docs.mapbox.com/mapbox-gl-js/example/popup-on-click/)
* [Animate a point along a route](https://docs.mapbox.com/mapbox-gl-js/example/animate-point-along-route/)

## Setup

You need several Mapbox tools installed if you want to create and upload [Mapbox vector tiles (`mbtiles`)](https://docs.mapbox.com/vector-tiles/reference/):

* [Mapbox CLI](https://github.com/mapbox/mapbox-cli-py)
* [`tippecanoe`](https://github.com/mapbox/tippecanoe)

Alternatively, Mapbox has a [tilesets CLI](https://github.com/mapbox/tilesets-cli) in beta for interacting with their new tilset source data model and a [step-by-step guide](https://docs.mapbox.com/help/tutorials/get-started-tilesets-api-and-cli/).

## Usage

Then run the simplistic command line script:

```bash
python3 trail.py --geocode --optimize --geojson -d data/
```

Finally, create and upload the mbtiles:

```bash
sh update_mapbox.sh
```

## Versioning

I like the old school [`bumpversion`](https://github.com/peritus/bumpversion):

```bash
bumpversion minor --verbose
```

## Code Quality

1. Install and configure [Sonarqube](https://docs.sonarqube.org/latest/) or launch a maintained container:

    ```bash
    docker run -d --name sonarqube -p 9000:9000 sonarqube
    ```

2. Setup a `sonar-project.properties` file with configurations for scans.

3. Run a scan:

    ```bash
    sonar-scanner
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
* Display itinerary as Gantt.
* Add animation to markers on arrival.
* Dig into this [awesome viz](https://github.com/chriswhong/nyctaxi)

## Credits

* [MapAnything routing optimization engine](https://developer.mapanything.com/)
* [HERE geocoder](https://developer.here.com/documentation/geocoder/dev_guide/topics/what-is.html)
* [hicsail `polyline` decoder](https://github.com/hicsail/polyline)
* [jazzband `geojson` utilities](https://github.com/jazzband/geojson)
* [vaab `colour` library](https://github.com/vaab/colour)
* [Mapbox](https://www.mapbox.com/about/maps/)
* [OpenStreetMap](http://www.openstreetmap.org/about/)
* [Turf.js](https://turfjs.org/)

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](LICENSE).

![Creative Commons License](https://i.creativecommons.org/l/by-sa/4.0/88x31.png "license")
