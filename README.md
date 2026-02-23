# Arrowcrab Dive Studio

A Windows desktop application for creating interactive dive log dashboards from Shearwater dive computer data, with trip photo management, AI-powered image captioning, and slideshow generation.

## Overview

Arrowcrab Dive Studio imports your Shearwater Cloud database export and generates an interactive dashboard with charts, gas analysis, trip summaries, and a full photo management system. Everything runs locally in a native Windows window — no browser or internet connection required for core features.

## Features

- **Interactive Dive Table** — Sortable columns, click any row to view dive details with estimated depth and pressure profiles
- **Charts & Visualizations** — Depth profiles, duration trends, water temperature, dives by location
- **Gas Analysis** — Consumption rates, start/end pressure comparison, average and max gas by location, end pressure distribution
- **Trip Management** — Summary cards per location, add custom trips, edit trip locations, upload photos per trip
- **Photo Management** — Upload JPG/ORF images per trip, thumbnail selection, keep/discard workflow, automatic dark image correction
- **AI Image Captioning** — TensorFlow.js MobileNet classifies dive photos and generates captions (marine life identification)
- **Slideshow Generator** — Export trip or individual dive photos as standalone HTML slideshows with auto-play
- **Dashboard Backgrounds** — Set any photo as the dashboard background image
- **Project Save/Load** — Save your entire project (dives, trips, photos, background) as a JSON file and reload later
- **Unit Toggle** — Switch between Metric/Imperial and PSI/bar at any time
- **RAW Support** — ORF (Olympus RAW) files are converted to JPG for viewing via rawpy

## Getting Started

### Prerequisites

- **Windows 10/11** with Edge WebView2 runtime (included with Windows 10 1803+)
- **Python 3.10+**
- Python packages: `pywebview`, `Pillow`
- Optional: `rawpy` (for ORF/RAW photo conversion)

### Installation

```bash
git clone https://github.com/olsenj65/ArrowcrabDiveStudio.git
cd ArrowcrabDiveStudio
pip install pywebview Pillow
pip install rawpy  # optional, for RAW photo support
```

### Running the App

```bash
python divelog_app.py
```

### Building a Standalone Executable

```bash
pip install pyinstaller
pyinstaller ArrowcrabDiveStudio.spec
```

The executable will be in `dist/ArrowcrabDiveStudio/ArrowcrabDiveStudio.exe`.

### Command-Line Dashboard Only

You can also generate a dashboard HTML file directly without the desktop app:

```bash
python generate_dive_dashboard.py "Shearwater_Cloud__diver@email.com__2026-01-22.db"
```

This creates `dive_dashboard.html` in the same directory as the database file.

## Exporting from Shearwater Cloud

1. Open the **Shearwater Cloud** desktop application
2. Go to **Settings** > **Export** > **Export Database**
3. Save the `.db` file to a known location
4. Import the `.db` file using the **Import Dive Log** button in Arrowcrab Dive Studio

## Dashboard Tabs

### Trips
Trip summary cards showing dive count, total hours, max depth, and average gas consumption per location. Each card can display a thumbnail from uploaded photos. Add new trips manually with start/end dates, or rename existing trip locations.

### Dive Table
Sortable table with all dive data: number, date, location, site, max depth, duration, gas mix, tank pressures, gas used, consumption rate, and GF99. Click any row to open a detail panel with estimated depth and pressure profile charts. Edit dive site names with the pencil icon.

### Charts
- Dive depth profile across all dives
- Dive duration trends
- Water temperature over time
- Dives by location (pie chart)

### Gas Analysis
- Gas consumption per dive (bar chart)
- Consumption rate trends (PSI/min or bar/min)
- Start vs end pressure comparison
- Depth vs gas consumption (scatter plot with axis labels)
- Average and max gas usage by location (horizontal bar)
- End pressure distribution (histogram)

## Photo Management

Upload photos per trip using the **Add Pictures** button on any trip card. Supported formats: JPG, PNG, ORF (Olympus RAW). The thumbnail pane lets you select which photos to keep. ORF files are converted sequentially with progress indication.

Photos are assigned to individual dives based on their timestamps. Use the **View Photos** link on any dive to browse that dive's photos with:
- Arrow key navigation
- Keep/discard checkboxes
- Automatic dark image brightness correction
- Set any photo as the dashboard background
- Generate standalone HTML slideshows

## Supported Dive Computers

Tested with:
- Shearwater Tern TX
- Should work with any Shearwater computer that syncs to Shearwater Cloud

## Technical Details

- **pywebview** — Native Windows window using Edge WebView2
- **Chart.js 4.4.1** — Loaded from CDN for chart rendering
- **TensorFlow.js + MobileNet v2** — Browser-based image classification for captions
- **PyInstaller** — Bundles into a standalone Windows executable
- **No server required** — All processing happens locally

## Project Structure

```
ArrowcrabDiveStudio/
  divelog_app.py                 # Desktop app (pywebview GUI)
  generate_dive_dashboard.py     # Dashboard HTML generator
  ArrowcrabDiveStudio.spec       # PyInstaller build spec
  arrowcrab.png                  # App icon (PNG)
  arrowcrab.ico                  # App icon (ICO)
```

## License

MIT License — feel free to use and modify.

## Acknowledgments

- [Shearwater Research](https://www.shearwater.com/) for making excellent dive computers
- [Chart.js](https://www.chartjs.org/) for the visualization library
- [TensorFlow.js](https://www.tensorflow.org/js) for browser-based image classification
