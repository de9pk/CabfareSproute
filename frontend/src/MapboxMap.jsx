import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxGeocoder from '@mapbox/mapbox-gl-geocoder';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.css';

// Token is loaded from .env (VITE_MAPBOX_TOKEN) — never hardcode secrets in source
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

mapboxgl.accessToken = MAPBOX_TOKEN;

/**
 * MapboxMap
 * Props:
 *   onLocationSelect(info) – called when the user picks a geocoder suggestion.
 *     info = { placeName, coordinates: [lng, lat] }
 */
export default function MapboxMap({ onLocationSelect }) {
  const mapContainer = useRef(null);
  const mapRef       = useRef(null);
  const markerRef    = useRef(null);

  useEffect(() => {
    // Initialise the map only once
    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [75.7873, 26.9124], // Jaipur
      zoom: 11,
    });
    mapRef.current = map;

    // Navigation controls (zoom / rotate)
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    // Geocoder with fuzzy matching + autocomplete
    const geocoder = new MapboxGeocoder({
      accessToken: MAPBOX_TOKEN,
      mapboxgl,
      placeholder: 'Search any location…',
      fuzzyMatch: true,
      autocomplete: true,
      marker: false, // we manage our own marker
    });

    map.addControl(geocoder, 'top-left');

    // When user selects a result
    geocoder.on('result', (e) => {
      const { place_name, center } = e.result; // center = [lng, lat]

      // Remove previous marker
      if (markerRef.current) markerRef.current.remove();

      // Add a glowing amber marker element
      const el = document.createElement('div');
      el.className = 'mapbox-custom-marker';

      markerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat(center)
        .setPopup(
          new mapboxgl.Popup({ offset: 25, className: 'mapbox-custom-popup' }).setHTML(
            `<strong>${place_name}</strong><br/><small>${center[1].toFixed(5)}, ${center[0].toFixed(5)}</small>`
          )
        )
        .addTo(map);

      markerRef.current.togglePopup();

      // Fly to selected location
      map.flyTo({ center, zoom: 14, speed: 1.4, curve: 1.2 });

      // Notify parent
      if (onLocationSelect) {
        onLocationSelect({ placeName: place_name, coordinates: center });
      }
    });

    return () => {
      geocoder.onRemove();
      map.remove();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mapbox-wrapper">
      <div ref={mapContainer} className="mapbox-container" />
    </div>
  );
}
