#!/usr/bin/env python
# coding: utf-8

import argparse
import csv
import datetime
import json
import logging
import math
import os
import re
import shutil
import sys
import time
import traceback

import geojson
import polyline
import pyproj
import requests
from colour import Color
from tqdm import tqdm


class FullPaths(argparse.Action):
    """Expand user- and relative-paths"""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, os.path.abspath(
            os.path.expanduser(values)))


def is_dir(dirname):
    """Checks if a path is an actual directory"""
    if not os.path.isdir(dirname):
        msg = "{0} is not a directory".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname


def clean_string(s):
    pattern = re.compile('[\W_]+', re.UNICODE)
    s = pattern.sub(' ', s.lower())
    return s


def iso_time(intime, time_format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strptime(intime, time_format).isoformat()


def here_geocoder(address):
    url = 'https://geocoder.ls.hereapi.com/6.2/geocode.json?apiKey={}&searchtext={}'
    apikey = os.getenv("HERE_APIKEY")
    address = address.lower().replace(" ", "+")
    lat, lng = 0.0, 0.0
    try:
        response = requests.request('GET', url.format(apikey, address))
        response = response.json()
        if len(response['Response']['View']) > 0:
            loc_data = response['Response']['View'][0]['Result'][0]['Location']
            lat = loc_data['NavigationPosition'][0]['Latitude']
            lng = loc_data['NavigationPosition'][0]['Longitude']
            address = loc_data['Address']['Label']
        else:
            logging.warning('Could not geocode: {}'.format(address))
            lat = 0.0
            lng = 0.0
    except Exception as e:
        logging.exception(e)
        logging.exception(traceback.format_exc())
    finally:
        return lat, lng, address


def mapanything_geocoder(address):
    url = 'https://api.mapanything.io/services/core/geocoding/v2?address={}'.format(
        address)
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("MAPANYTHING_APIKEY")
    }
    lat, lng = 0.0, 0.0
    try:
        response = requests.request(
            'GET', url, headers=headers, allow_redirects=True)
        response = response.json()
        if 'data' in response:
            lat = response['data']['position']['lat']
            lng = response['data']['position']['lng']
            address = response['data']['fullAddress']
        else:
            logging.warning('Could not geocode: {}'.format(address))
            lat = 0.0
            lng = 0.0
    except Exception as e:
        logging.exception(e)
        logging.exception(traceback.format_exc())
    finally:
        return lat, lng, address


def mapanything_routing(payload):
    url = 'https://public-api.mapanything.io/mare/routing/sync'
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("MAPANYTHING_APIKEY")
    }
    try:
        response = requests.request(
            'POST', url, headers=headers, data=json.dumps(payload), allow_redirects=True)
        if response.status_code != 200:
            logging.error('Optimization failed')
            msg = response.json()
            logging.error(msg['JobMessage'])
            sys.exit(1)
        else:
            response = response.json()
    except Exception as e:
        logging.exception(e)
        logging.exception(traceback.format_exc())

    return response


def write_geojson(outfile, features, bbox, crs, metadata=None):
    feature_collection = geojson.FeatureCollection(features)
    feature_collection['metadata'] = metadata
    feature_collection['bbox'] = bbox
    feature_collection['crs'] = crs
    with open(outfile, 'w') as f:
        json.dump(feature_collection, f, separators=(',', ':'), sort_keys=True)


def degrees_to_cardinal(d):
    dirs = ['N', 'NbE', 'NNE', 'NEbN', 'NE', 'NEbE', 'ENE', 'EbN',
            'E', 'EbS', 'ESE', 'SEbE', 'SE', 'SEbS', 'SSE', 'SbE',
            'S', 'SbW', 'SSW', 'SWbS', 'SW', 'SWbW', 'WSW', 'WbS',
            'W', 'WbN', 'WNW', 'NWbW', 'NW', 'NWbN', 'NNW', 'NbW']
    ix = round(d / (360. / len(dirs)))
    return dirs[ix % len(dirs)]


