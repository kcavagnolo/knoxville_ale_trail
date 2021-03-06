#!/usr/bin/env python
# coding: utf-8

import argparse
import csv
import datetime as dt
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
from geopy.distance import distance
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
    pattern = re.compile('[\W]+', re.UNICODE)
    s = pattern.sub(' ', s.lower())
    return s


def here_geocoder(address):
    geocode_url = 'https://geocoder.ls.hereapi.com/6.2/geocode.json?apiKey={}&searchtext={}'
    apikey = os.getenv("HERE_APIKEY")
    address = address.lower().replace(" ", "+")
    lat, lng = 0, 0
    try:
        response = requests.request('GET', geocode_url.format(apikey, address))
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


def here_places(lat, lng, name):
    places_url = 'https://places.ls.hereapi.com/places/v1/discover/search?apiKey={}&at={},{}&q={}'
    apikey = os.getenv("HERE_APIKEY")
    try:
        response = requests.request(
            'GET', places_url.format(apikey, lat, lng, name))
        response = response.json()
        if len(response['results']['items']) > 0:
            coords = response['results']['items'][0]['position']
            d = distance((lat, lng), (coords[0], coords[1])).miles
            if d < 0.5:
                return response['results']['items'][0]
            else:
                return {}
        else:
            return {}
    except Exception as e:
        logging.exception(e)
        logging.exception(traceback.format_exc())


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
        logging.error('Optimization failed')
        logging.exception(e)
        logging.exception(traceback.format_exc())
        sys.exit(1)
    return response


def write_geojson(outfile, features, bbox, crs, metadata=None):
    feature_collection = geojson.FeatureCollection(features)
    feature_collection['metadata'] = metadata
    feature_collection['bbox'] = bbox
    feature_collection['crs'] = crs
    with open(outfile, 'w') as f:
        json.dump(feature_collection, f, separators=(',', ':'), sort_keys=True)


def opening_hours(hours):
    days_map = {
        "MO": 0,
        "TU": 1,
        "WE": 2,
        "TH": 3,
        "FR": 4,
        "SA": 5,
        "SU": 6
    }
    hours_operation = {'open': None, 'duration': None}
    weekly_hours = {}
    for day, day_num in days_map.items():
        weekly_hours[day_num] = hours_operation.copy()
    periods = hours['structured']
    for period in periods:
        open_time = dt.datetime.strptime(period['start'][1:], '%H%M%S')
        hours, minutes = period['duration'][2:-1].split('H')
        duration = dt.timedelta(hours=int(hours), minutes=int(minutes))# + open_time
        recurrence = dict(x.split(":")
                          for x in period['recurrence'].split(";"))
        for day in recurrence['BYDAY'].split(','):
            weekly_hours[days_map[day]]['open'] = open_time
            weekly_hours[days_map[day]]['duration'] = duration
    return weekly_hours


def degrees_to_cardinal(d):
    dirs = ['N', 'NbE', 'NNE', 'NEbN', 'NE', 'NEbE', 'ENE', 'EbN',
            'E', 'EbS', 'ESE', 'SEbE', 'SE', 'SEbS', 'SSE', 'SbE',
            'S', 'SbW', 'SSW', 'SWbS', 'SW', 'SWbW', 'WSW', 'WbS',
            'W', 'WbN', 'WNW', 'NWbW', 'NW', 'NWbN', 'NNW', 'NbW']
    ix = round(d / (360. / len(dirs)))
    return dirs[ix % len(dirs)]


def next_day(adate, aday):
    return adate + dt.timedelta(days=(aday - adate.weekday() + 7) % 7)


