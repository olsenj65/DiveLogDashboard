#!/usr/bin/env python3
"""
Shearwater Dive Log Dashboard Generator
=======================================
Generates an interactive HTML dashboard from a Shearwater Cloud database export.

Usage:
    python generate_dive_dashboard.py <path_to_shearwater.db>
    
Example:
    python generate_dive_dashboard.py "Shearwater_Cloud__myemail__2026-01-22.db"

The script will create 'dive_dashboard.html' in the same folder.
Double-click the HTML file to open it in your browser.

Requirements:
    - Python 3.6+
    - No additional packages needed (uses built-in sqlite3 and json)
"""

import sqlite3
import json
import sys
import os
from datetime import datetime

def extract_dive_data(db_path):
    """Extract dive data from Shearwater Cloud database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query dive details with calculated values
    cursor.execute('''
        SELECT d.DiveNumber, d.DiveDate, d.Location, d.Site, d.Depth, d.DiveLengthTime, 
               d.TankProfileData, l.calculated_values_from_samples
        FROM dive_details d
        LEFT JOIN log_data l ON d.DiveId = l.log_id
        ORDER BY d.DiveDate
    ''')
    
    dives = []
    for row in cursor.fetchall():
        calc = json.loads(row[7]) if row[7] else {}
        tank_data = json.loads(row[6]) if row[6] else {}
        
        # Get tank info
        start_psi = end_psi = 0
        o2_pct = 21
        if tank_data.get('TankData') and len(tank_data['TankData']) > 0:
            td = tank_data['TankData'][0]
            start_psi = int(td.get('StartPressurePSI') or 0)
            end_psi = int(td.get('EndPressurePSI') or 0)
            if td.get('GasProfile'):
                o2_pct = td['GasProfile'].get('O2Percent', 21)
        
        avg_temp_f = calc.get('AverageTemp', 82)
        avg_temp_c = round((avg_temp_f - 32) * 5/9, 1)
        
        depth_m = float(row[4]) if row[4] else 0
        duration_sec = int(row[5]) if row[5] else 0
        
        dive = {
            'number': int(row[0]) if row[0] else 0,
            'date': row[1][:10] if row[1] else '',
            'time': row[1][11:16] if row[1] and len(row[1]) > 11 else '',
            'location': row[2] or '',
            'site': row[3] or '',
            'maxDepthM': round(depth_m, 1),
            'maxDepthFt': round(depth_m * 3.28084),
            'durationMin': round(duration_sec / 60),
            'durationSec': duration_sec,
            'startPSI': start_psi,
            'endPSI': end_psi,
            'gasUsed': start_psi - end_psi if start_psi and end_psi else 0,
            'o2Percent': o2_pct,
            'avgTempC': avg_temp_c,
            'avgDepthM': round(calc.get('AverageDepth', 0) * 0.3048, 1),  # feet to meters
            'endGF99': round(calc.get('EndGF99', 0))
        }
        dives.append(dive)
    
    conn.close()
    return dives

def get_computer_info(db_path):
    """Get dive computer info from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT SerialNumber, Firmware FROM StoredDiveComputer LIMIT 1')
        row = cursor.fetchone()
        if row:
            return {'serial': row[0], 'firmware': row[1]}
    except:
        pass
    
    conn.close()
    return {'serial': 'Unknown', 'firmware': ''}

def calculate_trip_stats(dives):
    """Calculate statistics for each trip/location."""
    locations = {}
    for d in dives:
        loc = d['location'] if d['location'] else 'Unknown'
        if loc == 'Curaco':
            loc = 'Curacao'
        if loc not in locations:
            locations[loc] = {'dives': [], 'dates': []}
        locations[loc]['dives'].append(d)
        if d['date']:
            locations[loc]['dates'].append(d['date'])
    
    trips = []
    colors = {'Bonaire': '#3b82f6', 'Cozumel': '#22c55e', 'Curacao': '#f97316'}
    
    for loc, data in locations.items():
        if not data['dates']:
            continue
        dates = sorted(data['dates'])
        start_date = datetime.strptime(dates[0], '%Y-%m-%d').strftime('%b %d')
        end_date = datetime.strptime(dates[-1], '%Y-%m-%d').strftime('%b %d, %Y')
        
        total_min = sum(d['durationMin'] for d in data['dives'])
        max_depth = max(d['maxDepthM'] for d in data['dives'])
        avg_gas = sum(d['gasUsed'] for d in data['dives']) / len(data['dives']) if data['dives'] else 0
        
        trips.append({
            'name': loc if loc != 'Curacao' else 'Curaçao',
            'dates': f"{start_date} - {end_date}",
            'dives': len(data['dives']),
            'hours': round(total_min / 60, 1),
            'maxDepth': max_depth,
            'avgGas': round(avg_gas),
            'color': colors.get(loc, '#94a3b8')
        })
    
    return trips

