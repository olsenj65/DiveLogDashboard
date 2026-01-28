# 🤿 Shearwater Dive Log Dashboard

Generate beautiful, interactive HTML dashboards from your Shearwater dive computer data.

![Dashboard Preview](screenshots/dashboard-preview.png)

## Features

- **📋 Interactive Dive Table** - Sort by any column, click to view dive details
- **📊 Charts & Visualizations** - Depth profiles, duration trends, temperature, location breakdown
- **⛽ Gas Analysis** - Consumption rates, tank pressure tracking, depth vs gas usage
- **🗺️ Trip Summaries** - Statistics by location/trip
- **📉 Individual Dive Profiles** - Estimated depth and tank pressure curves for each dive
- **🌡️ Unit Toggle** - Switch between Metric/Imperial and PSI/bar
- **🔌 Offline Ready** - Generated HTML works without internet

## Quick Start

### Prerequisites

- Python 3.6 or higher (no additional packages needed)
- Shearwater Cloud database export (`.db` file)

### Installation

```bash
# Clone the repository
git clone https://github.com/olsenj65/DiveLogDashboard.git
cd DiveLogDashboard

# That's it! No pip install required.
```

### Usage

1. **Export your dive log from Shearwater Cloud:**
   - Open Shearwater Cloud desktop app
   - Go to **Settings** → **Export** → **Export Database**
   - Save the `.db` file

2. **Generate your dashboard:**
   ```bash
   python generate_dive_dashboard.py "path/to/Shearwater_Cloud__your_email__date.db"
   ```

3. **Open the dashboard:**
   - Double-click `dive_dashboard.html` in the current directory
   - Opens in your default browser - no internet connection needed!

### Example

```bash
$ python generate_dive_dashboard.py "Shearwater_Cloud__diver@email.com__2026-01-22.db"

Reading Shearwater database: Shearwater_Cloud__diver@email.com__2026-01-22.db
Found 58 dives
Computer serial: 3334300737
Found 3 trips/locations

✓ Dashboard created: dive_dashboard.html

Double-click the HTML file to open it in your browser!
```

## Dashboard Tabs

### 📋 Dive Table
Full sortable table with all dive data:
- Dive number, date, location, site
- Max depth, duration
- Gas mix (O₂%)
- Start/end tank pressure, gas used, consumption rate
- End GF99 (tissue loading)

**Click any row** to see detailed dive information with estimated depth and pressure profiles.

### 📊 Charts
- Depth profile across all dives
- Duration trends
- Water temperature
- Dives by location (pie chart)

### ⛽ Gas Analysis
- Gas consumption per dive
- Consumption rate trends (PSI/min or bar/min)
- Start vs end pressure comparison
- Depth vs gas consumption scatter plot
- Average gas usage by location
- End pressure distribution histogram

### 🗺️ Trips
Summary cards for each dive trip showing:
- Number of dives
- Total hours underwater
- Maximum depth achieved
- Average gas consumption

## Data Extracted

The dashboard extracts and displays:

| Field | Description |
|-------|-------------|
| Dive Number | Sequential dive number |
| Date/Time | When the dive occurred |
| Location | Dive location (e.g., Bonaire, Cozumel) |
| Site | Specific dive site name |
| Max Depth | Maximum depth reached |
| Avg Depth | Average depth during dive |
| Duration | Total dive time |
| Water Temp | Average water temperature |
| O₂% | Oxygen percentage in gas mix |
| Start PSI | Tank pressure at start |
| End PSI | Tank pressure at end |
| Gas Used | Total gas consumed |
| End GF99 | Gradient factor at end of dive |

## Supported Dive Computers

Tested with:
- Shearwater Tern TX
- Should work with other Shearwater computers that sync to Shearwater Cloud

## Technical Details

- **No dependencies** - Uses only Python standard library (`sqlite3`, `json`)
- **Single file output** - Self-contained HTML with embedded CSS/JS
- **Chart.js** - Loaded from CDN for visualizations
- **Responsive design** - Works on desktop and mobile browsers

## Screenshots

### Dive Table with Detail View
![Dive Table](screenshots/dive-table.png)

### Gas Analysis Charts
![Gas Analysis](screenshots/gas-analysis.png)

### Trip Summaries
![Trips](screenshots/trips.png)

## Contributing

Contributions welcome! Some ideas:

- [ ] Support for actual dive profile data (binary format decoding)
- [ ] Export to PDF
- [ ] Compare dives side-by-side
- [ ] SAC rate calculations
- [ ] Decompression obligation tracking
- [ ] Dark/light theme toggle

## License

MIT License - feel free to use and modify.

## Acknowledgments

- [Shearwater Research](https://www.shearwater.com/) for making excellent dive computers
- [Chart.js](https://www.chartjs.org/) for the visualization library

---

**Happy diving! 🐠🌊**
