#!/usr/bin/env python3
"""
Arrowcrab Dive Studio — Dashboard Generator
=============================================
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
import base64
import io
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
        
        start_time = row[1][11:16] if row[1] and len(row[1]) > 11 else ''
        end_time = ''
        if start_time and duration_sec:
            from datetime import datetime, timedelta
            try:
                st = datetime.strptime(start_time, '%H:%M')
                et = st + timedelta(seconds=duration_sec)
                end_time = et.strftime('%H:%M')
            except Exception:
                end_time = ''

        dive = {
            'number': int(row[0]) if row[0] else 0,
            'date': row[1][:10] if row[1] else '',
            'time': start_time,
            'endTime': end_time,
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
            'color': colors.get(loc, '#94a3b8'),
            '_endDate': dates[-1]
        })

    trips.sort(key=lambda t: t['_endDate'])
    return trips

def get_logo_base64():
    """Load and resize arrowcrab.png, return as base64 data URI."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Support PyInstaller bundled path
    if getattr(sys, "frozen", False):
        script_dir = sys._MEIPASS
    logo_path = os.path.join(script_dir, "arrowcrab.png")
    if not os.path.exists(logo_path):
        return ""
    try:
        from PIL import Image
        img = Image.open(logo_path)
        img = img.resize((80, 80), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def generate_html(dives, computer_info, trips):
    """Generate the complete HTML dashboard."""

    # Convert dives to JavaScript format
    dives_js = json.dumps(dives, indent=12)
    trips_js = json.dumps(trips, indent=12)
    computer_info_js = json.dumps(computer_info, indent=12)

    # Get date range
    dates = [d['date'] for d in dives if d['date']]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "Unknown"

    # Get primary gas
    o2_values = [d['o2Percent'] for d in dives if d['o2Percent'] > 21]
    primary_gas = f"EAN{max(set(o2_values), key=o2_values.count)}" if o2_values else "Air"

    # Get logo as base64
    logo_data_uri = get_logo_base64()
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arrowcrab Dive Studio</title>
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
            position: relative;
            z-index: 100;
        }}
        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }}
        .header h1 {{ font-size: 2rem; margin-bottom: 8px; }}
        .header p {{ color: #93c5fd; }}
        .header-logo {{
            width: 68px;
            height: 68px;
            border-radius: 12px;
            flex-shrink: 0;
        }}
        .controls {{ display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }}
        .settings-overlay {{
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5); z-index: 9998;
        }}
        .settings-overlay.visible {{ display: block; }}
        .settings-modal {{
            display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
            background: #1e293b; border: 1px solid rgba(255,255,255,0.2); border-radius: 16px;
            padding: 28px 32px; z-index: 9999; min-width: 320px; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }}
        .settings-modal.visible {{ display: block; }}
        .settings-modal h2 {{ font-size: 1.3rem; margin-bottom: 20px; color: #e2e8f0; }}
        .settings-row {{
            display: flex; align-items: center; justify-content: space-between;
            padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .settings-row:last-child {{ border-bottom: none; }}
        .settings-row label {{ color: #cbd5e1; font-size: 0.95rem; }}
        .settings-row button {{
            padding: 8px 18px; font-size: 0.85rem; min-width: 100px;
        }}
        .settings-close {{
            position: absolute; top: 12px; right: 16px; background: none; border: none;
            color: #94a3b8; font-size: 1.4rem; cursor: pointer; padding: 4px 8px;
        }}
        .settings-close:hover {{ color: #e2e8f0; background: rgba(255,255,255,0.1); border-radius: 6px; }}
        .pic-loading-bar {{
            display: none; background: rgba(6,182,212,0.15); border: 1px solid rgba(6,182,212,0.3);
            border-radius: 10px; padding: 12px 20px; margin-bottom: 16px;
            text-align: center; color: #94a3b8; font-size: 0.85rem;
        }}
        .pic-loading-bar.visible {{ display: block; }}
        .pic-loading-bar .plb-progress {{
            background: rgba(255,255,255,0.1); border-radius: 4px; height: 6px;
            margin-top: 8px; overflow: hidden;
        }}
        .pic-loading-bar .plb-fill {{
            background: #06b6d4; height: 100%; width: 0%; border-radius: 4px;
            transition: width 0.2s ease;
        }}
        .dropdown-wrap {{
            position: relative; display: inline-block;
        }}
        .dropdown-menu {{
            display: none; position: absolute; top: 100%; left: 0; margin-top: 4px;
            background: #1e293b; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px;
            min-width: 180px; box-shadow: 0 12px 40px rgba(0,0,0,0.5); z-index: 500;
            overflow: hidden;
        }}
        .dropdown-menu.open {{ display: block; }}
        .dropdown-menu button {{
            display: block; width: 100%; text-align: left; padding: 10px 16px;
            border: none; border-radius: 0; background: transparent; color: #e2e8f0;
            font-size: 0.9rem; cursor: pointer; white-space: nowrap;
        }}
        .dropdown-menu button:hover {{ background: rgba(255,255,255,0.15); }}
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
            background: #1e3045;
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
        th:hover {{ background: #253850; }}
        .pics-y {{ color: #4ade80; cursor: pointer; font-weight: 600; }}
        .pics-y:hover {{ text-decoration: underline; }}
        .pics-n {{ color: #f87171; font-weight: 600; }}
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
        .location-custom {{ background: #a855f7; }}
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
        .add-pics-btn {{
            margin-top: 14px;
            padding: 8px 16px;
            background: rgba(139,92,246,0.3);
            border: 1px solid rgba(139,92,246,0.5);
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 500;
            transition: background 0.2s;
            width: 100%;
        }}
        .add-pics-btn:hover {{ background: rgba(139,92,246,0.5); }}
        .trip-pic-info {{
            margin-top: 8px;
            font-size: 0.75rem;
            color: #93c5fd;
            cursor: pointer;
        }}
        .trip-pic-info:hover {{ color: #06b6d4; }}
        .trip-thumb {{
            margin-top: 10px;
            width: 100%;
            max-height: 220px;
            border-radius: 8px;
            object-fit: contain;
            cursor: pointer;
            border: 1px solid rgba(255,255,255,0.15);
            background: #0f1923;
        }}
        .pic-viewer {{
            position: fixed;
            inset: 0;
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .pic-backdrop {{
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.85);
        }}
        .pic-wrap {{
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            max-width: 92vw;
            max-height: 88vh;
            z-index: 1;
        }}
        .pic-wrap img {{
            max-width: 88vw;
            max-height: 82vh;
            border-radius: 8px;
            object-fit: contain;
            user-select: none;
        }}
        .pic-nav {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255,255,255,0.15);
            color: white;
            border: none;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            font-size: 1.5rem;
            cursor: pointer;
            transition: background 0.2s;
            z-index: 2;
        }}
        .pic-nav:hover {{ background: rgba(255,255,255,0.35); }}
        .pic-prev {{ left: -66px; }}
        .pic-next {{ right: -66px; }}
        .ext-modal {{
            position: fixed;
            inset: 0;
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .ext-backdrop {{
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.7);
        }}
        .ext-box {{
            position: relative;
            background: #1e3a5f;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 14px;
            padding: 24px;
            min-width: 320px;
            max-width: 420px;
            z-index: 1;
        }}
        .ext-box h3 {{
            font-size: 1rem;
            margin-bottom: 4px;
        }}
        .ext-box .ext-sub {{
            font-size: 0.75rem;
            color: #93c5fd;
            margin-bottom: 14px;
        }}
        .ext-list {{
            max-height: 260px;
            overflow-y: auto;
            margin-bottom: 16px;
        }}
        .ext-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 7px 8px;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .ext-row:hover {{ background: rgba(255,255,255,0.08); }}
        .ext-row input[type=checkbox] {{
            width: 16px;
            height: 16px;
            accent-color: #06b6d4;
            cursor: pointer;
        }}
        .ext-row label {{
            flex: 1;
            cursor: pointer;
            font-size: 0.85rem;
        }}
        .ext-row .ext-count {{
            font-size: 0.75rem;
            color: #94a3b8;
        }}
        .ext-btns {{
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }}
        .ext-btns button {{
            padding: 8px 20px;
            border-radius: 8px;
            border: none;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
        }}
        .ext-btn-cancel {{
            background: rgba(255,255,255,0.15);
            color: white;
        }}
        .ext-btn-cancel:hover {{ background: rgba(255,255,255,0.25); }}
        .ext-btn-import {{
            background: #06b6d4;
            color: #0f1923;
        }}
        .ext-btn-import:hover {{ background: #22d3ee; }}
        .ext-toggle {{
            font-size: 0.7rem;
            color: #06b6d4;
            cursor: pointer;
            margin-bottom: 10px;
            display: inline-block;
        }}
        .ext-toggle:hover {{ text-decoration: underline; }}
        .trip-form-row {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-bottom: 12px;
        }}
        .trip-form-row label {{
            font-size: 0.75rem;
            color: #93c5fd;
            font-weight: 600;
        }}
        .trip-form-row input {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 6px;
            padding: 8px 10px;
            color: white;
            font-size: 0.85rem;
            font-family: inherit;
        }}
        .trip-form-row input:focus {{
            outline: none;
            border-color: #06b6d4;
        }}
        .add-trip-btn {{
            margin-top: 14px;
            padding: 8px 16px;
            background: rgba(6,182,212,0.3);
            border: 1px solid rgba(6,182,212,0.5);
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .add-trip-btn:hover {{ background: rgba(6,182,212,0.5); }}
        .thumb-pane-box {{
            position: relative;
            background: #1e3a5f;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 14px;
            padding: 24px;
            width: 85vw;
            height: 85vh;
            z-index: 1;
            display: flex;
            flex-direction: column;
        }}
        .thumb-controls {{
            display: flex;
            gap: 8px;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}
        .thumb-controls button {{
            padding: 6px 14px;
            font-size: 0.75rem;
        }}
        .thumb-controls input {{
            width: 55px;
            padding: 6px 8px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 6px;
            color: white;
            font-size: 0.8rem;
            text-align: center;
        }}
        .thumb-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
            overflow-y: auto;
            flex: 1;
            min-height: 0;
            padding: 4px;
            align-content: start;
        }}
        .thumb-item {{
            position: relative;
            cursor: pointer;
            border-radius: 8px;
            overflow: hidden;
            border: 3px solid transparent;
            transition: border-color 0.15s;
            min-height: 150px;
            background: #0f1923;
        }}
        .thumb-item.selected {{ border-color: #06b6d4; }}
        .thumb-item.deselected {{ opacity: 0.35; }}
        .thumb-item img, .thumb-item video {{
            width: 100%;
            height: 150px;
            object-fit: cover;
            display: block;
        }}
        .thumb-placeholder {{
            width: 100%;
            height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #0f1923;
            color: #94a3b8;
            font-size: 0.8rem;
        }}
        .thumb-video-overlay {{
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
        }}
        .thumb-video-overlay::after {{
            content: '\\25B6';
            font-size: 2rem;
            color: rgba(255,255,255,0.8);
            background: rgba(0,0,0,0.45);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding-left: 4px;
        }}
        .thumb-item .thumb-label {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.7);
            color: #e2e8f0;
            font-size: 0.6rem;
            padding: 2px 4px;
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            border: none;
            outline: none;
            width: 100%;
            box-sizing: border-box;
            cursor: text;
        }}
        .thumb-item .thumb-label:focus {{
            background: rgba(0,0,0,0.9);
            text-overflow: clip;
        }}
        .thumb-item .thumb-check {{
            position: absolute;
            top: 4px;
            right: 4px;
            width: 18px;
            height: 18px;
        }}
        .thumb-keep {{
            position: absolute;
            bottom: 18px;
            left: 3px;
            z-index: 5;
            display: flex;
            align-items: center;
            gap: 0;
        }}
        .thumb-keep input {{
            width: 13px;
            height: 13px;
            cursor: pointer;
            accent-color: #06b6d4;
        }}
        .thumb-keep span {{
            display: none;
        }}
        .thumb-actions {{
            display: flex;
            gap: 8px;
            margin-top: 12px;
            justify-content: flex-end;
        }}
        .thumb-actions button {{
            padding: 8px 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .pic-btn-bar {{
            position: absolute;
            top: -44px;
            right: 0;
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            justify-content: flex-end;
            z-index: 3;
        }}
        .pic-btn {{
            background: #06b6d4;
            color: #0f1923;
            border: none;
            padding: 5px 14px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }}
        .pic-btn:hover {{ opacity: 0.85; }}
        .pic-info {{
            position: absolute;
            bottom: -36px;
            left: 0;
            right: 0;
            text-align: center;
            color: #93c5fd;
            font-size: 0.8rem;
        }}
        .pic-top-bar {{
            position: absolute;
            top: -44px;
            left: 0;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 10px;
            z-index: 3;
            flex-wrap: wrap;
        }}
        .pic-keep label {{
            cursor: pointer;
            user-select: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            color: #e2e8f0;
            font-size: 0.8rem;
            padding: 4px 8px;
            border-radius: 6px;
            background: rgba(255,255,255,0.08);
        }}
        .pic-keep input {{ width:16px; height:16px; cursor:pointer; }}
        .pic-caption-input {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(6,182,212,0.4);
            border-radius: 6px;
            color: #06b6d4;
            font-size: 0.8rem;
            font-weight: 700;
            padding: 4px 8px;
            width: 180px;
            outline: none;
        }}
        .pic-caption-input:focus {{
            border-color: #06b6d4;
            background: rgba(255,255,255,0.15);
        }}
        .pic-orf-msg {{
            color: #f59e0b;
            font-size: 0.75rem;
            font-style: italic;
        }}
        .remove-pics-btn {{
            background: rgba(239,68,68,0.25);
            border: 1px solid rgba(239,68,68,0.5);
            color: #fca5a5;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: background 0.2s;
            margin-left: 8px;
        }}
        .remove-pics-btn:hover {{ background: rgba(239,68,68,0.45); }}
        .dive-photos-section {{
            margin-top: 16px;
            padding: 12px 16px;
            background: rgba(6,182,212,0.08);
            border: 1px solid rgba(6,182,212,0.2);
            border-radius: 10px;
            text-align: center;
        }}
        .dive-photos-section .no-pics {{ color: #64748b; font-size: 0.85rem; }}
        .dive-photos-btn {{
            background: rgba(6,182,212,0.3);
            border: 1px solid rgba(6,182,212,0.5);
            color: #93c5fd;
            padding: 8px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .dive-photos-btn:hover {{ background: rgba(6,182,212,0.5); }}
        .slideshow-btn {{
            background: rgba(139,92,246,0.3);
            border: 1px solid rgba(139,92,246,0.5);
            color: #c4b5fd;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: background 0.2s;
            margin-left: 8px;
        }}
        .slideshow-btn:hover {{ background: rgba(139,92,246,0.5); }}
        .share-option-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 16px 0;
        }}
        .share-option-card {{
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 12px;
            padding: 18px 12px;
            text-align: center;
            cursor: pointer;
            transition: background 0.2s, border-color 0.2s, transform 0.15s;
        }}
        .share-option-card:hover:not(.share-disabled) {{
            background: rgba(6,182,212,0.15);
            border-color: rgba(6,182,212,0.5);
            transform: translateY(-2px);
        }}
        .share-option-card.share-disabled {{
            opacity: 0.35;
            cursor: not-allowed;
        }}
        .share-option-card .share-icon {{
            font-size: 2rem;
            margin-bottom: 8px;
        }}
        .share-option-card .share-label {{
            font-size: 0.85rem;
            font-weight: 600;
            color: #e2e8f0;
        }}
        .share-option-card .share-desc {{
            font-size: 0.7rem;
            color: #94a3b8;
            margin-top: 4px;
        }}
        #sharePreviewCanvas {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            display: block;
            margin: 0 auto;
        }}
        .share-photo-strip {{
            display: flex;
            gap: 6px;
            overflow-x: auto;
            padding: 8px 0;
            margin-bottom: 8px;
        }}
        .share-photo-strip img {{
            width: 48px;
            height: 48px;
            object-fit: cover;
            border-radius: 6px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: border-color 0.2s;
        }}
        .share-photo-strip img.active {{
            border-color: #06b6d4;
        }}
        .share-photo-strip img:hover {{
            border-color: rgba(6,182,212,0.5);
        }}
        #photoTooltip {{
            position: absolute;
            pointer-events: none;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 6px;
            z-index: 100;
            display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }}
        #photoTooltip img {{
            max-width: 160px;
            max-height: 120px;
            border-radius: 4px;
            display: block;
        }}
        #photoTooltip .tt-name {{
            color: #94a3b8;
            font-size: 0.65rem;
            text-align: center;
            margin-top: 4px;
            max-width: 160px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .hidden {{ display: none; }}
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .charts-row, .charts-grid {{ grid-template-columns: 1fr; }}
            .detail-stats {{ grid-template-columns: repeat(3, 1fr); }}
            .trip-stats {{ grid-template-columns: repeat(2, 1fr); }}
            .pic-prev {{ left: 4px; }}
            .pic-next {{ right: 4px; }}
            .pic-nav {{ width: 44px; height: 44px; font-size: 1.2rem; }}
            .pic-btn {{ padding: 4px 10px; font-size: 0.72rem; }}
            .pic-top-bar {{ gap: 6px; }}
            .pic-btn-bar {{ gap: 4px; }}
        }}
        @keyframes mp4pulse {{
            0%   {{ opacity: 1; }}
            50%  {{ opacity: 0.35; }}
            100% {{ opacity: 1; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                {'<img class="header-logo" src="' + logo_data_uri + '" alt="Logo">' if logo_data_uri else ''}
                <span id="batchIdStatus" style="display:none;margin-right:12px;align-self:center;background:rgba(5,150,105,0.15);border:1px solid #059669;border-radius:8px;padding:6px 14px;font-size:0.82rem;color:#34d399;white-space:nowrap">
                    <span id="batchIdText">Identifying...</span>
                    <span id="batchIdProgress" style="margin-left:8px;color:#94a3b8"></span>
                </span>
                <div>
                    <h1>Arrowcrab Dive Studio</h1>
                    <p>Serial: {computer_info['serial']} | {date_range} | {primary_gas}</p>
                </div>
            </div>
            <div class="controls">
                <select id="locationFilter">
                    <option value="All">All Locations</option>
                </select>
                <button id="importBtn" onclick="if(window.parent&&window.parent.doImport)window.parent.doImport()">📂 Import Dive Log</button>
                <div class="dropdown-wrap">
                    <button onclick="toggleDropdown('projectsMenu')">📁 Projects ▾</button>
                    <div class="dropdown-menu" id="projectsMenu">
                        <button onclick="closeDropdowns();newProject()">📄 New Project</button>
                        <button onclick="closeDropdowns();saveProject()">💾 Save Project</button>
                        <button onclick="closeDropdowns();if(window.parent&&window.parent.doLoadProject)window.parent.doLoadProject()">📁 Load Project</button>
                    </div>
                </div>
                <button onclick="openSettings()">⚙️ Settings</button>
            </div>
        </div>

        <div class="settings-overlay" id="settingsOverlay" onclick="closeSettings()"></div>
        <div class="settings-modal" id="settingsModal">
            <button class="settings-close" onclick="closeSettings()">✕</button>
            <h2>⚙️ Settings</h2>
            <div class="settings-row">
                <label>Temperature / Depth Units</label>
                <button id="unitToggle">🌡️ Imperial</button>
            </div>
            <div class="settings-row">
                <label>Pressure Units</label>
                <button id="pressureToggle">⛽ PSI</button>
            </div>
            <div class="settings-row">
                <label>Background Image</label>
                <div style="display:flex;gap:8px">
                    <button onclick="chooseBackgroundFile()">🖼️ Change</button>
                    <button onclick="clearBackground()">🗑️ Clear</button>
                </div>
            </div>
        </div>

        <div class="stats-grid" id="statsGrid"></div>

        <div class="pic-loading-bar" id="picLoadingBar">
            <div id="plbText">Loading pictures... please wait</div>
            <div class="plb-progress"><div class="plb-fill" id="plbFill"></div></div>
        </div>

        <div class="tabs">
            <button class="tab active" data-tab="trips">🗺️ Trips</button>
            <button class="tab" data-tab="table">📋 Dive Table</button>
            <button class="tab" data-tab="charts">📊 Charts</button>
            <button class="tab" data-tab="gas">⛽ Gas Analysis</button>
            <button class="tab" id="addTripTabBtn" onclick="openTripModal()" style="margin-left:auto;background:rgba(6,182,212,0.25);border:1px dashed rgba(6,182,212,0.6)">➕ Add Trip</button>

        </div>

        <div class="content-panel">
            <div id="tripsPanel" class="trips-grid"></div>
            <div id="tablePanel" class="table-container hidden"></div>
            <div id="chartsPanel" class="charts-grid hidden"></div>
            <div id="gasPanel" class="charts-grid hidden"></div>
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
                <div class="dive-photos-section" id="divePhotosSection"></div>
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

    <input type="file" id="dirInput" webkitdirectory multiple style="display:none" onchange="onDirSelected(this.files)">
    <div id="extModal" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="closeExtModal()"></div>
        <div class="ext-box">
            <h3>Select File Types to Import</h3>
            <div class="ext-sub">Uncheck any file types you want to exclude.</div>
            <span class="ext-toggle" id="extToggle" onclick="toggleAllExt()">Deselect all</span>
            <div class="ext-list" id="extList"></div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="closeExtModal()">Cancel</button>
                <button class="ext-btn-import" onclick="importSelected()">Import</button>
            </div>
        </div>
    </div>
    <div id="tripModal" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="closeTripModal()"></div>
        <div class="ext-box">
            <h3>Add Trip</h3>
            <div class="ext-sub">Enter trip details manually.</div>
            <div class="trip-form-row">
                <label>Trip / Location Name *</label>
                <input type="text" id="tripName" placeholder="e.g. Bonaire">
            </div>
            <div class="trip-form-row">
                <label>Start Date</label>
                <input type="date" id="tripStartDate" onchange="autoTripEndDate()">
            </div>
            <div class="trip-form-row">
                <label>End Date</label>
                <input type="date" id="tripEndDate">
            </div>
            <div class="trip-form-row">
                <label>Pictures (optional)</label>
                <input type="file" id="tripDirInput" webkitdirectory multiple style="display:none" onchange="onTripDirPicked(this.files)">
                <button id="tripDirBtn" onclick="document.getElementById('tripDirInput').click()" style="padding:8px 16px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;cursor:pointer;font-size:0.85rem">Select Folder...</button>
                <div id="tripDirStatus" style="font-size:0.75rem;color:#94a3b8;margin-top:4px"></div>
            </div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="closeTripModal()">Cancel</button>
                <button class="ext-btn-import" onclick="addManualTrip()">Add Trip</button>
            </div>
        </div>
    </div>
    <div id="diveEditModal" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="closeDiveEdit()"></div>
        <div class="ext-box" style="max-width:360px">
            <h3 id="diveEditTitle">Edit Dive</h3>
            <div class="trip-form-row" style="margin-top:12px">
                <label>Site</label>
                <input type="text" id="deSite" placeholder="e.g. Salt Pier">
            </div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="closeDiveEdit()">Cancel</button>
                <button class="ext-btn-import" onclick="saveDiveEdit()">Save</button>
            </div>
        </div>
    </div>
    <div id="thumbPane" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="thumbCancel()"></div>
        <div class="thumb-pane-box">
            <h3 id="thumbTitle">Trip Inventory</h3>
            <div id="thumbProgress" style="display:none;margin:-8px 0 8px 0">
                <div style="display:flex;align-items:center;gap:10px">
                    <div style="flex:1;background:rgba(255,255,255,0.1);border-radius:4px;height:6px;overflow:hidden">
                        <div id="thumbProgressBar" style="background:#06b6d4;height:100%;width:0%;transition:width 0.2s;border-radius:4px"></div>
                    </div>
                    <span id="thumbProgressText" style="color:#94a3b8;font-size:0.8rem;white-space:nowrap">0 / 0</span>
                </div>
            </div>
            <div class="thumb-controls">
                <button onclick="startCollection()" id="createCollBtn" style="background:#7c3aed;color:#fff">Create Collection</button>
                <span id="diveThumbControls" style="display:none">
                    <button onclick="thumbSelectAll()">Select All</button>
                    <button onclick="thumbDeselectAll()">Deselect All</button>
                    <button onclick="diveSlideshowFromThumb()" style="background:#0e7490;color:#fff">Create Slideshow</button>
                    <button onclick="diveVideoConcatFromThumb()" id="diveConcatBtn" style="background:#7c3aed;color:#fff;display:none">Concatenate Videos</button>
                    <button onclick="diveCopyFromThumb()" style="background:#4ade80;color:#0f1923">Copy to Directory</button>
                </span>
                <span id="collectionControls" style="display:none">
                    <button onclick="thumbSelectAll()">Select All</button>
                    <button onclick="thumbDeselectAll()">Deselect All</button>
                    <button onclick="thumbRandom()">Random</button>
                    <input type="number" id="randomCount" value="25" min="1" style="width:60px">
                    <button onclick="finishCollection(event)" style="background:#4ade80;color:#0f1923">Save Collection</button>
                </span>
                <span id="collViewControls" style="display:none">
                    <button id="collIdentifyAllBtn" onclick="identifyCollectionMarineLife()" style="background:#059669;color:#fff" title="Run marine life identification on all photos in this collection">Identify All Marine Life</button>
                </span>
                <span style="flex:1"></span>
                <button onclick="thumbCancel()" style="background:#64748b;color:#fff">Back</button>
            </div>
            <div class="thumb-grid" id="thumbGrid"></div>
        </div>
    </div>
    <div id="picViewer" class="pic-viewer hidden">
        <div class="pic-backdrop" onclick="closePicViewer()"></div>
        <div class="pic-wrap">
            <div class="pic-top-bar">
                <span class="pic-keep" id="picKeepWrap"><label><input type="checkbox" id="picKeep" checked onchange="onKeepToggle()"> Keep</label></span>
                <input type="text" class="pic-caption-input" id="picCaption" placeholder="Enter caption..." oninput="onCaptionChange()" onkeydown="if(event.key==='Enter')this.blur()">
                <span id="picDepthWrap" style="color:#06b6d4;font-weight:600;font-size:0.85rem"></span>
                <span class="pic-orf-msg hidden" id="picOrfMsg">.orf converted to .jpg</span>
            </div>
            <button class="pic-nav pic-prev" onclick="navPic(-1)">&#10094;</button>
            <img id="picImg" src="" alt="">
            <video id="picVid" controls style="display:none;max-width:90vw;max-height:80vh;border-radius:10px"></video>
            <button class="pic-nav pic-next" onclick="navPic(1)">&#10095;</button>
            <div class="pic-btn-bar">
                <button class="pic-btn" id="marineIdBtn" onclick="identifyMarineLife()" style="background:#059669;color:#fff">Identify Marine Life</button>
                <button class="pic-btn" id="viewMarineIdBtn" onclick="viewSavedMarineId()" style="background:#0d9488;color:#fff;display:none">View Marine ID</button>
                <button class="pic-btn" id="uwCorrectBtn" onclick="applyUnderwaterCorrection()" style="background:#7c3aed;color:#fff">🌊 Underwater Correct</button>
                <button class="pic-btn" onclick="setAsBackground()" style="background:#0e7490;color:#fff">Set Background</button>
                <button class="pic-btn" onclick="picGoBack()" style="background:#64748b;color:#fff">Back</button>
            </div>
            <div class="pic-info"><span id="picName"></span> &mdash; <span id="picCounter"></span></div>
        </div>
    </div>
    <div id="marineIdModal" class="ext-modal hidden" style="z-index:1100">
        <div class="ext-backdrop" onclick="closeMarineId()"></div>
        <div class="ext-box" style="max-width:550px;max-height:80vh;overflow-y:auto">
            <h3 id="marineIdTitle">Marine Life Identification</h3>
            <div id="marineIdContent" style="white-space:pre-wrap;color:#cbd5e1;font-size:0.9rem;line-height:1.6"></div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="closeMarineId()">Close</button>
                <button class="ext-btn-import" id="marineIdSaveBtn" onclick="saveMarineId()" title="Save the marine life identification text for this photo">Save</button>
                <button class="ext-btn-import" id="marineIdOverlayBtn" onclick="overlayMarineId()" style="background:#0d9488" title="Create and save a copy of the photo with marine ID text overlaid">🖼️ Overlay Photo</button>
            </div>
        </div>
    </div>
    <div id="apiKeyModal" class="ext-modal hidden" style="z-index:1100">
        <div class="ext-backdrop" onclick="closeApiKeyModal()"></div>
        <div class="ext-box" style="max-width:450px">
            <h3>Anthropic API Key Required</h3>
            <p style="color:#94a3b8;font-size:0.85rem;margin-bottom:16px">Enter your Anthropic API key to use marine life identification. Your key is stored locally and never shared.</p>
            <div class="trip-form-row">
                <label>API Key</label>
                <input type="password" id="apiKeyInput" placeholder="sk-ant-..." style="font-size:0.85rem">
            </div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="closeApiKeyModal()">Cancel</button>
                <button class="ext-btn-import" onclick="saveApiKey()">Save & Continue</button>
            </div>
        </div>
    </div>
    <div id="slideshowOptsModal" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="cancelSlideshowOpts()"></div>
        <div class="ext-box">
            <h3>Slideshow Options</h3>
            <div class="trip-form-row">
                <label>Format</label>
                <select id="ssOptFormat" onchange="ssFormatChanged()" style="padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;font-size:0.85rem">
                    <option value="html" selected>HTML</option>
                    <option value="mp4">MP4 Video</option>
                </select>
            </div>
            <div class="trip-form-row">
                <label>Title</label>
                <input type="text" id="ssOptTitle" placeholder="Slideshow title">
            </div>
            <div class="trip-form-row">
                <label>Time Between Slides (seconds)</label>
                <input type="number" id="ssOptInterval" value="5" min="1" max="60" style="width:80px">
            </div>
            <div id="ssHtmlOnlyOpts">
            <div class="trip-form-row">
                <label>Show Slideshow Controls</label>
                <select id="ssOptControls" style="padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;font-size:0.85rem">
                    <option value="N" selected>No</option>
                    <option value="Y">Yes</option>
                </select>
            </div>
            <div class="trip-form-row">
                <label>Include File Caption</label>
                <select id="ssOptCaption" style="padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;font-size:0.85rem">
                    <option value="Y" selected>Yes</option>
                    <option value="N">No</option>
                </select>
            </div>
            <div class="trip-form-row">
                <label>Show Slide Number</label>
                <select id="ssOptSlideNum" style="padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;font-size:0.85rem">
                    <option value="N" selected>No</option>
                    <option value="Y">Yes</option>
                </select>
            </div>
            </div>
            <div class="trip-form-row">
                <label>Background Sound</label>
                <div style="display:flex;gap:8px;align-items:center">
                    <select id="ssOptSound" style="flex:1;padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;font-size:0.85rem">
                        <option value="" selected>None</option>
                    </select>
                    <button onclick="ssPickSoundFile()" style="padding:6px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.08);color:#e2e8f0;cursor:pointer;font-size:0.8rem;white-space:nowrap">Browse...</button>
                </div>
            </div>
            <div class="ext-btns">
                <button class="ext-btn-cancel" onclick="cancelSlideshowOpts()">Cancel</button>
                <button class="ext-btn-import" onclick="confirmSlideshowOpts()">Generate</button>
            </div>
        </div>
    </div>
    <div id="shareModal" class="ext-modal hidden">
        <div class="ext-backdrop" onclick="closeShareModal()"></div>
        <div class="ext-box" style="max-width:520px;min-width:380px">
            <div id="sharePhase1">
                <h3>🌐 Share Dive</h3>
                <div class="ext-sub">Choose a shareable image style</div>
                <div class="share-option-grid">
                    <div class="share-option-card" id="shareOptCard" onclick="shareSelectOption('card')">
                        <div class="share-icon">🤿</div>
                        <div class="share-label">Dive Card</div>
                        <div class="share-desc">Stats overlay on photo</div>
                    </div>
                    <div class="share-option-card" id="shareOptCaption" onclick="shareSelectOption('caption')">
                        <div class="share-icon">📸</div>
                        <div class="share-label">Photo + Caption</div>
                        <div class="share-desc">Full photo with caption</div>
                    </div>
                    <div class="share-option-card" id="shareOptTrip" onclick="shareSelectOption('trip')">
                        <div class="share-icon">🗺️</div>
                        <div class="share-label">Trip Summary</div>
                        <div class="share-desc">Trip stats banner</div>
                    </div>
                </div>
                <div class="ext-btns">
                    <button class="ext-btn-cancel" onclick="closeShareModal()">Cancel</button>
                </div>
            </div>
            <div id="sharePhase2" style="display:none">
                <h3 id="sharePhase2Title">Preview</h3>
                <div id="sharePhotoStrip" class="share-photo-strip" style="display:none"></div>
                <canvas id="sharePreviewCanvas"></canvas>
                <div id="shareHint" style="font-size:0.75rem;color:#94a3b8;text-align:center;margin-top:8px;min-height:1.2em"></div>
                <div class="ext-btns" style="margin-top:12px">
                    <button class="ext-btn-cancel" onclick="shareBack()">Back</button>
                    <button class="ext-btn-import" onclick="shareSave()" style="background:#22c55e">💾 Save</button>
                </div>
            </div>
        </div>
    </div>
    <div id="progressOverlay" class="ext-modal hidden">
        <div class="ext-backdrop"></div>
        <div style="position:relative;background:#1e3a5f;border:1px solid rgba(255,255,255,0.2);border-radius:14px;padding:30px 40px;text-align:center;min-width:300px;z-index:1">
            <div id="progressTitle" style="font-size:1.1rem;font-weight:600;color:#e2e8f0;margin-bottom:12px">Copying Files...</div>
            <div id="progressText" style="color:#94a3b8;font-size:0.9rem;margin-bottom:16px"></div>
            <div id="progressBarWrap" style="background:rgba(255,255,255,0.1);border-radius:6px;height:8px;overflow:hidden;margin-bottom:16px">
                <div id="progressBar" style="background:#06b6d4;height:100%;width:0%;transition:width 0.3s;border-radius:6px"></div>
            </div>
            <button id="progressCloseBtn" class="pic-btn" onclick="document.getElementById('progressOverlay').classList.add('hidden')" style="display:none;background:#06b6d4;color:#0f1923;font-weight:600">OK</button>
        </div>
    </div>
    <div id="confirmModal" class="ext-modal hidden">
        <div class="ext-backdrop"></div>
        <div style="position:relative;background:#1e3a5f;border:1px solid rgba(255,255,255,0.2);border-radius:14px;padding:30px 40px;text-align:center;min-width:300px;max-width:420px;z-index:1">
            <div id="confirmTitle" style="font-size:1.1rem;font-weight:600;color:#e2e8f0;margin-bottom:12px"></div>
            <div id="confirmText" style="color:#94a3b8;font-size:0.9rem;margin-bottom:20px;white-space:pre-line"></div>
            <div style="display:flex;gap:12px;justify-content:center">
                <button class="pic-btn" onclick="resolveConfirmModal(false)" style="background:#64748b;color:#fff;font-weight:600">Cancel</button>
                <button class="pic-btn" onclick="resolveConfirmModal(true)" style="background:#06b6d4;color:#0f1923;font-weight:600">OK</button>
            </div>
        </div>
    </div>
    <div id="rawCopyModal" class="ext-modal hidden">
        <div class="ext-backdrop"></div>
        <div style="position:relative;background:#1e3a5f;border:1px solid rgba(255,255,255,0.2);border-radius:14px;padding:30px 40px;text-align:center;min-width:320px;max-width:440px;z-index:1">
            <div style="font-size:1.1rem;font-weight:600;color:#e2e8f0;margin-bottom:8px">RAW Files Detected</div>
            <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:20px;white-space:pre-line">This selection contains RAW files.\nHow would you like to handle them?</div>
            <div style="display:flex;flex-direction:column;gap:10px;align-items:center">
                <button class="pic-btn" onclick="resolveRawCopyModal('convert')" style="background:#06b6d4;color:#0f1923;font-weight:600;width:220px">Convert RAW to JPG</button>
                <button class="pic-btn" onclick="resolveRawCopyModal('keep')" style="background:#22c55e;color:#0f1923;font-weight:600;width:220px">Keep Original Format</button>
                <button class="pic-btn" onclick="resolveRawCopyModal('cancel')" style="background:#64748b;color:#fff;font-weight:600;width:220px">Cancel Copy</button>
            </div>
        </div>
    </div>
    <div id="photoTooltip"><img id="ttImg" src=""><div class="tt-name" id="ttName"></div></div>

    <script>
        const dives = {dives_js};
        const tripsData = {trips_js};
        const computerInfo = {computer_info_js};

        let isMetric = false;
        let isPSI = true;
        let currentLocation = 'All';
        let sortField = 'location';
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
                let cmp;
                if (typeof aVal === 'string') cmp = aVal.localeCompare(bVal);
                else cmp = aVal - bVal;
                if (sortDir === 'desc') cmp = -cmp;
                if (cmp !== 0) return cmp;
                /* Secondary sort by dive number */
                return a.number - b.number;
            }});
            return filtered;
        }}

        function formatDepth(m, ft) {{ return isMetric ? `${{m}}m` : `${{ft}}ft`; }}
        function formatTemp(c) {{ return isMetric ? `${{c}}°C` : `${{Math.round(c * 9/5 + 32)}}°F`; }}
        function formatPressure(psi) {{ return isPSI ? `${{psi}}` : `${{psiToBar(psi)}}`; }}
        function pressureUnit() {{ return isPSI ? 'PSI' : 'bar'; }}
        function depthUnit() {{ return isMetric ? 'm' : 'ft'; }}

        function renderStats() {{
            const f = getFilteredDives();
            if (f.length === 0) {{ document.getElementById('statsGrid').innerHTML = ''; return; }}
            const realDives = f.filter(d => !d.photoOnly);
            const gasCount = realDives.length || 1;
            const avgGas = Math.round(realDives.reduce((s, d) => s + d.gasUsed, 0) / gasCount);
            const avgRate = (realDives.reduce((s, d) => s + (d.durationMin > 0 ? d.gasUsed / d.durationMin : 0), 0) / gasCount).toFixed(1);
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
                <th>Pics</th>
                <th onclick="sortBy('site')">Site${{arrow('site')}}</th>
                <th onclick="sortBy('maxDepthM')">Depth${{arrow('maxDepthM')}}</th>
                <th onclick="sortBy('durationMin')">Duration${{arrow('durationMin')}}</th>
                <th onclick="sortBy('time')">Start${{arrow('time')}}</th>
                <th onclick="sortBy('endTime')">End${{arrow('endTime')}}</th>
                <th onclick="sortBy('o2Percent')">O\u2082</th>
                <th onclick="sortBy('startPSI')">Start ${{pressureUnit()}}${{arrow('startPSI')}}</th>
                <th onclick="sortBy('endPSI')">End ${{pressureUnit()}}${{arrow('endPSI')}}</th>
                <th onclick="sortBy('gasUsed')">Used${{arrow('gasUsed')}}</th>
                <th>Rate</th>
                <th onclick="sortBy('endGF99')">GF99${{arrow('endGF99')}}</th>
            </tr></thead><tbody>`;
            filtered.forEach(d => {{
                const loc = (d.location || 'unknown').toLowerCase().replace('curaco','curacao');
                const knownLocs = ['bonaire','cozumel','curacao','unknown'];
                const locClass = knownLocs.includes(loc) ? 'location-' + loc : 'location-custom';
                const gfClass = d.endGF99 > 70 ? 'gf-high' : d.endGF99 > 50 ? 'gf-med' : 'gf-low';
                const rate = d.durationMin > 0 ? (d.gasUsed / d.durationMin).toFixed(1) : '0';
                const rateClass = rate > 40 ? 'consumption-high' : rate > 30 ? 'consumption-med' : 'consumption-low';
                const selected = selectedDive && selectedDive.number === d.number ? 'selected' : '';
                const hasMetrics = d.maxDepthM > 0 || d.startPSI > 0 || d.endPSI > 0;
                const rowClick = hasMetrics ? `onclick="selectDive(${{d.number}})"` : '';
                const rowStyle = hasMetrics ? '' : 'style="cursor:default;opacity:0.7"';
                html += `<tr class="${{selected}}" ${{rowClick}} ${{rowStyle}}>
                    <td class="mono">${{d.number}} <span onclick="event.stopPropagation();editDive(${{d.number}})" style="cursor:pointer;font-size:0.7rem;color:#94a3b8" title="Edit dive">&#9998;</span></td><td>${{d.date}}</td>
                    <td><span class="location-badge ${{locClass}}">${{d.location || 'Unknown'}}</span></td>
                    <td>${{divePhotos[d.number] && divePhotos[d.number].length ? `<span class="pics-y" onclick="event.stopPropagation();openDivePics(${{d.number}})">${{divePhotos[d.number].length}}</span>` : `<span class="pics-n">N</span>`}}</td>
                    <td>${{d.site || '-'}}</td>
                    <td class="mono">${{formatDepth(d.maxDepthM, d.maxDepthFt)}}</td>
                    <td class="mono">${{d.durationMin}}min</td>
                    <td class="mono">${{d.time || '-'}}</td>
                    <td class="mono">${{d.endTime || '-'}}</td>
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



        function mergeNewDives(newDives, newTrips) {{
            /* Build a set of existing dive keys (number + date) for dedup */
            const existingKeys = new Set(dives.map(d => d.number + '|' + d.date));
            const added = [];
            newDives.forEach(d => {{
                const key = d.number + '|' + d.date;
                if (!existingKeys.has(key)) {{
                    dives.push(d);
                    existingKeys.add(key);
                    added.push(d);
                }}
            }});
            if (added.length === 0) return 0;
            /* Merge trips: only add locations that don't already exist */
            const existingLocs = new Set(tripsData.map(t => normLoc(t.name)));
            const tripColors = ['#3b82f6','#22c55e','#f97316','#a855f7','#ef4444','#eab308','#ec4899','#14b8a6','#f59e0b','#6366f1'];
            newTrips.forEach(t => {{
                if (!existingLocs.has(normLoc(t.name))) {{
                    if (!t.color || t.color === '#94a3b8') t.color = tripColors[tripsData.length % tripColors.length];
                    tripsData.push(t);
                    existingLocs.add(normLoc(t.name));
                }}
            }});
            /* Refresh location filter */
            const locSelect = document.getElementById('locationFilter');
            const locs = [...new Set(dives.map(d => d.location || 'Unknown').map(l => l === 'Curaco' ? 'Curacao' : l))];
            const cur = locSelect.value;
            locSelect.innerHTML = '<option value="All">All Locations</option>';
            locs.forEach(loc => {{
                const opt = document.createElement('option');
                opt.value = loc;
                opt.textContent = loc === 'Curacao' ? 'Cura\u00e7ao' : loc;
                locSelect.appendChild(opt);
            }});
            locSelect.value = locs.includes(cur) ? cur : 'All';
            renderStats();
            renderTrips();
            renderTable();
            return added.length;
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

        let editDiveNum = null;
        function editDive(num) {{
            const d = dives.find(x => x.number === num);
            if (!d) return;
            editDiveNum = num;
            document.getElementById('diveEditTitle').textContent = 'Edit Dive #' + num + ' — ' + (d.location || 'Unknown') + ' — ' + d.date;
            document.getElementById('deSite').value = d.site || '';
            document.getElementById('diveEditModal').classList.remove('hidden');
        }}
        function closeDiveEdit() {{
            document.getElementById('diveEditModal').classList.add('hidden');
            editDiveNum = null;
        }}
        function saveDiveEdit() {{
            const d = dives.find(x => x.number === editDiveNum);
            if (!d) return;
            d.site = document.getElementById('deSite').value.trim() || '';
            closeDiveEdit();
            if (selectedDive && selectedDive.number === d.number) renderDetail();
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
            document.getElementById('detailTitle').innerHTML = `Dive #${{d.number}} <span onclick="editDive(${{d.number}})" style="cursor:pointer;font-size:0.75rem;color:#94a3b8;margin-left:6px" title="Edit dive">&#9998;</span>`;
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
            /* Dive photos section */
            const photoSec = document.getElementById('divePhotosSection');
            const photos = divePhotos[d.number];
            const anyTripsHavePics = Object.keys(tripFiles).length > 0;
            if (photos && photos.length > 0) {{
                photoSec.innerHTML = `<button class="dive-photos-btn" onclick="openDivePics(${{d.number}})">📷 View ${{photos.length}} Photo${{photos.length > 1 ? 's' : ''}} from this Dive</button> <button class="dive-photos-btn" style="background:rgba(139,92,246,0.3);border-color:rgba(139,92,246,0.5);color:#c4b5fd" onclick="createDiveSlideshow(${{d.number}})">🎬 Create Slideshow</button> <button class="dive-photos-btn" style="background:rgba(74,222,128,0.2);border-color:rgba(74,222,128,0.4);color:#4ade80" onclick="copyDivePhotos(${{d.number}})">📁 Copy to Directory</button> <button class="dive-photos-btn" style="background:rgba(6,182,212,0.2);border-color:rgba(6,182,212,0.4);color:#22d3ee" onclick="openShareModal('dive',${{d.number}})">🌐 Share</button>`;
            }} else if (anyTripsHavePics) {{
                photoSec.innerHTML = `<div class="no-pics">No pictures found for this dive</div> <button class="dive-photos-btn" style="background:rgba(6,182,212,0.2);border-color:rgba(6,182,212,0.4);color:#22d3ee;margin-top:6px" onclick="openShareModal('dive',${{d.number}})">🌐 Share</button>`;
            }} else {{
                photoSec.innerHTML = `<button class="dive-photos-btn" style="background:rgba(6,182,212,0.2);border-color:rgba(6,182,212,0.4);color:#22d3ee" onclick="openShareModal('dive',${{d.number}})">🌐 Share</button>`;
            }}
            if (depthChart) depthChart.destroy();
            const depthData = generateDepthProfile(d);
            const photoOffsets = getPhotoTimeOffsets(d);
            chartPhotoPoints = photoOffsets;
            const photoScatter = photoOffsets.map(p => ({{ x: p.min, y: interpolateDepth(depthData, p.min) }}));
            const datasets = [
                {{ data: depthData, borderColor: '#06b6d4', backgroundColor: 'rgba(6, 182, 212, 0.2)', fill: true, tension: 0.3, pointRadius: 0 }}
            ];
            if (photoScatter.length > 0) {{
                datasets.push({{
                    data: photoScatter,
                    type: 'scatter',
                    backgroundColor: '#f59e0b',
                    borderColor: '#fbbf24',
                    pointRadius: 7,
                    pointHoverRadius: 10,
                    pointStyle: 'circle',
                    label: 'Photos'
                }});
            }}
            const depthCanvas = document.getElementById('depthProfileChart');
            depthChart = new Chart(depthCanvas, {{
                type: 'line',
                data: {{ datasets: datasets }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            enabled: false,
                            external: function(context) {{
                                const tt = document.getElementById('photoTooltip');
                                if (context.tooltip.opacity === 0) {{ tt.style.display = 'none'; return; }}
                                const dp = context.tooltip.dataPoints && context.tooltip.dataPoints[0];
                                if (!dp || dp.datasetIndex !== 1) {{ tt.style.display = 'none'; return; }}
                                const pt = chartPhotoPoints[dp.dataIndex];
                                if (!pt) {{ tt.style.display = 'none'; return; }}
                                const file = pt.file;
                                const imgEl = document.getElementById('ttImg');
                                const nameEl = document.getElementById('ttName');
                                /* Show caption if available, otherwise filename */
                                const capKey1 = picTripIdx + '_' + file.name;
                                const capKey2 = 'dive_' + d.number + '_' + file.name;
                                nameEl.textContent = picCaptions[capKey2] || picCaptions[capKey1] || file.name;
                                if (isRaw(file.name) && rawCache[file.name]) {{
                                    imgEl.src = rawCache[file.name];
                                }} else if (!isRaw(file.name)) {{
                                    imgEl.src = URL.createObjectURL(file);
                                }} else {{
                                    imgEl.src = '';
                                    nameEl.textContent = file.name + ' (RAW)';
                                }}
                                const pos = context.chart.canvas.getBoundingClientRect();
                                tt.style.display = 'block';
                                tt.style.left = (pos.left + window.scrollX + context.tooltip.caretX + 14) + 'px';
                                tt.style.top = (pos.top + window.scrollY + context.tooltip.caretY - 60) + 'px';
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ type: 'linear', title: {{ display: true, text: 'Time (min)', color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ reverse: true, title: {{ display: true, text: `Depth (${{isMetric ? 'm' : 'ft'}})`, color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }}, min: 0 }}
                    }},
                    onClick: function(evt, elements) {{
                        if (elements.length > 0 && elements[0].datasetIndex === 1) {{
                            const idx = elements[0].index;
                            const pt = chartPhotoPoints[idx];
                            if (pt) {{
                                document.getElementById('photoTooltip').style.display = 'none';
                                picViewMode = 'dive';
                                viewDiveNum = d.number;
                                openPicViewer(0, pt.index);
                            }}
                        }}
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
            document.getElementById('addTripTabBtn').style.display = tab === 'trips' ? '' : 'none';

            if (tab === 'table') renderTable();
            if (tab === 'charts') renderCharts();
            if (tab === 'gas') renderGasCharts();
            if (tab === 'trips') {{ renderTrips(); }}
            if (tab !== 'table') document.getElementById('detailPanel').classList.add('hidden');
        }}

        document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));

        function renderCharts() {{
            const filtered = getFilteredDives().filter(d => !d.photoOnly);
            const colors = {{ Bonaire: '#3b82f6', Cozumel: '#22c55e', Curacao: '#f97316', Curaco: '#f97316', '': '#94a3b8', Unknown: '#94a3b8' }};
            document.getElementById('chartsPanel').innerHTML = `
                <div class="chart-card"><h3>Dive Depth Profile</h3><div class="chart-container"><canvas id="depthChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Dive Duration</h3><div class="chart-container"><canvas id="durationChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Water Temperature</h3><div class="chart-container"><canvas id="tempChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Dives by Location</h3><div class="chart-container"><canvas id="locationChartMain"></canvas></div></div>
                <div class="chart-card"><h3>Max Depth Progression</h3><div class="chart-container"><canvas id="depthProgressChart"></canvas></div></div>
                <div class="chart-card"><h3>Dive Frequency</h3><div class="chart-container"><canvas id="freqChart"></canvas></div></div>
            `;
            Object.keys(charts).forEach(k => {{ if (charts[k]) charts[k].destroy(); }});

            /* Click handler: navigate to dive detail page */
            function chartClickToDive(evt, elements, chart) {{
                if (elements.length > 0) {{
                    const idx = elements[0].index;
                    const dive = filtered[idx];
                    if (dive && (dive.maxDepthM > 0 || dive.startPSI > 0)) {{
                        switchTab('table');
                        setTimeout(function() {{ selectDive(dive.number); }}, 50);
                    }}
                }}
            }}

            /* Tooltip callback: show dive site and details */
            function diveTooltipCallbacks(valueLabel) {{
                return {{
                    title: function(items) {{
                        const idx = items[0].dataIndex;
                        const d = filtered[idx];
                        let t = 'Dive #' + d.number + ' \u2014 ' + (d.location || 'Unknown');
                        if (d.site) t += ' \u2014 ' + d.site;
                        return t;
                    }},
                    afterTitle: function(items) {{
                        const d = filtered[items[0].dataIndex];
                        return d.date;
                    }},
                    label: function(item) {{
                        return valueLabel(item, filtered[item.dataIndex]);
                    }},
                    footer: function() {{
                        return 'Click to view dive details';
                    }}
                }};
            }}

            const tooltipStyle = {{
                titleColor: '#e2e8f0',
                bodyColor: '#94a3b8',
                footerColor: '#64748b',
                footerFont: {{ style: 'italic', size: 11 }},
                backgroundColor: 'rgba(15,25,35,0.95)',
                borderColor: 'rgba(6,182,212,0.4)',
                borderWidth: 1,
                padding: 10,
                displayColors: false
            }};

            const chartOpts = {{
                responsive: true, maintainAspectRatio: false,
                onClick: chartClickToDive,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        ...tooltipStyle,
                        callbacks: diveTooltipCallbacks(function(item, d) {{
                            return formatDepth(d.maxDepthM, d.maxDepthFt);
                        }})
                    }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                }},
                onHover: function(evt, elements) {{
                    evt.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }}
            }};

            /* Depth chart */
            charts.depthMain = new Chart(document.getElementById('depthChartMain'), {{
                type: 'bar',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isMetric ? d.maxDepthM : d.maxDepthFt), backgroundColor: filtered.map(d => colors[d.location] || '#94a3b8'), borderRadius: 3 }}] }},
                options: {{ ...chartOpts, scales: {{ ...chartOpts.scales, y: {{ ...chartOpts.scales.y, reverse: true }} }} }}
            }});

            /* Duration chart */
            charts.durationMain = new Chart(document.getElementById('durationChartMain'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => d.durationMin), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', fill: true, tension: 0.3 }}] }},
                options: {{ ...chartOpts, plugins: {{ ...chartOpts.plugins, tooltip: {{ ...tooltipStyle, callbacks: diveTooltipCallbacks(function(item, d) {{ return d.durationMin + ' min'; }}) }} }} }}
            }});

            /* Temperature chart */
            charts.tempMain = new Chart(document.getElementById('tempChartMain'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isMetric ? d.avgTempC : (d.avgTempC * 9/5 + 32)), borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.1)', fill: true, tension: 0.3 }}] }},
                options: {{ ...chartOpts, plugins: {{ ...chartOpts.plugins, tooltip: {{ ...tooltipStyle, callbacks: diveTooltipCallbacks(function(item, d) {{ return formatTemp(d.avgTempC); }}) }} }} }}
            }});

            /* Dives by Location — doughnut with detailed tooltip */
            const locStats = {{}};
            filtered.forEach(d => {{
                const loc = (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location;
                if (!locStats[loc]) locStats[loc] = {{ count: 0, totalMin: 0, maxDepth: 0, sites: new Set() }};
                locStats[loc].count++;
                locStats[loc].totalMin += d.durationMin;
                const depth = isMetric ? d.maxDepthM : d.maxDepthFt;
                if (depth > locStats[loc].maxDepth) locStats[loc].maxDepth = depth;
                if (d.site) locStats[loc].sites.add(d.site);
            }});
            const locNames = Object.keys(locStats);
            charts.locationMain = new Chart(document.getElementById('locationChartMain'), {{
                type: 'doughnut',
                data: {{ labels: locNames, datasets: [{{ data: locNames.map(l => locStats[l].count), backgroundColor: locNames.map(l => colors[l] || '#94a3b8') }}] }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: 'white' }} }},
                        tooltip: {{
                            ...tooltipStyle,
                            displayColors: true,
                            callbacks: {{
                                title: function(items) {{ return items[0].label; }},
                                label: function(item) {{
                                    const s = locStats[item.label];
                                    return s.count + ' dive' + (s.count !== 1 ? 's' : '');
                                }},
                                afterLabel: function(item) {{
                                    const s = locStats[item.label];
                                    const hours = Math.floor(s.totalMin / 60);
                                    const mins = s.totalMin % 60;
                                    const lines = [];
                                    lines.push('Total: ' + hours + 'h ' + mins + 'm');
                                    lines.push('Deepest: ' + s.maxDepth + (isMetric ? 'm' : 'ft'));
                                    if (s.sites.size > 0) {{
                                        const siteList = Array.from(s.sites).sort();
                                        lines.push('Sites: ' + siteList.slice(0, 5).join(', ') + (siteList.length > 5 ? ' +' + (siteList.length - 5) + ' more' : ''));
                                    }}
                                    return lines;
                                }}
                            }}
                        }}
                    }}
                }}
            }});

            /* Max Depth Progression — running max depth over time */
            let runningMax = 0;
            const depthProgData = filtered.map(d => {{
                const depth = isMetric ? d.maxDepthM : d.maxDepthFt;
                if (depth > runningMax) runningMax = depth;
                return runningMax;
            }});
            charts.depthProgress = new Chart(document.getElementById('depthProgressChart'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [
                    {{ label: 'Max Depth', data: filtered.map(d => isMetric ? d.maxDepthM : d.maxDepthFt), borderColor: 'rgba(6,182,212,0.4)', backgroundColor: 'transparent', tension: 0.3, pointRadius: 3, borderWidth: 1 }},
                    {{ label: 'Personal Best', data: depthProgData, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0, pointRadius: 0, borderWidth: 2, borderDash: [5, 3] }}
                ] }},
                options: {{ ...chartOpts,
                    plugins: {{ ...chartOpts.plugins,
                        legend: {{ display: true, labels: {{ color: 'white' }} }},
                        tooltip: {{ ...tooltipStyle, callbacks: diveTooltipCallbacks(function(item, d) {{ return formatDepth(d.maxDepthM, d.maxDepthFt); }}) }}
                    }},
                    scales: {{ ...chartOpts.scales, y: {{ ...chartOpts.scales.y, reverse: true }} }}
                }}
            }});

            /* Dive Frequency — dives per month */
            const monthCounts = {{}};
            filtered.forEach(d => {{
                if (!d.date) return;
                const ym = d.date.substring(0, 7);
                monthCounts[ym] = (monthCounts[ym] || 0) + 1;
            }});
            const months = Object.keys(monthCounts).sort();
            charts.freq = new Chart(document.getElementById('freqChart'), {{
                type: 'bar',
                data: {{ labels: months, datasets: [{{ data: months.map(m => monthCounts[m]), backgroundColor: '#06b6d4', borderRadius: 4 }}] }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            ...tooltipStyle,
                            callbacks: {{
                                title: function(items) {{
                                    const ym = months[items[0].dataIndex];
                                    const [y, m] = ym.split('-');
                                    const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                                    return names[parseInt(m)-1] + ' ' + y;
                                }},
                                label: function(item) {{
                                    const count = item.raw;
                                    return count + ' dive' + (count !== 1 ? 's' : '');
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ color: '#94a3b8', maxRotation: 45 }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ ticks: {{ color: '#94a3b8', stepSize: 1 }}, grid: {{ color: 'rgba(255,255,255,0.1)' }}, beginAtZero: true }}
                    }}
                }}
            }});
        }}

        function renderGasCharts() {{
            const filtered = getFilteredDives().filter(d => !d.photoOnly);
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

            /* Click handler: navigate to dive detail page */
            function gasClickToDive(evt, elements, chart) {{
                if (elements.length > 0) {{
                    const idx = elements[0].index;
                    const dive = filtered[idx];
                    if (dive && (dive.maxDepthM > 0 || dive.startPSI > 0)) {{
                        switchTab('table');
                        setTimeout(function() {{ selectDive(dive.number); }}, 50);
                    }}
                }}
            }}

            /* Tooltip callbacks with site name */
            function gasTooltipCallbacks(valueLabel) {{
                return {{
                    title: function(items) {{
                        const d = filtered[items[0].dataIndex];
                        let t = 'Dive #' + d.number + ' \u2014 ' + (d.location || 'Unknown');
                        if (d.site) t += ' \u2014 ' + d.site;
                        return t;
                    }},
                    afterTitle: function(items) {{
                        return filtered[items[0].dataIndex].date;
                    }},
                    label: function(item) {{
                        return valueLabel(item, filtered[item.dataIndex]);
                    }},
                    footer: function() {{
                        return 'Click to view dive details';
                    }}
                }};
            }}

            const tooltipStyle = {{
                titleColor: '#e2e8f0',
                bodyColor: '#94a3b8',
                footerColor: '#64748b',
                footerFont: {{ style: 'italic', size: 11 }},
                backgroundColor: 'rgba(15,25,35,0.95)',
                borderColor: 'rgba(6,182,212,0.4)',
                borderWidth: 1,
                padding: 10,
                displayColors: false
            }};

            const chartOpts = {{
                responsive: true, maintainAspectRatio: false,
                onClick: gasClickToDive,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        ...tooltipStyle,
                        callbacks: gasTooltipCallbacks(function(item, d) {{
                            return formatPressure(d.gasUsed) + ' ' + pressureUnit();
                        }})
                    }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                }},
                onHover: function(evt, elements) {{
                    evt.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                }}
            }};

            /* Gas Used chart */
            charts.gasUsed = new Chart(document.getElementById('gasUsedChart'), {{
                type: 'bar',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => isPSI ? d.gasUsed : psiToBar(d.gasUsed)), backgroundColor: filtered.map(d => colors[d.location] || '#94a3b8'), borderRadius: 3 }}] }},
                options: chartOpts
            }});

            /* Consumption Rate chart */
            charts.gasRate = new Chart(document.getElementById('gasRateChart'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [{{ data: filtered.map(d => {{ const rate = d.durationMin > 0 ? d.gasUsed / d.durationMin : 0; return isPSI ? rate.toFixed(1) : (rate * 0.0689).toFixed(2); }}), borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.1)', fill: true, tension: 0.3 }}] }},
                options: {{ ...chartOpts, plugins: {{ ...chartOpts.plugins, tooltip: {{ ...tooltipStyle, callbacks: gasTooltipCallbacks(function(item, d) {{
                    const rate = d.durationMin > 0 ? d.gasUsed / d.durationMin : 0;
                    return (isPSI ? rate.toFixed(1) : (rate * 0.0689).toFixed(2)) + ' ' + pressureUnit() + '/min';
                }}) }} }} }}
            }});

            /* Tank Pressure Start vs End chart */
            charts.tankPressureMain = new Chart(document.getElementById('tankPressureMainChart'), {{
                type: 'line',
                data: {{ labels: filtered.map(d => d.number), datasets: [
                    {{ label: 'Start', data: filtered.map(d => isPSI ? d.startPSI : psiToBar(d.startPSI)), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', tension: 0.3 }},
                    {{ label: 'End', data: filtered.map(d => isPSI ? d.endPSI : psiToBar(d.endPSI)), borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.3 }}
                ] }},
                options: {{ ...chartOpts, plugins: {{
                    legend: {{ display: true, labels: {{ color: 'white' }} }},
                    tooltip: {{ ...tooltipStyle, displayColors: true, callbacks: gasTooltipCallbacks(function(item, d) {{
                        const label = item.dataset.label;
                        const val = label === 'Start' ? d.startPSI : d.endPSI;
                        return label + ': ' + formatPressure(val) + ' ' + pressureUnit();
                    }}) }}
                }} }}
            }});

            /* Depth vs Gas Consumption scatter — build dive lookup for tooltips */
            const locs = [...new Set(filtered.map(d => (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location))];
            const scatterDiveLookup = {{}};
            locs.forEach((loc, li) => {{
                scatterDiveLookup[li] = filtered.filter(d => (d.location === loc) || (loc === 'Curacao' && (d.location === 'Curaco' || !d.location)));
            }});
            charts.depthGas = new Chart(document.getElementById('depthGasChart'), {{
                type: 'scatter',
                data: {{ datasets: locs.map((loc, li) => ({{
                    label: loc,
                    data: scatterDiveLookup[li].map(d => ({{ x: isMetric ? d.maxDepthM : d.maxDepthFt, y: isPSI ? d.gasUsed : psiToBar(d.gasUsed) }})),
                    backgroundColor: colors[loc] || '#94a3b8',
                    pointRadius: 6
                }})) }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    onClick: function(evt, elements) {{
                        if (elements.length > 0) {{
                            const d = scatterDiveLookup[elements[0].datasetIndex][elements[0].index];
                            if (d && (d.maxDepthM > 0 || d.startPSI > 0)) {{
                                switchTab('table');
                                setTimeout(function() {{ selectDive(d.number); }}, 50);
                            }}
                        }}
                    }},
                    onHover: function(evt, elements) {{
                        evt.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                    }},
                    plugins: {{
                        legend: {{ display: true, labels: {{ color: 'white' }} }},
                        tooltip: {{
                            ...tooltipStyle,
                            displayColors: true,
                            callbacks: {{
                                title: function(items) {{
                                    const d = scatterDiveLookup[items[0].datasetIndex][items[0].dataIndex];
                                    let t = 'Dive #' + d.number + ' \u2014 ' + (d.location || 'Unknown');
                                    if (d.site) t += ' \u2014 ' + d.site;
                                    return t;
                                }},
                                afterTitle: function(items) {{
                                    return scatterDiveLookup[items[0].datasetIndex][items[0].dataIndex].date;
                                }},
                                label: function(item) {{
                                    const d = scatterDiveLookup[item.datasetIndex][item.dataIndex];
                                    return formatDepth(d.maxDepthM, d.maxDepthFt) + ' \u2022 ' + formatPressure(d.gasUsed) + ' ' + pressureUnit();
                                }},
                                footer: function() {{
                                    return 'Click to view dive details';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ title: {{ display: true, text: `Depth (${{depthUnit()}})`, color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ title: {{ display: true, text: `Gas Used (${{pressureUnit()}})`, color: '#94a3b8' }}, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                    }}
                }}
            }});

            /* Gas Usage by Location — summary chart, no per-dive click */
            const locGas = {{}};
            filtered.forEach(d => {{ const loc = (d.location === 'Curaco' || !d.location) ? 'Curacao' : d.location; if (!locGas[loc]) locGas[loc] = []; locGas[loc].push(d.gasUsed); }});
            const locGasStats = Object.entries(locGas).map(([loc, vals]) => ({{ loc, avg: vals.reduce((a,b) => a+b, 0) / vals.length, max: Math.max(...vals) }}));
            charts.gasLocation = new Chart(document.getElementById('gasLocationChart'), {{
                type: 'bar',
                data: {{ labels: locGasStats.map(d => d.loc), datasets: [
                    {{ label: 'Average', data: locGasStats.map(d => isPSI ? Math.round(d.avg) : psiToBar(d.avg)), backgroundColor: locGasStats.map(d => colors[d.loc] || '#94a3b8'), borderRadius: 4 }},
                    {{ label: 'Max', data: locGasStats.map(d => isPSI ? d.max : psiToBar(d.max)), backgroundColor: locGasStats.map(d => {{ const c = colors[d.loc] || '#94a3b8'; return c + '80'; }}), borderRadius: 4 }}
                ] }},
                options: {{
                    indexAxis: 'y',
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: true, labels: {{ color: 'white' }} }},
                        tooltip: {{
                            ...tooltipStyle,
                            displayColors: true,
                            callbacks: {{
                                label: function(item) {{
                                    return item.dataset.label + ': ' + item.raw + ' ' + pressureUnit();
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ beginAtZero: true, ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}
                    }}
                }}
            }});

            /* End Pressure Distribution — histogram, no per-dive click */
            const endBuckets = [0, 500, 750, 1000, 1250, 1500, 2000, 3500];
            const endCounts = endBuckets.slice(0, -1).map((min, i) => filtered.filter(d => d.endPSI >= min && d.endPSI < endBuckets[i+1]).length);
            charts.endPressure = new Chart(document.getElementById('endPressureChart'), {{
                type: 'bar',
                data: {{ labels: endBuckets.slice(0, -1).map((v, i) => `${{isPSI ? v : psiToBar(v)}}-${{isPSI ? endBuckets[i+1] : psiToBar(endBuckets[i+1])}}`), datasets: [{{ data: endCounts, backgroundColor: '#06b6d4', borderRadius: 4 }}] }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            ...tooltipStyle,
                            callbacks: {{
                                label: function(item) {{
                                    const count = item.raw;
                                    return count + ' dive' + (count !== 1 ? 's' : '');
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }}
                    }}
                }}
            }});
        }}

        /* Parse 'YYYY-MM-DD' + 'HH:mm' as local time (avoids UTC ambiguity) */
        function parseLocalMs(dateStr, timeStr) {{
            const p = dateStr.split('-');
            const t = timeStr.split(':');
            return new Date(+p[0], p[1]-1, +p[2], +t[0], +t[1]).getTime();
        }}

        /* ── Trip pictures state ── */
        const tripFiles = {{}};
        const keptStatus = {{}};     /* tripIdx -> [bool, ...] */
        const divePhotos = {{}};     /* diveNumber -> [File, ...] */
        const tripPicData = {{}};    /* tripIdx -> [{{ name, path, lastModified }}, ...] */
        let picTripIdx = null;
        let picIdx = 0;
        let picUrl = null;
        let picViewMode = 'trip';    /* 'trip', 'dive', or 'collection' */
        let viewDiveNum = null;      /* dive number when in dive mode */
        let viewCollIdx = null;      /* collection index when in collection mode */
        const rawExts = new Set(['.orf','.cr2','.cr3','.nef','.arw','.dng']);
        const rawCache = {{}};       /* filename -> data-URI */
        const picCaptions = {{}};    /* "tripIdx_filename" -> caption */
        const marineIds = {{}};      /* "tripIdx_filename" -> identification text */
        let thumbTripIdx = null;     /* trip index for thumbnail pane */
        let thumbSelected = [];      /* bool[] parallel to tripFiles[thumbTripIdx] */
        const tripCollections = {{}};  /* tripIdx -> [{{ name: string, files: File[] }}, ...] */
        let thumbPaneMode = 'trip';   /* 'trip', 'dive', or 'collection' */
        let thumbPaneCollIdx = null;  /* index into tripCollections when mode='collection' */
        let thumbPaneDiveNum = null;  /* dive number when mode='dive' */

        function fileExt(name) {{
            const dot = name.lastIndexOf('.');
            return dot > 0 ? name.slice(dot).toLowerCase() : '';
        }}
        function isRaw(name) {{ return rawExts.has(fileExt(name)); }}
        const videoExts = new Set(['.mp4','.mov','.mpeg','.mpg','.avi','.mkv','.webm']);
        function isVideo(name) {{ return videoExts.has(fileExt(name)); }}


        /* ── Thumbnail pane ── */
        let thumbLazyQueue = [];
        let thumbLazyRunning = false;
        let thumbTotalCount = 0;
        let thumbLoadedCount = 0;

        function thumbProgressTick() {{
            thumbLoadedCount++;
            const bar = document.getElementById('thumbProgressBar');
            const text = document.getElementById('thumbProgressText');
            const wrap = document.getElementById('thumbProgress');
            if (!bar) return;
            const pct = Math.round((thumbLoadedCount / thumbTotalCount) * 100);
            bar.style.width = pct + '%';
            text.textContent = thumbLoadedCount + ' / ' + thumbTotalCount;
            if (thumbLoadedCount >= thumbTotalCount) {{
                setTimeout(function() {{ wrap.style.display = 'none'; }}, 600);
            }}
        }}

        function lazyLoadNextThumb() {{
            if (thumbLazyQueue.length === 0) {{ thumbLazyRunning = false; return; }}
            thumbLazyRunning = true;
            const item = thumbLazyQueue.shift();
            const reader = new FileReader();
            reader.onload = function(e) {{
                item.img.src = e.target.result;
                item.img.onload = function() {{
                    correctImageForViewer(item.img);
                    /* Load next after this one renders */
                    setTimeout(lazyLoadNextThumb, 10);
                }};
            }};
            reader.onerror = function() {{ setTimeout(lazyLoadNextThumb, 10); }};
            reader.readAsDataURL(item.file);
        }}

        function showThumbPane(tripIdx, mode, sourceData) {{
            thumbTripIdx = tripIdx;
            thumbPaneMode = mode || 'trip';
            thumbPaneDiveNum = null;
            thumbPaneCollIdx = null;
            /* Resolve files and title based on mode */
            let files, title;
            if (thumbPaneMode === 'dive') {{
                thumbPaneDiveNum = sourceData.diveNum;
                files = divePhotos[sourceData.diveNum] || [];
                const dive = dives.find(d => d.number === sourceData.diveNum);
                title = 'Dive ' + sourceData.diveNum + (dive ? ' \u2014 ' + (dive.site || dive.location || '') : '') + ' (' + files.length + ')';
            }} else if (thumbPaneMode === 'collection') {{
                thumbPaneCollIdx = sourceData.collIdx;
                const coll = tripCollections[tripIdx][sourceData.collIdx];
                files = coll.files;
                title = coll.name + ' (' + files.length + ')';
            }} else {{
                files = tripFiles[tripIdx] || [];
                title = 'Trip Inventory (' + files.length + ')';
            }}
            if (thumbPaneMode === 'trip') {{
                thumbSelected = files.map((_, i) => keptStatus[tripIdx] ? keptStatus[tripIdx][i] !== false : true);
            }} else if (thumbPaneMode === 'dive') {{
                const dKey = 'dive_' + sourceData.diveNum;
                if (!keptStatus[dKey]) keptStatus[dKey] = files.map(() => true);
                thumbSelected = files.map((_, i) => keptStatus[dKey][i] !== false);
            }} else {{
                thumbSelected = files.map(() => true);
            }}
            const grid = document.getElementById('thumbGrid');
            document.getElementById('thumbTitle').textContent = title;
            grid.innerHTML = '';
            /* Show Create Collection button only in trip mode, dive controls in dive mode */
            document.getElementById('createCollBtn').style.display = (thumbPaneMode === 'trip') ? '' : 'none';
            document.getElementById('diveThumbControls').style.display = (thumbPaneMode === 'dive') ? '' : 'none';
            if (thumbPaneMode === 'dive') {{
                const allVid = files.length > 0 && files.every(f => isVideo(f.name));
                document.getElementById('diveConcatBtn').style.display = allVid ? '' : 'none';
            }}
            document.getElementById('collectionControls').style.display = 'none';
            document.getElementById('collViewControls').style.display = (thumbPaneMode === 'collection') ? '' : 'none';
            thumbLazyQueue = [];
            thumbLazyRunning = false;
            thumbTotalCount = files.length;
            thumbLoadedCount = 0;
            const thumbProg = document.getElementById('thumbProgress');
            const thumbProgBar = document.getElementById('thumbProgressBar');
            const thumbProgText = document.getElementById('thumbProgressText');
            if (files.length > 0) {{
                thumbProgBar.style.width = '0%';
                thumbProgText.textContent = '0 / ' + files.length;
                thumbProg.style.display = '';
            }} else {{
                thumbProg.style.display = 'none';
            }}
            const rawQueue = [];
            const videoThumbQueue = [];
            files.forEach((f, i) => {{
                const div = document.createElement('div');
                div.className = 'thumb-item' + (thumbSelected[i] ? ' selected' : ' deselected');
                div.id = 'ti' + i;
                /* Click image/placeholder area to open viewer */
                const mediaWrap = document.createElement('div');
                mediaWrap.style.cssText = 'cursor:pointer;position:relative';
                mediaWrap.onclick = function(e) {{
                    e.stopPropagation();
                    if (thumbPaneMode === 'dive') {{
                        picViewMode = 'dive';
                        viewDiveNum = thumbPaneDiveNum;
                    }} else if (thumbPaneMode === 'collection') {{
                        picViewMode = 'collection';
                        viewCollIdx = thumbPaneCollIdx;
                    }} else {{
                        picViewMode = 'trip';
                    }}
                    document.getElementById('thumbPane').dataset.origin = 'thumbpane';
                    document.getElementById('thumbPane').classList.add('hidden');
                    openPicViewer(tripIdx, i);
                }};
                const label = document.createElement('input');
                label.type = 'text';
                label.className = 'thumb-label';
                const capKey = tripIdx + '_' + f.name;
                label.value = picCaptions[capKey] || f.name;
                label.onclick = function(e) {{ e.stopPropagation(); }};
                label.oninput = function() {{ picCaptions[capKey] = label.value; }};
                label.onkeydown = function(e) {{ if (e.key === 'Enter') label.blur(); }};
                /* Keep checkbox */
                const keepDiv = document.createElement('div');
                keepDiv.className = 'thumb-keep';
                const keepCb = document.createElement('input');
                keepCb.type = 'checkbox';
                keepCb.checked = thumbSelected[i];
                keepCb.id = 'keepCb' + i;
                keepCb.onclick = function(e) {{ e.stopPropagation(); toggleThumb(i); keepCb.checked = thumbSelected[i]; }};
                const keepLbl = document.createElement('span');
                keepLbl.textContent = 'Keep';
                keepDiv.appendChild(keepCb);
                keepDiv.appendChild(keepLbl);
                if (isVideo(f.name)) {{
                    const ph = document.createElement('div');
                    ph.className = 'thumb-placeholder';
                    ph.textContent = 'Loading video...';
                    mediaWrap.appendChild(ph);
                    div.appendChild(mediaWrap);
                    div.appendChild(label);
                    div.appendChild(keepDiv);
                    videoThumbQueue.push({{ file: f, placeholder: ph, wrap: mediaWrap, div: div }});
                }} else if (isRaw(f.name)) {{
                    const ph = document.createElement('div');
                    ph.className = 'thumb-placeholder';
                    ph.textContent = 'RAW - queued...';
                    mediaWrap.appendChild(ph);
                    div.appendChild(mediaWrap);
                    div.appendChild(label);
                    div.appendChild(keepDiv);
                    rawQueue.push({{ el: div, placeholder: ph, file: f, wrap: mediaWrap }});
                }} else {{
                    /* JPG/PNG — lazy load one at a time */
                    const thumbImg = document.createElement('img');
                    thumbImg.dataset.filename = f.name;
                    const ph = document.createElement('div');
                    ph.className = 'thumb-placeholder';
                    ph.textContent = 'Loading...';
                    mediaWrap.appendChild(ph);
                    div.appendChild(mediaWrap);
                    div.appendChild(label);
                    div.appendChild(keepDiv);
                    thumbLazyQueue.push({{ img: thumbImg, file: f, placeholder: ph, wrap: mediaWrap }});
                }}
                grid.appendChild(div);
            }});
            document.getElementById('thumbPane').classList.remove('hidden');
            /* Start lazy loading JPGs one at a time */
            if (thumbLazyQueue.length > 0) {{
                thumbLazyRunning = true;
                function lazyLoad() {{
                    if (thumbLazyQueue.length === 0) {{ thumbLazyRunning = false; return; }}
                    const item = thumbLazyQueue.shift();
                    const reader = new FileReader();
                    reader.onload = function(ev) {{
                        item.img.src = ev.target.result;
                        item.img.onload = function() {{
                            correctImageForViewer(item.img);
                            item.wrap.replaceChild(item.img, item.placeholder);
                            thumbProgressTick();
                            setTimeout(lazyLoad, 10);
                        }};
                        item.img.onerror = function() {{ thumbProgressTick(); setTimeout(lazyLoad, 10); }};
                    }};
                    reader.onerror = function() {{ thumbProgressTick(); setTimeout(lazyLoad, 10); }};
                    reader.readAsDataURL(item.file);
                }}
                lazyLoad();
            }}
            /* Convert RAW files one at a time */
            if (rawQueue.length > 0) convertRawQueue(rawQueue);
            /* Extract video thumbnails one at a time */
            if (videoThumbQueue.length > 0) extractVideoThumbs(videoThumbQueue);
        }}

        async function convertRawQueue(queue) {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.convert_raw) {{
                queue.forEach(q => {{ q.placeholder.textContent = 'RAW'; thumbProgressTick(); }});
                return;
            }}
            for (let qi = 0; qi < queue.length; qi++) {{
                const q = queue[qi];
                q.placeholder.textContent = 'RAW - converting ' + (qi + 1) + '/' + queue.length + '...';
                try {{
                    let dataUri = rawCache[q.file.name];
                    if (!dataUri) {{
                        const buf = await q.file.arrayBuffer();
                        const bytes = new Uint8Array(buf);
                        let bin = '';
                        for (let j = 0; j < bytes.length; j += 8192)
                            bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                        dataUri = await api.convert_raw(btoa(bin));
                        if (dataUri && dataUri.startsWith('data:')) rawCache[q.file.name] = dataUri;
                        else dataUri = null;
                    }}
                    if (dataUri) {{
                        const thumbImg = document.createElement('img');
                        thumbImg.dataset.filename = q.file.name;
                        thumbImg.onload = function() {{ correctImageForViewer(thumbImg); }};
                        thumbImg.src = dataUri;
                        q.wrap.replaceChild(thumbImg, q.placeholder);
                    }} else {{
                        q.placeholder.textContent = 'RAW';
                    }}
                }} catch (e) {{
                    q.placeholder.textContent = 'RAW';
                }}
                thumbProgressTick();
            }}
        }}

        function extractVideoThumbs(queue) {{
            let idx = 0;
            function next() {{
                if (idx >= queue.length) return;
                const q = queue[idx++];
                q.placeholder.textContent = 'Loading video...';
                const url = URL.createObjectURL(q.file);
                const vid = document.createElement('video');
                vid.muted = true;
                vid.preload = 'auto';
                vid.onloadeddata = function() {{
                    /* Seek to 1 second or 10% of duration, whichever is less */
                    vid.currentTime = Math.min(1, vid.duration * 0.1);
                }};
                vid.onseeked = function() {{
                    try {{
                        const canvas = document.createElement('canvas');
                        canvas.width = vid.videoWidth;
                        canvas.height = vid.videoHeight;
                        canvas.getContext('2d').drawImage(vid, 0, 0);
                        const thumbImg = document.createElement('img');
                        thumbImg.src = canvas.toDataURL('image/jpeg', 0.7);
                        thumbImg.style.cssText = 'width:100%;height:150px;object-fit:cover;display:block';
                        q.wrap.replaceChild(thumbImg, q.placeholder);
                        /* Add play icon overlay */
                        const overlay = document.createElement('div');
                        overlay.className = 'thumb-video-overlay';
                        q.wrap.appendChild(overlay);
                    }} catch(e) {{
                        q.placeholder.textContent = '\\u25B6 Video';
                    }}
                    URL.revokeObjectURL(url);
                    vid.remove();
                    thumbProgressTick();
                    setTimeout(next, 10);
                }};
                vid.onerror = function() {{
                    q.placeholder.textContent = '\\u25B6 Video';
                    URL.revokeObjectURL(url);
                    vid.remove();
                    thumbProgressTick();
                    setTimeout(next, 10);
                }};
                vid.src = url;
            }}
            next();
        }}

        function toggleThumb(i) {{
            thumbSelected[i] = !thumbSelected[i];
            const el = document.getElementById('ti' + i);
            el.classList.toggle('selected', thumbSelected[i]);
            el.classList.toggle('deselected', !thumbSelected[i]);
            /* Sync keptStatus for trip and dive modes */
            if (thumbPaneMode === 'trip' && keptStatus[thumbTripIdx]) keptStatus[thumbTripIdx][i] = thumbSelected[i];
            if (thumbPaneMode === 'dive' && thumbPaneDiveNum) {{
                const dKey = 'dive_' + thumbPaneDiveNum;
                if (keptStatus[dKey]) keptStatus[dKey][i] = thumbSelected[i];
            }}
        }}
        function syncThumbCheckboxes() {{
            thumbSelected.forEach((v, i) => {{
                const cb = document.getElementById('keepCb' + i);
                if (cb) cb.checked = v;
            }});
        }}
        function thumbSelectAll() {{
            thumbSelected = thumbSelected.map(() => true);
            thumbSelected.forEach((_, i) => {{
                const el = document.getElementById('ti' + i);
                el.classList.add('selected');
                el.classList.remove('deselected');
            }});
            syncThumbCheckboxes();
        }}
        function thumbDeselectAll() {{
            thumbSelected = thumbSelected.map(() => false);
            thumbSelected.forEach((_, i) => {{
                const el = document.getElementById('ti' + i);
                el.classList.remove('selected');
                el.classList.add('deselected');
            }});
            syncThumbCheckboxes();
        }}
        function thumbRandom() {{
            const n = parseInt(document.getElementById('randomCount').value) || 25;
            const total = thumbSelected.length;
            thumbDeselectAll();
            const indices = Array.from({{ length: total }}, (_, i) => i);
            /* Fisher-Yates shuffle */
            for (let i = indices.length - 1; i > 0; i--) {{
                const j = Math.floor(Math.random() * (i + 1));
                [indices[i], indices[j]] = [indices[j], indices[i]];
            }}
            indices.slice(0, Math.min(n, total)).forEach(i => {{
                thumbSelected[i] = true;
                const el = document.getElementById('ti' + i);
                el.classList.add('selected');
                el.classList.remove('deselected');
            }});
            syncThumbCheckboxes();
        }}
        function thumbCancel() {{
            /* Close thumb pane with no changes */
            document.getElementById('thumbPane').classList.add('hidden');
        }}
        function startCollection() {{
            document.getElementById('createCollBtn').style.display = 'none';
            document.getElementById('collectionControls').style.display = '';
        }}
        function finishCollection(evt) {{
            const files = tripFiles[thumbTripIdx] || [];
            const selected = files.filter((_, i) => thumbSelected[i]);
            if (selected.length === 0) {{ alert('No pictures selected.'); return; }}
            /* Prompt for collection name */
            const name = prompt('Enter collection name:');
            if (!name || !name.trim()) return;
            const trimmed = name.trim();
            /* Ensure uniqueness within this trip */
            if (!tripCollections[thumbTripIdx]) tripCollections[thumbTripIdx] = [];
            const exists = tripCollections[thumbTripIdx].some(c => c.name.toLowerCase() === trimmed.toLowerCase());
            if (exists) {{
                alert('A collection named "' + trimmed + '" already exists for this trip.');
                return;
            }}
            /* Create the in-memory collection */
            tripCollections[thumbTripIdx].push({{ name: trimmed, files: selected.slice() }});
            /* Close thumb pane and refresh the trip card to show collection link */
            document.getElementById('thumbPane').classList.add('hidden');
            showThumb(thumbTripIdx);
        }}
        function closeThumbPane() {{
            document.getElementById('thumbPane').classList.add('hidden');
        }}

        function normLoc(s) {{
            return (s || '').toLowerCase().replace('curaçao','curacao').replace('curaco','curacao').trim();
        }}

        function renderTrips() {{
            document.getElementById('tripsPanel').innerHTML = tripsData.map((t, i) => `
                <div class="trip-card">
                    <div class="trip-header">
                        <div class="trip-dot" style="background:${{t.color}}"></div>
                        <strong>${{t.name}}</strong>
                        <span onclick="editTripLocation(${{i}})" style="cursor:pointer;margin-left:6px;font-size:0.75rem;color:#94a3b8" title="Rename location">&#9998;</span>
                        <span onclick="deleteTrip(${{i}})" style="cursor:pointer;margin-left:4px;font-size:0.75rem;color:#94a3b8" title="Delete trip">&#128465;</span>
                    </div>
                    <div style="color:#93c5fd;font-size:0.875rem">${{t.dates}}</div>
                    <div class="trip-stats">
                        <div><div class="trip-stat-value">${{t.dives}}</div><div class="trip-stat-label">Dives</div></div>
                        <div><div class="trip-stat-value">${{t.hours}}h</div><div class="trip-stat-label">Hours</div></div>
                        <div><div class="trip-stat-value">${{isMetric ? t.maxDepth + 'm' : Math.round(t.maxDepth * 3.28) + 'ft'}}</div><div class="trip-stat-label">Max Depth</div></div>
                        <div><div class="trip-stat-value">${{isPSI ? t.avgGas : psiToBar(t.avgGas)}}</div><div class="trip-stat-label">Avg ${{pressureUnit()}} Used</div></div>
                    </div>
                    <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
                        <button class="add-pics-btn" onclick="addPictures(${{i}})">📷 Add Pictures</button>
                        <button class="add-pics-btn" style="background:rgba(6,182,212,0.2);border-color:rgba(6,182,212,0.4);color:#22d3ee" onclick="openShareModal('trip',${{i}})">🌐 Share</button>
                    </div>
                    <div id="tripThumb${{i}}"></div>
                </div>
            `).join('');
            /* Re-render thumbnails for trips that already have pictures loaded */
            Object.keys(tripFiles).forEach(idx => showThumb(parseInt(idx)));
        }}

        let pendingTripDirFiles = [];
        function onTripDirPicked(files) {{
            pendingTripDirFiles = Array.from(files);
            const status = document.getElementById('tripDirStatus');
            const btn = document.getElementById('tripDirBtn');
            if (pendingTripDirFiles.length > 0) {{
                status.textContent = pendingTripDirFiles.length + ' files selected';
                status.style.color = '#4ade80';
                if (btn) btn.textContent = 'Folder Selected';
            }} else {{
                status.textContent = '';
                if (btn) btn.textContent = 'Select Folder...';
            }}
        }}
        function autoTripEndDate() {{
            const start = document.getElementById('tripStartDate').value;
            if (!start) return;
            const d = new Date(start + 'T00:00:00');
            d.setDate(d.getDate() + 7);
            const end = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
            document.getElementById('tripEndDate').value = end;
        }}
        function openTripModal() {{
            document.getElementById('tripName').value = '';
            document.getElementById('tripStartDate').value = '';
            document.getElementById('tripEndDate').value = '';
            document.getElementById('tripDirInput').value = '';
            document.getElementById('tripDirStatus').textContent = '';
            var dirBtn = document.getElementById('tripDirBtn');
            if (dirBtn) dirBtn.textContent = 'Select Folder...';
            pendingTripDirFiles = [];
            document.getElementById('tripModal').classList.remove('hidden');
        }}
        function closeTripModal() {{
            document.getElementById('tripModal').classList.add('hidden');
            pendingTripDirFiles = [];
        }}
        const tripColors = ['#3b82f6','#22c55e','#f97316','#a855f7','#ef4444','#eab308','#ec4899','#14b8a6','#f59e0b','#6366f1'];
        function addManualTrip() {{
            const name = document.getElementById('tripName').value.trim();
            if (!name) {{ alert('Trip name is required.'); return; }}
            const startStr = document.getElementById('tripStartDate').value;
            const endStr = document.getElementById('tripEndDate').value;
            let dates = '';
            if (startStr) {{
                const s = new Date(startStr + 'T00:00:00');
                const mo = s.toLocaleString('en', {{ month: 'short' }});
                const day = s.getDate();
                const yr = s.getFullYear();
                if (endStr && endStr !== startStr) {{
                    const e = new Date(endStr + 'T00:00:00');
                    const emo = e.toLocaleString('en', {{ month: 'short' }});
                    const eday = e.getDate();
                    const eyr = e.getFullYear();
                    dates = yr === eyr ? `${{mo}} ${{day}} - ${{emo}} ${{eday}}, ${{yr}}` : `${{mo}} ${{day}}, ${{yr}} - ${{emo}} ${{eday}}, ${{eyr}}`;
                }} else {{
                    dates = `${{mo}} ${{day}}, ${{yr}}`;
                }}
            }}
            const color = tripColors[tripsData.length % tripColors.length];
            const newIdx = tripsData.length;
            tripsData.push({{
                name: name,
                dates: dates,
                dives: 0,
                hours: 0,
                maxDepth: 0,
                avgGas: 0,
                color: color
            }});
            const savedFiles = pendingTripDirFiles;
            closeTripModal();
            renderTrips();
            /* If pictures were selected, run them through the ext modal import */
            if (savedFiles.length > 0) {{
                picTripIdx = newIdx;
                onDirSelected(savedFiles);
            }}
        }}

        function editTripLocation(idx) {{
            const trip = tripsData[idx];
            const newName = prompt('Enter new location name:', trip.name);
            if (!newName || newName.trim() === '' || newName.trim() === trip.name) return;
            const oldLoc = normLoc(trip.name);
            const trimmed = newName.trim();
            /* Update all dives that belong to this trip */
            dives.forEach(d => {{
                if (normLoc(d.location) === oldLoc) d.location = trimmed;
            }});
            trip.name = trimmed;
            /* Refresh location filter */
            const locSelect = document.getElementById('locationFilter');
            const locs = [...new Set(dives.map(d => d.location || 'Unknown').map(l => l === 'Curaco' ? 'Curacao' : l))];
            const cur = locSelect.value;
            locSelect.innerHTML = '<option value="All">All Locations</option>';
            locs.forEach(loc => {{
                const opt = document.createElement('option');
                opt.value = loc;
                opt.textContent = loc === 'Curacao' ? 'Cura\\u00e7ao' : loc;
                locSelect.appendChild(opt);
            }});
            locSelect.value = locs.includes(cur) ? cur : 'All';
            renderTrips();
            renderTable();
        }}

        function deleteTrip(idx) {{
            const trip = tripsData[idx];
            if (!trip) return;
            if (!confirm('Delete trip "' + trip.name + '"? This will remove the trip and its associated dives.')) return;
            const tripLoc = normLoc(trip.name);
            /* Remove pictures for this trip */
            if (tripFiles[idx]) {{
                tripFiles[idx].forEach(f => {{ if (rawCache[f.name]) delete rawCache[f.name]; }});
                delete tripFiles[idx];
                delete keptStatus[idx];
                delete tripPicData[idx];
                clearDivePhotosForTrip(idx);
            }}
            /* Remove dives belonging to this trip (mutate in-place since dives is const) */
            for (let i = dives.length - 1; i >= 0; i--) {{
                if (normLoc(dives[i].location) === tripLoc) dives.splice(i, 1);
            }}
            /* Remove the trip from tripsData */
            tripsData.splice(idx, 1);
            /* Reindex tripFiles/keptStatus/tripPicData for indices above the removed one */
            const newTripFiles = {{}};
            const newKeptStatus = {{}};
            const newTripPicData = {{}};
            Object.keys(tripFiles).forEach(k => {{
                const ki = parseInt(k);
                if (ki > idx) {{
                    newTripFiles[ki - 1] = tripFiles[ki];
                    if (keptStatus[ki]) newKeptStatus[ki - 1] = keptStatus[ki];
                    if (tripPicData[ki]) newTripPicData[ki - 1] = tripPicData[ki];
                }} else {{
                    newTripFiles[ki] = tripFiles[ki];
                    if (keptStatus[ki]) newKeptStatus[ki] = keptStatus[ki];
                    if (tripPicData[ki]) newTripPicData[ki] = tripPicData[ki];
                }}
            }});
            Object.keys(tripFiles).forEach(k => delete tripFiles[k]);
            Object.keys(keptStatus).forEach(k => delete keptStatus[k]);
            Object.keys(tripPicData).forEach(k => delete tripPicData[k]);
            Object.assign(tripFiles, newTripFiles);
            Object.assign(keptStatus, newKeptStatus);
            Object.assign(tripPicData, newTripPicData);
            /* Refresh location filter */
            const locSelect = document.getElementById('locationFilter');
            const locs = [...new Set(dives.map(d => d.location || 'Unknown').map(l => l === 'Curaco' ? 'Curacao' : l))];
            locSelect.innerHTML = '<option value="All">All Locations</option>';
            locs.forEach(loc => {{
                const opt = document.createElement('option');
                opt.value = loc;
                opt.textContent = loc === 'Curacao' ? 'Cura\\u00e7ao' : loc;
                locSelect.appendChild(opt);
            }});
            locSelect.value = 'All';
            currentLocation = 'All';
            selectedDive = null;
            document.getElementById('detailPanel').classList.add('hidden');
            renderStats();
            renderTrips();
            renderTable();
        }}

        const knownExts = [
            {{ ext: '.jpg',  label: '.jpg',  cat: 'Images', on: true }},
            {{ ext: '.jpeg', label: '.jpeg', cat: 'Images', on: true }},
            {{ ext: '.png',  label: '.png',  cat: 'Images', on: true }},
            {{ ext: '.gif',  label: '.gif',  cat: 'Images', on: true }},
            {{ ext: '.webp', label: '.webp', cat: 'Images', on: true }},
            {{ ext: '.bmp',  label: '.bmp',  cat: 'Images', on: true }},
            {{ ext: '.tif',  label: '.tif',  cat: 'Images', on: false }},
            {{ ext: '.tiff', label: '.tiff', cat: 'Images', on: false }},
            {{ ext: '.heic', label: '.heic', cat: 'Images', on: false }},
            {{ ext: '.heif', label: '.heif', cat: 'Images', on: false }},
            {{ ext: '.svg',  label: '.svg',  cat: 'Images', on: false }},
            {{ ext: '.cr2',  label: '.cr2',  cat: 'RAW',    on: false }},
            {{ ext: '.cr3',  label: '.cr3',  cat: 'RAW',    on: false }},
            {{ ext: '.nef',  label: '.nef',  cat: 'RAW',    on: false }},
            {{ ext: '.arw',  label: '.arw',  cat: 'RAW',    on: false }},
            {{ ext: '.orf',  label: '.orf',  cat: 'RAW',    on: false }},
            {{ ext: '.dng',  label: '.dng',  cat: 'RAW',    on: false }},
            {{ ext: '.mp4',  label: '.mp4',  cat: 'Video',  on: true }},
            {{ ext: '.mov',  label: '.mov',  cat: 'Video',  on: true }},
            {{ ext: '.mpeg', label: '.mpeg', cat: 'Video',  on: true }},
            {{ ext: '.mpg',  label: '.mpg',  cat: 'Video',  on: true }},
            {{ ext: '.avi',  label: '.avi',  cat: 'Video',  on: false }},
            {{ ext: '.mkv',  label: '.mkv',  cat: 'Video',  on: false }},
        ];
        let pendingDirFiles = [];   /* files from directory picker awaiting ext filter */

        /* Custom confirm modal */
        let confirmModalResolve = null;
        function showConfirmModal(title, text) {{
            return new Promise(function(resolve) {{
                confirmModalResolve = resolve;
                document.getElementById('confirmTitle').textContent = title;
                document.getElementById('confirmText').textContent = text;
                document.getElementById('confirmModal').classList.remove('hidden');
            }});
        }}
        function resolveConfirmModal(result) {{
            document.getElementById('confirmModal').classList.add('hidden');
            if (confirmModalResolve) {{ confirmModalResolve(result); confirmModalResolve = null; }}
        }}

        let rawCopyModalResolve = null;
        function showRawCopyModal() {{
            return new Promise(function(resolve) {{
                rawCopyModalResolve = resolve;
                document.getElementById('rawCopyModal').classList.remove('hidden');
            }});
        }}
        function resolveRawCopyModal(result) {{
            document.getElementById('rawCopyModal').classList.add('hidden');
            if (rawCopyModalResolve) {{ rawCopyModalResolve(result); rawCopyModalResolve = null; }}
        }}

        async function addPictures(idx) {{
            if (tripFiles[idx] && tripFiles[idx].length > 0) {{
                const ok = await showConfirmModal('Add Pictures', 'This trip already has a Trip Inventory with ' + tripFiles[idx].length + ' photos.\\n\\nAdding new pictures will replace the existing inventory.\\nExisting collections will be kept.\\n\\nContinue?');
                if (!ok) return;
            }}
            picTripIdx = idx;
            const inp = document.getElementById('dirInput');
            inp.value = '';
            inp.click();
        }}

        function onDirSelected(files) {{
            if (picTripIdx === null || files.length === 0) return;
            pendingDirFiles = Array.from(files);

            /* Scan directory for extensions that match known types */
            const foundExts = new Set();
            pendingDirFiles.forEach(f => {{
                const ext = fileExt(f.name);
                if (ext) foundExts.add(ext);
            }});
            const available = knownExts.filter(e => foundExts.has(e.ext));
            if (available.length === 0) return;

            /* Build checkbox list showing only found types, all checked */
            const list = document.getElementById('extList');
            let html = '';
            let lastCat = '';
            available.forEach(e => {{
                if (e.cat !== lastCat) {{
                    html += `<div style="font-size:0.7rem;color:#94a3b8;margin-top:${{lastCat?'10':'0'}}px;margin-bottom:4px;padding-left:4px">${{e.cat}}</div>`;
                    lastCat = e.cat;
                }}
                const count = pendingDirFiles.filter(f => fileExt(f.name) === e.ext).length;
                html += `<div class="ext-row" onclick="this.querySelector('input').click()">
                    <input type="checkbox" value="${{e.ext}}" checked onclick="event.stopPropagation()">
                    <label>${{e.label}} (${{count}})</label>
                </div>`;
            }});
            list.innerHTML = html;
            document.getElementById('extToggle').textContent = 'Deselect all';
            document.getElementById('extModal').classList.remove('hidden');
        }}

        function toggleAllExt() {{
            const boxes = document.querySelectorAll('#extList input[type=checkbox]');
            const allChecked = Array.from(boxes).every(cb => cb.checked);
            boxes.forEach(cb => cb.checked = !allChecked);
            document.getElementById('extToggle').textContent = allChecked ? 'Select all' : 'Deselect all';
        }}

        function closeExtModal() {{
            document.getElementById('extModal').classList.add('hidden');
            pendingDirFiles = [];
        }}

        async function importSelected() {{
            const chosen = new Set(
                Array.from(document.querySelectorAll('#extList input[type=checkbox]:checked'))
                    .map(cb => cb.value)
            );
            if (chosen.size === 0) {{ closeExtModal(); return; }}
            const filtered = pendingDirFiles
                .filter(f => chosen.has(fileExt(f.name)))
                .sort((a, b) => a.name.localeCompare(b.name));
            document.getElementById('extModal').classList.add('hidden');
            pendingDirFiles = [];
            if (filtered.length === 0) return;
            tripFiles[picTripIdx] = filtered;
            keptStatus[picTripIdx] = filtered.map(() => true);

            /* Resolve absolute paths from webkitRelativePath via Python */
            let baseDir = '';
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.resolve_folder) {{
                const firstRel = (filtered[0].webkitRelativePath || '').replace(/\\\\/g, '/');
                const topFolder = firstRel.split('/')[0];
                if (topFolder) {{
                    baseDir = await api.resolve_folder(topFolder);
                }}
            }}
            tripPicData[picTripIdx] = filtered.map(f => {{
                let fullPath = '';
                if (baseDir && f.webkitRelativePath) {{
                    /* webkitRelativePath is like 'Folder/sub/file.jpg', baseDir is 'C:\...\Folder' */
                    /* Strip the top folder from the relative path, combine with baseDir */
                    const rel = f.webkitRelativePath.replace(/\\\\/g, '/');
                    const parts = rel.split('/');
                    parts.shift();  /* remove top folder name (already in baseDir) */
                    fullPath = baseDir + '\\\\' + parts.join('\\\\');
                }}
                return {{ name: f.name, path: fullPath, lastModified: f.lastModified }};
            }});

            buildDivePhotoMap(picTripIdx);
            /* Auto-generate dives from photo timestamps for new trips (0 dives) */
            if (tripsData[picTripIdx] && tripsData[picTripIdx].dives === 0) {{
                generateDivesFromPhotos(picTripIdx);
            }} else {{
                renderTrips();
            }}
            picViewMode = 'trip';
            showThumbPane(picTripIdx);
        }}

        function generateDivesFromPhotos(tripIdx) {{
            const files = tripFiles[tripIdx] || [];
            if (files.length === 0) return;
            const trip = tripsData[tripIdx];
            const location = trip ? trip.name : '';

            /* Collect timestamps and sort ascending */
            const timed = files
                .map(f => ({{ ts: f.lastModified || 0, file: f }}))
                .filter(t => t.ts > 0)
                .sort((a, b) => a.ts - b.ts);
            if (timed.length === 0) return;

            /* Group into dives: 75-minute window from each group start */
            const WINDOW_MS = 75 * 60 * 1000;
            const groups = [];
            let groupStart = timed[0].ts;
            let group = [timed[0]];
            for (let i = 1; i < timed.length; i++) {{
                if (timed[i].ts <= groupStart + WINDOW_MS) {{
                    group.push(timed[i]);
                }} else {{
                    groups.push(group);
                    groupStart = timed[i].ts;
                    group = [timed[i]];
                }}
            }}
            groups.push(group);

            /* Find highest existing dive number */
            let maxNum = dives.reduce((m, d) => Math.max(m, d.number), 0);

            /* Create a dive entry for each group */
            groups.forEach(g => {{
                maxNum++;
                const startDate = new Date(g[0].ts);
                const endDate = new Date(g[g.length - 1].ts);
                const durationSec = Math.round((endDate - startDate) / 1000);
                const dateStr = startDate.getFullYear() + '-' +
                    String(startDate.getMonth() + 1).padStart(2, '0') + '-' +
                    String(startDate.getDate()).padStart(2, '0');
                const timeStr = String(startDate.getHours()).padStart(2, '0') + ':' +
                    String(startDate.getMinutes()).padStart(2, '0');
                const endTimeStr = String(endDate.getHours()).padStart(2, '0') + ':' +
                    String(endDate.getMinutes()).padStart(2, '0');
                dives.push({{
                    number: maxNum,
                    date: dateStr,
                    time: timeStr,
                    endTime: endTimeStr,
                    location: location,
                    site: '',
                    maxDepthM: 0,
                    maxDepthFt: 0,
                    durationMin: Math.round(durationSec / 60),
                    durationSec: durationSec,
                    startPSI: 0,
                    endPSI: 0,
                    gasUsed: 0,
                    o2Percent: 0,
                    avgTempC: 0,
                    avgDepthM: 0,
                    endGF99: 0,
                    photoOnly: true
                }});
            }});

            /* Update trip stats */
            trip.dives = groups.length;

            /* Add new location to filter if needed */
            const locSelect = document.getElementById('locationFilter');
            const existing = Array.from(locSelect.options).map(o => o.value);
            if (location && !existing.includes(location)) {{
                const opt = document.createElement('option');
                opt.value = location;
                opt.textContent = location;
                locSelect.appendChild(opt);
            }}

            /* Re-map photos to the new dives and re-render */
            buildDivePhotoMap(tripIdx);
            renderTable();
            renderTrips();
        }}

        function removePictures(idx) {{
            /* Clear all photos for this trip and its dive mappings */
            const files = tripFiles[idx];
            if (files) {{
                files.forEach(f => {{
                    if (rawCache[f.name]) delete rawCache[f.name];
                }});
            }}
            delete tripFiles[idx];
            delete keptStatus[idx];
            delete tripPicData[idx];
            delete tripCollections[idx];
            clearDivePhotosForTrip(idx);
            renderTrips();
            if (selectedDive) renderDetail();
        }}

        function buildDivePhotoMap(tripIdx) {{
            /* Clear previous mappings for this trip */
            clearDivePhotosForTrip(tripIdx);
            const files = tripFiles[tripIdx];
            if (!files || files.length === 0) return;
            const tripName = tripsData[tripIdx] ? tripsData[tripIdx].name : '';
            const tripLoc = normLoc(tripName);
            /* Find dives at this location */
            const tripDives = dives.filter(d => normLoc(d.location) === tripLoc);
            if (tripDives.length === 0) return;
            /* Buffer: 30 min before dive start, 30 min after dive end */
            const BUFFER_MS = 30 * 60 * 1000;
            files.forEach(f => {{
                const ts = f.lastModified;
                if (!ts) return;
                for (const d of tripDives) {{
                    if (!d.date || !d.time) continue;
                    const start = parseLocalMs(d.date, d.time);
                    if (isNaN(start)) continue;
                    const end = start + (d.durationSec || 0) * 1000;
                    if (ts >= start - BUFFER_MS && ts <= end + BUFFER_MS) {{
                        if (!divePhotos[d.number]) divePhotos[d.number] = [];
                        divePhotos[d.number].push(f);
                        return; /* assign to first matching dive */
                    }}
                }}
            }});
        }}

        function clearDivePhotosForTrip(tripIdx) {{
            const tripName = tripsData[tripIdx] ? tripsData[tripIdx].name : '';
            const tripLoc = normLoc(tripName);
            dives.forEach(d => {{
                if (normLoc(d.location) === tripLoc) delete divePhotos[d.number];
            }});
        }}

        async function showThumb(idx) {{
            const el = document.getElementById('tripThumb' + idx);
            if (!el) return;
            const files = tripFiles[idx];
            if (!files || files.length === 0) {{ el.innerHTML = ''; return; }}
            const info = `<div class="trip-pic-info"><span style="color:#94a3b8;margin-right:4px">Trip Inventory:</span><span onclick="showThumbPane(${{idx}})" style="cursor:pointer">${{files.length}} photo${{files.length > 1 ? 's' : ''}} \u2014 click to view</span> | <span onclick="event.stopPropagation();removePictures(${{idx}})" style="cursor:pointer;color:#f87171">remove all</span> | <span onclick="event.stopPropagation();createSlideshow(${{idx}})" style="cursor:pointer;color:#a78bfa">create slideshow</span></div>`;
            /* Build collection links */
            let collHtml = '';
            const colls = tripCollections[idx] || [];
            colls.forEach((c, ci) => {{
                const allVideo = c.files.length > 0 && c.files.every(f => isVideo(f.name));
                const mediaLabel = allVideo ? 'video' : 'photo';
                const lastAction = allVideo
                    ? `<span onclick="event.stopPropagation();concatenateCollectionVideos(${{idx}}, ${{ci}})" style="cursor:pointer;color:#a78bfa">concatenate videos</span>`
                    : `<span onclick="event.stopPropagation();createCollectionSlideshow(${{idx}}, ${{ci}})" style="cursor:pointer;color:#a78bfa">slideshow</span>`;
                collHtml += `<div class="trip-pic-info" style="margin-top:2px"><span style="color:#c4b5fd;margin-right:4px">\ud83d\udcc1</span><span onclick="openCollection(${{idx}}, ${{ci}})" style="cursor:pointer;color:#a78bfa">${{c.name}}</span> <span style="color:#94a3b8">(${{c.files.length}} ${{mediaLabel}}${{c.files.length !== 1 ? 's' : ''}} \u2014 click to view)</span> | <span onclick="event.stopPropagation();deleteCollection(${{idx}}, ${{ci}})" style="cursor:pointer;color:#f87171">delete</span> | <span onclick="event.stopPropagation();copyCollection(${{idx}}, ${{ci}})" style="cursor:pointer;color:#4ade80">copy</span> | ${{lastAction}}</div>`;
            }});
            /* Preserve existing thumbnail image if present */
            const existingThumb = el.querySelector('.trip-thumb');
            if (existingThumb) {{
                el.innerHTML = info + collHtml;
                el.insertBefore(existingThumb, el.firstChild);
                return;
            }}
            /* Find first displayable image (not RAW, not video) for thumbnail */
            const thumbIdx = files.findIndex(f => !isRaw(f.name) && !isVideo(f.name));
            if (thumbIdx >= 0) {{
                el.innerHTML = info + collHtml;
                const reader = new FileReader();
                reader.onload = function(e) {{
                    const img = document.createElement('img');
                    img.className = 'trip-thumb';
                    img.dataset.filename = files[thumbIdx].name;
                    img.src = e.target.result;
                    img.onload = function() {{ correctImageForViewer(img); }};
                    img.onclick = function() {{ showThumbPane(idx); }};
                    el.insertBefore(img, el.firstChild);
                }};
                reader.readAsDataURL(files[thumbIdx]);
            }} else {{
                /* All RAW — try to convert the first one for thumbnail */
                el.innerHTML = info + collHtml;
                const file = files[0];
                let uri = rawCache[file.name];
                if (!uri) {{
                    const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                    if (api && api.convert_raw) {{
                        try {{
                            const buf = await file.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            uri = await api.convert_raw(btoa(bin));
                            if (uri && uri.startsWith('data:')) rawCache[file.name] = uri;
                            else uri = null;
                        }} catch (e) {{ uri = null; }}
                    }}
                }}
                if (uri) {{
                    const img = document.createElement('img');
                    img.className = 'trip-thumb';
                    img.dataset.filename = file.name;
                    img.src = uri;
                    img.onload = function() {{ correctImageForViewer(img); }};
                    img.onclick = function() {{ showThumbPane(idx); }};
                    el.insertBefore(img, el.firstChild);
                }}
            }}
        }}

        function getViewFiles() {{
            if (picViewMode === 'dive') return divePhotos[viewDiveNum] || [];
            if (picViewMode === 'collection') {{
                const coll = tripCollections[picTripIdx] && tripCollections[picTripIdx][viewCollIdx];
                return coll ? coll.files : [];
            }}
            return tripFiles[picTripIdx] || [];
        }}

        async function openPicViewer(idx, i) {{
            let files;
            if (picViewMode === 'dive') {{
                files = divePhotos[viewDiveNum] || [];
            }} else if (picViewMode === 'collection') {{
                const coll = tripCollections[idx] && tripCollections[idx][viewCollIdx];
                files = coll ? coll.files : [];
                picTripIdx = idx;
            }} else {{
                files = tripFiles[idx];
                picTripIdx = idx;
            }}
            if (!files || i < 0 || i >= files.length) return;
            if (picUrl) {{ URL.revokeObjectURL(picUrl); picUrl = null; }}
            picIdx = i;
            const file = files[i];

            document.getElementById('picName').textContent = file.name;
            document.getElementById('picCounter').textContent = (i + 1) + ' / ' + files.length;
            document.getElementById('picViewer').classList.remove('hidden');
            /* Reset underwater correction state */
            uwApplied = false;
            uwOriginalSrc = '';
            const uwBtn = document.getElementById('uwCorrectBtn');
            uwBtn.textContent = '\ud83c\udf0a Underwater Correct';
            uwBtn.style.background = '#7c3aed';
            uwBtn.disabled = false;
            /* picThumbBtn removed — no action needed */

            /* Show estimated depth at photo time for dive mode */
            const depthWrap = document.getElementById('picDepthWrap');
            if (picViewMode === 'dive') {{
                const diveObj = dives.find(d => d.number === viewDiveNum);
                if (diveObj && diveObj.durationSec > 0 && file.lastModified) {{
                    const diveStart = parseLocalMs(diveObj.date, diveObj.time);
                    const offsetMin = Math.max(0, Math.min(diveObj.durationMin, (file.lastModified - diveStart) / 60000));
                    const profile = generateDepthProfile(diveObj);
                    const depthVal = interpolateDepth(profile, offsetMin);
                    if (depthVal > 0) {{
                        const depthM = isMetric ? depthVal : depthVal;
                        depthWrap.textContent = Math.round(depthVal * 10) / 10 + (isMetric ? 'm' : 'ft');
                    }} else {{
                        depthWrap.textContent = '';
                    }}
                }} else {{
                    depthWrap.textContent = '';
                }}
            }} else {{
                depthWrap.textContent = '';
            }}

            /* Keep checkbox: show in trip, dive, and collection modes.
               Always use thumbSelected as the source of truth when available,
               since it reflects the thumbnail pane's current state. */
            const keepWrap = document.getElementById('picKeepWrap');
            if (thumbSelected && i < thumbSelected.length) {{
                keepWrap.style.display = '';
                document.getElementById('picKeep').checked = thumbSelected[i];
            }} else if (picViewMode === 'dive') {{
                const dKey = 'dive_' + viewDiveNum;
                if (!keptStatus[dKey]) keptStatus[dKey] = (divePhotos[viewDiveNum] || []).map(() => true);
                keepWrap.style.display = '';
                document.getElementById('picKeep').checked = keptStatus[dKey][i];
            }} else if (keptStatus[picTripIdx]) {{
                keepWrap.style.display = '';
                document.getElementById('picKeep').checked = keptStatus[picTripIdx][i];
            }} else {{
                keepWrap.style.display = 'none';
            }}

            /* ORF message */
            const orfMsg = document.getElementById('picOrfMsg');
            if (fileExt(file.name) === '.orf') {{
                orfMsg.classList.remove('hidden');
            }} else {{
                orfMsg.classList.add('hidden');
            }}

            const imgEl = document.getElementById('picImg');
            const vidEl = document.getElementById('picVid');

            if (isVideo(file.name)) {{
                /* Show video, hide image */
                imgEl.style.display = 'none';
                imgEl.src = '';
                vidEl.style.display = 'block';
                picUrl = URL.createObjectURL(file);
                vidEl.src = picUrl;
                vidEl.play().catch(function(){{}});
            }} else if (isRaw(file.name)) {{
                /* Convert RAW via Python (pywebview in parent) */
                vidEl.style.display = 'none';
                vidEl.src = '';
                imgEl.style.display = '';
                imgEl.style.filter = '';
                imgEl.dataset.filename = file.name;
                imgEl.onload = function() {{ correctImageForViewer(imgEl); }};
                const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                if (!api || !api.convert_raw) {{
                    imgEl.src = '';
                    document.getElementById('picName').textContent = file.name + ' (RAW preview not available outside app)';
                    return;
                }}
                if (rawCache[file.name]) {{
                    imgEl.src = rawCache[file.name];
                    return;
                }}
                imgEl.src = '';
                document.getElementById('picName').textContent = file.name + ' — converting...';
                try {{
                    const buf = await file.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let bin = '';
                    for (let j = 0; j < bytes.length; j += 8192)
                        bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                    const b64 = btoa(bin);
                    let uri = await api.convert_raw(b64);
                    /* Retry once on failure */
                    if (!uri || !uri.startsWith('data:')) {{
                        uri = await api.convert_raw(b64);
                    }}
                    if (uri && uri.startsWith('data:')) {{
                        rawCache[file.name] = uri;
                        if (picIdx === i) {{
                            imgEl.src = uri;
                            document.getElementById('picName').textContent = file.name;
                        }}
                    }} else {{
                        document.getElementById('picName').textContent = file.name + ' (conversion failed)';
                    }}
                }} catch (e) {{
                    /* Retry once on error */
                    try {{
                        const buf2 = await file.arrayBuffer();
                        const bytes2 = new Uint8Array(buf2);
                        let bin2 = '';
                        for (let j = 0; j < bytes2.length; j += 8192)
                            bin2 += String.fromCharCode.apply(null, bytes2.subarray(j, j + 8192));
                        const uri2 = await api.convert_raw(btoa(bin2));
                        if (uri2 && uri2.startsWith('data:')) {{
                            rawCache[file.name] = uri2;
                            if (picIdx === i) {{
                                imgEl.src = uri2;
                                document.getElementById('picName').textContent = file.name;
                            }}
                        }} else {{
                            document.getElementById('picName').textContent = file.name + ' (conversion failed)';
                        }}
                    }} catch (e2) {{
                        document.getElementById('picName').textContent = file.name + ' (conversion error)';
                    }}
                }}
            }} else {{
                /* Regular image */
                vidEl.style.display = 'none';
                vidEl.src = '';
                imgEl.style.display = '';
                imgEl.style.filter = '';
                imgEl.dataset.filename = file.name;
                imgEl.onload = function() {{ correctImageForViewer(imgEl); }};
                picUrl = URL.createObjectURL(file);
                imgEl.src = picUrl;
            }}

            /* Show caption — load existing or default to filename */
            const capEl = document.getElementById('picCaption');
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + file.name;
            if (picCaptions[capKey]) {{
                capEl.value = picCaptions[capKey];
            }} else {{
                capEl.value = file.name;
            }}
            updateViewMarineIdBtn();
        }}

        function onCaptionChange() {{
            const capEl = document.getElementById('picCaption');
            const files = getViewFiles();
            if (!files[picIdx]) return;
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + files[picIdx].name;
            picCaptions[capKey] = capEl.value;
        }}

        function onKeepToggle() {{
            const checked = document.getElementById('picKeep').checked;
            if (picViewMode === 'dive') {{
                const dKey = 'dive_' + viewDiveNum;
                if (keptStatus[dKey]) keptStatus[dKey][picIdx] = checked;
            }} else if (keptStatus[picTripIdx]) {{
                keptStatus[picTripIdx][picIdx] = checked;
            }}
            /* Sync with thumbnail selector state */
            if (thumbSelected && picIdx < thumbSelected.length) {{
                thumbSelected[picIdx] = checked;
                /* Update thumbnail visual if visible */
                const el = document.getElementById('ti' + picIdx);
                if (el) {{
                    el.classList.toggle('selected', checked);
                    el.classList.toggle('deselected', !checked);
                }}
            }}
        }}

        function navPic(dir) {{
            const vid = document.getElementById('picVid');
            vid.pause(); vid.src = '';
            /* Save keep state (default keep when pressing next) */
            const checked = document.getElementById('picKeep').checked;
            if (picViewMode === 'dive') {{
                const dKey = 'dive_' + viewDiveNum;
                if (keptStatus[dKey]) keptStatus[dKey][picIdx] = checked;
            }} else if (keptStatus[picTripIdx]) {{
                keptStatus[picTripIdx][picIdx] = checked;
            }}
            /* Sync thumbnail visual */
            if (thumbSelected && picIdx < thumbSelected.length) {{
                thumbSelected[picIdx] = checked;
                const el = document.getElementById('ti' + picIdx);
                if (el) {{ el.classList.toggle('selected', checked); el.classList.toggle('deselected', !checked); }}
            }}
            const files = getViewFiles();
            if (!files || files.length === 0) return;
            let next = picIdx + dir;
            if (next < 0) next = files.length - 1;
            if (next >= files.length) next = 0;
            if (picViewMode === 'dive') {{
                picIdx = next;
                openPicViewer(0, next);
            }} else {{
                openPicViewer(picTripIdx, next);
            }}
        }}

        function closePicViewer() {{
            /* Save keep state for current picture */
            const checked = document.getElementById('picKeep').checked;
            if (picViewMode === 'dive') {{
                const dKey = 'dive_' + viewDiveNum;
                if (keptStatus[dKey]) {{
                    keptStatus[dKey][picIdx] = checked;
                    /* Filter out discarded dive photos */
                    const kept = keptStatus[dKey];
                    const photos = divePhotos[viewDiveNum];
                    if (photos && kept) {{
                        const discarded = new Set(photos.filter((_, idx) => !kept[idx]));
                        if (discarded.size > 0) {{
                            /* Remove from divePhotos */
                            divePhotos[viewDiveNum] = photos.filter((_, idx) => kept[idx]);
                            /* Also remove from tripFiles and tripPicData */
                            Object.keys(tripFiles).forEach(tIdx => {{
                                const before = tripFiles[tIdx].length;
                                const keepMask = tripFiles[tIdx].map(f => !discarded.has(f));
                                tripFiles[tIdx] = tripFiles[tIdx].filter((_, i) => keepMask[i]);
                                if (tripPicData[tIdx]) tripPicData[tIdx] = tripPicData[tIdx].filter((_, i) => keepMask[i]);
                                if (tripFiles[tIdx].length !== before) {{
                                    keptStatus[tIdx] = tripFiles[tIdx].map(() => true);
                                }}
                            }});
                            delete keptStatus[dKey];
                            renderTrips();
                            renderTable();
                            if (selectedDive) renderDetail();
                        }}
                    }}
                }}
            }} else if (keptStatus[picTripIdx]) {{
                keptStatus[picTripIdx][picIdx] = checked;
                /* Filter out discarded pictures */
                const kept = keptStatus[picTripIdx];
                const files = tripFiles[picTripIdx];
                if (files && kept) {{
                    const filtered = files.filter((_, idx) => kept[idx]);
                    if (filtered.length < files.length) {{
                        tripFiles[picTripIdx] = filtered;
                        if (tripPicData[picTripIdx]) tripPicData[picTripIdx] = tripPicData[picTripIdx].filter((_, idx) => kept[idx]);
                        keptStatus[picTripIdx] = filtered.map(() => true);
                        buildDivePhotoMap(picTripIdx);
                        renderTrips();
                        renderTable();
                        if (selectedDive) renderDetail();
                    }}
                }}
            }}
            document.getElementById('picViewer').classList.add('hidden');
            document.getElementById('picOrfMsg').classList.add('hidden');
            const vid = document.getElementById('picVid');
            vid.pause(); vid.src = ''; vid.style.display = 'none';
            document.getElementById('picImg').style.display = '';
            if (picUrl) {{ URL.revokeObjectURL(picUrl); picUrl = null; }}
        }}

        function picGoBack() {{
            /* Save keep state for current picture */
            const checked = document.getElementById('picKeep').checked;
            if (picViewMode === 'trip' && keptStatus[picTripIdx]) {{
                keptStatus[picTripIdx][picIdx] = checked;
                if (thumbSelected && picIdx < thumbSelected.length) thumbSelected[picIdx] = checked;
            }}
            /* Close viewer */
            document.getElementById('picViewer').classList.add('hidden');
            document.getElementById('picOrfMsg').classList.add('hidden');
            const vid = document.getElementById('picVid');
            vid.pause(); vid.src = ''; vid.style.display = 'none';
            document.getElementById('picImg').style.display = '';
            document.getElementById('picImg').style.filter = '';
            if (picUrl) {{ URL.revokeObjectURL(picUrl); picUrl = null; }}
            /* Return to thumbnail pane if we came from one */
            const thumbPane = document.getElementById('thumbPane');
            if (thumbPane.dataset.origin === 'thumbpane') {{
                thumbPane.classList.remove('hidden');
                syncThumbCheckboxes();
                thumbSelected.forEach((v, i) => {{
                    const el = document.getElementById('ti' + i);
                    if (el) {{
                        el.classList.toggle('selected', v);
                        el.classList.toggle('deselected', !v);
                    }}
                }});
                /* Sync caption labels from picCaptions */
                const viewFiles = getViewFiles();
                viewFiles.forEach((f, i) => {{
                    const el = document.getElementById('ti' + i);
                    if (el) {{
                        const lbl = el.querySelector('.thumb-label');
                        if (lbl) {{
                            const tripKey = (picViewMode === 'collection' || picViewMode === 'trip') ? picTripIdx : 'dive_' + viewDiveNum;
                            const capKey = tripKey + '_' + f.name;
                            lbl.value = picCaptions[capKey] || f.name;
                        }}
                    }}
                }});
                delete thumbPane.dataset.origin;
            }}
        }}

        let dashboardBg = '';
        let dashboardBgPath = '';
        function setAsBackground() {{
            const imgEl = document.getElementById('picImg');
            const vidEl = document.getElementById('picVid');
            if (vidEl.style.display !== 'none') {{ alert('Cannot use a video as background.'); return; }}
            if (!imgEl.src || !imgEl.naturalWidth) return;
            try {{
                const c = document.createElement('canvas');
                const maxW = 1920, maxH = 1080;
                let w = imgEl.naturalWidth, h = imgEl.naturalHeight;
                if (w > maxW || h > maxH) {{
                    const scale = Math.min(maxW / w, maxH / h);
                    w = Math.round(w * scale);
                    h = Math.round(h * scale);
                }}
                c.width = w; c.height = h;
                c.getContext('2d').drawImage(imgEl, 0, 0, w, h);
                dashboardBg = c.toDataURL('image/jpeg', 0.8);
                applyBackground();
                /* Save to background_images/ via Python */
                const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                if (api && api.save_background_image) {{
                    const fname = 'background_' + Date.now() + '.jpg';
                    api.save_background_image(dashboardBg, fname).then(function(p) {{
                        if (p) dashboardBgPath = p;
                    }});
                }}
            }} catch (e) {{
                alert('Could not set background: ' + e.message);
            }}
        }}
        function applyBackground() {{
            if (dashboardBg) {{
                document.body.style.background = 'none';
                document.body.style.backgroundImage = 'linear-gradient(rgba(15,25,35,0.75), rgba(15,25,35,0.75)), url(' + dashboardBg + ')';
                document.body.style.backgroundSize = 'cover';
                document.body.style.backgroundPosition = 'center';
                document.body.style.backgroundAttachment = 'fixed';
            }} else {{
                document.body.style.backgroundImage = '';
                document.body.style.backgroundSize = '';
                document.body.style.backgroundPosition = '';
                document.body.style.backgroundAttachment = '';
                document.body.style.background = 'linear-gradient(135deg, #1e3a5f 0%, #0c4a6e 50%, #164e63 100%)';
            }}
        }}
        function openSettings() {{
            document.getElementById('settingsOverlay').classList.add('visible');
            document.getElementById('settingsModal').classList.add('visible');
        }}
        function closeSettings() {{
            document.getElementById('settingsOverlay').classList.remove('visible');
            document.getElementById('settingsModal').classList.remove('visible');
        }}
        function toggleDropdown(id) {{
            var menu = document.getElementById(id);
            var isOpen = menu.classList.contains('open');
            closeDropdowns();
            if (!isOpen) menu.classList.add('open');
        }}
        function closeDropdowns() {{
            document.querySelectorAll('.dropdown-menu.open').forEach(function(m) {{ m.classList.remove('open'); }});
        }}
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.dropdown-wrap')) closeDropdowns();
        }});
        function chooseBackgroundFile() {{
            closeSettings();
            var api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.choose_image_file) {{ alert('File picker not available.'); return; }}
            api.choose_image_file().then(function(path) {{
                if (!path) return;
                var ext = path.split('.').pop().toLowerCase();
                if (ext !== 'png' && ext !== 'jpg' && ext !== 'jpeg') {{
                    alert('Please select a PNG or JPG image file.');
                    return;
                }}
                api.load_pic_file(path).then(function(b64) {{
                    if (!b64) {{ alert('Could not read file.'); return; }}
                    var mime = ext === 'png' ? 'image/png' : 'image/jpeg';
                    var dataUri = 'data:' + mime + ';base64,' + b64;
                    dashboardBg = dataUri;
                    dashboardBgPath = path;
                    applyBackground();
                    var fname = 'background_' + Date.now() + '.' + ext;
                    if (api.save_background_image) {{
                        api.save_background_image(dataUri, fname).then(function(p) {{
                            if (p) dashboardBgPath = p;
                        }});
                    }}
                }});
            }});
        }}
        function clearBackground() {{
            dashboardBg = '';
            dashboardBgPath = '';
            applyBackground();
            closeSettings();
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.clear_background_config) api.clear_background_config();
        }}
        function applyLoadedBackground(dataUri, bgPath) {{
            dashboardBg = dataUri;
            if (bgPath) dashboardBgPath = bgPath;
            applyBackground();
        }}

        function picViewerToThumbs() {{
            /* Close viewer and open thumbnail pane for current trip */
            if (picViewMode !== 'trip' || picTripIdx === null) return;
            document.getElementById('picViewer').classList.add('hidden');
            const vid = document.getElementById('picVid');
            vid.pause(); vid.src = ''; vid.style.display = 'none';
            document.getElementById('picImg').style.display = '';
            if (picUrl) {{ URL.revokeObjectURL(picUrl); picUrl = null; }}
            showThumbPane(picTripIdx);
        }}

        function openDivePics(diveNum) {{
            const photos = divePhotos[diveNum];
            if (!photos || photos.length === 0) return;
            /* Find the trip index that owns this dive's photos */
            let ownerTripIdx = 0;
            const dive = dives.find(d => d.number === diveNum);
            if (dive) {{
                const diveLoc = normLoc(dive.location);
                for (const tIdx of Object.keys(tripFiles)) {{
                    if (tripsData[parseInt(tIdx)] && normLoc(tripsData[parseInt(tIdx)].name) === diveLoc) {{
                        ownerTripIdx = parseInt(tIdx);
                        break;
                    }}
                }}
            }}
            showThumbPane(ownerTripIdx, 'dive', {{ diveNum: diveNum }});
        }}

        function openCollection(tripIdx, collIdx) {{
            showThumbPane(tripIdx, 'collection', {{ collIdx: collIdx }});
        }}

        function deleteCollection(tripIdx, collIdx) {{
            const colls = tripCollections[tripIdx];
            if (!colls || !colls[collIdx]) return;
            if (!confirm('Delete collection "' + colls[collIdx].name + '"?')) return;
            colls.splice(collIdx, 1);
            if (colls.length === 0) delete tripCollections[tripIdx];
            showThumb(tripIdx);
        }}

        async function copyFilesToDirectory(files, folderName, capKeyPrefix) {{
            if (files.length === 0) {{ alert('No files to copy.'); return; }}
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.choose_folder || !api.save_collection_file) {{
                alert('File export is only available in the app.');
                return;
            }}
            const parentDir = await api.choose_folder();
            if (!parentDir) return;
            const safeName = folderName.replace(/[^a-zA-Z0-9_\\-\\s]/g, '').trim();
            const folder = parentDir + '\\\\' + safeName;
            if (api.create_directory) await api.create_directory(folder);
            const hasRaw = files.some(f => isRaw(f.name));
            let convertRaws = false;
            if (hasRaw) {{
                const rawChoice = await showRawCopyModal();
                if (rawChoice === 'cancel') return;
                convertRaws = rawChoice === 'convert';
            }}
            const overlay = document.getElementById('progressOverlay');
            const pTitle = document.getElementById('progressTitle');
            const pText = document.getElementById('progressText');
            const pBar = document.getElementById('progressBar');
            const pClose = document.getElementById('progressCloseBtn');
            pTitle.textContent = 'Copying Files...';
            pText.textContent = '0 / ' + files.length;
            pBar.style.width = '0%';
            pClose.style.display = 'none';
            pClose.textContent = 'OK';
            overlay.classList.remove('hidden');
            let saved = 0;
            for (let si = 0; si < files.length; si++) {{
                const f = files[si];
                pText.textContent = (si + 1) + ' / ' + files.length + ' \u2014 ' + f.name;
                pBar.style.width = Math.round(((si + 1) / files.length) * 100) + '%';
                try {{
                    const capKey = capKeyPrefix + '_' + f.name;
                    const caption = picCaptions[capKey] || '';
                    const ext = f.name.substring(f.name.lastIndexOf('.'));
                    let newName = caption ? caption.replace(/\\s+/g, '_').replace(/[^a-zA-Z0-9_\\-]/g, '') + ext : f.name;
                    let b64;
                    const fext = fileExt(f.name);
                    if (fext === '.jpg' || fext === '.jpeg' || fext === '.png') {{
                        const uri = await fileToDataURI(f, 99999, 99999);
                        if (uri) {{
                            b64 = uri.split(',')[1];
                            if (fext === '.png') newName = newName.replace(/\\.png$/i, '.jpg');
                        }} else {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            b64 = btoa(bin);
                        }}
                    }} else if (isRaw(f.name) && convertRaws) {{
                        let dataUri = rawCache[f.name];
                        if (!dataUri) {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            dataUri = await api.convert_raw(btoa(bin));
                            if (dataUri && dataUri.startsWith('data:')) rawCache[f.name] = dataUri;
                        }}
                        if (dataUri && dataUri.startsWith('data:')) {{
                            b64 = dataUri.split(',')[1];
                            newName = newName.replace(/\\.[^.]+$/, '.jpg');
                        }} else {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            b64 = btoa(bin);
                        }}
                    }} else {{
                        const buf = await f.arrayBuffer();
                        const bytes = new Uint8Array(buf);
                        let bin = '';
                        for (let j = 0; j < bytes.length; j += 8192)
                            bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                        b64 = btoa(bin);
                    }}
                    const destPath = folder + '\\\\' + newName;
                    const result = await api.save_collection_file(b64, destPath);
                    if (result) saved++;
                }} catch (e) {{}}
            }}
            pTitle.textContent = 'Copy Completed';
            pText.textContent = 'Saved ' + saved + ' of ' + files.length + ' files to:\\n' + folder;
            pBar.style.width = '100%';
            pClose.style.display = '';
        }}

        async function copyCollection(tripIdx, collIdx) {{
            const colls = tripCollections[tripIdx];
            if (!colls || !colls[collIdx]) return;
            const coll = colls[collIdx];
            await copyFilesToDirectory(coll.files, coll.name, tripIdx);
        }}

        async function copyDivePhotos(diveNum) {{
            const photos = divePhotos[diveNum];
            if (!photos || photos.length === 0) return;
            const dive = dives.find(d => d.number === diveNum);
            const folderName = dive ? (dive.site || dive.location || 'Dive') + '_' + dive.date : 'Dive_' + diveNum;
            await copyFilesToDirectory(photos, folderName, 'dive_' + diveNum);
        }}

        /* ── Social Media Share ─────────────────────────────────────── */
        let shareDiveNum = null;
        let shareTripIdx = null;
        let shareMode = null;       /* 'card', 'caption', 'trip' */
        let shareContext = null;     /* 'dive' or 'trip' */
        let sharePhotoIdx = 0;

        function openShareModal(context, idx) {{
            shareContext = context;
            if (context === 'dive') {{
                shareDiveNum = idx;
                const dive = dives.find(d => d.number === idx);
                /* Find the trip index for this dive */
                if (dive) {{
                    const diveLoc = normLoc(dive.location);
                    shareTripIdx = tripsData.findIndex(t => normLoc(t.name) === diveLoc);
                }}
                const photos = divePhotos[idx];
                const hasPhotos = photos && photos.length > 0;
                /* Enable/disable photo-dependent options */
                document.getElementById('shareOptCard').classList.toggle('share-disabled', !hasPhotos);
                document.getElementById('shareOptCaption').classList.toggle('share-disabled', !hasPhotos);
                document.getElementById('shareOptTrip').classList.remove('share-disabled');
            }} else {{
                shareTripIdx = idx;
                shareDiveNum = null;
                document.getElementById('shareOptCard').classList.add('share-disabled');
                document.getElementById('shareOptCaption').classList.add('share-disabled');
                document.getElementById('shareOptTrip').classList.remove('share-disabled');
            }}
            document.getElementById('sharePhase1').style.display = '';
            document.getElementById('sharePhase2').style.display = 'none';
            document.getElementById('shareModal').classList.remove('hidden');
        }}

        function closeShareModal() {{
            document.getElementById('shareModal').classList.add('hidden');
            shareMode = null;
        }}

        function shareBack() {{
            document.getElementById('sharePhase1').style.display = '';
            document.getElementById('sharePhase2').style.display = 'none';
            shareMode = null;
        }}

        function shareSelectOption(mode) {{
            /* Don't allow disabled options */
            const optId = mode === 'card' ? 'shareOptCard' : mode === 'caption' ? 'shareOptCaption' : 'shareOptTrip';
            if (document.getElementById(optId).classList.contains('share-disabled')) return;
            shareMode = mode;
            sharePhotoIdx = mode === 'trip' ? -1 : 0;
            document.getElementById('sharePhase1').style.display = 'none';
            document.getElementById('sharePhase2').style.display = '';
            const titles = {{ card: '🤿 Dive Card Preview', caption: '📸 Photo + Caption Preview', trip: '🗺️ Trip Summary Preview' }};
            document.getElementById('sharePhase2Title').textContent = titles[mode] || 'Preview';
            buildSharePhotoStrip();
            renderShareCanvas();
        }}

        function getSharePhotoList() {{
            /* Return the list of File objects available for the current share context */
            if (shareMode === 'trip' || shareContext === 'trip') {{
                /* Gather trip inventory + collection files */
                const idx = shareTripIdx;
                const all = [];
                if (idx != null && tripFiles[idx]) {{
                    tripFiles[idx].forEach(f => all.push(f));
                }}
                if (idx != null && tripCollections[idx]) {{
                    tripCollections[idx].forEach(coll => {{
                        coll.files.forEach(f => {{
                            if (!all.some(a => a.name === f.name && a.lastModified === f.lastModified)) all.push(f);
                        }});
                    }});
                }}
                return all;
            }}
            return divePhotos[shareDiveNum] || [];
        }}

        function buildSharePhotoStrip() {{
            const strip = document.getElementById('sharePhotoStrip');
            const photos = getSharePhotoList();
            if (!photos || photos.length === 0) {{
                strip.style.display = 'none';
                return;
            }}
            /* For single-photo dive card/caption, hide strip */
            if (shareMode !== 'trip' && photos.length <= 1) {{
                strip.style.display = 'none';
                return;
            }}
            strip.style.display = '';
            strip.innerHTML = '';
            /* First option: no photo (gradient only) — only for trip mode */
            if (shareMode === 'trip') {{
                const noImg = document.createElement('div');
                noImg.style.cssText = 'width:48px;height:48px;border-radius:6px;cursor:pointer;border:2px solid ' + (sharePhotoIdx === -1 ? '#06b6d4' : 'transparent') + ';background:linear-gradient(135deg,#1e3a5f,#164e63);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;transition:border-color 0.2s';
                noImg.textContent = '∅';
                noImg.title = 'No background photo';
                noImg.onclick = function() {{
                    sharePhotoIdx = -1;
                    updateStripSelection(strip);
                    renderShareCanvas();
                }};
                strip.appendChild(noImg);
            }}
            photos.forEach((f, i) => {{
                const img = document.createElement('img');
                img.src = URL.createObjectURL(f);
                if (i === sharePhotoIdx) img.classList.add('active');
                img.onclick = function() {{
                    sharePhotoIdx = i;
                    updateStripSelection(strip);
                    renderShareCanvas();
                }};
                strip.appendChild(img);
            }});
        }}

        function updateStripSelection(strip) {{
            /* Update active state on strip children (first child may be the 'no photo' div) */
            let idx = 0;
            strip.querySelectorAll(':scope > *').forEach(el => {{
                if (el.tagName === 'IMG') {{
                    el.classList.toggle('active', idx === sharePhotoIdx);
                    idx++;
                }} else {{
                    /* The 'no photo' div */
                    el.style.borderColor = sharePhotoIdx === -1 ? '#06b6d4' : 'transparent';
                }}
            }});
        }}

        async function getSharePhoto() {{
            if (sharePhotoIdx === -1) return null;
            const photos = getSharePhotoList();
            if (!photos || photos.length === 0) return null;
            const f = photos[sharePhotoIdx] || photos[0];
            return new Promise(resolve => {{
                const img = new Image();
                img.onload = () => resolve(img);
                img.onerror = () => resolve(null);
                img.src = URL.createObjectURL(f);
            }});
        }}

        function getShareDive() {{
            return dives.find(d => d.number === shareDiveNum) || null;
        }}

        function getShareActualDepth() {{
            /* Return the actual depth at the selected photo's time, or max depth as fallback */
            const dive = getShareDive();
            if (!dive) return '';
            const photos = getSharePhotoList();
            const f = photos[sharePhotoIdx] || photos[0];
            if (f && f.lastModified && dive.durationSec > 0) {{
                const diveStart = parseLocalMs(dive.date, dive.time);
                const offsetMin = Math.max(0, Math.min(dive.durationMin, (f.lastModified - diveStart) / 60000));
                const profile = generateDepthProfile(dive);
                const depthVal = interpolateDepth(profile, offsetMin);
                if (depthVal > 0) return Math.round(depthVal * 10) / 10 + (isMetric ? 'm' : 'ft');
            }}
            return formatDepth(dive.maxDepthM, dive.maxDepthFt);
        }}

        function getShareTrip() {{
            if (shareTripIdx != null && shareTripIdx >= 0) return tripsData[shareTripIdx];
            return null;
        }}

        function getShareCaption() {{
            const photos = divePhotos[shareDiveNum];
            if (!photos || !photos[sharePhotoIdx]) return '';
            const f = photos[sharePhotoIdx];
            const tripKey = shareTripIdx + '_' + f.name;
            const diveKey = 'dive_' + shareDiveNum + '_' + f.name;
            return picCaptions[diveKey] || picCaptions[tripKey] || '';
        }}

        async function renderShareCanvas() {{
            const canvas = document.getElementById('sharePreviewCanvas');
            const ctx = canvas.getContext('2d');
            const hint = document.getElementById('shareHint');
            hint.textContent = '';

            if (shareMode === 'card') {{
                await renderShareCard(canvas, ctx, hint);
            }} else if (shareMode === 'caption') {{
                await renderShareCaption(canvas, ctx, hint);
            }} else if (shareMode === 'trip') {{
                await renderShareTrip(canvas, ctx, hint);
            }}
        }}

        async function renderShareCard(canvas, ctx, hint) {{
            const dive = getShareDive();
            if (!dive) return;
            const photo = await getSharePhoto();
            const W = 1080, H = 1080;
            canvas.width = W; canvas.height = H;

            if (photo) {{
                /* Draw photo covering canvas */
                const scale = Math.max(W / photo.width, H / photo.height);
                const sw = W / scale, sh = H / scale;
                const sx = (photo.width - sw) / 2, sy = (photo.height - sh) / 2;
                ctx.drawImage(photo, sx, sy, sw, sh, 0, 0, W, H);
            }} else {{
                /* Gradient background */
                const grad = ctx.createLinearGradient(0, 0, W, H);
                grad.addColorStop(0, '#1e3a5f');
                grad.addColorStop(1, '#164e63');
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, W, H);
            }}

            /* Dark overlay at bottom */
            const gradOverlay = ctx.createLinearGradient(0, H * 0.45, 0, H);
            gradOverlay.addColorStop(0, 'rgba(0,0,0,0)');
            gradOverlay.addColorStop(0.4, 'rgba(0,0,0,0.5)');
            gradOverlay.addColorStop(1, 'rgba(0,0,0,0.85)');
            ctx.fillStyle = gradOverlay;
            ctx.fillRect(0, 0, W, H);

            /* Top-left: Dive number badge */
            ctx.fillStyle = 'rgba(6,182,212,0.9)';
            roundRect(ctx, 30, 30, 200, 50, 12);
            ctx.fill();
            ctx.fillStyle = '#0f1923';
            ctx.font = 'bold 26px "Segoe UI", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Dive #' + dive.number, 130, 63);

            /* Bottom stats block */
            const statsY = H - 310;
            ctx.textAlign = 'left';

            /* Location + site */
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 38px "Segoe UI", sans-serif';
            const locText = (dive.location || 'Unknown') + (dive.site ? ' — ' + dive.site : '');
            ctx.fillText(locText, 40, statsY);

            /* Date */
            ctx.fillStyle = '#94a3b8';
            ctx.font = '24px "Segoe UI", sans-serif';
            ctx.fillText(dive.date + '  •  ' + (dive.time || ''), 40, statsY + 38);

            /* Stats grid */
            const gridY = statsY + 75;
            const photoDepth = getShareActualDepth();
            const maxDepth = formatDepth(dive.maxDepthM, dive.maxDepthFt);
            const stats = [
                {{ label: 'Max Depth', value: maxDepth }},
                {{ label: 'Photo Depth', value: photoDepth }},
                {{ label: 'Duration', value: dive.durationMin + ' min' }},
                {{ label: 'Water Temp', value: formatTemp(dive.avgTempC) }},
                {{ label: 'Gas', value: 'EAN' + dive.o2Percent }},
                {{ label: pressureUnit() + ' Used', value: formatPressure(dive.gasUsed) }},
                {{ label: 'GF99', value: dive.endGF99 + '%' }},
            ];
            const colW = (W - 80) / 3;
            stats.forEach((s, i) => {{
                const col = i % 3;
                const row = Math.floor(i / 3);
                const x = 40 + col * colW;
                const y = gridY + row * 68;
                ctx.fillStyle = '#06b6d4';
                ctx.font = 'bold 32px "Segoe UI", sans-serif';
                ctx.fillText(s.value, x, y);
                ctx.fillStyle = '#94a3b8';
                ctx.font = '18px "Segoe UI", sans-serif';
                ctx.fillText(s.label, x, y + 24);
            }});

            /* Branding */
            ctx.fillStyle = 'rgba(148,163,184,0.5)';
            ctx.font = '16px "Segoe UI", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Arrowcrab Dive Studio', W - 30, H - 20);

            hint.textContent = photo ? 'Dive stats overlaid on your photo' : 'Dive stats card (add photos for background)';
        }}

        async function renderShareCaption(canvas, ctx, hint) {{
            const dive = getShareDive();
            if (!dive) return;
            const photo = await getSharePhoto();
            if (!photo) return;

            const W = 1080;
            const barH = 120;
            /* Scale photo to fit width */
            const photoH = Math.round((photo.height / photo.width) * W);
            const H = photoH + barH;
            canvas.width = W; canvas.height = H;

            /* Draw photo */
            ctx.drawImage(photo, 0, 0, W, photoH);

            /* Caption bar */
            ctx.fillStyle = '#0f1923';
            ctx.fillRect(0, photoH, W, barH);

            const caption = getShareCaption();
            const displayText = caption || (dive.location || 'Unknown') + (dive.site ? ' — ' + dive.site : '') + '  •  ' + dive.date;

            ctx.fillStyle = '#e2e8f0';
            ctx.font = '28px "Segoe UI", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(displayText, W / 2, photoH + 45, W - 60);

            /* Sub-line with dive info */
            ctx.fillStyle = '#64748b';
            ctx.font = '20px "Segoe UI", sans-serif';
            ctx.fillText('Dive #' + dive.number + '  •  ' + getShareActualDepth() + ' (max ' + formatDepth(dive.maxDepthM, dive.maxDepthFt) + ')  •  ' + dive.durationMin + ' min', W / 2, photoH + 80, W - 60);

            /* Branding */
            ctx.fillStyle = 'rgba(148,163,184,0.4)';
            ctx.font = '14px "Segoe UI", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Arrowcrab Dive Studio', W - 20, photoH + barH - 10);

            hint.textContent = caption ? 'Photo with your caption' : 'Photo with dive info (add a caption for custom text)';
        }}

        async function renderShareTrip(canvas, ctx, hint) {{
            const trip = getShareTrip();
            const dive = getShareDive();
            if (!trip && !dive) return;
            const photo = await getSharePhoto();

            const W = 1080, H = photo ? 1080 : 560;
            canvas.width = W; canvas.height = H;

            if (photo) {{
                /* Draw photo covering canvas */
                const scale = Math.max(W / photo.width, H / photo.height);
                const sw = W / scale, sh = H / scale;
                const sx = (photo.width - sw) / 2, sy = (photo.height - sh) / 2;
                ctx.drawImage(photo, sx, sy, sw, sh, 0, 0, W, H);
                /* Dark overlay for readability */
                const gradOverlay = ctx.createLinearGradient(0, 0, 0, H);
                gradOverlay.addColorStop(0, 'rgba(0,0,0,0.55)');
                gradOverlay.addColorStop(0.5, 'rgba(0,0,0,0.35)');
                gradOverlay.addColorStop(1, 'rgba(0,0,0,0.7)');
                ctx.fillStyle = gradOverlay;
                ctx.fillRect(0, 0, W, H);
            }} else {{
                /* Gradient background */
                const grad = ctx.createLinearGradient(0, 0, W, H);
                grad.addColorStop(0, '#1e3a5f');
                grad.addColorStop(0.5, '#0c4a6e');
                grad.addColorStop(1, '#164e63');
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, W, H);
                /* Decorative circles */
                ctx.globalAlpha = 0.08;
                ctx.fillStyle = '#06b6d4';
                ctx.beginPath(); ctx.arc(W - 100, 100, 200, 0, Math.PI * 2); ctx.fill();
                ctx.beginPath(); ctx.arc(100, H - 80, 150, 0, Math.PI * 2); ctx.fill();
                ctx.globalAlpha = 1;
            }}

            const name = trip ? trip.name : (dive.location || 'Unknown');
            const color = trip ? trip.color : '#06b6d4';
            /* Offset content down when photo is present so image is visible */
            const topOff = photo ? H - 480 : 0;

            /* Color accent bar */
            ctx.fillStyle = color;
            ctx.fillRect(40, 40 + topOff, 6, 80);

            /* Trip name */
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 48px "Segoe UI", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(name, 60, 90 + topOff);

            /* Dates */
            ctx.fillStyle = photo ? '#cbd5e1' : '#94a3b8';
            ctx.font = '22px "Segoe UI", sans-serif';
            if (trip && trip.dates) ctx.fillText(trip.dates, 60, 125 + topOff);

            /* Stats boxes */
            const boxY = 170 + topOff;
            const boxH = 130;
            const boxPad = 16;
            const tripStats = [];
            if (trip) {{
                tripStats.push({{ label: 'Dives', value: String(trip.dives) }});
                tripStats.push({{ label: 'Hours', value: trip.hours.toFixed(1) }});
                tripStats.push({{ label: 'Max Depth', value: formatDepth(trip.maxDepth, Math.round(trip.maxDepth * 3.28)) }});
                tripStats.push({{ label: 'Avg Gas Used', value: formatPressure(trip.avgGas) + ' ' + pressureUnit() }});
            }} else {{
                tripStats.push({{ label: 'Max Depth', value: formatDepth(dive.maxDepthM, dive.maxDepthFt) }});
                tripStats.push({{ label: 'Duration', value: dive.durationMin + ' min' }});
                tripStats.push({{ label: 'Temp', value: formatTemp(dive.avgTempC) }});
                tripStats.push({{ label: 'Gas', value: 'EAN' + dive.o2Percent }});
            }}
            const boxW = (W - 80 - boxPad * (tripStats.length - 1)) / tripStats.length;
            tripStats.forEach((s, i) => {{
                const x = 40 + i * (boxW + boxPad);
                ctx.fillStyle = photo ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.07)';
                roundRect(ctx, x, boxY, boxW, boxH, 12);
                ctx.fill();
                ctx.fillStyle = color;
                ctx.font = 'bold 40px "Segoe UI", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(s.value, x + boxW / 2, boxY + 58);
                ctx.fillStyle = photo ? '#cbd5e1' : '#94a3b8';
                ctx.font = '18px "Segoe UI", sans-serif';
                ctx.fillText(s.label, x + boxW / 2, boxY + 90);
            }});

            /* Dive list (up to 6 dives) */
            if (trip) {{
                const tripLoc = normLoc(trip.name);
                const maxList = photo ? 4 : 6;
                const tripDives = dives.filter(d => normLoc(d.location) === tripLoc).slice(0, maxList);
                if (tripDives.length > 0) {{
                    const listY = boxY + boxH + 30;
                    ctx.fillStyle = photo ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.05)';
                    roundRect(ctx, 40, listY, W - 80, H - listY - 60, 12);
                    ctx.fill();
                    ctx.textAlign = 'left';
                    const lineH = 30;
                    tripDives.forEach((d, i) => {{
                        const y = listY + 28 + i * lineH;
                        ctx.fillStyle = photo ? '#a5b4c4' : '#94a3b8';
                        ctx.font = '18px "Segoe UI", sans-serif';
                        ctx.fillText('#' + d.number, 60, y);
                        ctx.fillStyle = '#e2e8f0';
                        ctx.fillText((d.site || d.date) + '  •  ' + formatDepth(d.maxDepthM, d.maxDepthFt) + '  •  ' + d.durationMin + 'min', 110, y);
                    }});
                    const totalTrip = dives.filter(d => normLoc(d.location) === tripLoc).length;
                    if (totalTrip > maxList) {{
                        ctx.fillStyle = '#64748b';
                        ctx.font = 'italic 16px "Segoe UI", sans-serif';
                        ctx.fillText('+ ' + (totalTrip - maxList) + ' more dives', 60, listY + 28 + maxList * lineH);
                    }}
                }}
            }}

            /* Branding */
            ctx.fillStyle = 'rgba(148,163,184,0.5)';
            ctx.font = '16px "Segoe UI", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Arrowcrab Dive Studio', W - 30, H - 20);

            hint.textContent = photo ? 'Trip summary with photo background — pick another from the strip above' : (trip ? 'Trip summary card — select a photo above for a background' : 'Location summary card');
        }}

        /* Rounded rectangle helper */
        function roundRect(ctx, x, y, w, h, r) {{
            ctx.beginPath();
            ctx.moveTo(x + r, y);
            ctx.lineTo(x + w - r, y);
            ctx.quadraticCurveTo(x + w, y, x + w, y + r);
            ctx.lineTo(x + w, y + h - r);
            ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
            ctx.lineTo(x + r, y + h);
            ctx.quadraticCurveTo(x, y + h, x, y + h - r);
            ctx.lineTo(x, y + r);
            ctx.quadraticCurveTo(x, y, x + r, y);
            ctx.closePath();
        }}

        async function shareSave() {{
            const canvas = document.getElementById('sharePreviewCanvas');
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            try {{
                const dataUrl = canvas.toDataURL('image/png');
                const b64 = dataUrl.split(',')[1];
                const dive = getShareDive();
                const trip = getShareTrip();
                const name = shareMode === 'trip'
                    ? (trip ? trip.name : 'trip') + '_summary'
                    : 'dive_' + (dive ? dive.number : '') + '_' + shareMode;
                const defaultName = name.replace(/[^a-zA-Z0-9_-]/g, '_') + '.png';
                if (api && api.save_share_image) {{
                    const path = await api.save_share_image(b64, defaultName);
                    if (path) {{
                        const bar = document.createElement('div');
                        bar.textContent = 'Saved to ' + path.split(/[\\\\/]/).pop();
                        bar.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);background:#059669;color:#fff;padding:8px 24px;border-radius:8px;font-size:0.9rem;font-weight:600;z-index:9999;transition:opacity 0.5s';
                        document.body.appendChild(bar);
                        setTimeout(() => {{ bar.style.opacity = '0'; }}, 2000);
                        setTimeout(() => {{ bar.remove(); }}, 2500);
                    }}
                }} else {{
                    /* Fallback: browser download */
                    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = defaultName;
                    document.body.appendChild(a); a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }}
            }} catch (e) {{
                alert('Save failed: ' + e.message);
            }}
        }}

        async function shareCopy() {{
            const canvas = document.getElementById('sharePreviewCanvas');
            try {{
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
                if (!blob) {{ alert('Could not generate image.'); return; }}
                await navigator.clipboard.write([new ClipboardItem({{ 'image/png': blob }})]);
                const bar = document.createElement('div');
                bar.textContent = 'Copied to clipboard';
                bar.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);background:#059669;color:#fff;padding:8px 24px;border-radius:8px;font-size:0.9rem;font-weight:600;z-index:9999;transition:opacity 0.5s';
                document.body.appendChild(bar);
                setTimeout(() => {{ bar.style.opacity = '0'; }}, 2000);
                setTimeout(() => {{ bar.remove(); }}, 2500);
            }} catch (e) {{
                alert('Copy failed: ' + e.message);
            }}
        }}

        function diveCopyFromThumb() {{
            if (thumbPaneMode !== 'dive' || !thumbPaneDiveNum) return;
            const allPhotos = divePhotos[thumbPaneDiveNum];
            if (!allPhotos || allPhotos.length === 0) return;
            const kept = allPhotos.filter((_, i) => thumbSelected[i]);
            if (kept.length === 0) {{ alert('No photos selected.'); return; }}
            const dive = dives.find(d => d.number === thumbPaneDiveNum);
            const folderName = dive ? (dive.site || dive.location || 'Dive') + '_' + dive.date : 'Dive_' + thumbPaneDiveNum;
            copyFilesToDirectory(kept, folderName, 'dive_' + thumbPaneDiveNum);
        }}

        async function concatenateCollectionVideos(tripIdx, collIdx) {{
            const colls = tripCollections[tripIdx];
            if (!colls || !colls[collIdx]) return;
            const coll = colls[collIdx];
            await concatenateVideoFiles(coll.files, coll.name);
        }}

        async function diveVideoConcatFromThumb() {{
            if (thumbPaneMode !== 'dive' || !thumbPaneDiveNum) return;
            const allVideos = divePhotos[thumbPaneDiveNum];
            if (!allVideos || allVideos.length === 0) return;
            const kept = allVideos.filter((_, i) => thumbSelected[i]);
            if (kept.length === 0) {{ alert('No videos selected.'); return; }}
            const dive = dives.find(d => d.number === thumbPaneDiveNum);
            const siteName = dive ? (dive.site || dive.location || 'Dive_' + thumbPaneDiveNum) : 'Dive_' + thumbPaneDiveNum;
            await concatenateVideoFiles(kept, siteName);
        }}

        async function concatenateVideoFiles(files, outputName) {{
            if (files.length === 0) return;
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.choose_folder || !api.save_video_blob || !api.concatenate_videos) {{
                alert('Video concatenation is only available in the app.');
                return;
            }}
            const parentDir = await api.choose_folder();
            if (!parentDir) return;
            /* Show progress */
            const overlay = document.getElementById('progressOverlay');
            const pTitle = document.getElementById('progressTitle');
            const pText = document.getElementById('progressText');
            const pBar = document.getElementById('progressBar');
            const pClose = document.getElementById('progressCloseBtn');
            pTitle.textContent = 'Preparing Videos...';
            pText.textContent = '0 / ' + files.length;
            pBar.style.width = '0%';
            pClose.style.display = 'none';
            pClose.textContent = 'OK';
            overlay.classList.remove('hidden');
            /* Save each video to temp files in the chosen directory */
            const tempPaths = [];
            for (let i = 0; i < files.length; i++) {{
                const f = files[i];
                pText.textContent = (i + 1) + ' / ' + files.length + ' \u2014 ' + f.name;
                pBar.style.width = Math.round(((i + 1) / files.length) * 100) + '%';
                try {{
                    const buf = await f.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let bin = '';
                    for (let j = 0; j < bytes.length; j += 8192)
                        bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                    const b64 = btoa(bin);
                    const tempPath = parentDir + '\\\\__temp_' + i + '_' + f.name;
                    const ok = await api.save_video_blob(b64, tempPath);
                    if (ok) tempPaths.push(tempPath);
                }} catch (e) {{}}
            }}
            if (tempPaths.length === 0) {{
                pTitle.textContent = 'No video files saved';
                pText.textContent = '';
                pClose.style.display = '';
                return;
            }}
            /* Concatenate with ffmpeg */
            pTitle.textContent = 'Concatenating Videos...';
            pText.textContent = 'Running ffmpeg...';
            pBar.style.width = '100%';
            const safeName = outputName.replace(/[^a-zA-Z0-9_\\-\\s]/g, '').trim();
            const ext = files[0].name.substring(files[0].name.lastIndexOf('.'));
            const outputPath = parentDir + '\\\\' + safeName + ext;
            const resultRaw = await api.concatenate_videos(tempPaths, outputPath);
            const result = JSON.parse(resultRaw);
            /* Clean up temp files */
            if (api.delete_file) {{
                for (const tp of tempPaths) {{
                    try {{ await api.delete_file(tp); }} catch (e) {{}}
                }}
            }}
            if (result.success) {{
                pTitle.textContent = 'Videos Concatenated';
                pText.textContent = 'Saved to:\\n' + result.path;
            }} else {{
                pTitle.textContent = 'Concatenation Failed';
                pText.textContent = result.error || 'Unknown error';
            }}
            pClose.style.display = '';
        }}

        function createCollectionSlideshow(tripIdx, collIdx) {{
            const colls = tripCollections[tripIdx];
            if (!colls || !colls[collIdx]) return;
            const coll = colls[collIdx];
            const trip = tripsData[tripIdx];
            const defaultTitle = coll.name + (trip ? ' \u2014 ' + trip.name : '');
            showSlideshowOpts(defaultTitle, function(opts) {{ doCreateCollectionSlideshow(tripIdx, collIdx, opts); }});
        }}
        async function doCreateCollectionSlideshow(tripIdx, collIdx, opts) {{
            const coll = tripCollections[tripIdx][collIdx];
            const files = coll.files;
            if (files.length === 0) return;
            const overlay = document.getElementById('progressOverlay');
            const pTitle = document.getElementById('progressTitle');
            const pText = document.getElementById('progressText');
            const pBar = document.getElementById('progressBar');
            const pClose = document.getElementById('progressCloseBtn');
            pTitle.textContent = 'Generating Slideshow...';
            pText.textContent = '0 / ' + files.length;
            pBar.style.width = '0%';
            pClose.style.display = 'none';
            pClose.textContent = 'OK';
            overlay.classList.remove('hidden');
            const images = [];
            for (let fi = 0; fi < files.length; fi++) {{
                const f = files[fi];
                pText.textContent = (fi + 1) + ' / ' + files.length + ' \u2014 ' + f.name;
                pBar.style.width = Math.round(((fi + 1) / files.length) * 100) + '%';
                let uri;
                if (isRaw(f.name) && rawCache[f.name]) {{
                    uri = rawCache[f.name];
                }} else if (isRaw(f.name)) {{
                    const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                    if (api && api.convert_raw) {{
                        try {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            uri = await api.convert_raw(btoa(bin));
                            if (uri && uri.startsWith('data:')) rawCache[f.name] = uri;
                            else uri = null;
                        }} catch (e) {{ uri = null; }}
                    }}
                }} else {{
                    uri = await fileToDataURI(f, 1920, 1080);
                }}
                if (uri) {{
                    const capKey = tripIdx + '_' + f.name;
                    images.push({{ name: picCaptions[capKey] || f.name, src: uri }});
                }}
            }}
            if (images.length === 0) {{
                pTitle.textContent = 'No images to include';
                pText.textContent = '';
                pClose.style.display = '';
                return;
            }}
            /* Prepend title card for MP4 */
            if (opts.format === 'mp4') {{
                const trip = tripsData[tripIdx] || null;
                const titleUri = generateSlideshowTitleCard('collection', {{ collection: coll, trip: trip }});
                images.unshift({{ name: '__title__', src: titleUri }});
                opts.titleDuration = 4;
            }}
            const defName = coll.name.replace(/\\s+/g, '_') + '_slideshow.html';
            if (opts.format === 'mp4') {{
                await saveMp4Slideshow(images, opts, defName, pTitle, pText, pBar, pClose);
                return;
            }}
            const html = buildSlideshowHtml(images, opts);
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.save_slideshow) {{
                const path = await api.save_slideshow(html, defName);
                if (path && api.launch_slideshow) await api.launch_slideshow(path);
                pTitle.textContent = path ? 'Slideshow Saved' : 'Slideshow not saved';
                pText.textContent = path || '';
            }} else {{
                const blob = new Blob([html], {{type: 'text/html'}});
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = coll.name.replace(/\\s/g, '_') + '_slideshow.html';
                a.click();
                pTitle.textContent = 'Slideshow Downloaded';
                pText.textContent = '';
            }}
            pBar.style.width = '100%';
            pClose.style.display = '';
        }}

        function diveSlideshowFromThumb() {{
            if (thumbPaneMode !== 'dive' || !thumbPaneDiveNum) return;
            const allPhotos = divePhotos[thumbPaneDiveNum];
            if (!allPhotos || allPhotos.length === 0) return;
            const kept = allPhotos.filter((_, i) => thumbSelected[i]);
            if (kept.length === 0) {{ alert('No photos selected.'); return; }}
            const dive = dives.find(d => d.number === thumbPaneDiveNum);
            if (!dive) return;
            const defaultTitle = 'Dive #' + thumbPaneDiveNum + ' \u2014 ' + (dive.location || 'Unknown') + (dive.site ? ' - ' + dive.site : '') + ' \u2014 ' + dive.date;
            const diveNum = thumbPaneDiveNum;
            showSlideshowOpts(defaultTitle, function(opts) {{ doCreateDiveSlideshow(diveNum, opts, kept); }});
        }}

        function createDiveSlideshow(diveNum) {{
            const photos = divePhotos[diveNum];
            if (!photos || photos.length === 0) return;
            const dive = dives.find(d => d.number === diveNum);
            if (!dive) return;
            const defaultTitle = 'Dive #' + diveNum + ' \u2014 ' + (dive.location || 'Unknown') + (dive.site ? ' - ' + dive.site : '') + ' \u2014 ' + dive.date;
            showSlideshowOpts(defaultTitle, function(opts) {{ doCreateDiveSlideshow(diveNum, opts); }});
        }}
        async function doCreateDiveSlideshow(diveNum, opts, customPhotos) {{
            const photos = customPhotos || divePhotos[diveNum];
            const dive = dives.find(d => d.number === diveNum);
            const overlay = document.getElementById('progressOverlay');
            const pTitle = document.getElementById('progressTitle');
            const pText = document.getElementById('progressText');
            const pBar = document.getElementById('progressBar');
            const pClose = document.getElementById('progressCloseBtn');
            pTitle.textContent = 'Generating Slideshow...';
            pText.textContent = '0 / ' + photos.length;
            pBar.style.width = '0%';
            pClose.style.display = 'none';
            pClose.textContent = 'OK';
            overlay.classList.remove('hidden');
            const images = [];
            for (let fi = 0; fi < photos.length; fi++) {{
                const f = photos[fi];
                pText.textContent = (fi + 1) + ' / ' + photos.length + ' \u2014 ' + f.name;
                pBar.style.width = Math.round(((fi + 1) / photos.length) * 100) + '%';
                let uri;
                if (isRaw(f.name) && rawCache[f.name]) {{
                    uri = rawCache[f.name];
                }} else if (isRaw(f.name)) {{
                    const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                    if (api && api.convert_raw) {{
                        try {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            uri = await api.convert_raw(btoa(bin));
                            if (uri && uri.startsWith('data:')) rawCache[f.name] = uri;
                            else uri = null;
                        }} catch (e) {{ uri = null; }}
                    }}
                }} else {{
                    uri = await fileToDataURI(f, 1920, 1080);
                }}
                if (uri) {{
                    const capKey = 'dive_' + diveNum + '_' + f.name;
                    images.push({{ name: picCaptions[capKey] || f.name, src: uri }});
                }}
            }}
            if (images.length === 0) {{
                pTitle.textContent = 'No images to include';
                pText.textContent = '';
                pClose.style.display = '';
                return;
            }}
            /* Prepend title card for MP4 */
            if (opts.format === 'mp4' && dive) {{
                const titleUri = generateSlideshowTitleCard('dive', {{ dive: dive }});
                images.unshift({{ name: '__title__', src: titleUri }});
                opts.titleDuration = 4;
            }}
            const siteName = (dive.site || dive.location || '').replace(/\\s+/g, '_');
            const defName = siteName + '_' + dive.date.replace(/[\\s\\/\\-]+/g, '_') + '.html';
            if (opts.format === 'mp4') {{
                await saveMp4Slideshow(images, opts, defName, pTitle, pText, pBar, pClose);
                return;
            }}
            const html = buildSlideshowHtml(images, opts);
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.save_slideshow) {{
                const path = await api.save_slideshow(html, defName);
                if (path && api.launch_slideshow) await api.launch_slideshow(path);
                pTitle.textContent = path ? 'Slideshow Saved' : 'Slideshow not saved';
                pText.textContent = path || '';
            }} else {{
                const blob = new Blob([html], {{type: 'text/html'}});
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = (dive.site || dive.location || '').replace(/\\s+/g, '_') + '_slideshow.html';
                a.click();
                pTitle.textContent = 'Slideshow Downloaded';
                pText.textContent = '';
            }}
            pBar.style.width = '100%';
            pClose.style.display = '';
        }}



        const uwCache = {{}};               /* filename -> underwater-corrected data-URI */
        let uwApplied = false;              /* whether UW correction is active on current image */
        let uwOriginalSrc = '';             /* original src to revert to */

        function correctImageForViewer(imgEl) {{
            imgEl.style.filter = '';
        }}

        async function applyUnderwaterCorrection() {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api) {{ alert('Underwater correction is only available in the app.'); return; }}
            const imgEl = document.getElementById('picImg');
            const vidEl = document.getElementById('picVid');
            if (vidEl.style.display !== 'none') return; /* skip videos */
            const btn = document.getElementById('uwCorrectBtn');
            const files = getViewFiles();
            const file = files && files[picIdx];
            if (!file) return;
            const fname = file.name;

            /* Toggle off — revert to original */
            if (uwApplied) {{
                imgEl.style.filter = '';
                if (uwOriginalSrc) imgEl.src = uwOriginalSrc;
                uwApplied = false;
                btn.textContent = '\ud83c\udf0a Underwater Correct';
                btn.style.background = '#7c3aed';
                correctImageForViewer(imgEl);
                return;
            }}

            /* Check cache first */
            if (uwCache[fname]) {{
                uwOriginalSrc = imgEl.src;
                imgEl.style.filter = '';
                imgEl.src = uwCache[fname];
                uwApplied = true;
                btn.textContent = '\u21a9 Revert';
                btn.style.background = '#059669';
                return;
            }}

            /* Apply correction */
            btn.textContent = '\ud83c\udf0a Correcting...';
            btn.disabled = true;
            try {{
                let corrected = '';
                if (isRaw(fname) && api.convert_raw_underwater) {{
                    /* RAW file: use dedicated underwater RAW processing */
                    const buf = await file.arrayBuffer();
                    const bytes = new Uint8Array(buf);
                    let bin = '';
                    for (let j = 0; j < bytes.length; j += 8192)
                        bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                    corrected = await api.convert_raw_underwater(btoa(bin));
                }} else if (api.correct_underwater) {{
                    /* Regular image: get current src as base64 */
                    let srcData = imgEl.src;
                    if (srcData.startsWith('blob:')) {{
                        /* Convert blob URL to base64 */
                        const resp = await fetch(srcData);
                        const blob = await resp.blob();
                        srcData = await new Promise(resolve => {{
                            const reader = new FileReader();
                            reader.onload = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        }});
                    }}
                    if (srcData.startsWith('data:')) {{
                        const b64 = srcData.split(',')[1];
                        corrected = await api.correct_underwater(b64);
                    }}
                }}
                if (corrected && corrected.startsWith('data:')) {{
                    uwCache[fname] = corrected;
                    uwOriginalSrc = imgEl.src;
                    imgEl.style.filter = '';
                    imgEl.src = corrected;
                    uwApplied = true;
                    btn.textContent = '\u21a9 Revert';
                    btn.style.background = '#059669';
                }} else {{
                    btn.textContent = '\ud83c\udf0a Underwater Correct';
                    alert('Correction failed. The image may not need correction.');
                }}
            }} catch (e) {{
                btn.textContent = '\ud83c\udf0a Underwater Correct';
            }}
            btn.disabled = false;
        }}

        /* ── Marine Life Identification ── */
        let marineIdPendingCallback = null;
        async function identifyMarineLife() {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api) {{ alert('Marine life identification is only available in the app.'); return; }}
            const imgEl = document.getElementById('picImg');
            const vidEl = document.getElementById('picVid');
            if (vidEl.style.display !== 'none') {{ alert('Cannot identify marine life in videos.'); return; }}
            if (!imgEl.src || !imgEl.naturalWidth) return;
            const btn = document.getElementById('marineIdBtn');
            /* Check for API key */
            if (api.get_has_api_key) {{
                const hasKey = await api.get_has_api_key();
                if (hasKey !== 'yes') {{
                    marineIdPendingCallback = function() {{ identifyMarineLife(); }};
                    document.getElementById('apiKeyInput').value = '';
                    document.getElementById('apiKeyModal').classList.remove('hidden');
                    return;
                }}
            }}
            btn.textContent = 'Identifying...';
            btn.disabled = true;
            try {{
                /* Resize image via canvas to max 1024px before sending to API */
                const MAX_DIM = 1024;
                let w = imgEl.naturalWidth, h = imgEl.naturalHeight;
                if (w > MAX_DIM || h > MAX_DIM) {{
                    const scale = MAX_DIM / Math.max(w, h);
                    w = Math.round(w * scale);
                    h = Math.round(h * scale);
                }}
                const resizeCanvas = document.createElement('canvas');
                resizeCanvas.width = w; resizeCanvas.height = h;
                resizeCanvas.getContext('2d').drawImage(imgEl, 0, 0, w, h);
                const srcData = resizeCanvas.toDataURL('image/jpeg', 0.85);
                const b64 = srcData.split(',')[1];
                const mediaType = 'image/jpeg';
                const result = await api.identify_marine_life(b64, mediaType);
                const res = JSON.parse(result);
                if (res.error) {{
                    document.getElementById('marineIdContent').textContent = 'Error: ' + res.error;
                }} else {{
                    document.getElementById('marineIdContent').textContent = res.result || 'No response.';
                }}
                document.getElementById('marineIdSaveBtn').style.display = '';
                document.getElementById('marineIdOverlayBtn').style.display = '';
                document.getElementById('marineIdModal').classList.remove('hidden');
            }} catch (e) {{
                document.getElementById('marineIdContent').textContent = 'Error: ' + (e.message || 'Unknown error');
                document.getElementById('marineIdSaveBtn').style.display = 'none';
                document.getElementById('marineIdOverlayBtn').style.display = 'none';
                document.getElementById('marineIdModal').classList.remove('hidden');
            }}
            btn.textContent = 'Identify Marine Life';
            btn.disabled = false;
        }}
        function closeMarineId() {{
            document.getElementById('marineIdModal').classList.add('hidden');
        }}
        function saveMarineId() {{
            const files = getViewFiles();
            if (!files[picIdx]) return;
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + files[picIdx].name;
            marineIds[capKey] = document.getElementById('marineIdContent').textContent;
            closeMarineId();
            updateViewMarineIdBtn();
        }}

        async function overlayMarineId() {{
            const text = document.getElementById('marineIdContent').textContent;
            if (!text) return;
            /* Also save the ID if not already saved */
            const files = getViewFiles();
            if (!files[picIdx]) return;
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + files[picIdx].name;
            if (!marineIds[capKey]) {{
                marineIds[capKey] = text;
                updateViewMarineIdBtn();
            }}
            /* Load the current photo */
            const f = files[picIdx];
            let imgSrc;
            if (isRaw(f.name) && rawCache[f.name]) {{
                imgSrc = rawCache[f.name];
            }} else {{
                imgSrc = URL.createObjectURL(f);
            }}
            const img = await new Promise(resolve => {{
                const im = new Image();
                im.onload = () => resolve(im);
                im.onerror = () => resolve(null);
                im.src = imgSrc;
            }});
            if (!img) {{ alert('Could not load image.'); return; }}

            /* Parse marine ID text into species entries, removing header lines like "# Marine Life Identification" */
            const lines = text.split('\\n').filter(l => {{
                const t = l.trim();
                if (!t) return false;
                if (/^#*\\s*Marine Life Identification/i.test(t)) return false;
                return true;
            }});

            /* Render overlay on canvas */
            const W = img.width, H = img.height;
            const canvas = document.createElement('canvas');
            canvas.width = W; canvas.height = H;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);

            /* Get context for site name + depth (dive) or trip location + date (trip/collection) */
            let diveSite = '';
            let diveDepth = '';
            let diveLocation = '';
            if (picViewMode === 'dive' && viewDiveNum) {{
                const d = dives.find(dd => dd.number === viewDiveNum);
                if (d) {{
                    diveSite = d.site || '';
                    diveLocation = d.location || '';
                    /* Use actual depth at photo time instead of max depth */
                    if (d.durationSec > 0 && f.lastModified) {{
                        const diveStart = parseLocalMs(d.date, d.time);
                        const offsetMin = Math.max(0, Math.min(d.durationMin, (f.lastModified - diveStart) / 60000));
                        const profile = generateDepthProfile(d);
                        const depthVal = interpolateDepth(profile, offsetMin);
                        if (depthVal > 0) {{
                            diveDepth = Math.round(depthVal * 10) / 10 + (isMetric ? 'm' : 'ft');
                        }} else {{
                            diveDepth = formatDepth(d.maxDepthM, d.maxDepthFt);
                        }}
                    }} else {{
                        diveDepth = formatDepth(d.maxDepthM, d.maxDepthFt);
                    }}
                }}
            }} else if ((picViewMode === 'trip' || picViewMode === 'collection') && tripsData[picTripIdx]) {{
                const trip = tripsData[picTripIdx];
                diveSite = trip.name || '';
                diveLocation = trip.dates || '';
            }}
            const hasSubLine = !!(diveSite || diveDepth);

            /* Calculate text area at bottom */
            const fontSize = Math.max(12, Math.round(W / 80));
            const lineH = fontSize * 1.4;
            const padding = Math.round(W / 40);
            const titleFontSize = Math.round(fontSize * 1.3);
            const subLineH = hasSubLine ? lineH : 0;
            const headerH = titleFontSize + subLineH + padding;
            const maxLines = Math.min(lines.length, Math.floor((H * 0.4) / lineH) - 2);
            const boxH = headerH + maxLines * lineH + padding;

            /* Semi-transparent background */
            const gradOverlay = ctx.createLinearGradient(0, H - boxH - 40, 0, H);
            gradOverlay.addColorStop(0, 'rgba(0,0,0,0)');
            gradOverlay.addColorStop(0.15, 'rgba(0,0,0,0.55)');
            gradOverlay.addColorStop(1, 'rgba(0,0,0,0.7)');
            ctx.fillStyle = gradOverlay;
            ctx.fillRect(0, H - boxH - 40, W, boxH + 40);

            /* Title */
            ctx.fillStyle = '#06b6d4';
            ctx.font = 'bold ' + titleFontSize + 'px "Segoe UI", sans-serif';
            ctx.textAlign = 'left';
            const titleY = H - boxH + titleFontSize;
            ctx.fillText('Marine Life Identification', padding, titleY);

            /* Site/location line under title */
            let contentY = titleY + padding * 0.5;
            if (hasSubLine) {{
                ctx.fillStyle = '#ffffff';
                ctx.font = Math.round(fontSize * 0.95) + 'px "Segoe UI", sans-serif';
                const subText = (diveLocation ? diveLocation + ' \u2014 ' : '') + (diveSite || '') + (diveDepth ? '  \u2022  ' + diveDepth : '');
                contentY = titleY + lineH;
                ctx.fillText(subText, padding, contentY);
                contentY += padding * 0.3;
            }}

            /* Text lines with word wrap */
            ctx.font = fontSize + 'px "Segoe UI", sans-serif';
            let y = contentY + lineH * 0.8;
            const maxWidth = W - padding * 2;
            for (let i = 0; i < lines.length && y < H - padding; i++) {{
                const line = lines[i].trim();
                ctx.fillStyle = '#ffffff';
                /* Bold for headers: lines starting with #, number, *, or - */
                if (/^[#\\d\\*\\-]/.test(line) || (/^[A-Z]/.test(line) && line.length < 60)) {{
                    ctx.font = 'bold ' + fontSize + 'px "Segoe UI", sans-serif';
                }} else {{
                    ctx.font = fontSize + 'px "Segoe UI", sans-serif';
                }}
                /* Simple word wrap */
                const words = line.split(' ');
                let currentLine = '';
                for (let w = 0; w < words.length; w++) {{
                    const testLine = currentLine ? currentLine + ' ' + words[w] : words[w];
                    if (ctx.measureText(testLine).width > maxWidth && currentLine) {{
                        ctx.fillText(currentLine, padding, y);
                        y += lineH;
                        currentLine = words[w];
                        if (y >= H - padding) break;
                    }} else {{
                        currentLine = testLine;
                    }}
                }}
                if (currentLine && y < H - padding) {{
                    ctx.fillText(currentLine, padding, y);
                    y += lineH;
                }}
            }}

            /* Branding */
            ctx.fillStyle = 'rgba(148,163,184,0.4)';
            ctx.font = Math.round(fontSize * 0.7) + 'px "Segoe UI", sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText('Arrowcrab Dive Studio', W - padding, H - 8);

            /* Save via API */
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
            const b64 = dataUrl.split(',')[1];
            const baseName = f.name.replace(/\\.[^.]+$/, '') + '_marine_id.jpg';
            if (api && api.save_share_image) {{
                const path = await api.save_share_image(b64, baseName);
                if (path) {{
                    const bar = document.createElement('div');
                    bar.textContent = 'Saved to ' + path.split(/[\\\\/]/).pop();
                    bar.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);background:#059669;color:#fff;padding:8px 24px;border-radius:8px;font-size:0.9rem;font-weight:600;z-index:9999;transition:opacity 0.5s';
                    document.body.appendChild(bar);
                    setTimeout(() => {{ bar.style.opacity = '0'; }}, 2000);
                    setTimeout(() => {{ bar.remove(); }}, 2500);
                }}
            }} else {{
                /* Fallback download */
                const a = document.createElement('a');
                a.href = dataUrl;
                a.download = baseName;
                document.body.appendChild(a); a.click(); document.body.removeChild(a);
            }}
            closeMarineId();
        }}
        function viewSavedMarineId() {{
            const files = getViewFiles();
            if (!files[picIdx]) return;
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + files[picIdx].name;
            const text = marineIds[capKey];
            if (!text) return;
            document.getElementById('marineIdContent').textContent = text;
            document.getElementById('marineIdSaveBtn').style.display = 'none';
            document.getElementById('marineIdOverlayBtn').style.display = '';
            document.getElementById('marineIdModal').classList.remove('hidden');
        }}
        function updateViewMarineIdBtn() {{
            const files = getViewFiles();
            const viewBtn = document.getElementById('viewMarineIdBtn');
            const idBtn = document.getElementById('marineIdBtn');
            if (!viewBtn) return;
            if (!files || !files[picIdx]) {{ viewBtn.style.display = 'none'; if (idBtn) idBtn.style.display = ''; return; }}
            const tripKey = (picViewMode === 'dive') ? 'dive_' + viewDiveNum : picTripIdx;
            const capKey = tripKey + '_' + files[picIdx].name;
            const hasSaved = !!marineIds[capKey];
            viewBtn.style.display = hasSaved ? '' : 'none';
            if (idBtn) idBtn.style.display = hasSaved ? 'none' : '';
        }}
        async function identifyCollectionMarineLife() {{
            /* Batch marine ID for entire collection */
            if (thumbPaneMode !== 'collection' || thumbPaneCollIdx == null) return;
            const coll = tripCollections[thumbTripIdx] && tripCollections[thumbTripIdx][thumbPaneCollIdx];
            if (!coll || !coll.files || coll.files.length === 0) return;
            const photos = coll.files.filter(f => !isVideo(f.name));
            if (photos.length === 0) {{ alert('No photos in this collection to identify.'); return; }}
            if (photos.length > 20) {{
                alert('Marine life identification requires 20 or fewer images. This collection has ' + photos.length + ' photos. Please reduce the collection size.');
                return;
            }}
            /* Check API key first */
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.identify_marine_life) {{
                alert('Marine life identification is only available in the app.');
                return;
            }}
            if (api.get_has_api_key) {{
                const hasKey = await api.get_has_api_key();
                if (hasKey !== 'yes') {{
                    marineIdPendingCallback = function() {{ identifyCollectionMarineLife(); }};
                    document.getElementById('apiKeyInput').value = '';
                    document.getElementById('apiKeyModal').classList.remove('hidden');
                    return;
                }}
            }}
            /* Close thumb pane and start background processing */
            document.getElementById('thumbPane').classList.add('hidden');
            const collName = coll.name;
            const tripIdx = thumbTripIdx;
            /* Show status indicator in header */
            const statusEl = document.getElementById('batchIdStatus');
            const statusText = document.getElementById('batchIdText');
            const statusProg = document.getElementById('batchIdProgress');
            statusText.textContent = 'Identifying "' + collName + '"';
            statusProg.textContent = '0 / ' + photos.length;
            statusEl.style.display = '';
            /* Process each photo sequentially in background */
            let identified = 0;
            let errors = 0;
            let processed = 0;
            for (let pi = 0; pi < photos.length; pi++) {{
                const f = photos[pi];
                const capKey = tripIdx + '_' + f.name;
                /* Skip already identified */
                if (marineIds[capKey]) {{
                    identified++;
                    processed++;
                    statusProg.textContent = processed + ' / ' + photos.length;
                    continue;
                }}
                try {{
                    /* Resize to max 1024px */
                    const MAX_DIM = 1024;
                    let imgSrc;
                    if (isRaw(f.name) && rawCache[f.name]) {{
                        imgSrc = rawCache[f.name];
                    }} else if (isRaw(f.name)) {{
                        const buf = await f.arrayBuffer();
                        const bytes = new Uint8Array(buf);
                        let bin = '';
                        for (let j = 0; j < bytes.length; j += 8192)
                            bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                        imgSrc = await api.convert_raw(btoa(bin));
                        if (imgSrc && imgSrc.startsWith('data:')) rawCache[f.name] = imgSrc;
                    }} else {{
                        imgSrc = await fileToDataURI(f, MAX_DIM, MAX_DIM);
                    }}
                    if (!imgSrc) {{ errors++; processed++; statusProg.textContent = processed + ' / ' + photos.length; continue; }}
                    /* Extract base64 */
                    const img = await new Promise(resolve => {{
                        const im = new Image();
                        im.onload = () => resolve(im);
                        im.onerror = () => resolve(null);
                        im.src = imgSrc;
                    }});
                    if (!img) {{ errors++; processed++; statusProg.textContent = processed + ' / ' + photos.length; continue; }}
                    let w = img.width, h = img.height;
                    if (w > MAX_DIM || h > MAX_DIM) {{
                        const scale = MAX_DIM / Math.max(w, h);
                        w = Math.round(w * scale);
                        h = Math.round(h * scale);
                    }}
                    const rc = document.createElement('canvas');
                    rc.width = w; rc.height = h;
                    rc.getContext('2d').drawImage(img, 0, 0, w, h);
                    const b64 = rc.toDataURL('image/jpeg', 0.85).split(',')[1];
                    const result = await api.identify_marine_life(b64, 'image/jpeg');
                    const res = JSON.parse(result);
                    if (res.error) {{
                        errors++;
                    }} else {{
                        marineIds[capKey] = res.result || '';
                        identified++;
                    }}
                }} catch (e) {{
                    errors++;
                }}
                processed++;
                statusProg.textContent = processed + ' / ' + photos.length;
            }}
            /* Show completion in header then fade out */
            statusText.textContent = 'ID complete: "' + collName + '"';
            statusProg.textContent = identified + ' of ' + photos.length + (errors > 0 ? ' (' + errors + ' errors)' : '');
            statusEl.style.borderColor = '#06b6d4';
            statusEl.style.background = 'rgba(6,182,212,0.15)';
            setTimeout(function() {{
                statusEl.style.transition = 'opacity 1s';
                statusEl.style.opacity = '0';
                setTimeout(function() {{
                    statusEl.style.display = 'none';
                    statusEl.style.opacity = '1';
                    statusEl.style.transition = '';
                    statusEl.style.borderColor = '#059669';
                    statusEl.style.background = 'rgba(5,150,105,0.15)';
                }}, 1000);
            }}, 6000);
            showToast('Marine ID complete for "' + collName + '": ' + identified + ' of ' + photos.length + ' identified' + (errors > 0 ? ' (' + errors + ' errors)' : ''), 8000);
        }}

        function closeApiKeyModal() {{
            document.getElementById('apiKeyModal').classList.add('hidden');
            marineIdPendingCallback = null;
        }}
        async function saveApiKey() {{
            const key = document.getElementById('apiKeyInput').value.trim();
            if (!key) {{ alert('Please enter an API key.'); return; }}
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.save_api_key) {{
                await api.save_api_key(key);
            }}
            document.getElementById('apiKeyModal').classList.add('hidden');
            if (marineIdPendingCallback) {{
                const cb = marineIdPendingCallback;
                marineIdPendingCallback = null;
                cb();
            }}
        }}

        /* ── Slideshow generation ── */
        function fileToDataURI(file, maxW, maxH) {{
            return new Promise((resolve) => {{
                if (isRaw(file.name) && rawCache[file.name]) {{
                    resolve(rawCache[file.name]);
                    return;
                }}
                const reader = new FileReader();
                reader.onload = () => {{
                    const img = new Image();
                    img.onload = () => {{
                        const scale = Math.min(1, maxW / img.width, maxH / img.height);
                        const w = Math.round(img.width * scale);
                        const h = Math.round(img.height * scale);
                        const c = document.createElement('canvas');
                        c.width = w; c.height = h;
                        const ctx = c.getContext('2d');
                        ctx.drawImage(img, 0, 0, w, h);
                        resolve(c.toDataURL('image/jpeg', 0.85));
                    }};
                    img.onerror = () => resolve(null);
                    img.src = reader.result;
                }};
                reader.onerror = () => resolve(null);
                reader.readAsDataURL(file);
            }});
        }}

        /* Slideshow options modal */
        let slideshowOptsCallback = null;
        let ssCustomSoundPath = '';
        async function ssPopulateSounds() {{
            const sel = document.getElementById('ssOptSound');
            /* Clear all except "None" */
            while (sel.options.length > 1) sel.remove(1);
            ssCustomSoundPath = '';
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.list_sound_files) {{
                const files = await api.list_sound_files();
                if (files && files.length > 0) {{
                    files.forEach(function(f) {{
                        const opt = document.createElement('option');
                        opt.value = f.path;
                        opt.textContent = f.name;
                        sel.appendChild(opt);
                    }});
                }}
            }}
        }}
        async function ssPickSoundFile() {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.pick_sound_file) return;
            const path = await api.pick_sound_file();
            if (!path) return;
            ssCustomSoundPath = path;
            const sel = document.getElementById('ssOptSound');
            /* Check if already in list */
            for (let i = 0; i < sel.options.length; i++) {{
                if (sel.options[i].value === path) {{ sel.selectedIndex = i; return; }}
            }}
            /* Add as new option */
            const opt = document.createElement('option');
            opt.value = path;
            const parts = path.replace(/\\\\/g, '/').split('/');
            opt.textContent = parts[parts.length - 1];
            sel.appendChild(opt);
            sel.value = path;
        }}
        function ssFormatChanged() {{
            const fmt = document.getElementById('ssOptFormat').value;
            document.getElementById('ssHtmlOnlyOpts').style.display = fmt === 'html' ? '' : 'none';
        }}
        function showSlideshowOpts(defaultTitle, callback) {{
            document.getElementById('ssOptFormat').value = 'html';
            document.getElementById('ssHtmlOnlyOpts').style.display = '';
            document.getElementById('ssOptTitle').value = defaultTitle;
            document.getElementById('ssOptInterval').value = '5';
            document.getElementById('ssOptControls').value = 'N';
            document.getElementById('ssOptCaption').value = 'Y';
            document.getElementById('ssOptSlideNum').value = 'N';
            document.getElementById('ssOptSound').value = '';
            slideshowOptsCallback = callback;
            ssPopulateSounds();
            document.getElementById('slideshowOptsModal').classList.remove('hidden');
        }}
        function cancelSlideshowOpts() {{
            document.getElementById('slideshowOptsModal').classList.add('hidden');
            slideshowOptsCallback = null;
        }}
        async function confirmSlideshowOpts() {{
            const format = document.getElementById('ssOptFormat').value;
            const title = document.getElementById('ssOptTitle').value.trim() || 'Slideshow';
            const interval = Math.max(1, parseInt(document.getElementById('ssOptInterval').value) || 5) * 1000;
            const showControls = document.getElementById('ssOptControls').value === 'Y';
            const showCaption = document.getElementById('ssOptCaption').value === 'Y';
            const showSlideNum = document.getElementById('ssOptSlideNum').value === 'Y';
            const soundPath = document.getElementById('ssOptSound').value;
            let soundDataUri = '';
            if (soundPath && format === 'html') {{
                const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                if (api && api.read_sound_base64) {{
                    soundDataUri = await api.read_sound_base64(soundPath);
                }}
            }}
            document.getElementById('slideshowOptsModal').classList.add('hidden');
            if (slideshowOptsCallback) slideshowOptsCallback({{ format: format, title: title, interval: interval, showControls: showControls, showCaption: showCaption, showSlideNum: showSlideNum, soundDataUri: soundDataUri, soundPath: soundPath }});
            slideshowOptsCallback = null;
        }}
        function generateSlideshowTitleCard(type, data) {{
            /* Render a 1920x1080 title card and return as data URI.
               type: 'dive', 'trip', or 'collection'
               data: {{ dive, trip, collection }} as applicable */
            const c = document.createElement('canvas');
            c.width = 1920; c.height = 1080;
            const ctx = c.getContext('2d');
            const W = 1920, H = 1080;

            /* Gradient background */
            const grad = ctx.createLinearGradient(0, 0, W, H);
            grad.addColorStop(0, '#0c2d48');
            grad.addColorStop(0.5, '#0c4a6e');
            grad.addColorStop(1, '#134e5e');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, W, H);

            /* Decorative elements */
            ctx.globalAlpha = 0.06;
            ctx.fillStyle = '#06b6d4';
            ctx.beginPath(); ctx.arc(W - 200, 200, 350, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(200, H - 150, 250, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(W / 2, H / 2, 400, 0, Math.PI * 2); ctx.fill();
            ctx.globalAlpha = 1;

            /* Accent line */
            const accentColor = (data.trip && data.trip.color) || '#06b6d4';
            ctx.fillStyle = accentColor;
            ctx.fillRect(W / 2 - 60, 180, 120, 4);

            if (type === 'dive' && data.dive) {{
                const d = data.dive;
                const rate = d.durationMin > 0 ? (d.gasUsed / d.durationMin).toFixed(1) : '0';

                /* Dive number badge */
                ctx.fillStyle = accentColor;
                roundRect(ctx, W / 2 - 120, 60, 240, 50, 25);
                ctx.fill();
                ctx.fillStyle = '#0f1923';
                ctx.font = 'bold 26px "Segoe UI", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Dive #' + d.number, W / 2, 93);

                /* Location */
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 58px "Segoe UI", sans-serif';
                ctx.fillText(d.location || 'Unknown', W / 2, 190);

                /* Site */
                if (d.site) {{
                    ctx.fillStyle = '#cbd5e1';
                    ctx.font = '34px "Segoe UI", sans-serif';
                    ctx.fillText(d.site, W / 2, 235);
                }}

                /* Date + time range + gas mix */
                ctx.fillStyle = '#64748b';
                ctx.font = '24px "Segoe UI", sans-serif';
                const timeRange = (d.time || '') + (d.endTime ? ' \u2013 ' + d.endTime : '');
                ctx.fillText(d.date + '  \u2022  ' + timeRange + '  \u2022  EAN' + d.o2Percent, W / 2, 280);

                /* Stats grid - 2 rows of 5 */
                const stats = [
                    {{ label: 'Max Depth', value: formatDepth(d.maxDepthM, d.maxDepthFt) }},
                    {{ label: 'Avg Depth', value: (isMetric ? d.avgDepthM + 'm' : Math.round(d.avgDepthM * 3.28) + 'ft') }},
                    {{ label: 'Duration', value: d.durationMin + ' min' }},
                    {{ label: 'Water Temp', value: formatTemp(d.avgTempC) }},
                    {{ label: 'End GF99', value: d.endGF99 + '%' }},
                    {{ label: 'Start ' + pressureUnit(), value: formatPressure(d.startPSI) }},
                    {{ label: 'End ' + pressureUnit(), value: formatPressure(d.endPSI) }},
                    {{ label: pressureUnit() + ' Used', value: formatPressure(d.gasUsed) }},
                    {{ label: pressureUnit() + '/min', value: isPSI ? rate : (rate * 0.0689).toFixed(1) }},
                    {{ label: 'Gas Mix', value: 'EAN' + d.o2Percent }},
                ];
                const cols = 5, gridW = 1700, cellW = gridW / cols;
                const gridX = (W - gridW) / 2;
                stats.forEach((s, i) => {{
                    const col = i % cols, row = Math.floor(i / cols);
                    const cx = gridX + col * cellW + cellW / 2;
                    const cy = 350 + row * 150;
                    ctx.fillStyle = 'rgba(255,255,255,0.06)';
                    roundRect(ctx, cx - cellW / 2 + 10, cy - 15, cellW - 20, 120, 12);
                    ctx.fill();
                    ctx.fillStyle = accentColor;
                    ctx.font = 'bold 46px "Segoe UI", sans-serif';
                    ctx.fillText(s.value, cx, cy + 42);
                    ctx.fillStyle = '#94a3b8';
                    ctx.font = '20px "Segoe UI", sans-serif';
                    ctx.fillText(s.label, cx, cy + 72);
                }});

                /* Dive photos count if available */
                const photos = divePhotos[d.number];
                const photoCount = photos ? photos.length : 0;
                if (photoCount > 0) {{
                    ctx.fillStyle = '#475569';
                    ctx.font = '22px "Segoe UI", sans-serif';
                    ctx.fillText(photoCount + ' photo' + (photoCount > 1 ? 's' : '') + ' in this dive', W / 2, 700);
                }}
            }} else if (type === 'trip' && data.trip) {{
                const t = data.trip;
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 64px "Segoe UI", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(t.name, W / 2, 200);
                ctx.fillStyle = '#94a3b8';
                ctx.font = '28px "Segoe UI", sans-serif';
                if (t.dates) ctx.fillText(t.dates, W / 2, 245);

                /* Photo count */
                const tripIdx = tripsData.indexOf(t);
                const tripPhotos = tripIdx >= 0 && tripFiles[tripIdx] ? tripFiles[tripIdx].length : 0;
                if (tripPhotos > 0) {{
                    ctx.fillStyle = '#475569';
                    ctx.font = '22px "Segoe UI", sans-serif';
                    ctx.fillText(tripPhotos + ' photos', W / 2, 280);
                }}

                const stats = [
                    {{ label: 'Dives', value: String(t.dives) }},
                    {{ label: 'Hours', value: t.hours.toFixed(1) }},
                    {{ label: 'Max Depth', value: formatDepth(t.maxDepth, Math.round(t.maxDepth * 3.28)) }},
                    {{ label: 'Avg ' + pressureUnit() + ' Used', value: formatPressure(t.avgGas) }},
                ];
                const gridW = 1400, cellW = gridW / stats.length;
                const gridX = (W - gridW) / 2;
                stats.forEach((s, i) => {{
                    const cx = gridX + i * cellW + cellW / 2;
                    ctx.fillStyle = 'rgba(255,255,255,0.06)';
                    roundRect(ctx, cx - cellW / 2 + 16, 320, cellW - 32, 140, 14);
                    ctx.fill();
                    ctx.fillStyle = accentColor;
                    ctx.font = 'bold 50px "Segoe UI", sans-serif';
                    ctx.fillText(s.value, cx, 400);
                    ctx.fillStyle = '#94a3b8';
                    ctx.font = '22px "Segoe UI", sans-serif';
                    ctx.fillText(s.label, cx, 435);
                }});

                /* Dive list with more detail */
                const tripLoc = normLoc(t.name);
                const tripDives = dives.filter(dd => normLoc(dd.location) === tripLoc).slice(0, 8);
                if (tripDives.length > 0) {{
                    const lineH = 36;
                    const listH = tripDives.length * lineH + 30;
                    ctx.fillStyle = 'rgba(255,255,255,0.04)';
                    roundRect(ctx, W / 2 - 650, 510, 1300, listH, 14);
                    ctx.fill();
                    ctx.textAlign = 'left';
                    tripDives.forEach((d, i) => {{
                        const y = 545 + i * lineH;
                        ctx.fillStyle = '#64748b';
                        ctx.font = '20px "Segoe UI", sans-serif';
                        ctx.fillText('#' + d.number, W / 2 - 620, y);
                        ctx.fillStyle = '#cbd5e1';
                        ctx.font = '20px "Segoe UI", sans-serif';
                        const siteText = d.site || d.date;
                        ctx.fillText(siteText, W / 2 - 560, y);
                        ctx.fillStyle = '#94a3b8';
                        const details = formatDepth(d.maxDepthM, d.maxDepthFt) + '  \u2022  ' + d.durationMin + 'min  \u2022  EAN' + d.o2Percent;
                        ctx.fillText(details, W / 2 + 100, y);
                    }});
                    const total = dives.filter(dd => normLoc(dd.location) === tripLoc).length;
                    if (total > 8) {{
                        ctx.fillStyle = '#475569';
                        ctx.font = 'italic 18px "Segoe UI", sans-serif';
                        ctx.fillText('+ ' + (total - 8) + ' more dives', W / 2 - 620, 545 + 8 * lineH);
                    }}
                    ctx.textAlign = 'center';
                }}
            }} else if (type === 'collection' && data.collection) {{
                const coll = data.collection;
                const t = data.trip;
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 64px "Segoe UI", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(coll.name, W / 2, 340);
                if (t) {{
                    ctx.fillStyle = '#94a3b8';
                    ctx.font = '32px "Segoe UI", sans-serif';
                    ctx.fillText(t.name + (t.dates ? '  •  ' + t.dates : ''), W / 2, 400);
                }}
                ctx.fillStyle = '#64748b';
                ctx.font = '28px "Segoe UI", sans-serif';
                ctx.fillText(coll.files.length + ' photos', W / 2, 460);
            }}

            /* Branding */
            ctx.fillStyle = 'rgba(148,163,184,0.3)';
            ctx.font = '20px "Segoe UI", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Arrowcrab Dive Studio', W / 2, H - 40);

            return c.toDataURL('image/jpeg', 0.92);
        }}

        function showToast(message, duration) {{
            duration = duration || 5000;
            let container = document.getElementById('toastContainer');
            if (!container) {{
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none';
                document.body.appendChild(container);
            }}
            const toast = document.createElement('div');
            toast.style.cssText = 'background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-left:4px solid #06b6d4;padding:12px 20px;border-radius:8px;font-size:0.9rem;box-shadow:0 4px 12px rgba(0,0,0,0.4);pointer-events:auto;opacity:0;transition:opacity 0.3s';
            toast.textContent = message;
            container.appendChild(toast);
            requestAnimationFrame(function() {{ toast.style.opacity = '1'; }});
            setTimeout(function() {{
                toast.style.opacity = '0';
                setTimeout(function() {{ toast.remove(); }}, 300);
            }}, duration);
        }}

        async function saveMp4Slideshow(images, opts, defName, pTitle, pText, pBar, pClose) {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.create_mp4_slideshow) {{
                pTitle.textContent = 'MP4 export not available';
                pText.textContent = 'Python API not found';
                pClose.style.display = '';
                return;
            }}
            pTitle.textContent = 'Creating MP4 Video...';
            pText.textContent = 'Preparing images...';
            const imagesData = images.map(im => ({{ name: im.name, src: im.src }}));
            const optsData = {{
                interval_ms: opts.interval,
                soundPath: opts.soundPath || '',
                title: opts.title || '',
                showCaption: opts.showCaption !== false,
                titleDuration: opts.titleDuration || 0
            }};
            const mp4DefName = defName.replace(/\\.html$/i, '') + '.mp4';
            const result = await api.create_mp4_slideshow(JSON.stringify(imagesData), JSON.stringify(optsData), mp4DefName);
            try {{
                const res = JSON.parse(result);
                if (res.error) {{
                    pTitle.textContent = 'MP4 Creation Failed';
                    pText.textContent = res.error;
                    pBar.style.width = '100%';
                    pBar.style.animation = 'none';
                    pClose.style.display = '';
                    return;
                }}
            }} catch(e) {{
                pTitle.textContent = 'MP4 Creation Failed';
                pText.textContent = 'Unexpected error';
                pBar.style.width = '100%';
                pBar.style.animation = 'none';
                pClose.style.display = '';
                return;
            }}
            /* ffmpeg is running in background — allow user to close dialog */
            pTitle.textContent = 'Encoding MP4 Video...';
            pText.textContent = 'Encoding in background. You can close this and continue working.';
            pBar.style.width = '100%';
            pBar.style.animation = 'mp4pulse 1.5s ease-in-out infinite';
            pClose.style.display = '';
            pClose.textContent = 'Continue';
            const overlay = document.getElementById('progressOverlay');
            /* Poll in background — updates dialog if still open, or shows toast when done */
            const poll = setInterval(async function() {{
                try {{
                    const raw = await api.get_mp4_status();
                    const st = JSON.parse(raw);
                    if (st.state === 'done') {{
                        clearInterval(poll);
                        if (!overlay.classList.contains('hidden')) {{
                            pTitle.textContent = 'MP4 Slideshow Saved';
                            pText.textContent = st.path || '';
                            pBar.style.animation = 'none';
                            pBar.style.width = '100%';
                            pClose.textContent = 'OK';
                        }} else {{
                            showToast('MP4 video saved: ' + (st.path || '').split(/[\\\\/]/).pop(), 6000);
                        }}
                    }} else if (st.state === 'error') {{
                        clearInterval(poll);
                        if (!overlay.classList.contains('hidden')) {{
                            pTitle.textContent = 'MP4 Creation Failed';
                            pText.textContent = st.error || '';
                            pBar.style.animation = 'none';
                            pBar.style.width = '100%';
                            pClose.textContent = 'OK';
                        }} else {{
                            showToast('MP4 creation failed: ' + (st.error || 'Unknown error'), 6000);
                        }}
                    }}
                }} catch(e) {{}}
            }}, 800);
        }}
        function buildSlideshowHtml(images, opts) {{
            const imgJson = JSON.stringify(images.map(im => im.src));
            const nameJson = JSON.stringify(images.map(im => im.name));
            const showCaption = opts.showCaption !== false;
            const showSlideNum = opts.showSlideNum === true;
            const ctrlsHtml = opts.showControls ?
                '<div class="ctrls"><button onclick="nav(-1)">\\u25C0 Prev</button><button id="playBtn" onclick="togglePlay()">\\u23F8 Pause</button><button onclick="nav(1)">Next \\u25B6</button></div>' : '';
            const ctrlsJs = opts.showControls ?
                'function togglePlay(){{playing=!playing;document.getElementById("playBtn").textContent=playing?"\\u23F8 Pause":"\\u25B6 Play";if(playing)startTimer();else clearInterval(timer);}}' : '';
            const keyJs = opts.showControls ?
                'document.addEventListener("keydown",function(e){{if(e.key==="ArrowRight")nav(1);else if(e.key==="ArrowLeft")nav(-1);else if(e.key===" ")togglePlay();}});' :
                'document.addEventListener("keydown",function(e){{if(e.key==="ArrowRight")nav(1);else if(e.key==="ArrowLeft")nav(-1);}});';
            /* Info bar: caption and/or slide number */
            let infoHtml = '';
            if (showCaption || showSlideNum) {{
                infoHtml = '<div class="info">';
                if (showCaption) infoHtml += '<span id="fname"></span>';
                if (showCaption && showSlideNum) infoHtml += ' \\u2014 ';
                if (showSlideNum) infoHtml += '<span id="counter"></span>';
                infoHtml += '</div>';
            }}
            /* Show JS: update visible elements */
            let showFnameJs = showCaption ? 'document.getElementById("fname").textContent=names[i];' : '';
            let showCounterJs = showSlideNum ? 'document.getElementById("counter").textContent=(i+1)+" / "+imgs.length;' : '';
            /* Audio element */
            const hasAudio = !!opts.soundDataUri;
            const audioHtml = hasAudio ? '<audio id="bgAudio" loop autoplay><source src="' + opts.soundDataUri + '"></audio>' : '';
            const audioJs = hasAudio ?
                'var aud=document.getElementById("bgAudio");aud.volume=0.5;aud.play().catch(function(){{}});' +
                'function tryAudio(){{aud.play().catch(function(){{}});document.removeEventListener("click",tryAudio);document.removeEventListener("keydown",tryAudio);}}' +
                'document.addEventListener("click",tryAudio);document.addEventListener("keydown",tryAudio);' : '';
            return '<!DOCTYPE html>' +
'<html><head><meta charset="UTF-8"><title>' + opts.title + ' Slideshow</title>' +
'<style>' +
'*{{margin:0;padding:0;box-sizing:border-box}}' +
'html,body{{height:100%;overflow:hidden;background:#000;font-family:sans-serif;color:#fff}}' +
'.slide{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity 0.8s}}' +
'.slide.active{{opacity:1}}' +
'.slide img{{max-width:95vw;max-height:90vh;object-fit:contain;border-radius:6px}}' +
'.info{{position:fixed;bottom:16px;left:0;right:0;text-align:center;font-size:0.85rem;color:#94a3b8;z-index:10}}' +
'.ctrls{{position:fixed;bottom:50px;left:0;right:0;display:flex;justify-content:center;gap:12px;z-index:10}}' +
'.ctrls button{{background:rgba(255,255,255,0.15);border:none;color:#fff;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:0.85rem}}' +
'.ctrls button:hover{{background:rgba(255,255,255,0.3)}}' +
'.title{{position:fixed;top:16px;left:0;right:0;text-align:center;font-size:1.3rem;font-weight:700;color:#06b6d4;z-index:10;text-shadow:0 2px 8px rgba(0,0,0,0.5)}}' +
'</style></head><body>' +
'<div class="title">' + opts.title + '</div>' +
'<div id="slides"></div>' +
infoHtml +
ctrlsHtml +
audioHtml +
'<scr' + 'ipt>' +
'var imgs=' + imgJson + ';' +
'var names=' + nameJson + ';' +
'var cur=0,timer=null,playing=true;' +
'var box=document.getElementById("slides");' +
'imgs.forEach(function(s,i){{var d=document.createElement("div");d.className="slide"+(i===0?" active":"");var im=document.createElement("img");im.src=s;d.appendChild(im);box.appendChild(d);}});' +
'function show(i){{document.querySelectorAll(".slide").forEach(function(s,j){{s.classList.toggle("active",j===i);}});' + showFnameJs + showCounterJs + '}}' +
'function nav(dir){{cur=(cur+dir+imgs.length)%imgs.length;show(cur);}}' +
ctrlsJs +
'function startTimer(){{clearInterval(timer);timer=setInterval(function(){{nav(1);}},' + opts.interval + ');}}' +
keyJs +
audioJs +
'show(0);startTimer();' +
'</scr' + 'ipt></body></html>';
        }}

        function createSlideshow(idx) {{
            const files = tripFiles[idx];
            if (!files || files.length === 0) return;
            const trip = tripsData[idx];
            const defaultTitle = trip.name + ' \u2014 ' + trip.dates;
            showSlideshowOpts(defaultTitle, function(opts) {{ doCreateSlideshow(idx, opts); }});
        }}
        async function doCreateSlideshow(idx, opts) {{
            const files = tripFiles[idx];
            const trip = tripsData[idx];
            const overlay = document.getElementById('progressOverlay');
            const pTitle = document.getElementById('progressTitle');
            const pText = document.getElementById('progressText');
            const pBar = document.getElementById('progressBar');
            const pClose = document.getElementById('progressCloseBtn');
            pTitle.textContent = 'Generating Slideshow...';
            pText.textContent = '0 / ' + files.length;
            pBar.style.width = '0%';
            pClose.style.display = 'none';
            pClose.textContent = 'OK';
            overlay.classList.remove('hidden');
            const images = [];
            for (let fi = 0; fi < files.length; fi++) {{
                const f = files[fi];
                pText.textContent = (fi + 1) + ' / ' + files.length + ' \u2014 ' + f.name;
                pBar.style.width = Math.round(((fi + 1) / files.length) * 100) + '%';
                let uri;
                if (isRaw(f.name) && rawCache[f.name]) {{
                    uri = rawCache[f.name];
                }} else if (isRaw(f.name)) {{
                    const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                    if (api && api.convert_raw) {{
                        try {{
                            const buf = await f.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let bin = '';
                            for (let j = 0; j < bytes.length; j += 8192)
                                bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 8192));
                            uri = await api.convert_raw(btoa(bin));
                            if (uri && uri.startsWith('data:')) rawCache[f.name] = uri;
                            else uri = null;
                        }} catch (e) {{ uri = null; }}
                    }}
                }} else {{
                    uri = await fileToDataURI(f, 1920, 1080);
                }}
                if (uri) {{
                    const capKey = idx + '_' + f.name;
                    images.push({{ name: picCaptions[capKey] || f.name, src: uri }});
                }}
            }}
            if (images.length === 0) {{
                pTitle.textContent = 'No images to include';
                pText.textContent = '';
                pClose.style.display = '';
                return;
            }}
            /* Prepend title card for MP4 */
            if (opts.format === 'mp4' && trip) {{
                const titleUri = generateSlideshowTitleCard('trip', {{ trip: trip }});
                images.unshift({{ name: '__title__', src: titleUri }});
                opts.titleDuration = 4;
            }}
            const dateMatch = trip.dates.match(/([A-Za-z]+)\\s+\\d+.*?(\\d{{4}})/);
            const defName = trip.name.replace(/\\s+/g, '_') + (dateMatch ? '_' + dateMatch[1] + '_' + dateMatch[2] : '') + '.html';
            if (opts.format === 'mp4') {{
                await saveMp4Slideshow(images, opts, defName, pTitle, pText, pBar, pClose);
                return;
            }}
            const html = buildSlideshowHtml(images, opts);
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (api && api.save_slideshow) {{
                const path = await api.save_slideshow(html, defName);
                if (path && api.launch_slideshow) await api.launch_slideshow(path);
                pTitle.textContent = path ? 'Slideshow Saved' : 'Slideshow not saved';
                pText.textContent = path || '';
            }} else {{
                const blob = new Blob([html], {{type: 'text/html'}});
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = trip.name.replace(/\\s/g, '_') + '_slideshow.html';
                a.click();
                pTitle.textContent = 'Slideshow Downloaded';
                pText.textContent = '';
            }}
            pBar.style.width = '100%';
            pClose.style.display = '';
        }}

        /* ── Photo dots on depth chart helpers ── */
        function getPhotoTimeOffsets(dive) {{
            /* Returns array of {{ min, file, index }} for photos during this dive */
            const photos = divePhotos[dive.number];
            if (!photos || photos.length === 0) return [];
            const start = parseLocalMs(dive.date, dive.time);
            if (isNaN(start)) return [];
            return photos.map((f, idx) => {{
                const offsetMin = (f.lastModified - start) / 60000;
                return {{ min: Math.max(0, Math.min(dive.durationMin, Math.round(offsetMin * 10) / 10)), file: f, index: idx }};
            }}).sort((a, b) => a.min - b.min);
        }}

        function interpolateDepth(depthData, timeMin) {{
            /* Find depth at a given time from the depth profile points */
            for (let i = 0; i < depthData.length - 1; i++) {{
                if (timeMin >= depthData[i].x && timeMin <= depthData[i + 1].x) {{
                    const t = (timeMin - depthData[i].x) / (depthData[i + 1].x - depthData[i].x);
                    return depthData[i].y + t * (depthData[i + 1].y - depthData[i].y);
                }}
            }}
            return depthData.length > 0 ? depthData[depthData.length - 1].y : 0;
        }}

        let chartPhotoPoints = [];  /* cached for click handler */

        /* ── Save / Load project ── */
        function hasProjectData() {{
            return dives.length > 0 || tripsData.length > 0 || Object.keys(tripFiles).length > 0;
        }}

        async function newProject() {{
            if (hasProjectData()) {{
                const save = confirm('Do you want to save the current project?\\n\\nOK = Save\\nCancel = Don\\'t save');
                if (save) {{
                    const saved = await saveProject();
                    if (!saved) return;
                }} else {{
                    const discard = confirm('Discard current project and start new?\\n\\nOK = Discard\\nCancel = Keep current project');
                    if (!discard) return;
                }}
            }}
            if (window.parent && window.parent.doNewProject) window.parent.doNewProject();
        }}

        async function saveProject() {{
            const api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
            if (!api || !api.save_project_json) {{ alert('Save is only available in the app.'); return false; }}
            try {{
                /* Build pictures manifest with file paths and captions */
                const pictures = {{}};
                for (const [idx, files] of Object.entries(tripFiles)) {{
                    const picData = tripPicData[idx] || [];
                    pictures[idx] = files.map((f, i) => {{
                        const entry = {{
                            name: f.name,
                            path: (picData[i] && picData[i].path) || '',
                            lastModified: f.lastModified
                        }};
                        const capKey = idx + '_' + f.name;
                        if (picCaptions[capKey]) entry.caption = picCaptions[capKey];
                        return entry;
                    }});
                }}
                /* Build collections manifest */
                const collections = {{}};
                for (const [idx, colls] of Object.entries(tripCollections)) {{
                    collections[idx] = colls.map(c => ({{
                        name: c.name,
                        fileNames: c.files.map(f => f.name)
                    }}));
                }}
                const proj = {{
                    dives: dives,
                    computerInfo: computerInfo,
                    trips: tripsData,
                    pictures: pictures,
                    captions: picCaptions,
                    marineIds: marineIds,
                    collections: collections
                }};
                if (dashboardBgPath) proj.backgroundPath = dashboardBgPath;
                if (dashboardBg) proj.background = dashboardBg;
                const projectJson = JSON.stringify(proj, null, 2);
                const result = await api.save_project_json(projectJson);
                if (result) {{
                    const bar = document.createElement('div');
                    bar.textContent = 'Project saved';
                    bar.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);background:#059669;color:#fff;padding:8px 24px;border-radius:8px;font-size:0.9rem;font-weight:600;z-index:9999;transition:opacity 0.5s';
                    document.body.appendChild(bar);
                    setTimeout(() => {{ bar.style.opacity = '0'; }}, 2000);
                    setTimeout(() => {{ bar.remove(); }}, 2500);
                }}
                return !!result;
            }} catch (e) {{
                alert('Save error: ' + e);
                return false;
            }}
        }}

        /* Called by parent frame when loading a project */
        function injectPic(tripIdx, name, lastModified, path, b64Data, caption) {{
            const binary = atob(b64Data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const file = new File([bytes], name, {{ lastModified: lastModified }});
            if (!tripFiles[tripIdx]) {{
                tripFiles[tripIdx] = [];
                keptStatus[tripIdx] = [];
                tripPicData[tripIdx] = [];
            }}
            tripFiles[tripIdx].push(file);
            keptStatus[tripIdx].push(true);
            tripPicData[tripIdx].push({{ name: name, path: path, lastModified: lastModified }});
            if (caption) picCaptions[tripIdx + '_' + name] = caption;
        }}

        function loadCaptions(captionsObj) {{
            if (!captionsObj) return;
            Object.keys(captionsObj).forEach(k => {{
                picCaptions[k] = captionsObj[k];
            }});
        }}

        function loadMarineIds(obj) {{
            if (!obj) return;
            Object.keys(obj).forEach(k => {{
                marineIds[k] = obj[k];
            }});
        }}

        function loadCollections(collectionsObj) {{
            if (!collectionsObj) return;
            Object.keys(collectionsObj).forEach(idx => {{
                const colls = collectionsObj[idx];
                if (!colls || !Array.isArray(colls)) return;
                const files = tripFiles[idx] || [];
                const fileMap = {{}};
                files.forEach(f => {{ fileMap[f.name] = f; }});
                tripCollections[idx] = colls.map(c => {{
                    const matched = (c.fileNames || []).map(n => fileMap[n]).filter(Boolean);
                    return {{ name: c.name, files: matched }};
                }}).filter(c => c.files.length > 0);
                if (tripCollections[idx].length === 0) delete tripCollections[idx];
            }});
        }}

        function showPicLoading(total) {{
            var bar = document.getElementById('picLoadingBar');
            bar.classList.add('visible');
            document.getElementById('plbText').textContent = 'Loading pictures... 0 / ' + total + ' \u2014 please be patient, this may take a moment';
            document.getElementById('plbFill').style.width = '0%';
        }}
        function updatePicLoading(current, total) {{
            document.getElementById('plbText').textContent = 'Loading pictures... ' + current + ' / ' + total + ' \u2014 please be patient, this may take a moment';
            document.getElementById('plbFill').style.width = Math.round((current / total) * 100) + '%';
        }}
        function hidePicLoading() {{
            document.getElementById('picLoadingBar').classList.remove('visible');
        }}

        function finishPicInjection() {{
            hidePicLoading();
            Object.keys(tripFiles).forEach(idx => {{
                buildDivePhotoMap(parseInt(idx));
            }});
            renderTrips();
            renderTable();
        }}

        /* Keyboard navigation for picture viewer */
        document.addEventListener('keydown', e => {{
            if (document.getElementById('picViewer').classList.contains('hidden')) return;
            if (e.key === 'ArrowRight') navPic(1);
            else if (e.key === 'ArrowLeft') navPic(-1);
            else if (e.key === 'Escape') closePicViewer();
        }});

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
        renderTrips();
        renderTable();

        /* Auto-load saved default background from parent pywebview API */
        (function() {{
            var attempts = 0;
            function tryLoadBg() {{
                if (dashboardBg) return;
                if (attempts++ > 50) return;
                var api = window.parent && window.parent.pywebview && window.parent.pywebview.api;
                if (api && api.get_default_background) {{
                    api.get_default_background().then(function(uri) {{
                        if (uri && !dashboardBg) applyLoadedBackground(uri);
                    }});
                }} else {{
                    setTimeout(tryLoadBg, 100);
                }}
            }}
            setTimeout(tryLoadBg, 150);
        }})();
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
        
        print(f"\nDashboard created: {output_path}")
        print("\nDouble-click the HTML file to open it in your browser!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