def add_timezone(atime):
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = dt.timedelta(seconds=-utc_offset_sec)
    return atime.replace(microsecond=0).replace(tzinfo=dt.timezone(offset=utc_offset))


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
                if lat != 0 and lng != 0:
                    place_details = here_places(lat, lng, brewery_name)
                else:
                    place_details = {}
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
                json_lines[brewery_name]['place_details'] = place_details
        with open(geocoded_breweries, 'w') as f:
            json.dump(json_lines, f, indent=4)

    # send routing opt req
    if args.optimize:
        logging.info('Solving routing optimization problem')

        # TODO: Remove hardwired shift_times
        # set start shift_times and durations for days of week
        # note: 0=Mon ... 6=Sun
        shift_times = {
            0: [dt.time(hour=17, minute=30), 4.5],
            1: [dt.time(hour=17, minute=30), 4.5],
            2: [dt.time(hour=17, minute=30), 4.5],
            3: [dt.time(hour=17, minute=30), 4.5],
            4: [dt.time(hour=17, minute=00), 8],
            5: [dt.time(hour=13, minute=00), 12],
            6: [dt.time(hour=14, minute=00), 7]
        }

        # set days of week to make visits -- Fri to Sun
        visit_days = range(4, 7)

        # create an array of possible shifts
        shifts = []

        # get dates for the upcoming weekend from today
        for x in visit_days:
            d = next_day(dt.date.today(), x)
            t = shift_times[x]

            # set shift_times for at least this coming weekend
            s1 = dt.datetime.combine(d, t[0])
            e1 = s1 + dt.timedelta(hours=t[1])
            shifts.append([s1, e1])

            # TODO: Add n_weeks as a cli param
            # set shift_times for the next n_weeks
            n_weeks = 2
            for week_n in range(n_weeks+1):
                sn = s1 + dt.timedelta(days=7 + (week_n * 7))
                en = e1 + dt.timedelta(days=7 + (week_n * 7))
                shifts.append([sn, en])

        # create array of all dates in range needed for time windows
        d1 = shifts[0][0]
        d2 = shifts[-1][1]
        diff = d2 - d1
        date_range = [(d1 + dt.timedelta(x)) for x in range(diff.days + 1)]

        # TODO: Allow for user input linger time
        # how long to linger at each stop, in hours
        default_linger = 1.5 * 3600

        # create orders
        with open(geocoded_breweries) as jsonfile:
            brewery_data = json.load(jsonfile)
            locations = []
            orders = []

            # loop over all breweries
            for brewery_name, brewery_info in brewery_data.items():

                # only visit new breweries
                if brewery_info['visited'] == "no":

                    # set the location object
                    locations.append({
                        "latitude": brewery_info['latitude'],
                        "longitude": brewery_info['longitude'],
                        "location_id": brewery_name
                    })

                    # set the order object
                    if "home" not in brewery_name:
                        order = {
                            "order_id": brewery_name,
                            "location_id": brewery_name,
                            "duration": default_linger
                        }

                        # add open hours if they exist
                        place_details = brewery_info['place_details']
                        if 'openingHours' in place_details.keys():
                            time_windows = []
                            open_hours = opening_hours(brewery_info['place_details']['openingHours'])
                            for date in date_range:
                                date_hours = open_hours[date.weekday()]
                                if date_hours['open']:
                                    date_open = date_hours['open'].replace(year=date.year, month=date.month, day=date.day)
                                    date_close = date_open + date_hours['duration']
                                    time_windows.append({
                                        "start_time_window": add_timezone(date_open).isoformat(),
                                        "end_time_window": add_timezone(date_close).isoformat()
                                    })
                            order['time_windows'] = time_windows
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
                    "shift_start": add_timezone(shift[0]).isoformat(),
                    "shift_end": add_timezone(shift[-1]).isoformat(),
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
                "constraint_name": "minimize travel time",
                "violation_increment": 1,
                "penalty_per_violation": 1,
                "max_travel_time_seconds": 0
            },
            {
                "constraint_type": "visit_range",
                "constraint_name": "visit as many orders as possible",
                "violation_increment": 1,
                "penalty_per_violation": 10000
            },
            {
                "constraint_type": "time_window",
                "constraint_name": "honor time windows",
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

        # read-off incomplete visits
        incomplete_visits = solution['orders_incomplete_visits']
        for icv in incomplete_visits:
            logging.warning('Did not visit: {}'.format(icv['order_id']))

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

        # colors to style stops and routes
        n_routes = len(routes)
        color_start = Color("red")
        color_end = Color("violet")
        colors = list(color_start.range_to(color_end, n_routes))

        # due to empty routes, enumerate can get out of sync
        route_num = 0
        for route in routes:

            # check for no where routes
            if route['route_distance'] == 0:
                logging.warning(
                    'Empty route; unused shift {}, skipping'.format(route['shift_id']))
                continue

            # define a route id
            route_id = "route_{}".format(route_num)

            # define a geodetic for calculations
            geodesic = pyproj.Geod(ellps='WGS84')

            # highcharts compatible details
            route_color = colors[route_num].hex_l
            route['name'] = 'Route {}'.format(route_num)
            route['id'] = route_id
            route['start'] = route['abs_route_start_time'] * 1000
            route['end'] = route['abs_route_end_time'] * 1000

            # store desirable geo features and remove globally
            route_polylines = route['polylines']
            del route['polylines']
            route_stops = route['stops']
            del route['stops']
            route_directions = route['directions']['trip']['legs']
            del route['directions']

            # initialize route params
            routefile = os.path.join(
                datadir, "geojson/{}.geojson".format(route_id))
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
                datadir, "geojson/{}_stops.geojson".format(route_id))
            stop_features = []

            # get the saved brewery data
            with open(geocoded_breweries) as f:
                breweries_data = json.load(f)

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
                stop['title'] = "route {} stop {}".format(
                    route_num, str(stop['position_in_route']))
                stop['description'] = stop['location_id']
                stop['marker-size'] = "small"
                stop['marker-symbol'] = "beer"
                stop['marker-color'] = route_color

                # highcharts compatible details
                stop['name'] = stop['location_id'].title()
                stop['id'] = "{}_stop_{}".format(
                    route_id, str(stop['position_in_route']))
                # stop['parent'] = route_id  # only needed for collapsible itin
                stop['start'] = stop['abs_arrival_time'] * 1000
                stop['end'] = stop['abs_departure_time'] * 1000
                stop['y'] = route_num

                # convert point to geom
                lat = stop['latitude']
                lng = stop['longitude']
                geometry = geojson.Point((lng, lat))

                # calculate bearing origin -> stop
                fwd_azimuth, back_azimuth, pts_distance = geodesic.inv(origin[0],
                                                                       origin[1],
                                                                       stop['longitude'],
                                                                       stop['latitude']
                                                                       )
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
            route['average_bearing'] = degrees_to_cardinal(
                math.degrees(math.atan2(xs, ys)))

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
                        filename='./debug/' + script_name + '.log')

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
    elapsed = str(dt.timedelta(seconds=elapsed))
    logging.info("--- Run time: {} ---".format(elapsed))
    sys.exit(0)
