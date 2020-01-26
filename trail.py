#!/usr/bin/env python
# coding: utf-8

from tqdm import tqdm
import datetime
import requests
import logging
import string
import json
import time
import csv
import sys
import re
import os


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
        address = address
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

    # geocode addresses
    breweries = "breweries.csv"
    geocoded_breweries = "breweries_geocoded.csv"
    outfile = open(geocoded_breweries, "w")
    logging.info("Geocoding addresses")
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

    # set dynamic shift
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    now = datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=utc_offset))
    later = now + datetime.timedelta(hours=168)

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
    logging.info('Creating payload')
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
                # if 'elkmont' in brewery_name:
                #     appointment = [
                #         {
                #             "appointment_start": appt_start,
                #             "appointment_end": appt_end
                #         }
                #     ]
                #     order['appointments'] = appointment
                #     order['duration'] = 2.5*3600
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

    # send routing opt req
    logging.info('Solving routing optimization problem')
    response = mapanything_routing(payload)
    with open('request.json', 'w') as f:
        json.dump(payload, f)
    with open('response.json', 'w') as f:
        json.dump(response, f)


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