def generate_html(dives, computer_info, trips):
    """Generate the complete HTML dashboard."""
    
    # Convert dives to JavaScript format
    dives_js = json.dumps(dives, indent=12)
    trips_js = json.dumps(trips, indent=12)
    
    # Get date range
    dates = [d['date'] for d in dives if d['date']]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "Unknown"
    
    # Get primary gas
    o2_values = [d['o2Percent'] for d in dives if d['o2Percent'] > 21]
    primary_gas = f"EAN{max(set(o2_values), key=o2_values.count)}" if o2_values else "Air"
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shearwater Dive Log Analysis</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0c4a6e 50%, #164e63 100%);
            min-height: 100vh;
            padding: 20px;
            color: white;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        .header {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .header h1 {{ font-size: 2rem; margin-bottom: 8px; }}
        .header p {{ color: #93c5fd; }}
        .controls {{ display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }}
        select, button {{
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            padding: 10px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }}
        select:hover, button:hover {{ background: rgba(255,255,255,0.3); }}
        select option {{ color: #1e3a5f; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 14px;
            border: 1px solid rgba(255,255,255,0.2);
            text-align: center;
        }}
        .stat-card .icon {{ font-size: 1.2rem; margin-bottom: 4px; }}
        .stat-card .value {{ font-size: 1.4rem; font-weight: bold; }}
        .stat-card .label {{ color: #93c5fd; font-size: 0.75rem; }}
        .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
        .tab {{
            padding: 10px 20px;
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            border: none;
            color: white;
            cursor: pointer;
            font-weight: 500;
        }}
        .tab.active {{ background: #06b6d4; }}
        .content-panel {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.2);
            overflow: hidden;
        }}
        .table-container {{ overflow-x: auto; max-height: 60vh; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{
            background: rgba(255,255,255,0.15);
            padding: 10px 8px;
            text-align: left;
            color: #93c5fd;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        th:hover {{ background: rgba(255,255,255,0.2); }}
        td {{ padding: 8px; border-top: 1px solid rgba(255,255,255,0.1); }}
        tr {{ cursor: pointer; transition: background 0.2s; }}
        tr:hover {{ background: rgba(255,255,255,0.1); }}
        tr.selected {{ background: rgba(6, 182, 212, 0.3); }}
        .location-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 0.7rem;
            font-weight: 500;
        }}
        .location-bonaire {{ background: #3b82f6; }}
        .location-cozumel {{ background: #22c55e; }}
        .location-curacao, .location-curaco {{ background: #f97316; }}
        .location-unknown {{ background: #94a3b8; }}
        .mono {{ font-family: 'SF Mono', Monaco, monospace; font-size: 0.8rem; }}
        .gf-low {{ color: #4ade80; }}
        .gf-med {{ color: #fbbf24; }}
        .gf-high {{ color: #f87171; }}
        .gas-badge {{ background: #8b5cf6; padding: 2px 5px; border-radius: 5px; font-size: 0.65rem; }}
        .consumption-high {{ color: #f87171; }}
        .consumption-med {{ color: #fbbf24; }}
        .consumption-low {{ color: #4ade80; }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            padding: 20px;
        }}
        .chart-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .chart-card h3 {{ margin-bottom: 12px; font-size: 0.95rem; }}
        .chart-container {{ height: 200px; position: relative; }}
        .trips-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 16px;
            padding: 20px;
        }}
        .trip-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .trip-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
        .trip-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        .trip-stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 16px;
            text-align: center;
        }}
        .trip-stat-value {{ font-size: 1.1rem; font-weight: bold; }}
        .trip-stat-label {{ font-size: 0.7rem; color: #93c5fd; }}
        .detail-panel {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.2);
            margin-top: 20px;
            overflow: hidden;
        }}
        .detail-header {{
            background: rgba(6, 182, 212, 0.3);
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .detail-header h2 {{ font-size: 1.3rem; }}
        .detail-header .dive-meta {{ color: #93c5fd; font-size: 0.9rem; }}
        .detail-close {{
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2rem;
        }}
        .detail-body {{ padding: 20px; }}
        .detail-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }}
        .detail-stat {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }}
        .detail-stat .value {{ font-size: 1.3rem; font-weight: bold; }}
        .detail-stat .label {{ font-size: 0.7rem; color: #93c5fd; margin-top: 2px; }}
        .charts-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }}
        .chart-box {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 16px;
        }}
        .chart-box h4 {{ margin-bottom: 12px; font-size: 0.9rem; color: #93c5fd; }}
        .profile-note {{
            font-size: 0.7rem;
            color: #94a3b8;
            text-align: center;
            margin-top: 8px;
            font-style: italic;
        }}
        .hidden {{ display: none; }}
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .charts-row, .charts-grid {{ grid-template-columns: 1fr; }}
            .detail-stats {{ grid-template-columns: repeat(3, 1fr); }}
            .trip-stats {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤿 Shearwater Dive Log</h1>
            <p>Serial: {computer_info['serial']} | {date_range} | {primary_gas}</p>
            <div class="controls">
                <select id="locationFilter">
                    <option value="All">All Locations</option>
                </select>
                <button id="unitToggle">🌡️ Metric</button>
                <button id="pressureToggle">⛽ PSI</button>
            </div>
        </div>

        <div class="stats-grid" id="statsGrid"></div>

        <div class="tabs">
            <button class="tab active" data-tab="table">📋 Dive Table</button>
            <button class="tab" data-tab="charts">📊 Charts</button>
            <button class="tab" data-tab="gas">⛽ Gas Analysis</button>
            <button class="tab" data-tab="trips">🗺️ Trips</button>
        </div>

        <div class="content-panel">
            <div id="tablePanel" class="table-container"></div>
            <div id="chartsPanel" class="charts-grid hidden"></div>
            <div id="gasPanel" class="charts-grid hidden"></div>
            <div id="tripsPanel" class="trips-grid hidden"></div>
        </div>

        <div id="detailPanel" class="detail-panel hidden">
            <div class="detail-header">
                <div>
                    <h2 id="detailTitle">Dive #1</h2>
                    <div class="dive-meta" id="detailMeta"></div>
                </div>
                <button class="detail-close" onclick="closeDetail()">×</button>
            </div>
            <div class="detail-body">
                <div class="detail-stats" id="detailStats"></div>
                <div class="charts-row">
                    <div class="chart-box">
                        <h4>📉 Estimated Depth Profile</h4>
                        <div class="chart-container"><canvas id="depthProfileChart"></canvas></div>
                        <div class="profile-note">* Estimated profile based on max depth, avg depth & duration</div>
                    </div>
                    <div class="chart-box">
                        <h4>⛽ Tank Pressure</h4>
                        <div class="chart-container"><canvas id="tankPressureChart"></canvas></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const dives = {dives_js};
        const tripsData = {trips_js};

        let isMetric = true;
        let isPSI = true;
        let currentLocation = 'All';
        let sortField = 'number';
        let sortDir = 'asc';
        let selectedDive = null;
        let depthChart = null;
        let pressureChart = null;
        let charts = {{}};

        const psiToBar = psi => Math.round(psi * 0.0689476);

        // Populate location filter
        const locations = [...new Set(dives.map(d => d.location || 'Unknown').map(l => l === 'Curaco' ? 'Curacao' : l))];
        const locSelect = document.getElementById('locationFilter');
        locations.forEach(loc => {{
            const opt = document.createElement('option');
            opt.value = loc;
            opt.textContent = loc === 'Curacao' ? 'Curaçao' : loc;
            locSelect.appendChild(opt);
        }});

        function getFilteredDives() {{
            let filtered = currentLocation === 'All' ? [...dives] : 
                dives.filter(d => {{
                    const loc = (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location;
                    return loc === currentLocation || d.location === currentLocation;
                }});
            filtered.sort((a, b) => {{
                const aVal = a[sortField], bVal = b[sortField];
                if (typeof aVal === 'string') return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
            }});
            return filtered;
        }}

        function formatDepth(m, ft) {{ return isMetric ? `${{m}}m` : `${{ft}}ft`; }}
        function formatTemp(c) {{ return isMetric ? `${{c}}°C` : `${{Math.round(c * 9/5 + 32)}}°F`; }}
        function formatPressure(psi) {{ return isPSI ? `${{psi}}` : `${{psiToBar(psi)}}`; }}
        function pressureUnit() {{ return isPSI ? 'PSI' : 'bar'; }}

        function renderStats() {{
            const f = getFilteredDives();
            if (f.length === 0) return;
            const avgGas = Math.round(f.reduce((s, d) => s + d.gasUsed, 0) / f.length);
            const avgRate = (f.reduce((s, d) => s + (d.durationMin > 0 ? d.gasUsed / d.durationMin : 0), 0) / f.length).toFixed(1);
            document.getElementById('statsGrid').innerHTML = `
                <div class="stat-card"><div class="icon">🏊</div><div class="value">${{f.length}}</div><div class="label">Dives</div></div>
                <div class="stat-card"><div class="icon">⏱️</div><div class="value">${{(f.reduce((s,d)=>s+d.durationMin,0)/60).toFixed(1)}}h</div><div class="label">Total Time</div></div>
                <div class="stat-card"><div class="icon">📏</div><div class="value">${{isMetric ? Math.max(...f.map(d=>d.maxDepthM))+'m' : Math.max(...f.map(d=>d.maxDepthFt))+'ft'}}</div><div class="label">Max Depth</div></div>
                <div class="stat-card"><div class="icon">⛽</div><div class="value">${{formatPressure(avgGas)}}</div><div class="label">Avg ${{pressureUnit()}} Used</div></div>
                <div class="stat-card"><div class="icon">📉</div><div class="value">${{isPSI ? avgRate : (avgRate*0.0689).toFixed(1)}}</div><div class="label">${{pressureUnit()}}/min</div></div>
            `;
        }}

        function renderTable() {{
            const filtered = getFilteredDives();
            const arrow = field => sortField === field ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';
            let html = `<table><thead><tr>
                <th onclick="sortBy('number')">#${{arrow('number')}}</th>
                <th onclick="sortBy('date')">Date${{arrow('date')}}</th>
                <th onclick="sortBy('location')">Location${{arrow('location')}}</th>
                <th onclick="sortBy('site')">Site${{arrow('site')}}</th>
                <th onclick="sortBy('maxDepthM')">Depth${{arrow('maxDepthM')}}</th>
                <th onclick="sortBy('durationMin')">Time${{arrow('durationMin')}}</th>
                <th onclick="sortBy('o2Percent')">O₂</th>
                <th onclick="sortBy('startPSI')">Start${{arrow('startPSI')}}</th>
                <th onclick="sortBy('endPSI')">End${{arrow('endPSI')}}</th>
                <th onclick="sortBy('gasUsed')">Used${{arrow('gasUsed')}}</th>
                <th>Rate</th>
                <th onclick="sortBy('endGF99')">GF99${{arrow('endGF99')}}</th>
            </tr></thead><tbody>`;
            filtered.forEach(d => {{
                const loc = (d.location || 'unknown').toLowerCase().replace('curaco','curacao');
                const locClass = 'location-' + loc;
                const gfClass = d.endGF99 > 70 ? 'gf-high' : d.endGF99 > 50 ? 'gf-med' : 'gf-low';
                const rate = d.durationMin > 0 ? (d.gasUsed / d.durationMin).toFixed(1) : '0';
                const rateClass = rate > 40 ? 'consumption-high' : rate > 30 ? 'consumption-med' : 'consumption-low';
                const selected = selectedDive && selectedDive.number === d.number ? 'selected' : '';
                html += `<tr class="${{selected}}" onclick="selectDive(${{d.number}})">
                    <td class="mono">${{d.number}}</td><td>${{d.date}}</td>
                    <td><span class="location-badge ${{locClass}}">${{d.location || 'Unknown'}}</span></td>
                    <td>${{d.site || '-'}}</td>
                    <td class="mono">${{formatDepth(d.maxDepthM, d.maxDepthFt)}}</td>
                    <td class="mono">${{d.durationMin}}min</td>
                    <td><span class="gas-badge">${{d.o2Percent}}%</span></td>
                    <td class="mono">${{formatPressure(d.startPSI)}}</td>
                    <td class="mono">${{formatPressure(d.endPSI)}}</td>
                    <td class="mono">${{formatPressure(d.gasUsed)}}</td>
                    <td class="mono ${{rateClass}}">${{isPSI ? rate : (rate*0.0689).toFixed(1)}}</td>
                    <td class="mono ${{gfClass}}">${{d.endGF99}}%</td>
                </tr>`;
            }});
            html += '</tbody></table>';
            document.getElementById('tablePanel').innerHTML = html;
        }}

        function sortBy(field) {{
            if (sortField === field) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            else {{ sortField = field; sortDir = 'asc'; }}
            renderTable();
        }}

        function selectDive(num) {{
            selectedDive = dives.find(d => d.number === num);
            renderTable();
            renderDetail();
            document.getElementById('detailPanel').classList.remove('hidden');
            document.getElementById('detailPanel').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}

        function closeDetail() {{
            selectedDive = null;
            document.getElementById('detailPanel').classList.add('hidden');
            renderTable();
        }}

        function generateDepthProfile(dive) {{
            const duration = dive.durationSec;
            const maxDepth = isMetric ? dive.maxDepthM : dive.maxDepthFt;
            const avgDepth = isMetric ? dive.avgDepthM : dive.avgDepthM * 3.28;
            const descentRate = isMetric ? 18 : 60;
            const ascentRate = isMetric ? 9 : 30;
            const descentTime = (maxDepth / descentRate) * 60;
            const safetyStopDepth = isMetric ? 5 : 15;
            const safetyStopTime = maxDepth > (isMetric ? 10 : 30) ? 180 : 0;
            const ascentTime = ((maxDepth - safetyStopDepth) / ascentRate) * 60 + (safetyStopDepth / ascentRate) * 60;
            const bottomTime = duration - descentTime - ascentTime - safetyStopTime;
            const points = [];
            const interval = 30;
            for (let t = 0; t <= duration; t += interval) {{
                let depth;
                if (t <= descentTime) depth = (t / descentTime) * maxDepth;
                else if (t <= descentTime + bottomTime * 0.3) depth = maxDepth;
                else if (t <= descentTime + bottomTime * 0.7) {{
                    const progress = (t - descentTime - bottomTime * 0.3) / (bottomTime * 0.4);
                    depth = maxDepth - (maxDepth - avgDepth * 1.2) * progress * 0.5;
                }} else if (t <= descentTime + bottomTime) depth = avgDepth * 1.1 + Math.sin(t / 60) * 2;
                else if (t <= duration - safetyStopTime - 60) {{
                    const ascentProgress = (t - descentTime - bottomTime) / (duration - descentTime - bottomTime - safetyStopTime - 60);
                    depth = avgDepth * 1.1 * (1 - ascentProgress) + safetyStopDepth * ascentProgress;
                }} else if (t <= duration - 60) depth = safetyStopDepth;
                else {{
                    const finalProgress = (t - (duration - 60)) / 60;
                    depth = safetyStopDepth * (1 - finalProgress);
                }}
                points.push({{ x: Math.round(t / 60), y: Math.max(0, Math.round(depth * 10) / 10) }});
            }}
            return points;
        }}

        function generatePressureProfile(dive) {{
            const points = [];
            const interval = 5;
            const startP = isPSI ? dive.startPSI : psiToBar(dive.startPSI);
            const endP = isPSI ? dive.endPSI : psiToBar(dive.endPSI);
            for (let t = 0; t <= dive.durationMin; t += interval) {{
                const progress = t / dive.durationMin;
                const curve = Math.pow(progress, 0.85);
                const pressure = startP - (startP - endP) * curve;
                points.push({{ x: t, y: Math.round(pressure) }});
            }}
            points.push({{ x: dive.durationMin, y: endP }});
            return points;
        }}

        function renderDetail() {{
            if (!selectedDive) return;
            const d = selectedDive;
            const rate = d.durationMin > 0 ? (d.gasUsed / d.durationMin).toFixed(1) : '0';
            document.getElementById('detailTitle').textContent = `Dive #${{d.number}}`;
            document.getElementById('detailMeta').innerHTML = `${{d.date}} at ${{d.time}} • ${{d.location || 'Unknown'}}${{d.site ? ' - ' + d.site : ''}} • EAN${{d.o2Percent}}`;
            document.getElementById('detailStats').innerHTML = `
                <div class="detail-stat"><div class="value">${{formatDepth(d.maxDepthM, d.maxDepthFt)}}</div><div class="label">Max Depth</div></div>
                <div class="detail-stat"><div class="value">${{isMetric ? d.avgDepthM : Math.round(d.avgDepthM*3.28)}}${{isMetric?'m':'ft'}}</div><div class="label">Avg Depth</div></div>
                <div class="detail-stat"><div class="value">${{d.durationMin}}min</div><div class="label">Duration</div></div>
                <div class="detail-stat"><div class="value">${{formatTemp(d.avgTempC)}}</div><div class="label">Water Temp</div></div>
                <div class="detail-stat"><div class="value">${{formatPressure(d.startPSI)}}</div><div class="label">Start ${{pressureUnit()}}</div></div>
                <div class="detail-stat"><div class="value">${{formatPressure(d.endPSI)}}</div><div class="label">End ${{pressureUnit()}}</div></div>
                <div class="detail-stat"><div class="value">${{formatPressure(d.gasUsed)}}</div><div class="label">${{pressureUnit()}} Used</div></div>
                <div class="detail-stat"><div class="value">${{isPSI ? rate : (rate*0.0689).toFixed(1)}}</div><div class="label">${{pressureUnit()}}/min</div></div>
                <div class="detail-stat"><div class="value">${{d.endGF99}}%</div><div class="label">End GF99</div></div>
            `;
            if (depthChart) depthChart.destroy();
            const depthData = generateDepthProfile(d);
            depthChart = new Chart(document.getElementById('depthProfileChart'), {{
                type: 'line',
                data: {{ datasets: [{{ data: depthData, borderColor: '#06b6d4', backgroundColor: 'rgba(6, 182, 212, 0.2)', fill: true, tension: 0.3, pointRadius: 0 }}] }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{ type: 'linear', title: {{ display: true, text: 'Time (min)', color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ reverse: true, title: {{ display: true, text: `Depth (${{isMetric ? 'm' : 'ft'}})`, color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }}, min: 0 }}
                    }}
                }}
            }});
            if (pressureChart) pressureChart.destroy();
            const pressureData = generatePressureProfile(d);
            pressureChart = new Chart(document.getElementById('tankPressureChart'), {{
                type: 'line',
                data: {{ datasets: [{{ data: pressureData, borderColor: '#22c55e', backgroundColor: 'rgba(34, 197, 94, 0.2)', fill: true, tension: 0.3, pointRadius: 0 }}] }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{ type: 'linear', title: {{ display: true, text: 'Time (min)', color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ title: {{ display: true, text: `Pressure (${{pressureUnit()}})`, color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }}, min: 0 }}
                    }}
                }}
            }});
        }}

        function switchTab(tab) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`[data-tab="${{tab}}"]`).classList.add('active');
            ['tablePanel', 'chartsPanel', 'gasPanel', 'tripsPanel'].forEach(p => document.getElementById(p).classList.add('hidden'));
            document.getElementById(tab + 'Panel').classList.remove('hidden');
            if (tab === 'charts') renderCharts();
            if (tab === 'gas') renderGasCharts();
            if (tab === 'trips') renderTrips();
            if (tab !== 'table') document.getElementById('detailPanel').classList.add('hidden');
        }}

        document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));

        function renderCharts() {{
            const filtered = getFilteredDives();
            const colors = {{ Bonaire: '#3b82f6', Cozumel: '#22c55e', Curacao: '#f97316', Curaco: '#f97316', '': '#94a3b8', Unknown: '#94a3b8' }};
            document.getElementById('chartsPanel').innerHTML = `
                <div class="chart-card"><h3>Dive Depth Profile</h3><div class="chart-container"><canvas id="depthChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Dive Duration</h3><div class="chart-container"><canvas id="durationChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Water Temperature</h3><div class="chart-container"><canvas id="tempChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Dives by Location</h3><div class="chart-container"><canvas id="locationChartMain"></canvas></div></div>
            `;
            Object.keys(charts).forEach(k => {{ if (charts[k]) charts[k].destroy(); }});
            const chartOpts = {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                }}
            }};
            charts.depthMain = new Chart(document.getElementById('depthChartMain'), {{
                type: 'bar',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isMetric ? d.maxDepthM : d.maxDepthFt), backgroundColor: filtered.map(d => colors[d.location] || '#94a3b8'), borderRadius: 3 }}] }},
                options: {{ ...chartOpts, scales: {{ ...chartOpts.scales, y: {{ ...chartOpts.scales.y, reverse: true }} }} }}
            }});
            charts.durationMain = new Chart(document.getElementById('durationChartMain'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => d.durationMin), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', fill: true, tension: 0.3 }}] }},
                options: chartOpts
            }});
            charts.tempMain = new Chart(document.getElementById('tempChartMain'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isMetric ? d.avgTempC : (d.avgTempC * 9/5 + 32)), borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.1)', fill: true, tension: 0.3 }}] }},
                options: chartOpts
            }});
            const locCounts = {{}};
            filtered.forEach(d => {{ const loc = (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location; locCounts[loc] = (locCounts[loc] || 0) + 1; }});
            charts.locationMain = new Chart(document.getElementById('locationChartMain'), {{
                type: 'doughnut',
                data: {{ labels: Object.keys(locCounts), datasets: [{{ data: Object.values(locCounts), backgroundColor: Object.keys(locCounts).map(l => colors[l] || '#94a3b8') }}] }},
                options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom', labels: {{ color: 'white' }} }} }} }}
            }});
        }}

        function renderGasCharts() {{
            const filtered = getFilteredDives();
            const colors = {{ Bonaire: '#3b82f6', Cozumel: '#22c55e', Curacao: '#f97316', Curaco: '#f97316', '': '#94a3b8' }};
            document.getElementById('gasPanel').innerHTML = `
                <div class="chart-card"><h3>Gas Consumption Per Dive (${{pressureUnit()}})</h3><div class="chart-container"><canvas id="gasUsedChart"></canvas></div></div>
                <div class="chart-card"><h3>Consumption Rate (${{pressureUnit()}}/min)</h3><div class="chart-container"><canvas id="gasRateChart"></canvas></div></div>
                <div class="chart-card"><h3>Tank Pressure: Start vs End</h3><div class="chart-container"><canvas id="tankPressureMainChart"></canvas></div></div>
                <div class="chart-card"><h3>Depth vs Gas Consumption</h3><div class="chart-container"><canvas id="depthGasChart"></canvas></div></div>
                <div class="chart-card"><h3>Gas Usage by Location</h3><div class="chart-container"><canvas id="gasLocationChart"></canvas></div></div>
                <div class="chart-card"><h3>End Pressure Distribution</h3><div class="chart-container"><canvas id="endPressureChart"></canvas></div></div>
            `;
            ['gasUsed','gasRate','tankPressureMain','depthGas','gasLocation','endPressure'].forEach(k => {{ if (charts[k]) charts[k].destroy(); }});
            const chartOpts = {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                }}
            }};
            charts.gasUsed = new Chart(document.getElementById('gasUsedChart'), {{
                type: 'bar',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isPSI ? d.gasUsed : psiToBar(d.gasUsed)), backgroundColor: filtered.map(d => colors[d.location] || '#94a3b8'), borderRadius: 3 }}] }},
                options: chartOpts
            }});
            charts.gasRate = new Chart(document.getElementById('gasRateChart'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => {{ const rate = d.durationMin > 0 ? d.gasUsed / d.durationMin : 0; return isPSI ? rate.toFixed(1) : (rate * 0.0689).toFixed(2); }}), borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.1)', fill: true, tension: 0.3 }}] }},
                options: chartOpts
            }});
            charts.tankPressureMain = new Chart(document.getElementById('tankPressureMainChart'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [
                    {{ label: 'Start', data: filtered.map(d => isPSI ? d.startPSI : psiToBar(d.startPSI)), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', tension: 0.3 }},
                    {{ label: 'End', data: filtered.map(d => isPSI ? d.endPSI : psiToBar(d.endPSI)), borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.3 }}
                ] }},
                options: {{ ...chartOpts, plugins: {{ legend: {{ display: true, labels: {{ color: 'white' }} }} }} }}
            }});
            const locs = [...new Set(filtered.map(d => (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location))];
            charts.depthGas = new Chart(document.getElementById('depthGasChart'), {{
                type: 'scatter',
                data: {{ datasets: locs.map(loc => ({{
                    label: loc,
                    data: filtered.filter(d => (d.location === loc) || (loc === 'Curacao' && (d.location === 'Curaco' || !d.location))).map(d => ({{ x: isMetric ? d.maxDepthM : d.maxDepthFt, y: isPSI ? d.gasUsed : psiToBar(d.gasUsed) }})),
                    backgroundColor: colors[loc] || '#94a3b8',
                    pointRadius: 6
                }})) }},
                options: {{ ...chartOpts, plugins: {{ legend: {{ display: true, labels: {{ color: 'white' }} }} }} }}
            }});
            const locGas = {{}};
            filtered.forEach(d => {{ const loc = (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location; if (!locGas[loc]) locGas[loc] = []; locGas[loc].push(d.gasUsed); }});
            const avgLocGas = Object.entries(locGas).map(([loc, vals]) => ({{ loc, avg: vals.reduce((a,b) => a+b, 0) / vals.length }}));
            charts.gasLocation = new Chart(document.getElementById('gasLocationChart'), {{
                type: 'bar',
                data: {{ labels: avgLocGas.map(d => d.loc), datasets: [{{ data: avgLocGas.map(d => isPSI ? Math.round(d.avg) : psiToBar(d.avg)), backgroundColor: avgLocGas.map(d => colors[d.loc] || '#94a3b8'), borderRadius: 4 }}] }},
                options: {{ ...chartOpts, indexAxis: 'y' }}
            }});
            const endBuckets = [0, 500, 750, 1000, 1250, 1500, 2000, 3500];
            const endCounts = endBuckets.slice(0, -1).map((min, i) => filtered.filter(d => d.endPSI >= min && d.endPSI < endBuckets[i+1]).length);
            charts.endPressure = new Chart(document.getElementById('endPressureChart'), {{
                type: 'bar',
                data: {{ labels: endBuckets.slice(0, -1).map((v, i) => `${{isPSI ? v : psiToBar(v)}}-${{isPSI ? endBuckets[i+1] : psiToBar(endBuckets[i+1])}}`), datasets: [{{ data: endCounts, backgroundColor: '#06b6d4', borderRadius: 4 }}] }},
                options: chartOpts
            }});
        }}

        function renderTrips() {{
            document.getElementById('tripsPanel').innerHTML = tripsData.map(t => `
                <div class="trip-card">
                    <div class="trip-header">
                        <div class="trip-dot" style="background:${{t.color}}"></div>
                        <strong>${{t.name}}</strong>
                    </div>
                    <div style="color:#93c5fd;font-size:0.875rem">${{t.dates}}</div>
                    <div class="trip-stats">
                        <div><div class="trip-stat-value">${{t.dives}}</div><div class="trip-stat-label">Dives</div></div>
                        <div><div class="trip-stat-value">${{t.hours}}h</div><div class="trip-stat-label">Hours</div></div>
                        <div><div class="trip-stat-value">${{isMetric ? t.maxDepth + 'm' : Math.round(t.maxDepth * 3.28) + 'ft'}}</div><div class="trip-stat-label">Max Depth</div></div>
                        <div><div class="trip-stat-value">${{isPSI ? t.avgGas : psiToBar(t.avgGas)}}</div><div class="trip-stat-label">Avg ${{pressureUnit()}} Used</div></div>
                    </div>
                </div>
            `).join('');
        }}

        document.getElementById('locationFilter').addEventListener('change', e => {{
            currentLocation = e.target.value;
            renderStats(); renderTable();
            if (!document.getElementById('chartsPanel').classList.contains('hidden')) renderCharts();
            if (!document.getElementById('gasPanel').classList.contains('hidden')) renderGasCharts();
        }});

        document.getElementById('unitToggle').addEventListener('click', () => {{
            isMetric = !isMetric;
            document.getElementById('unitToggle').textContent = isMetric ? '🌡️ Metric' : '🌡️ Imperial';
            renderStats(); renderTable();
            if (!document.getElementById('chartsPanel').classList.contains('hidden')) renderCharts();
            if (!document.getElementById('gasPanel').classList.contains('hidden')) renderGasCharts();
            if (!document.getElementById('tripsPanel').classList.contains('hidden')) renderTrips();
            if (selectedDive) renderDetail();
        }});

        document.getElementById('pressureToggle').addEventListener('click', () => {{
            isPSI = !isPSI;
            document.getElementById('pressureToggle').textContent = isPSI ? '⛽ PSI' : '⛽ bar';
            renderStats(); renderTable();
            if (!document.getElementById('gasPanel').classList.contains('hidden')) renderGasCharts();
            if (!document.getElementById('tripsPanel').classList.contains('hidden')) renderTrips();
            if (selectedDive) renderDetail();
        }});

        renderStats();
        renderTable();
    </script>
</body>
</html>
'''
    return html

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Please provide the path to your Shearwater database file.")
        print("Example: python generate_dive_dashboard.py Shearwater_Cloud__email__date.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    if not os.path.exists(db_path):
        print(f"Error: File not found: {db_path}")
        sys.exit(1)
    
    print(f"Reading Shearwater database: {db_path}")
    
    try:
        dives = extract_dive_data(db_path)
        print(f"Found {len(dives)} dives")
        
        computer_info = get_computer_info(db_path)
        print(f"Computer serial: {computer_info['serial']}")
        
        trips = calculate_trip_stats(dives)
        print(f"Found {len(trips)} trips/locations")
        
        html = generate_html(dives, computer_info, trips)
        
        output_path = 'dive_dashboard.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n✓ Dashboard created: {output_path}")
        print("\nDouble-click the HTML file to open it in your browser!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
