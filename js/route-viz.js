// an access token
mapboxgl.accessToken = 'pk.eyJ1Ijoia2NhdmFnbm9sbyIsImEiOiJjamtvOWExZHYydm1xM3BreG9pb3hza3J6In0.yKhLQH7NxC9rbsrCpilLQw';

// TODO: abstract the origin based on view
// set an origin
var origin = [-83.924137, 35.961671]

// initialize number of layers
var num_layers = 0;

// load mapbox gl
var map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v10?optimize=true',
    center: origin,
    zoom: 10,
    attributionControl: false,
    failIfMajorPerformanceCaveat: true
}).addControl(new mapboxgl.AttributionControl({
    compact: true,
    customAttribution: "<a href='https://github.com/kcavagnolo/knoxville_ale_trail' target='_blank'>&copy; kcavagnolo</a>"
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
    })
);

// Add zoom and rotation controls to the map.
map.addControl(new mapboxgl.NavigationControl());

// add map inspection
var inspect = new MapboxInspect({
    showInspectMap: false,
    showInspectButton: true,
});

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
    closeOnClick: false
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
function addRoutes(i, random_color) {

    // set the id
    var routeLayerId = 'route_' + i;

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
            'line-color': random_color,
            'line-width': 2
        }
    });

    // make visibility toggle
    toggleVisibility(routeLayerId, random_color);
}

// function to add stop layers
function addStops(i, random_color) {

    // set the id
    var stopLayerId = 'route_' + i + '_stops';

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
            'circle-radius': 6,
            'circle-color': [
                'case',
                ['boolean', ['feature-state', 'hover'], false],
                "#ffffff",
                random_color
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
        console.log("the data >>>", e.features[0])
        var coordinates = e.features[0].geometry.coordinates.slice();
        var properties = e.features[0].properties;
        var layer = e.features[0].layer;
        var description_elements = [
            properties.address,
            "arrive: " + new Date(properties.arrival_time).toLocaleString(),
            "depart: " + new Date(properties.departure_time).toLocaleString()
        ]
        var brewery = properties.location_id.toUpperCase();
        var description = '<h3>' + brewery + '</h3><p>' + description_elements.join('<br>') + '</p>'

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

    // make visibility toggle
    toggleVisibility(stopLayerId, random_color);
}

// toggle layer visibility
function toggleVisibility(layerId, random_color) {

    // test of fetching json data
    var url = `https://raw.githubusercontent.com/kcavagnolo/knoxville_ale_trail/master/data/geojson/${layerId}.geojson`;
    fetch(url)
        .then(response => response.json())
        .then(route_data => {
            var route_name = route_data['metadata']['average_bearing'];
        });

    // create a clickable button
    var button = document.createElement('button');
    button.id = layerId + "_toggle";
    button.className = 'active';
    button.textContent = layerId;
    button.style.opacity = 1.0;
    button.style.background = random_color;

    // toggle visibility when clicked
    button.onclick = function (e) {
        var clickedLayer = this.textContent;
        e.preventDefault();
        e.stopPropagation();
        var visibility = map.getLayoutProperty(clickedLayer, 'visibility');
        var target = document.getElementById(button.id);
        if (visibility === 'visible') {
            map.setLayoutProperty(clickedLayer, 'visibility', 'none');
            this.className = '';
            target.style.background = '#808080';
            target.style.color = '#ffffff';
        } else {
            this.className = 'active';
            map.setLayoutProperty(clickedLayer, 'visibility', 'visible');
            target.style.background = random_color;
        }
    };

    // add button to menu div
    var layers = document.getElementById('menu');
    layers.appendChild(button);
}

// add collapsible content
function addCollapsible() {
    var coll = document.getElementsByClassName("collapsible");
    var i;
    for (i = 0; i < coll.length; i++) {
        coll[i].addEventListener("click", function () {
            this.classList.toggle("active");
            var content = this.nextElementSibling;
            if (content.style.display === "block") {
                content.style.display = "none";
            } else {
                content.style.display = "block";
            }
        });
    }
}

// function to iteratively add as many layers as in tileset
function setLayers(new_num_layers) {
    for (let i = new_num_layers; i < num_layers; ++i) {
        map.removeLayer('route_' + i);
        map.removeLayer('route_' + i + '_stops');
    }
    for (let i = num_layers; i < new_num_layers; ++i) {
        // TODO: change random color to... not random
        var random_color = '#' + Math.random().toString(16).slice(2, 8).toUpperCase();
        addRoutes(i, random_color);
        addStops(i, random_color);
    }
    num_layers = new_num_layers;
};

// function to add map inspection
function addInspection() {
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
function animate() {

    // debugging
    //console.log("leg: " + leg, "counter: " + counter, "step: " + steps)

    // Update tracker geometry to a new position based on counter denoting
    // the index to access the arc.
    tracker.features[0].geometry.coordinates =
        route.features[leg].geometry.coordinates[counter];

    // Calculate the bearing to ensure the icon is rotated to match the route arc
    // The bearing is calculate between the current point and the next point, except
    // at the end of the arc use the previous point and the current point
    /* tracker.features[0].properties.bearing = turf.bearing(
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
    ); */

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
    numRoutes = 5;
    setLayers(numRoutes);

    // add collapsible
    addCollapsible();

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