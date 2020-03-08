#!/usr/bin/env python
# coding: utf-8

import argparse
import datetime
import glob
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback


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


def disk_check():
    disk_stat = os.statvfs(os.getcwd())
    disk_free = (disk_stat.f_bsize * disk_stat.f_bavail) / 1.0e9
    if disk_free < 1.0:
        logging.exception(
            'Less than 1G of disk space. Cowardly refusing to continue.')
        sys.exit(1)


def glob_files(filedir, pattern):
    # get files
    try:
        globfiles = glob.glob(filedir + '/' + pattern)
    except Exception as e:
        logging.exception('Something went wrong getting files: {}'.format(e))
        sys.exit(1)
    if len(globfiles) < 1:
        logging.exception('No files to process. Halting.')
        sys.exit(1)
    return globfiles


def shapefile_to_geojson(shapesdir, geojsondir):
    """Convert a shapefile to a geojson

    :rtype: none
    :param shapesdir: directory containing shapefiles to convert
    :param geojsondir: directory into which geojson output land
    """

    # get files
    shapefiles = glob_files(shapesdir, filepattern + '.shp')

    # iterate over each shapefile
    for shapefile in sorted(shapefiles):

        # check disk space
        disk_check()

        # create output file name
        outroot = str(os.path.basename(shapefile).split('.')[0])
        outjson = geojsondir + '/' + outroot + '.geojson'
        logging.debug("Processing {}".format(outroot))

        # convert to geojson; for speed use ogr directly
        try:
            logging.debug(
                "Converting shapefile to geojson: {}".format(shapefile))
            subprocess.call(["ogr2ogr",
                             "-f", "GeoJSON",
                             "-progress",
                             outjson, shapefile])
        except Exception as e:
            logging.exception(e)
            logging.exception(traceback.format_exc())


def geojson_to_mbtile(geojsondir, mbtiledir):
    """Convert a geojson to a Mapbox tile. See documentation on a tile here:
    https://www.mapbox.com/vector-tiles/

    :rtype: none
    :param geojsondir: dir containing geojson files to convert
    :param mbtiledir: dir into which converted files land
    """

    # check for tippecanoe
    if shutil.which('tippecanoe') is None:
        logging.exception(
            'Tippecanoe not detected. Is it installed? https://github.com/mapbox/tippecanoe')
        raise RuntimeError

    # get files
    geojsonfiles = glob_files(geojsondir, filepattern + '.geojson')
    logging.debug('Found files: {}'.format(geojsonfiles))

    # define base tippecanoe command params
    attribution = '<a href="https://github.com/kcavagnolo/knoxville_ale_trail" target="_blank">© kcavagnolo</a>'
    tippecanoe = ["tippecanoe",
                  "--read-parallel",  # https://github.com/mapbox/tippecanoe#parallel-processing-of-input
                  "-f",  # https://github.com/mapbox/tippecanoe#output-tileset
                  #"-A", attribution,  # https://github.com/mapbox/tippecanoe#tileset-description-and-attribution
                  "-N", '"routing optimization solution"',
                  "-b", "0",  # http://bit.ly/32qRNuK
                  "-r1",  # http://bit.ly/32xd7Pj
                  "-Z", "0", "-z", "14",  # https://github.com/mapbox/tippecanoe#zoom-levels
                  "-ah",  # https://github.com/mapbox/tippecanoe#reordering-features-within-each-tile
                  "-ai",  # https://github.com/mapbox/tippecanoe#adding-calculated-attributes
                  "-pf",  # https://github.com/mapbox/tippecanoe#setting-or-disabling-tile-size-limits
                  "-pk", 
                  "-Q"  # https://github.com/mapbox/tippecanoe#progress-indicator
                  ]

    # iterate over each shapefile
    layers = []
    for geojsonfile in sorted(geojsonfiles):

        # check disk space
        disk_check()

        # create output file name
        outroot = str(os.path.basename(geojsonfile).split('.')[0])
        layers.extend(['-L', '{}:{}'.format(outroot, geojsonfile)])
        outtile = os.path.join(mbtiledir, outroot + '.mbtiles')
        logging.debug("Processing {}".format(outroot))

        # convert to tile using tippecanoe
        unique_tippecanoe = tippecanoe + ["-o", outtile,
                                          geojsonfile,
                                          "-l", outroot,
                                          "-n", outroot]
        try:
            logging.debug("Converting geojson to mapbox tile.")
            subprocess.call(unique_tippecanoe)
        except Exception as e:
            logging.exception(e)
            logging.exception(traceback.format_exc())

    # TODO: Abstract master tile filename
    # create a layered master tile
    outtile = mbtiledir + '/' + 'knx-ale-trail.mbtiles'
    logging.debug("Processing combined routes")
    unique_tippecanoe = tippecanoe + ["-o", outtile] + layers + ["-n", "routes"]
    try:
        logging.debug("Converting all geojson to layered mapbox tile.")
        subprocess.call(unique_tippecanoe)
    except Exception as e:
        logging.exception(e)
        logging.exception(traceback.format_exc())


