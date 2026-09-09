import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, Tooltip as LTooltip, useMap } from 'react-leaflet';
import { mapApi, predictions } from '../api/endpoints';
import { RiskBadge, FactorBars, Spinner, ErrorState } from '../components/common.jsx';
import { riskColor, crimeColor } from '../utils/risk';
import { fmtDate } from '../utils/format';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../context/ToastContext.jsx';

// Karnataka center
const CENTER = [12.9, 77.6];
const ZOOM = 8;

function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 11), { duration: 0.8 });
  }, [target, map]);
  return null;
}

export default function LiveMap() {
  const toast = useToast();
  const { subscribe } = useWebSocket();
  const [hotspots, setHotspots] = useState([]);
  const [riskZones, setRiskZones] = useState([]);
  const [complaints, setComplaints] = useState([]);
  const [atms, setAtms] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [layers, setLayers] = useState({ hotspots: true, riskZones: true, complaints: true, atms: false, withdrawals: false });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [flyTarget, setFlyTarget] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    try {
      const [hs, rz, comp, atm, wd] = await Promise.all([
        mapApi.hotspots(),
        mapApi.riskZones(),
        mapApi.complaints(30, 500),
        mapApi.atms(),
        mapApi.withdrawals(3, 1000),
      ]);
      setHotspots(hs.features || []);
      setRiskZones(rz.features || []);
      setComplaints(comp.features || []);
      setAtms(atm.features || []);
      setWithdrawals(wd.features || []);
      setError('');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // react to live events
  useEffect(() => {
    const off = subscribe('hotspot', () => { load(); });
    const off2 = subscribe('alert_created', (m) => {
      toast.warn(`New ${m.payload?.severity} alert: ${m.payload?.atm_id}`);
      load();
    });
    const off3 = subscribe('predictions_generated', (m) => {
      setGenerating(false);
      toast.success(`Generated ${m.payload?.n_predictions} predictions — ${m.payload?.alerts_created ?? 0} alerts`);
      load();
    });
    const off4 = subscribe('predictions_error', (m) => {
      setGenerating(false);
      toast.error(m.payload?.error || 'Prediction generation failed');
    });
    return () => { off(); off2(); off3(); off4(); };
  }, [subscribe, load, toast]);

  async function regenerate() {
    setGenerating(true);
    toast.info('Running the model over all ATMs for the next 6h window…');
    try {
      await predictions.generate();
    } catch (e) {
      toast.error(e.message);
      setGenerating(false);
    }
  }

  function onHotspotClick(e) {
    const p = e.target.options?.props || e;
    const ll = e.latlng || { lat: p.latitude, lng: p.longitude };
    setSelected(p);
    setDetail(null);
    setFlyTarget({ lat: ll.lat, lon: ll.lng });
    predictions.get(p.prediction_id).then(setDetail).catch(() => {});
  }

  const topHotspots = useMemo(
    () => [...hotspots].sort((a, b) => (b.properties.risk_score || 0) - (a.properties.risk_score || 0)),
    [hotspots]
  );

  if (loading) return <Spinner label="Loading live threat map…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="map-page">
      <div className="map-shell">
        <MapContainer center={CENTER} zoom={ZOOM} style={{ height: '100%', width: '100%' }} zoomControl={true}>
          <TileLayer
            className="dark-tiles"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FlyTo target={flyTarget} />

          {layers.riskZones && riskZones.map((f, i) => {
            const [lon, lat] = f.geometry.coordinates;
            const r = f.properties;
            return (
              <Circle key={`rz${i}`} center={[lat, lon]} radius={r.radius_km * 1000}
                pathOptions={{ color: riskColor(r.risk_score), weight: 1, fillColor: riskColor(r.risk_score), fillOpacity: 0.12, dashArray: '4 4' }} />
            );
          })}

          {layers.atms && atms.map((f, i) => {
            const [lon, lat] = f.geometry.coordinates;
            return (
              <CircleMarker key={`atm${i}`} center={[lat, lon]} radius={2.5}
                pathOptions={{ color: '#5b6b82', fillColor: '#5b6b82', fillOpacity: 0.7, weight: 0.5 }}>
                <LTooltip><b>{f.properties.atm_id}</b><br />Bank {f.properties.bank_id}<br />{f.properties.district}</LTooltip>
              </CircleMarker>
            );
          })}

          {layers.complaints && complaints.map((f, i) => {
            const [lon, lat] = f.geometry.coordinates;
            const p = f.properties;
            const c = crimeColor(p.crime_category);
            return (
              <CircleMarker key={`c${i}`} center={[lat, lon]} radius={3.5}
                pathOptions={{ color: c, fillColor: c, fillOpacity: 0.8, weight: 0.5 }}>
                <LTooltip><b>{p.crime_category}</b><br />{p.victim_district}<br />{fmtDate(p.timestamp)}</LTooltip>
              </CircleMarker>
            );
          })}

          {layers.withdrawals && withdrawals.map((f, i) => {
            const [lon, lat] = f.geometry.coordinates;
            return (
              <CircleMarker key={`w${i}`} center={[lat, lon]} radius={3}
                pathOptions={{ color: '#a78bfa', fillColor: '#a78bfa', fillOpacity: 0.6, weight: 0.5 }}>
                <LTooltip><b>₹{f.properties.amount?.toLocaleString('en-IN')}</b><br />{f.properties.atm_id}<br />{fmtDate(f.properties.timestamp)}</LTooltip>
              </CircleMarker>
            );
          })}

          {layers.hotspots && topHotspots.map((f) => {
            const [lon, lat] = f.geometry.coordinates;
            const p = f.properties;
            const r = p.risk_score;
            const size = 6 + (r / 100) * 14;
            return (
              <CircleMarker key={p.prediction_id} center={[lat, lon]} radius={size}
                pathOptions={{ color: riskColor(r), weight: 2, fillColor: riskColor(r), fillOpacity: 0.35 }}
                props={p}
                eventHandlers={{ click: onHotspotClick }}>
                <LTooltip><b>{p.atm_id}</b> · risk {r}<br />{p.district}</LTooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>

        {/* Layer control */}
        <div className="map-panel">
          <h4>Map Layers</h4>
          {[
            ['hotspots', 'Predicted Hotspots', 'var(--red)'],
            ['riskZones', 'Risk Zones', 'var(--orange)'],
            ['complaints', 'Complaints', 'var(--purple)'],
            ['atms', 'ATMs', '#5b6b82'],
            ['withdrawals', 'Withdrawals', 'var(--purple)'],
          ].map(([key, label, color]) => (
            <label className="layer-toggle" key={key}>
              <input type="checkbox" checked={layers[key]} onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))} />
              <span className="swatch" style={{ background: color }} />
              {label}
            </label>
          ))}
          <div className="divider" />
          <button className="btn btn-primary btn-sm" style={{ width: '100%', justifyContent: 'center' }} onClick={regenerate} disabled={generating}>
            {generating ? 'Running model…' : '⟳ Regenerate predictions'}
          </button>
          <div className="text-xs muted mt-1" style={{ textAlign: 'center' }}>{generating ? 'Scoring all ATMs in the background…' : `${hotspots.length} hotspots · ${complaints.length} complaints`}</div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="map-detail">
            <div className="flex-between mb-1">
              <div>
                <div className="mono" style={{ fontSize: 15, fontWeight: 700 }}>{selected.atm_id}</div>
                <div className="text-sm muted">{selected.district}, Karnataka</div>
              </div>
              <button className="btn btn-sm" onClick={() => setSelected(null)}>✕</button>
            </div>
            <div className="flex" style={{ justifyContent: 'space-around', padding: '8px 0' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: riskColor(selected.risk_score) }}>{selected.risk_score}</div>
                <div className="text-xs muted">RISK</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--cyan)' }}>{(selected.probability * 100).toFixed(0)}%</div>
                <div className="text-xs muted">PROBABILITY</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--purple)' }}>{(selected.confidence * 100).toFixed(0)}%</div>
                <div className="text-xs muted">CONFIDENCE</div>
              </div>
            </div>
            <div className="text-xs muted">Window: {fmtDate(selected.window_start)} {selected.window_start?.slice(11, 16)} → {selected.window_end?.slice(11, 16)} UTC</div>
            <div className="divider" />
            <div className="panel-title" style={{ marginBottom: 8 }}>Key Drivers</div>
            {detail ? <FactorBars factors={detail.factors || []} /> : <div className="muted text-sm">Loading drivers…</div>}
            {detail?.recommended_action && (
              <>
                <div className="divider" />
                <div className="panel-title" style={{ marginBottom: 6 }}>Recommended Action</div>
                <div className="text-sm" style={{ lineHeight: 1.5 }}>{detail.recommended_action}</div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}