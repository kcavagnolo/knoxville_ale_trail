#!/usr/bin/env python
# coding: utf-8

from tqdm import tqdm
import traceback
import datetime
import polyline
import argparse
import requests
import geojson
import logging
import string
import json
import time
import csv
import sys
import re
import os


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


def iso_time(time, time_format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strptime(time, time_format).isoformat()


def mapanything_geocoder(address):
    url = 'https://api.mapanything.io/services/core/geocoding/v2?address={}'.format(address)
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("MAPANYTHING_APIKEY")
    }
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
        lat = 0.0
        lng = 0.0
    finally:
        return lat, lng, address


def mapanything_routing(payload):
    url = 'https://public-api.mapanything.io/mare/routing/sync'
    headers = {
        'Accept-Encoding': 'application/gzip',
        'Content-Type': 'application/json',
        'x-api-key': os.getenv("MAPANYTHING_APIKEY")
    }
    response = requests.request('POST', url, headers=headers, data=json.dumps(payload), allow_redirects=True)
    response = response.json()
    return response


def main():

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Create an optimized route for the Knoxville Ale Trail.')
    parser.add_argument("-d", "--datadir", help="directory containing data",
                        action=FullPaths, type=is_dir, required=False)
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
    geocoded_breweries = os.path.join(datadir, "breweries_geocoded.csv")
    requestfile = os.path.join(datadir, "request.json")
    responsefile = os.path.join(datadir, "response.json")
    geojsonfile = os.path.join(datadir, "route.geojson")

    # geocode addresses
    if args.geocode:
        logging.info("Geocoding addresses")
        
        outfile = open(geocoded_breweries, "w")
        with open(breweries, 'r') as csvfile:
            reader = csv.reader(csvfile, skipinitialspace=True)
            next(reader, None)
            for row in tqdm(sorted(reader)):
                brewery_name = clean_string(row[0])
                address = clean_string(' '.join(row))
                lat, lng, address = mapanything_geocoder(address)
                output_line = ','.join([
                    str(lat),
                    str(lng),
                    brewery_name,
                    address]
                )
                outfile.write(output_line + "\n")
        outfile.close()

    # send routing opt req
    if args.optimize:
        logging.info('Solving routing optimization problem')
        
        # set static shifts
        shift_times = []
        shift_times = [
            "2020-01-24 17:00:00",
            "2020-01-25 00:00:00",
            "2020-01-25 15:00:00",
            "2020-01-26 00:00:00",
            "2020-01-26 13:00:00",
            "2020-01-26 20:00:00"
        ]
        shift_times = [iso_time(shift_time) for shift_time in shift_times]

        # linger times in hours
        default_linger = 1.0*3600

        # create orders
        with open(geocoded_breweries, 'r') as csvfile:
            reader = csv.reader(csvfile, skipinitialspace=True)
            locations = []
            orders = []
            for row in reader:
                lat = float(row[0])
                lng = float(row[1])
                brewery_name = row[2]
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

        # blank payload
        payload = dict()

        # breweries to visit
        payload['locations'] = locations

        # places we actually want to visit (all of them)
        payload['orders'] = orders

        # how we'll move around
        payload['vehicles'] = [
            {
                "vehicle_id": "uber",
                "type": "car",
                "shifts": [
                    {
                        "start_location_id": "home",
                        "end_location_id": "home",
                        "shift_start": shift_times[0],
                        "shift_end": shift_times[-1],
                        "shift_id": "crawl_shift"
                    }
                ]
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
    if args.geojson:
        logging.info('Writing solution to geojson file')

        # add route polyline
        with open(responsefile) as f:
            response = json.load(f)
        route_polyline = response['Solution']['routes'][0]['polylines']
        features = []
        for n, leg in enumerate(route_polyline):
            leg = polyline.decode(leg, 5, geojson=True)
            geometry = geojson.LineString(leg)
            features.append(geojson.Feature(geometry=geometry, properties={"leg": "leg"+str(n)}))
        
        # add breweries
        with open(geocoded_breweries, 'r') as csvfile:
            reader = csv.reader(csvfile, skipinitialspace=True)
            locations = []
            orders = []
            for row in reader:
                lat = float(row[0])
                lng = float(row[1])
                brewery_name = row[2]
            geometry = geojson.Point((lng, lat))
            features.append(geojson.Feature(geometry=geometry, properties={"brewery": brewery_name}))
        
        # write feature collection to geojson
        feature_collection = geojson.FeatureCollection(features)
        with open(geojsonfile, 'w') as f:
            geojson.dump(feature_collection, f)


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
