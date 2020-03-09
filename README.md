# Knoxville Ale Trail

So you want to traverse the [Knoxville Ale Trail](https://knoxvillebrewers.com/ale-trail/) but are uncertain of the best route to take? [Here's a solution](https://www.kcavagnolo.com/knoxville_ale_trail/)! Some pre-computed routes are [available here](/data/geojson). Note that raw legs of the routing solution from the Optimization API are encoded polyline which is [easy to parse in JS](https://github.com/mapbox/polyline), but GeoJSON is more portable.

version: v0.5.0

## Setup

You need several Mapbox tools installed if you want to create and upload [Mapbox vector tiles (`mbtiles`)](https://docs.mapbox.com/vector-tiles/reference/):

- [Mapbox CLI](https://github.com/mapbox/mapbox-cli-py)
- [`tippecanoe`](https://github.com/mapbox/tippecanoe)

Alternatively, Mapbox has a [tilesets CLI](https://github.com/mapbox/tilesets-cli) in beta for interacting with their new tilset source data model and a [step-by-step guide](https://docs.mapbox.com/help/tutorials/get-started-tilesets-api-and-cli/).

## Usage

Then run the simplistic command line script:

```bash
python3 trail.py --geocode --optimize --geojson -d data/ -vv
```

Convert geojson to Mapbox tile and upload to Mapbox:

```sh
python3 create_tiles.py -gd data/geojson -td data/tiles --mbtiles --upload -vv
```

## Maintenance

### Mapbox Credentials

If you're working with multiple Mapbox accounts, the scripts assume you have standard env vars like this:

```bash
export MAPBOX_USERNAME=$MAPBOX_USER_PERSONAL
export MAPBOX_ACCESS_TOKEN=$MAPBOX_ACCESS_TOKEN_PERSONAL
```

### Local Tileserver

To inspect the tiles locally, I use [TileServer GL](https://tileserver.readthedocs.io):

```sh
docker pull klokantech/tileserver-gl
cd data/tiles/
docker run -it -v $(pwd):/data -p 8080:80 klokantech/tileserver-gl
```

Now navigate to `http://localhost:8080/` and you'll find the interactive tileserver dashboard.

### Versioning

I like the old school [`bumpversion`](https://github.com/peritus/bumpversion):

```bash
bumpversion minor --verbose
```

### Code Quality

1. Install and configure [Sonarqube](https://docs.sonarqube.org/latest/) or launch a maintained container:

   ```bash
   docker run -d --name sonarqube -p 9000:9000 sonarqube
   ```

2. Setup a `sonar-project.properties` file with configurations for scans.

3. Run a scan:

   ```bash
   sonar-scanner
   ```

### TODOs

- Add support for appointments:

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

- Add `time_windows` to each location for hours of operation.
- Add animation to markers on arrival.
- Dig into [this awesome viz](https://github.com/chriswhong/nyctaxi)
- Seek inspiration from [this design](https://demos.mapbox.com/vt_polygons)
- Add minify of css and js

## Mapbox Styling HowTo's

- [Loading options for GeoJSON](https://docs.mapbox.com/help/troubleshooting/working-with-large-geojson-data/)
- [Add multiple geometries in GeoJSON](https://docs.mapbox.com/mapbox-gl-js/example/multiple-geometries/)
- [Stylize a GeoJSON line](https://docs.mapbox.com/mapbox-gl-js/example/geojson-line/)
- [Interactively change a map style](https://docs.mapbox.com/mapbox-gl-js/example/setstyle/)
- [Toggle visible layers](https://docs.mapbox.com/mapbox-gl-js/example/toggle-layers/)
- [Display a popup with data](https://docs.mapbox.com/mapbox-gl-js/example/popup-on-click/)
- [Animate a point along a route](https://docs.mapbox.com/mapbox-gl-js/example/animate-point-along-route/)
- [Change style on hover](https://docs.mapbox.com/mapbox-gl-js/example/hover-styles/)
- [Localized search](https://docs.mapbox.com/mapbox-gl-js/example/mapbox-gl-geocoder-limit-region/)

## Credits

- [MapAnything routing optimization engine](https://developer.mapanything.com/)
- [HERE geocoder](https://developer.here.com/documentation/geocoder/dev_guide/topics/what-is.html)
- [hicsail `polyline` decoder](https://github.com/hicsail/polyline)
- [jazzband `geojson` utilities](https://github.com/jazzband/geojson)
- [vaab `colour` library](https://github.com/vaab/colour)
- [Mapbox](https://www.mapbox.com/about/maps/)
- [OpenStreetMap](http://www.openstreetmap.org/about/)
- [lukasmartinelli `mapbox-gl-inspect` plugin](https://github.com/lukasmartinelli/mapbox-gl-inspect)

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](LICENSE).

![Creative Commons License](https://i.creativecommons.org/l/by-sa/4.0/88x31.png "license")
