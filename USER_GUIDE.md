# Arrowcrab Dive Studio — User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Welcome Screen](#welcome-screen)
3. [Header Controls](#header-controls)
4. [Trips Tab](#trips-tab)
5. [Dive Table Tab](#dive-table-tab)
6. [Charts Tab](#charts-tab)
7. [Gas Analysis Tab](#gas-analysis-tab)
8. [Photo Management](#photo-management)
9. [Picture Viewer](#picture-viewer)
10. [Slideshows](#slideshows)
11. [Dashboard Background](#dashboard-background)
12. [Projects](#projects)
13. [Keyboard Shortcuts](#keyboard-shortcuts)

---

## Getting Started

### Exporting Your Dive Data

Before using Arrowcrab Dive Studio, you need to export your dive log from Shearwater Cloud:

1. Open the **Shearwater Cloud** desktop application
2. Go to **Settings** > **Export** > **Export Database**
3. Save the `.db` file somewhere you can find it

### Launching the App

- **From source:** Run `python divelog_app.py`
- **Standalone build:** Double-click `ArrowcrabDiveStudio.exe`

---

## Welcome Screen

When the app opens, you'll see three options:

- **New Project** — Start a fresh project with an empty dashboard. Useful if you want to add trips and photos manually without importing a dive log.
- **Import Dive Log** — Open a Shearwater Cloud `.db` file. The app reads all your dives and creates the dashboard automatically.
- **Load Project** — Open a previously saved `.json` project file, restoring all dives, trips, photos, and background settings.

---

## Header Controls

At the top of the dashboard you'll find:

| Button | What It Does |
|--------|-------------|
| **Imperial / Metric** | Toggle between feet/meters for depth display |
| **PSI / bar** | Toggle between PSI and bar for tank pressure |
| **New Project** | Start over with a blank dashboard |
| **Import Dive Log** | Import a Shearwater `.db` file |
| **Save Project** | Save your current project (dives, photos, background) to a `.json` file |
| **Load Project** | Open a saved project file |
| **Clear Background** | Remove the custom background image (only visible when a background is set) |

### Summary Statistics

Below the header, four stat cards show at a glance:
- **Total Dives** — Number of dives in your log
- **Total Hours** — Combined dive time
- **Max Depth** — Deepest dive recorded
- **Avg Gas Used** — Average gas consumption per dive (only counts dives from imported data, not photo-only trips)

---

## Trips Tab

The Trips tab is the default view. Each trip location gets a card showing:

- **Location name** — with a pencil icon to rename it
- **Date range** — first to last dive date
- **Dive count, total hours, max depth, avg gas**
- **Thumbnail** — a preview image from uploaded photos
- **Add Pictures** button — upload trip photos

### Adding a New Trip

Click the **+ Add Trip** button at the bottom of the trips grid. Fill in:
- **Location name** (required)
- **Start date** — the end date will auto-fill to 7 days later
- **End date** — adjust if needed

New trips appear as cards with a purple location badge. They can hold photos and generate slideshows, but won't affect the Charts or Gas Analysis tabs.

### Renaming a Trip Location

Click the pencil icon next to any trip name. Enter the new name in the prompt. All dives associated with that location will be updated.

---

## Dive Table Tab

A full sortable table of all dives with these columns:
- **#** — Dive number (with pencil icon to edit the dive site)
- **Date** — Dive date
- **Location** — Color-coded badge
- **Site** — Dive site name
- **Depth** — Maximum depth (ft or m, depending on unit toggle)
- **Duration** — Dive time in minutes
- **O2%** — Oxygen percentage in gas mix
- **Start / End PSI** — Tank pressure at start and end
- **Gas Used** — Total gas consumed
- **Rate** — Gas consumption rate (PSI/min or bar/min)
- **GF99** — Gradient factor at end of dive

### Sorting

Click any column header to sort. Click again to reverse the sort order.

### Filtering by Location

Use the dropdown at the top of the table to filter dives by location, or select **All Locations** to see everything.

### Dive Detail Panel

Click any table row to open the detail panel, which shows:
- All dive statistics in a card layout
- **Estimated Depth Profile** — a chart showing the descent, bottom time, and ascent
- **Estimated Tank Pressure** — a chart showing gas consumption over the dive
- **View Photos from this dive** — link to browse photos timestamped during this dive

### Editing a Dive Site

Click the pencil icon in the dive number column or in the detail panel title. A modal lets you update the site name.

---

## Charts Tab

Four charts rendered with Chart.js:

1. **Dive Depth Profile** — Bar chart of max depth for each dive, color-coded by location
2. **Dive Duration** — Line chart of dive duration over time
3. **Water Temperature** — Line chart of average water temperature per dive
4. **Dives by Location** — Pie chart showing dive count per location

Charts only include dives from imported Shearwater data. Photo-only trips are excluded.

---

## Gas Analysis Tab

Six charts focused on gas consumption:

1. **Gas Consumption per Dive** — Bar chart of gas used (PSI or bar)
2. **Consumption Rate** — Line chart of PSI/min or bar/min over time
3. **Start vs End Pressure** — Dual-bar chart comparing start and end tank pressure
4. **Depth vs Gas Consumption** — Scatter plot with labeled axes
5. **Gas Usage by Location** — Horizontal bar chart showing both average and max gas per location
6. **End Pressure Distribution** — Histogram of end-of-dive tank pressures

Like Charts, this tab excludes photo-only trips.

---

## Photo Management

### Uploading Photos to a Trip

1. Go to the **Trips** tab
2. Click **Add Pictures** on any trip card
3. Select photos from the file dialog (JPG, PNG, or ORF)
4. Photos appear in a thumbnail pane

### Thumbnail Pane

After uploading, the thumbnail pane shows all photos for that trip:

- **Click a thumbnail** to toggle its selection (green border = selected, red border = deselected)
- ORF (RAW) files are converted to JPG one at a time with a progress indicator
- Click **Apply Selection** to confirm your keep/discard choices
- Click **View Selected** to open the picture viewer for kept photos
- Click **Close** to dismiss the thumbnail pane

### How Photos Map to Dives

Photos are automatically assigned to dives based on their file timestamps. Each photo is matched to the dive whose time window (start time to end time) contains the photo's timestamp. You can view a dive's photos from the detail panel by clicking **View Photos from this dive**.

---

## Picture Viewer

The picture viewer opens in a full-screen overlay for browsing photos. Controls:

### Navigation
- **Left/Right arrow buttons** on either side of the image
- **Left/Right arrow keys** on your keyboard

### Top Bar (Left Side)
- **Keep checkbox** — Check to keep the photo, uncheck to discard
- Photo filename and counter (e.g., "3 / 12")

### Button Bar (Right Side)
- **Thumbnails** — Switch to thumbnail selection view
- **Set Background** — Use the current photo as the dashboard background
- **Save** — Close the viewer and apply your keep/discard selections
- **Back** — Close the viewer without saving any changes

### Dark Image Correction

JPG images that appear too dark are automatically brightened for viewing. This correction applies both in the viewer and when generating slideshows.

### AI Captions

Each photo is automatically captioned using TensorFlow.js with MobileNet v2. The model attempts to identify marine life (fish, eels, turtles, corals, etc.) and underwater subjects. If the model can't make a specific identification, it falls back to a general description based on image colors. Captions appear below each photo in the viewer and in generated slideshows.

---

## Slideshows

You can generate standalone HTML slideshow files that work without the app.

### Trip Slideshow

On any trip card, click **Create Slideshow**. The app generates an HTML file with:
- All kept photos for that trip
- Auto-play with play/pause control
- Previous/next navigation
- AI-generated captions under each photo
- Dark image brightness correction applied

### Dive Slideshow

In the dive detail panel, click **Create Slideshow** to generate a slideshow of just that dive's photos. The filename uses the dive site name with underscores replacing spaces.

### Saving

- **In the desktop app:** A save dialog lets you choose where to save the HTML file
- **In a browser:** The file downloads automatically

---

## Dashboard Background

Any photo can be set as the dashboard background:

1. Open the picture viewer for any trip or dive
2. Navigate to the photo you want
3. Click **Set Background**
4. The photo is resized to 1920x1080 and applied behind a dark overlay

To remove the background, click **Clear Background** in the header bar.

The background is saved with your project, so it persists across save/load cycles.

---

## Projects

### Saving a Project

Click **Save Project** in the header. The app saves a `.json` file containing:
- All dive data (imported and manually created)
- Trip information
- Photo file references (paths on disk)
- Dashboard background image (as embedded data)

### Loading a Project

Click **Load Project** and select a previously saved `.json` file. The app restores:
- All dives and trips
- Photos are reloaded from their original file paths
- The dashboard background is reapplied

**Note:** Photos are stored by file path, not embedded in the project file. If you move or delete the original photo files, they won't appear when you reload the project.

### Starting Fresh

Click **New Project** to start over. You'll be prompted to save your current project first, or discard it.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Left Arrow** | Previous photo (in picture viewer) |
| **Right Arrow** | Next photo (in picture viewer) |

---

## Tips

- **Unit toggles are global** — Switching between Imperial/Metric or PSI/bar updates all tables, charts, and statistics immediately.
- **ORF conversion takes time** — RAW files are converted one at a time. The thumbnail pane shows progress.
- **Photo timestamps matter** — The app uses file modification dates to match photos to dives. If your camera's clock was off, photos may map to the wrong dive.
- **Save often** — Use Save Project to preserve your work, especially after uploading photos or editing data.
- **Charts exclude photo trips** — Trips created just for photos (without imported dive data) don't appear in the Charts or Gas Analysis tabs, keeping your statistics accurate.
