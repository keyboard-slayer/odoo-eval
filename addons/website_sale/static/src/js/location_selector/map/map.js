/** @odoo-module **/
/*global L*/

import { Component, useEffect, useRef } from "@odoo/owl";
import { renderToString } from "@web/core/utils/render";

export class Map extends Component {
    static template = 'website_sale.locationSelector.map';
    static props = {
        locations: Array, // TODO VCR
        selectedLocationId: [String, {value: false}],
        setSelectedLocation: Function,
    };

    setup() {
        this.leafletMap = null;
        this.markers = [];
        this.mapContainerRef = useRef("mapContainer");

        useEffect(
            () => {
                this.leafletMap = L.map(this.mapContainerRef.el, {
                    zoom: 13,
                });
                L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }).addTo(this.leafletMap);
            },
            () => []
        );
        useEffect(
            (locations) => {
                this.addMarkers(locations);
            },
            () => [this.props.locations]
        );
        useEffect(
            (locations, selectedLocationId) => {
                const selectedLocation = locations.find(
                    l => String(l.id) === selectedLocationId
                );
                if (selectedLocation) {
                    this.centerMap([selectedLocation.latitude, selectedLocation.longitude]);
                }
            },
            () => [this.props.locations, this.props.selectedLocationId]
        );
    }

    centerMap(LatLong) {
        this.leafletMap.panTo(LatLong, { animate: true });
    }

    addMarkers(locations) {
        this.removeMarkers();
        for (const loc of locations) {
            // Icon creation
            const iconInfo = {
                className: "",
                html: renderToString(
                    "website_sale.locationSelector.map.marker",
                    { number: locations.indexOf(loc) + 1 },
                ),
            };
            const marker = L.marker(
                [ loc.latitude, loc.longitude ],
                {
                    icon: L.divIcon(iconInfo),
                    title: locations.indexOf(loc) + 1,
                },
            );
            marker.addTo(this.leafletMap);
            marker.on("click", () => {
                this.props.setSelectedLocation(loc.id);
            });
            this.markers.push(marker);
        }
    }

    removeMarkers() {
        for (const marker of this.markers) {
            marker.off("click");
            this.leafletMap.removeLayer(marker);
        }
        this.markers = [];
    }
}
