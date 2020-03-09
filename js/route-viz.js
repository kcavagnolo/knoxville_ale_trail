// verify Mapbox GL JS support
var bodyElement = document.body;
var mapElement = document.getElementById('map');

// check for mapbox support
if (!mapboxgl.supported()) {
    alert('Mapbox GL is not supported by your browser');
    mapElement.innerHTML = mapboxgl.notSupportedReason({
        failIfMajorPerformanceCaveat: true
    });
    bodyElement.className = 'fill-red';
} else {

    // an access token
    mapboxgl.accessToken = 'pk.eyJ1Ijoia2NhdmFnbm9sbyIsImEiOiJjamtvOWExZHYydm1xM3BreG9pb3hza3J6In0.yKhLQH7NxC9rbsrCpilLQw';

    // TODO: abstract the origin based on view
    // set an origin
    var origin = [-83.924137, 35.961671]

    // highcharts
    var hcDefined = Highcharts.defined;
    var hcReduce = Highcharts.reduce;
    var hcMap = Highcharts.map;

    // initialize number of layers
    var numLayers = 0;

    // initialize a global route schedule
    var routeSchedule = [];

    // load mapbox gl
    var map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v10?optimize=true',
        center: origin,
        zoom: 9,
        attributionControl: false,
        failIfMajorPerformanceCaveat: true
    }).addControl(new mapboxgl.AttributionControl({
        compact: true,
        customAttribution: "<a href='https://github.com/kcavagnolo/knoxville_ale_trail' target='_blank'>&copy; kcavagnolo</a>"
    }));

    // add language control
    mapboxgl.setRTLTextPlugin(
        'https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-rtl-text/v0.2.3/mapbox-gl-rtl-text.js',
        null,
        true
    );
    map.addControl(
        new MapboxLanguage({
            defaultLanguage: 'mul'
        }));

    // add geocoder
    map.addControl(
        new MapboxGeocoder({
            accessToken: mapboxgl.accessToken,
            mapboxgl: mapboxgl,
            collapsed: true,
            placeholder: 'Search',
            countries: 'us',
            proximity: {
                longitude: origin[0],
                latitude: origin[1]
            },
            marker: false
        }), "top-right"
    );

    // add nav controls
    map.addControl(
        new mapboxgl.NavigationControl()
    );

    // A single tracker point that animates along the route.
    // Coordinates are initially set to origin.
    var tracker = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {},
            'geometry': {
                'type': 'Point',
                'coordinates': [0, 0]
            }
        }]
    };

    // initialize some vars
    var steps = 0;
    var counter = 0;
    var leg = 0;
    var hoverId = null;

    // Create a popup, but don't add it to the map yet.
    var popup = new mapboxgl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: {
            "top": [0, 10],
            "bottom": [0, -10]
        }
    });

    // function to add sources
    function addSources() {
        // load route tiles
        map.addSource('routes_source', {
            type: 'vector',
            url: 'mapbox://kcavagnolo.knx-ale-trail'
        });

        // add a tracking point to move along route
        map.addSource('tracker_source', {
            'type': 'geojson',
            'data': tracker
        });
    }

    // add the tracker
    function addTracker() {
        map.addLayer({
            'id': 'tracker',
            'source': 'tracker_source',
            'type': 'symbol',
            'layout': {
                'icon-image': 'beer-15',
                'icon-rotate': ['get', 'bearing'],
                'icon-rotation-alignment': 'map',
                'icon-allow-overlap': true,
                'icon-ignore-placement': true
            }
        });

    }

    // function to add route layers
    function addRoutes(routeLayerId, stopLayerId, dirLayerId, layerColor) {

        // add the route legs as lines
        map.addLayer({
            'id': routeLayerId,
            'type': 'line',
            'source': 'routes_source',
            'source-layer': routeLayerId,
            'layout': {
                'visibility': 'visible',
                'line-join': 'round',
                'line-cap': 'round'
            },
            'paint': {
                'line-color': layerColor,
                'line-width': 2
            }
        });

        // add the routes directionality symbols
        map.addLayer({
            'id': dirLayerId,
            'type': 'symbol',
            'source': 'routes_source',
            'source-layer': routeLayerId,
            'layout': {
                'symbol-placement': 'line',
                'text-field': '▶',
                'text-size': [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    12, 24,
                    22, 48
                ],
                'symbol-spacing': [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    12, 30,
                    22, 160
                ],
                'text-keep-upright': false
            },
            'paint': {
                'text-color': layerColor
            }
        }, 'waterway-label');

        // add the route stops as circles
        map.addLayer({
            'id': stopLayerId,
            'type': 'circle',
            'source': 'routes_source',
            'source-layer': stopLayerId,
            'layout': {
                'visibility': 'visible',
            },
            'paint': {
                'circle-radius': [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    12, 6,
                    22, 12
                ],
                'circle-color': [
                    'case',
                    ['boolean', ['feature-state', 'hover'], false],
                    "#ffffff",
                    layerColor
                ],
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1,
                'circle-opacity': [
                    'case',
                    ['boolean', ['feature-state', 'hover'], false],
                    0.8,
                    1.0
                ]
            }
        });

        // hovering stops opens popup and changes symbol
        map.on('mouseenter', stopLayerId, function (e) {

            // change cursor to indicator
            map.getCanvas().style.cursor = 'pointer';

            // set the html description
            var coordinates = e.features[0].geometry.coordinates.slice();
            var properties = e.features[0].properties;
            var layer = e.features[0].layer;
            var descriptionElements = [
                properties.address,
                "arrive: " + new Date(properties.arrival_time).toLocaleString(),
                "depart: " + new Date(properties.departure_time).toLocaleString()
            ]
            var brewery = properties.location_id.toUpperCase();
            var description = '<h3>' + brewery + '</h3><p>' + descriptionElements.join('<br>') + '</p>'

            // Ensure that if the map is zoomed out such that multiple
            // copies of the feature are visible, the popup appears
            // over the copy being pointed to.
            while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
                coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
            }

            // load the hover popup
            popup.setLngLat(coordinates)
                .setHTML(description)
                .addTo(map);

            // change the symbol color and opacity
            if (e.features.length > 0) {
                if (hoverId) {
                    map.setFeatureState({
                        source: 'routes_source',
                        sourceLayer: stopLayerId,
                        id: hoverId
                    }, {
                        hover: false
                    });
                }
                hoverId = e.features[0].id;
                map.setFeatureState({
                    source: 'routes_source',
                    sourceLayer: stopLayerId,
                    id: hoverId
                }, {
                    hover: true
                });
            }
        });

        // no hover reverts state
        map.on('mouseleave', stopLayerId, function () {
            if (hoverId) {
                map.setFeatureState({
                    source: 'routes_source',
                    sourceLayer: stopLayerId,
                    id: hoverId
                }, {
                    hover: false
                });
            }
            hoverId = null;

            // change cursor back to pointer
            map.getCanvas().style.cursor = '';

            // remove the hover popup
            popup.remove();
        });

        // add route stops to gantt
        addItinerary(routeLayerId, stopLayerId, layerColor);
    }

    // function to add intin to gantt
    function addItinerary(routeLayerId, stopLayerId, layerColor) {
        var url = `https://raw.githubusercontent.com/kcavagnolo/knoxville_ale_trail/master/data/geojson/${stopLayerId}.geojson`;
        fetch(url).then(function (resp) {
            return resp.json();
        }).then(function (routeData) {
            var ganttLabel = routeLayerId.replace("_", " ");
            var stopData = routeData.features.map(function (feature, i) {
                feature.properties['color'] = layerColor;
                return feature.properties;
            });
            stopData.push(routeData.metadata);
            routeSchedule.push({
                name: ganttLabel.charAt(0).toUpperCase() + ganttLabel.slice(1),
                data: stopData
            });
            return routeSchedule;
        }).then(function (routeSchedule) {
            Highcharts.ganttChart('gantt-container', {
                series: routeSchedule,
                navigator: {
                    enabled: true,
                    liveRedraw: true,
                    series: {
                        type: 'gantt',
                        pointPlacement: 0.5,
                        pointPadding: 0.25
                    }
                },
                scrollbar: {
                    enabled: true
                },
                rangeSelector: {
                    selected: 1
                },
                tooltip: {
                    pointFormatter: function () {
                        var point = this;
                        var lines = [{
                                title: 'Brewery',
                                value: point.name
                            },
                            {
                                title: 'Arrive',
                                value: new Date(point.arrival_time).toLocaleString()
                            }, {
                                title: 'Depart',
                                value: new Date(point.departure_time).toLocaleString()
                            }
                        ];
                        return hcReduce(lines, function (str, line) {
                            var s = '',
                                style = (
                                    hcDefined(line.style) ? line.style : 'font-size: 1.0em;'
                                );
                            if (line.visible !== false) {
                                s = (
                                    '<span style="' + style + '">' +
                                    (hcDefined(line.title) ? line.title + ': ' : '') +
                                    (hcDefined(line.value) ? line.value : '') +
                                    '</span><br/>'
                                );
                            }
                            return str + s;
                        }, '');
                    }
                },
                xAxis: {
                    currentDateIndicator: true
                },
                yAxis: {
                    type: 'category',
                    grid: {
                        columns: [{
                            categories: hcMap(routeSchedule, function (s) {
                                return s.name;
                            })
                        }]
                    }
                }
            });
        });
    }

    // toggle layer visibility
    function toggleVisibility(layerId, allLayers, layerColor) {

        // create a clickable button
        var button = document.createElement('button');
        var buttonLabel = layerId.replace("_", " ");
        button.id = layerId;
        button.className = 'active';
        button.textContent = buttonLabel.charAt(0).toUpperCase() + buttonLabel.slice(1);
        button.style.opacity = 1.0;
        button.style.background = layerColor;

        // toggle visibility when clicked
        button.onclick = function (e) {
            var clickedLayer = this.id;
            e.preventDefault();
            e.stopPropagation();
            var visibility = map.getLayoutProperty(clickedLayer, 'visibility');
            var target = document.getElementById(clickedLayer);
            if (visibility === 'visible') {
                for (let i = 0; i < allLayers.length; i++) {
                    map.setLayoutProperty(allLayers[i], 'visibility', 'none');
                }
                this.className = '';
                target.style.background = '#808080';
                target.style.color = '#ffffff';
            } else {
                this.className = 'active';
                for (let i = 0; i < allLayers.length; i++) {
                    map.setLayoutProperty(allLayers[i], 'visibility', 'visible');
                }
                target.style.background = layerColor;
            }
        };

        // add button to menu div
        var layers = document.getElementById('layers');
        layers.appendChild(button);
    }

    // distinct color pallete
    function distinctColors(i) {
        // Generate colors (as Chroma.js objects)
        var colors = paletteGenerator.generate(
            i, // Colors
            function (color) { // This function filters valid colors
                var hcl = color.hcl();
                return hcl[0] >= 0 && hcl[0] <= 360 &&
                    hcl[1] >= 40 && hcl[1] <= 70 &&
                    hcl[2] >= 15 && hcl[2] <= 85;
            },
            false, // Using Force Vector instead of k-Means
            50, // Steps (quality)
            false, // Ultra precision
            'Compromise' // Color distance type (colorblindness)
        );
        // Sort colors by differenciation first
        return paletteGenerator.diffSort(colors, 'Compromise');
    }

    // function to iteratively add as many layers as in tileset
    function setLayers(newNumLayers) {
        var colors = distinctColors(newNumLayers);
        for (let i = numLayers; i < newNumLayers; ++i) {
            var layerColor = colors[i].hex();
            var routeLayerId = 'route_' + i;
            var stopLayerId = routeLayerId + '_stops';
            var dirLayerId = routeLayerId + '_dirs';
            var allLayers = [routeLayerId, stopLayerId, dirLayerId];
            addRoutes(routeLayerId, stopLayerId, dirLayerId, layerColor);
            toggleVisibility(routeLayerId, allLayers, layerColor);
        }
        numLayers = newNumLayers;
    };

    // function to add map inspection
    function addInspection() {
        var inspect = new MapboxInspect({
            showInspectMap: false,
            showInspectButton: true,
        });
        map.addControl(inspect);
        map.on('styledata', function () {
            var layerList = document.getElementById('layerList');
            layerList.innerHTML = '';
            Object.keys(inspect.sources).forEach(function (sourceId) {
                var layerIds = inspect.sources[sourceId];
                layerIds.forEach(function (layerId) {
                    var item = document.createElement('div');
                    item.innerHTML = '<div style="' +
                        'background:' + inspect.assignLayerColor(layerId) + ';' +
                        '"></div> ' + layerId;
                    layerList.appendChild(item);
                });
            })
        });
    }

    // function to animate tracker on route
    function animate(counter, leg, steps) {

        // debugging
        console.log("leg: " + leg, "counter: " + counter, "step: " + steps)

        // Update tracker geometry to a new position based on counter denoting
        // the index to access the arc.
        tracker.features[0].geometry.coordinates =
            route.features[leg].geometry.coordinates[counter];

        // Calculate the bearing to ensure the icon is rotated to match the route arc
        // The bearing is calculate between the current point and the next point, except
        // at the end of the arc use the previous point and the current point
        tracker.features[0].properties.bearing = turf.bearing(
            turf.point(
                route.features[leg].geometry.coordinates[
                    counter >= steps ? counter - 1 : counter
                ]
            ),
            turf.point(
                route.features[leg].geometry.coordinates[
                    counter >= steps ? counter : counter + 1
                ]
            )
        );

        // Update the source with this new data.
        map.getSource('tracker_source').setData(tracker);

        // Request the next frame of animation so long the end has not been reached.
        counter = counter + 1;
        if (counter < steps) {
            requestAnimationFrame(animate);
        }
    }

    // function to reset animation
    function animateResetRoute() {
        document.getElementById('reset-animation').addEventListener('click', function () {
            // Set the coordinates of the original tracker back to origin
            tracker.features[0].geometry.coordinates = [0, 0];

            // Update the source layer
            map.getSource('tracker_source').setData(tracker);

            // Reset the counter
            leg = 0;
            counter = 0;

            // get coordinates
            var coordinates = route.features[leg].geometry.coordinates
            steps = coordinates.length

            // get bbox of linestring
            var bounds = coordinates.reduce(function (bounds, coord) {
                return bounds.extend(coord);
            }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));

            // fit linestring to zoom
            map.fitBounds(bounds, {
                padding: 200
            });

            // Restart the animation.
            animate(counter, leg, steps);
        });
    }

    // function to start next route leg animation
    function animateNextLeg() {
        document.getElementById('next-leg').addEventListener('click', function () {

            // Reset the counter
            leg = leg + 1;
            counter = 0;

            // get coordinates
            var coordinates = route.features[leg].geometry.coordinates
            steps = coordinates.length

            // get bbox of linestring
            var bounds = coordinates.reduce(function (bounds, coord) {
                return bounds.extend(coord);
            }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));

            // fit linestring to zoom
            map.fitBounds(bounds, {
                padding: 200
            });

            // TODO: Wait on zoom to complete before starting animation
            // Restart the animation.
            animate(counter, leg, steps)
        });

    }

    // function to start previous route leg animation
    function animatePreviousLeg() {
        document.getElementById('prev-leg').addEventListener('click', function () {
            // Reset the counter
            leg = leg - 1;
            counter = 0;

            // get coordinates
            var coordinates = route.features[leg].geometry.coordinates
            steps = coordinates.length

            // get bbox of linestring
            var bounds = coordinates.reduce(function (bounds, coord) {
                return bounds.extend(coord);
            }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));

            // fit linestring to zoom
            map.fitBounds(bounds, {
                padding: 200
            });

            // Restart the animation.
            animate(counter, leg, steps);
        });

    }

    // load the map
    map.on('load', function () {

        // add sources
        addSources();

        // add routes
        const numRoutes = 6;
        setLayers(numRoutes);

        // add animation and controls
        /* addTracker();
           animateResetRoute();
           animateNextLeg();
           animatePreviousLeg(); */

        // for debugging
        /* addInspection();
           console.log("the route json >>> ", route)
           route.features.forEach(function (feature) {
            console.log(feature.properties)
        }); */

    });
}