def main():
    # parse command line arguments
    parser = argparse.ArgumentParser(
        description='Create an optimized route for the Knoxville Ale Trail.')
    parser.add_argument("-d", "--datadir", help="directory containing data",
                        action=FullPaths, type=is_dir, required=True)
    parser.add_argument("--geocode", help="call the geocoder",
                        action="store_true")
    parser.add_argument("--optimize", help="call the optimizer",
                        action="store_true")
    parser.add_argument("--geojson", help="create geojson file of route",
                        action="store_true")
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    args = parser.parse_args()

    # I/O files -- TODO: abstract filenames
    datadir = args.datadir
    breweries = os.path.join(datadir, "csv/breweries.csv")
    geocoded_breweries = os.path.join(datadir, "json/geocoded_breweries.json")
    requestfile = os.path.join(datadir, "json/routing_opt_request.json")
    responsefile = os.path.join(datadir, "json/routing_opt_response.json")

    # geocode addresses
    if args.geocode:
        logging.info("Geocoding addresses")
        csv_lines = []
        json_lines = {}
        with open(breweries, 'r') as csvfile:
            reader = csv.reader(csvfile, skipinitialspace=True)
            next(reader, None)
            for row in tqdm(sorted(reader)):
                visited = row[0]
                brewery_name = clean_string(row[1])
                address = clean_string(' '.join(row))
                lat, lng, address = here_geocoder(address)
                csv_lines.append(','.join([
                    visited,
                    str(lat),
                    str(lng),
                    brewery_name,
                    address + "\n"])
                )
                json_lines[brewery_name] = {}
                json_lines[brewery_name]['visited'] = visited
                json_lines[brewery_name]['address'] = address
                json_lines[brewery_name]['latitude'] = lat
                json_lines[brewery_name]['longitude'] = lng
        with open(geocoded_breweries, 'w') as f:
            json.dump(json_lines, f, indent=4)

    # send routing opt req
    if args.optimize:
        logging.info('Solving routing optimization problem')

        # TODO: abstract shift time input
        # set static shifts
        shifts = [
            ["2020-01-24 17:00:00", "2020-01-25 00:00:00"],
            ["2020-01-25 15:00:00", "2020-01-26 00:00:00"],
            ["2020-01-26 13:00:00", "2020-01-26 20:00:00"],
            ["2020-02-14 17:00:00", "2020-02-15 00:00:00"],
            ["2020-02-15 15:00:00", "2020-02-16 00:00:00"],
            ["2020-02-16 13:00:00", "2020-02-17 00:00:00"],
            ["2020-02-17 13:00:00", "2020-02-17 20:00:00"]
        ]
        shifts = [[iso_time(shift_time) for shift_time in shift]
                  for shift in shifts]

        # linger times in hours
        default_linger = 1.5 * 3600

        # create orders
        with open(geocoded_breweries) as jsonfile:
            brewery_data = json.load(jsonfile)
            locations = []
            orders = []
            for brewery_name, brewery_info in brewery_data.items():
                if brewery_info['visited'] == "no":
                    locations.append({
                        "latitude": brewery_info['latitude'],
                        "longitude": brewery_info['longitude'],
                        "location_id": brewery_name
                    })
                    if "home" not in brewery_name:
                        order = {
                            "order_id": brewery_name,
                            "location_id": brewery_name,
                            "duration": default_linger
                        }
                        orders.append(order)
                else:
                    logging.warning('Skipping {}'.format(brewery_name))

        # blank payload
        payload = dict()

        # breweries to visit
        payload['locations'] = locations

        # places we actually want to visit (all of them)
        payload['orders'] = orders

        # how we'll move around
        vehicle_shifts = []
        for i, shift in enumerate(shifts):
            vehicle_shifts.append(
                {
                    "start_location_id": "home",
                    "end_location_id": "home",
                    "shift_start": shift[0],
                    "shift_end": shift[-1],
                    "shift_id": "crawl_shift_{}".format(i)
                }
            )

        payload['vehicles'] = [
            {
                "vehicle_id": "uber",
                "type": "car",
                "shifts": vehicle_shifts
            }
        ]

        # constraints
        payload['constraints'] = [
            {
                "constraint_type": "travel_time",
                "constraint_name": "Minimize travel time",
                "violation_increment": 1,
                "penalty_per_violation": 1,
                "max_travel_time_seconds": 0
            },
            {
                "constraint_type": "visit_range",
                "constraint_name": "visit as many orders as possible",
                "violation_increment": 1,
                "penalty_per_violation": 10000
            }
        ]

        # call the routing opt engine
        response = mapanything_routing(payload)

        # save req/resp
        with open(requestfile, 'w') as f:
            json.dump(payload, f)
        with open(responsefile, 'w') as f:
            json.dump(response, f)

    # create an IETF geojson complying to rfc7946: https://tools.ietf.org/html/rfc7946
    if args.geojson:
        logging.info('Writing solution to geojson file')

        # empty the geojson dir
        folder = os.path.join(datadir, 'geojson')
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete {}. Reason: {}'.format(file_path, e))
            logging.info('Removed {}'.format(filename))

        # routing opt json
        with open(responsefile) as f:
            response = json.load(f)

        # routing opt solution
        solution = response['Solution']

        # bounding box; note: bbox = [min Longitude , min Latitude , max Longitude , max Latitude]
        soln_bbox = solution['bounding_box']
        bbox = [
            soln_bbox['min_long'],
            soln_bbox['min_lat'],
            soln_bbox['max_long'],
            soln_bbox['max_lat']
        ]

        # coordinate reference system; HERE data is WGS84 -- http://www.opengis.net/def/crs/OGC/1.3/CRS84
        coord_ref_sys = {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }
        }

        # parse the routes
        routes = solution['routes']

        # due to empty routes, enumerate can get out of sync
        route_num = 0
        for route in routes:

            # define a geodetic for calculations
            geodesic = pyproj.Geod(ellps='WGS84')

            # check for no where routes
            if route['route_distance'] == 0:
                logging.warning('Empty route; unused shift {}, skipping'.format(route['shift_id']))
                continue

            # store desirable geo features and remove globally
            route_polylines = route['polylines']
            del route['polylines']
            route_stops = route['stops']
            del route['stops']
            route_directions = route['directions']['trip']['legs']
            del route['directions']

            # initialize route params
            routefile = os.path.join(
                datadir, "geojson/route_{}.geojson".format(route_num))
            route_features = []

            # loop over legs in route; note that route is already a nice dict
            leg_geoid = 0
            for n, leg in enumerate(route_polylines):
                # annotate the leg
                leg_properties = route_directions[n]
                leg_properties["leg"] = str(n)

                # decode the polyline
                leg = polyline.decode(leg, 5, geojson=True)

                # individual linestring
                geometry = geojson.LineString(leg)

                # save as linestrings
                route_features.append(
                    geojson.Feature(geometry=geometry, properties=leg_properties, id=leg_geoid))
                leg_geoid += 1

            # initialize stop params
            stopsfile = os.path.join(
                datadir, "geojson/route_{}_stops.geojson".format(route_num))
            stop_features = []

            # get the saved brewery data
            with open(geocoded_breweries) as f:
                breweries_data = json.load(f)

            # colors to style stops
            n_stops = len(route_stops)
            color_start = Color("red")
            color_end = Color("violet")
            colors = list(color_start.range_to(color_end, n_stops))

            # loop over stops; note: a stop is already a nice dict
            stop_geoid = 0
            route_bearing = []
            origin = [route_stops[0]['longitude'], route_stops[0]['latitude']]
            for n, stop in enumerate(route_stops):

                # make sure ordering of stops in response is correct
                assert n == stop['position_in_route']

                # add the original address
                loc = stop['location_id']
                stop['address'] = breweries_data[loc]['address']

                # mapbox compatible details
                stop['title'] = "route {} stop {}".format(route_num, str(stop['position_in_route']))
                stop['description'] = stop['location_id']
                stop['marker-size'] = "small"
                stop['marker-symbol'] = "beer"
                stop['marker-color'] = colors[n].hex_l

                # convert point to geom
                lat = stop['latitude']
                lng = stop['longitude']
                geometry = geojson.Point((lng, lat))

                # calculate bearing origin -> stop
                fwd_azimuth, back_azimuth, distance = geodesic.inv(origin[0], origin[1],
                                                                   stop['longitude'], stop['latitude'])
                if fwd_azimuth < 0:
                    fwd_azimuth += 360
                route_bearing.append(fwd_azimuth)

                # encode feature
                stop_features.append(geojson.Feature(
                    geometry=geometry, properties=stop, id=stop_geoid))
                stop_geoid += 1

            # average route bearing
            route_bearing = route_bearing[1:-1]
            xs = sum([math.sin(math.radians(x)) for x in route_bearing])
            ys = sum([math.cos(math.radians(x)) for x in route_bearing])
            route['average_bearing'] = degrees_to_cardinal(math.degrees(math.atan2(xs, ys)))

            # write the route geojson
            write_geojson(routefile, route_features, bbox,
                          coord_ref_sys, metadata=route)

            # write the route stops geojson
            write_geojson(stopsfile, stop_features, bbox,
                          coord_ref_sys, metadata=route)

            # increment routenum
            route_num += 1


if __name__ == '__main__':
    # setup file logger
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)-22s %(levelname)-8s %(message)s',
                        datefmt='%d-%m-%Y %H:%M:%S',
                        filename=script_name + '.log')

    # setup stdout logger
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    # run the main program
    logging.info("Starting new run...")
    start_time = time.time()
    main()
    logging.info("Run complete.")
    elapsed = time.time() - start_time
    elapsed = str(datetime.timedelta(seconds=elapsed))
    logging.info("--- Run time: {} ---".format(elapsed))
    sys.exit(0)