def upload_mbtiles(mbtiledir):
    """Upload Mapbox tile vectors to a users account

    :rtype: none
    :param mbtiledir: dir containing Mapbox tile files
    """

    # check for mapbox cli
    if shutil.which('mapbox') is None:
        logging.exception(
            'Mapbox command line interface not detected. Is mapbox cli installed?')
        raise RuntimeError

    # check for mapbox account credentials
    if os.getenv('MAPBOX_ACCESS_TOKEN') is None:
        logging.exception(
            'No Mapbox token detected. Is MAPBOX_ACCESS_TOKEN env var set?')
        raise RuntimeError
    mapboxuser = os.getenv('MAPBOX_USERNAME')
    if mapboxuser is None:
        logging.exception(
            'No Mapbox account detected. Is MAPBOX_USERNAME env var set?')
        raise RuntimeError

    # get files
    mbtilefiles = glob_files(mbtiledir, filepattern + '.mbtiles')

    # iterate over each tilefile
    for mbtilefile in mbtilefiles:

        # create output file name
        outroot = str(os.path.basename(mbtilefile).split('.')[0])

        # upload to mapbox account
        logging.debug("Uploading file Mapbox servers: {}".format(mbtilefile))
        try:
            subprocess.call(["mapbox",
                             "upload",
                             mapboxuser + "." + outroot,
                             mbtilefile])
        except Exception as e:
            logging.exception(e)
            logging.exception(traceback.format_exc())


def main():
    """
    Runs the main program
    :raise RuntimeError: if something goes wrong with API wrapper
    """

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Download HPMS data.')
    parser.add_argument(
        "-sd",
        "--shapesdir",
        help="directory containing shapefiles",
        action=FullPaths, type=is_dir,
        required=False)
    parser.add_argument("-gd", "--geojsondir", help="directory containing geojson files",
                        action=FullPaths, type=is_dir, required=False)
    parser.add_argument("-td", "--tilesdir", help="directory containing Mapbox tiles",
                        action=FullPaths, type=is_dir, required=False)
    parser.add_argument("--geojson", help="create geojson files from shapefiles",
                        action="store_true")
    parser.add_argument("--mbtiles", help="create Mapbox vector tiles from geojson files",
                        action="store_true")
    parser.add_argument("--uploadmb", help="upload Mapbox vector tiles",
                        action="store_true")
    parser.add_argument("-p", "--pattern", help="match files with this pattern",
                        required=False)
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    args = parser.parse_args()
    # FIX: dynamically changing logging level not working
    logging.getLogger('').setLevel(level=args.loglevel)

    # match file patterns
    global filepattern
    filepattern = '*'
    if args.pattern:
        filepattern = str(args.pattern)

    # convert shapefiles to geojson
    if args.geojson:
        if args.shapesdir and args.geojsondir:
            try:
                shapefile_to_geojson(args.shapesdir, args.geojsondir)
            except Exception as e:
                logging.exception(e)
        else:
            logging.error(
                'One or both of --shapesdir (-sd) and --geojsondir (-gd) are missing.')
            sys.exit(1)

    # convert geojson to tiles using tippecanoe
    if args.mbtiles:
        if args.geojsondir and args.tilesdir:
            try:
                geojson_to_mbtile(args.geojsondir, args.tilesdir)
            except Exception as e:
                logging.exception(e)
        else:
            logging.error(
                'One or both of --geojsondir (-gd) and --tilesdir (-td) are missing.')
            sys.exit(1)

    # upload tiles to mapbox
    if args.uploadmb:
        try:
            upload_mbtiles(args.tilesdir)
        except Exception as e:
            logging.exception(e)


if __name__ == "__main__":
    # setup file logger
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    logging.basicConfig(level=logging.INFO,
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
    elapsed = str(datetime.timedelta(seconds=elapsed))
    logging.info("--- Run time: {} ---".format(elapsed))
    sys.exit(0)
