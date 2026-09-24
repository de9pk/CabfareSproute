import React, { useState } from 'react';
import axios from 'axios';
import './index.css';
import MapboxMap from './MapboxMap';

const API_BASE_URL = 'http://127.0.0.1:8000';

function App() {
  const [pickup, setPickup] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [animating, setAnimating] = useState(false);
  const [results, setResults] = useState(null);
  const [bookingData, setBookingData] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!pickup || !destination) return;

    setLoading(true);
    setAnimating(true);
    setResults(null);
    setBookingData(null);

    // Enforce minimum animation time
    const minAnimTime = new Promise(resolve => setTimeout(resolve, 3000));

    try {
      const apiCall = axios.post(`${API_BASE_URL}/api/fares`, {
        pickup,
        destination,
        platforms: ['Uber', 'Ola', 'Rapido'],
        mode: 'demo' // using demo for quick showcase, change to real in production
      });

      const [res] = await Promise.all([apiCall, minAnimTime]);
      
      const successResults = res.data.results.filter(r => r.status === 'success' && r.fare_min > 0);
      setResults(successResults.sort((a, b) => a.fare_min - b.fare_min));
    } catch (error) {
      console.error("Error fetching fares:", error);
      alert("Failed to fetch fares. Is the backend running?");
    } finally {
      setLoading(false);
      // Wait a moment for cab to reach end before resetting
      setTimeout(() => setAnimating(false), 500); 
    }
  };

  const platformConfig = {
    "Uber": { color: "#ffffff", emoji: "⬛" },
    "Ola": { color: "#3CB371", emoji: "🟢" },
    "Rapido": { color: "#FFD700", emoji: "🟡" }
  };

  if (bookingData) {
    return (
      <div className="container mt-5 pt-5">
        <div className="booking-view mx-auto" style={{ maxWidth: '600px' }}>
          <h2 className="mb-4">Confirm Your Booking</h2>
          <div className="spinner-cab mb-4" style={{ fontSize: '4rem' }}>🚖</div>
          <h4 className="mb-3">
            {platformConfig[bookingData.platform]?.emoji} {bookingData.platform}
          </h4>
          <div className="mb-4 text-start bg-dark p-4 rounded text-light text-opacity-75">
            <p><strong>Route:</strong> {pickup} <i className="bi bi-arrow-right"></i> {destination}</p>
            <p><strong>Ride Type:</strong> {bookingData.ride_type}</p>
            <p><strong>Estimated Fare:</strong> <span className="fs-3 text-white fw-bold">{bookingData.fare}</span></p>
            <p><strong>ETA:</strong> {bookingData.eta}</p>
          </div>
          <div className="d-flex gap-3 justify-content-center">
            <button className="btn btn-secondary px-4 py-2 rounded-pill fw-bold" onClick={() => setBookingData(null)}>
              Cancel
            </button>
            <button className="btn btn-success px-4 py-2 rounded-pill fw-bold" onClick={() => alert('Booking confirmed! (Demo)')}>
              Confirm Booking
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-5">
      <div className="hero-header text-center shadow-lg">
        <h1 className="hero-title">Cab Fare <span>Comparator</span></h1>
        <p className="hero-sub mt-2">Real-time live fare comparison · Uber vs Ola vs Rapido</p>
      </div>

      <div className="card bg-dark border-0 shadow-lg p-4 mb-5" style={{ borderRadius: '16px' }}>
        <form onSubmit={handleSearch} className="row g-3 align-items-end">
          <div className="col-md-5">
            <label className="form-label text-muted small fw-bold mb-2">PICKUP LOCATION</label>
            <div className="input-group">
              <span className="input-group-text bg-transparent border-0 text-success ps-0"><i className="bi bi-geo-alt-fill"></i></span>
              <input 
                type="text" 
                className="form-control custom-input" 
                placeholder="Where from?" 
                value={pickup}
                onChange={(e) => setPickup(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="col-md-5">
            <label className="form-label text-muted small fw-bold mb-2">DESTINATION</label>
            <div className="input-group">
              <span className="input-group-text bg-transparent border-0 text-danger ps-0"><i className="bi bi-geo-fill"></i></span>
              <input 
                type="text" 
                className="form-control custom-input" 
                placeholder="Where to?" 
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="col-md-2">
            <button type="submit" className="search-btn w-100 d-flex align-items-center justify-content-center gap-2" disabled={loading}>
              {loading ? (
                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
              ) : (
                <i className="bi bi-search"></i>
              )}
              {loading ? 'Searching...' : 'Compare'}
            </button>
          </div>
        </form>
      </div>

      {/* Animation Section */}
      {(loading || animating) && (
        <div className="animation-container">
          <div className={`cab-icon ${animating ? 'animate' : ''}`}>🚖</div>
          <div className="destination-flag"><i className="bi bi-flag-fill"></i></div>
        </div>
      )}

      {/* Results Section */}
      {results && results.length > 0 && !loading && (
        <div className="results-section mt-5 fade-in">
          <h4 className="mb-4 text-center fw-bold" style={{ color: 'rgba(255,255,255,0.9)' }}>Cheapest Options Available</h4>
          <div className="row g-4 justify-content-center">
            {results.map((result, index) => {
              const isCheapest = index === 0;
              const platform = result.platform;
              const cfg = platformConfig[platform] || { color: '#888', emoji: '🚗' };

              return (
                <div className="col-md-4" key={platform}>
                  <div 
                    className={`fare-card ${isCheapest ? 'cheapest' : ''}`}
                    onClick={() => setBookingData(result)}
                  >
                    <div>
                      <span className="platform-badge" style={{ backgroundColor: `${cfg.color}22`, color: cfg.color, border: `1px solid ${cfg.color}44` }}>
                        {cfg.emoji} {platform}
                      </span>
                      {isCheapest && <span className="cheapest-badge"><i className="bi bi-check-circle-fill"></i> CHEAPEST</span>}
                    </div>
                    <div className="fare-amount">{result.fare}</div>
                    <div className="text-muted small mt-2">{result.ride_type}</div>
                    <div className="d-flex align-items-center gap-2 mt-3 text-light text-opacity-50 small">
                      <i className="bi bi-clock"></i> ETA: {result.eta}
                    </div>
                    {isCheapest && results.length > 1 && (
                      <div className="mt-3 p-2 rounded text-center small fw-bold" style={{ backgroundColor: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                        Save ₹{results[results.length - 1].fare_min - result.fare_min} vs {results[results.length - 1].platform}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {results && results.length === 0 && !loading && (
        <div className="text-center mt-5 text-muted">
          <h3><i className="bi bi-emoji-frown"></i> No rides available</h3>
          <p>Try searching for a different route.</p>
        </div>
      )}

      {/* ── Mapbox Section ── */}
      <div className="map-section mt-5">
        <div className="map-section-header d-flex align-items-center gap-3 mb-3">
          <div className="map-section-icon">
            <i className="bi bi-map-fill"></i>
          </div>
          <div>
            <h4 className="mb-0 fw-bold" style={{ color: 'rgba(255,255,255,0.9)' }}>
              Location Explorer
            </h4>
            <p className="mb-0 small" style={{ color: 'rgba(255,255,255,0.45)' }}>
              Search any place — autocomplete &amp; fuzzy matching enabled
            </p>
          </div>
        </div>

        {selectedLocation && (
          <div className="selected-location-pill fade-in mb-3">
            <i className="bi bi-geo-alt-fill"></i>
            <span className="fw-bold">{selectedLocation.placeName}</span>
            <span className="coords-badge">
              {selectedLocation.coordinates[1].toFixed(4)}, {selectedLocation.coordinates[0].toFixed(4)}
            </span>
          </div>
        )}

        <MapboxMap onLocationSelect={setSelectedLocation} />
      </div>

    </div>
  );
}

export default App;
