#!/usr/bin/env python
# coding: utf-8

import argparse
import csv
import datetime
import json
import logging
import os
import re
import sys
import time
import traceback

import geojson
import polyline
import requests
from colour import Color
from tqdm import tqdm


class FullPaths(argparse.Action):
    """Expand user- and relative-paths"""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))


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
    url = 'https://api.mapanything.io/services/core/geocoding/v2?address={}'.format(address)
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("MAPANYTHING_APIKEY")
    }
    lat, lng = 0.0, 0.0
    try:
        response = requests.request('GET', url, headers=headers, allow_redirects=True)
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
        response = requests.request('POST', url, headers=headers, data=json.dumps(payload), allow_redirects=True)
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


def main():
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Create an optimized route for the Knoxville Ale Trail.')
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

    # I/O files
    # TODO: abstract filenames
    datadir = args.datadir
    breweries = os.path.join(datadir, "breweries.csv")
    geocoded_breweries_csv = os.path.join(datadir, "breweries_geocoded.csv")
    geocoded_breweries_json = os.path.join(datadir, "breweries_geocoded.json")
    requestfile = os.path.join(datadir, "request.json")
    responsefile = os.path.join(datadir, "response.json")
    geojsonfile = os.path.join(datadir, "route.geojson")

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
        with open(geocoded_breweries_csv, 'w') as f:
            for line in csv_lines:
                f.write(line)
        with open(geocoded_breweries_json, 'w') as f:
            json.dump(json_lines, f, indent=4)

    # send routing opt req
    if args.optimize:
        logging.info('Solving routing optimization problem')

        # TODO: abstract shift time input
        # set static shifts
        shifts = [
            ["2020-01-24 17:00:00", "2020-01-28 00:00:00"]#,
            #["2020-01-25 15:00:00", "2020-01-26 00:00:00"],
            #["2020-01-26 13:00:00", "2020-01-26 20:00:00"],
            #["2020-02-14 17:00:00", "2020-02-15 00:00:00"],
            #["2020-02-15 15:00:00", "2020-02-16 00:00:00"],
            #["2020-02-16 13:00:00", "2020-02-17 00:00:00"],
            #["2020-02-17 13:00:00", "2020-02-17 20:00:00"]
        ]
        shifts = [[iso_time(shift_time) for shift_time in shift] for shift in shifts]

        # linger times in hours
        default_linger = 1.0 * 3600

        # create orders
        with open(geocoded_breweries_csv, 'r') as csvfile:
            reader = csv.reader(csvfile, skipinitialspace=True)
            locations = []
            orders = []
            for row in reader:
                if row[0] != "yes":
                    lat = float(row[1])
                    lng = float(row[2])
                    brewery_name = row[3]
                    locations.append({
                        "latitude": lat,
                        "longitude": lng,
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
                    logging.warning('Skipping {}'.format(row[3]))

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

    # decode polyline to GeoJSON
    # TODO: handle multiple routes instead of one grand route
    if args.geojson:
        logging.info('Writing solution to geojson file')
        uuid = 0

        # add route polyline
        with open(responsefile) as f:
            response = json.load(f)
        route_polyline = response['Solution']['routes'][0]['polylines']
        features = []
        for n, leg in enumerate(route_polyline):
            leg = polyline.decode(leg, 5, geojson=True)

            # individual linestring
            geometry = geojson.LineString(leg)

            # save as linestrings
            features.append(geojson.Feature(geometry=geometry, properties={"leg": "leg" + str(n)}, id=uuid))
            uuid += 1

        # add breweries
        with open(geocoded_breweries_json) as f:
            breweries_data = json.load(f)
        stops = response['Solution']['routes'][0]['stops']

        # colors to style stops
        n_stops = len(stops)
        color_start = Color("red")
        color_end = Color("violet")
        colors = list(color_start.range_to(color_end, n_stops))

        # loop over stops and make geojson
        for n, stop in enumerate(stops):
            # make sure ordering of stops in response is correct
            assert n == stop['position_in_route']

            # capture stop detail
            loc = stop['location_id']
            lat = stop['latitude']
            lng = stop['longitude']

            # add the original address
            stop['address'] = breweries_data[loc]['address']

            # mapbox compatible details
            stop['title'] = "trail stop " + str(stop['position_in_route'])
            stop['description'] = stop['location_id']
            stop['marker-size'] = "small"
            stop['marker-symbol'] = "beer"
            stop['marker-color'] = colors[n].hex_l

            # convert point to geom
            geometry = geojson.Point((lng, lat))

            # encode feature
            features.append(geojson.Feature(geometry=geometry,
                                            properties=stop, id=uuid)
                            )
            uuid += 1

        # write feature collection to geojson
        feature_collection = geojson.FeatureCollection(features)
        with open(geojsonfile, 'w') as f:
            geojson.dump(feature_collection, f, indent=4, sort_keys=True)
        with open(geojsonfile, 'r') as f:
            gdata = json.load(f)
        with open(geojsonfile, 'w') as f:
            json.dump(gdata, f, separators=(',', ':'))


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
