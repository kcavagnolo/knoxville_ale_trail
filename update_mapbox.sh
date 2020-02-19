export MAPBOX_USER=$MAPBOX_USER_PERSONAL
export MAPBOX_ACCESS_TOKEN=$MAPBOX_ACCESS_TOKEN_PERSONAL
tippecanoe --force -o data/knx-ale-trail.mbtiles -zg --drop-densest-as-needed data/knx-ale-trail.geojson
mapbox upload $MAPBOX_USER.knx-ale-trail data/knx-ale-trail.mbtiles
