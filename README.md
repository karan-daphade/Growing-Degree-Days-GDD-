# 🌱 Real-Time Cotton Crop Phenology & Integrated Pest Management System

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Folium](https://img.shields.io/badge/Geospatial-Folium%20%7C%20Shapely-77B800.svg)](https://python-visualization.github.io/folium/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)](#)

A precision agriculture decision-support platform designed for cotton (_Gossypium hirsutum_) cultivation. This system implements a **Heat Units / Growing Degree Days (GDD)** meteorological model integrated with microclimate weather tracking to forecast crop phenology, assess real-time pest and disease risks, project harvest dates, and provide interactive spatial mapping across farming clusters.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Agronomic & Scientific Models](#-agronomic--scientific-models)
  - [Growing Degree Days (GDD) Formulation](#1-growing-degree-days-gdd-formulation)
  - [Phenological Growth Stages (P1–P10)](#2-phenological-growth-stages-p1p10)
  - [Pink Bollworm (PBW) Life-Cycle & Weather Forecast](#3-pink-bollworm-pbw-life-cycle--weather-forecast)
  - [Sucking Pests & Disease Risk Engines](#4-sucking-pests--disease-risk-engines)
  - [Harvest Window Prediction](#5-harvest-window-prediction)
- [Directory Structure](#-directory-structure)
- [Database Schema Requirements](#-database-schema-requirements)
- [Installation & Environment Setup](#-installation--environment-setup)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
  - [1. Streamlit Web Dashboard](#1-streamlit-web-dashboard)
  - [2. CLI Single Farmer Analysis](#2-cli-single-farmer-analysis)
  - [3. Batch Pipeline Processing](#3-batch-pipeline-processing)
  - [4. Geospatial Data Exporters](#4-geospatial-data-exporters)
  - [5. Farmer User Provisioning](#5-farmer-user-provisioning)
- [Git & GitHub Migration Guide](#-git--github-migration-guide)
- [Security & Best Practices](#-security--best-practices)

---

## 🔍 Overview

Cotton development is strongly governed by thermal accumulation rather than calendar days alone. Variations in temperature and seasonal rainfall directly affect vegetative progress, reproductive initiation, and the incubation cycles of major crop threats such as the **Pink Bollworm (_Pectinophora gossypiella_)**, **Aphids**, **Whiteflies**, **Bacterial Blight**, and **Fusarium Wilt**.

This system bridges agrometeorological algorithms and relational spatial data to provide:

1. **Field-Level Diagnostics:** Detailed phenophase milestones and immediate pest advisories for individual farmers.
2. **Cluster & Regional Aggregation:** Cohort-based analysis grouped by sowing date windows across geographic grids.
3. **Geospatial Farm Maps:** Spatial polygon rendering of farm plots and grid tiles with interactive map layers.
4. **Automated ETL & Archival:** Batch computation and storage into structured PostgreSQL analytics tables with JSONB advisories.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph DataSources["Data Sources & Database (PostgreSQL / PostGIS)"]
        A1[("farmer_grid_mapping<br/>(Farmer profiles, sowing dates, geometries)")]
        A2[("farmer_grid_weather_data<br/>(Daily Tmax, Tmin, Precip, Humidity, Sunshine)")]
    end

    subgraph CoreEngine["Agronomic Analytics Engine (updated.py)"]
        B1["GDD Accumulation Engine<br/>(Tbase = 15.6°C, Tupper = 34.0°C)"]
        B2["Dynamic Sowing Window Matcher<br/>(15 intervals: May 20 to July 15)"]
        B3["Phenophase Tracker<br/>(P1 Emergence to P10 Harvest)"]
        B4["PBW Risk & Life-Stage Model<br/>(Larvae, Pupae, Adult + Climate Matrix)"]
        B5["Insect & Disease Risk Engines<br/>(Aphids, Whitefly, Blight, Wilt)"]
        B6["Harvest Projection Engine<br/>(Remaining GDD / 25°C baseline)"]
    end

    subgraph ProcessingPipelines["Pipelines & CLI"]
        C1["Batch Processor (gdd_result_script.py)"]
        C2[("cotton_gdd_results<br/>(Summary Table + JSONB)")]
        C3["GeoJSON / KML Exporters<br/>(gddgeojson.py, gddkml1.py)"]
        C4["User Account Sync (userappend.py)"]
    end

    subgraph UI["Streamlit Web Application (main.py)"]
        D1["Farmer ID View<br/>(pages/Farmer_ID.py)"]
        D2["Cluster & Grid View<br/>(pages/Cluster_grid_page.py)"]
        D3["Interactive Map<br/>(pages/Grid_Map.py)"]
    end

    A1 --> CoreEngine
    A2 --> CoreEngine
    CoreEngine --> ProcessingPipelines
    C1 --> C2
    CoreEngine --> UI
    A1 --> C3
    C3 --> D3
```

---

## ✨ Key Features

- **Dynamic Sowing Window Calibration:** Adapts phenological thresholds based on exact sowing dates across 15 bi-weekly and 4-day cohorts from May 20 through July 15.
- **Microclimate Risk Evaluation:** Evaluates pest and pathogen pressure by weighting daily maximum temperatures, relative humidity, precipitation frequency, and sunshine duration against specific crop stages.
- **Historical Season-Long Auditing:** Tracks initial disease/pest conducive dates, total conducive days, peak risk scores, and exact peak occurrence dates throughout the growing cycle.
- **Interactive Multi-Page Streamlit App:**
  - Modern UI styled with responsive metrics, color-coded severity cards, and custom typography (_Manrope_).
  - Instant transition between Farmer ID diagnostics and Grid/Cluster group summaries.
- **Geographic Exploration with Folium:** Integrated farm plot polygons and grid bounds rendered with OpenStreetMap / Satellite base layers, measurement tools, and mini-map navigators.
- **Scalable Database Architecture:** SQLAlchemy connection pooling (`pool_pre_ping`, recycle timeouts) and optimized indexed queries ensuring high concurrency and sub-second execution.

---

## 🔬 Agronomic & Scientific Models

### 1. Growing Degree Days (GDD) Formulation

Heat units are calculated on a daily basis using lower and upper physiological thresholds calibrated specifically for cotton:

$$\text{Daily GDD} = \max\left(0, \frac{\min(T_{\max}, T_{\text{upper}}) + \max(T_{\min}, T_{\text{base}})}{2} - T_{\text{base}}\right)$$

Where:

- **$T_{\text{base}}$ (Base Temperature):** `15.6 °C` (below which cotton metabolic development ceases)
- **$T_{\text{upper}}$ (Upper Cutoff):** `34.0 °C` (thermal stress limit where growth rate plateaus)

$$\text{Cumulative GDD} = \sum_{t = \text{Sowing Date}}^{\text{Question Date}} \text{Daily GDD}_t$$

### 2. Phenological Growth Stages (P1–P10)

The crop progression is segmented into 10 key phenophases:

| Phase   | Description      | Key Agronomic Significance                                   |
| :------ | :--------------- | :----------------------------------------------------------- |
| **P1**  | Emergence        | Seedling establishment and cotyledon development             |
| **P2**  | First Square     | Appearance of floral buds (squaring)                         |
| **P3**  | First Flower     | Initiation of anthesis                                       |
| **P4**  | Peak Flowering   | Maximum flower load; critical stage for moisture & nutrients |
| **P5**  | First Boll       | Initial fruit set                                            |
| **P6**  | Boll Development | Rapid boll filling and fiber elongation                      |
| **P7**  | First Boll Open  | Maturation; opening of early bottom bolls                    |
| **P8**  | 50% Boll Open    | Mid-maturation stage                                         |
| **P9**  | 90% Boll Open    | Defoliation readiness                                        |
| **P10** | Harvest Ready    | Full crop maturity                                           |

_Note: Sowing date windows alter the cumulative GDD required to reach each phenophase to account for photoperiod and temperature variances across early, normal, and late plantings._

### 3. Pink Bollworm (PBW) Life-Cycle & Weather Forecast

The Pink Bollworm (_Pectinophora gossypiella_) is one of the most destructive cotton pests. Its model triggers once floral squares appear (from stage **P4** through **P8**):

- **Life Stage Classification:**
  - **Larvae:** Accumulation $< 200$ PBW GDD
  - **Pupae:** Accumulation $200 - 399$ PBW GDD
  - **Adult:** Accumulation $\ge 400$ PBW GDD
- **Generational Tracking:**
  $$\text{Generation} = \min\left(3, \left\lfloor\frac{\text{PBW GDD}}{600}\right\rfloor + 1\right)$$
- **Environmental Vulnerability Matrix:**
  - Maximum Temperature in $[30^\circ\text{C}, 40^\circ\text{C}]$ (Weight: `0.5`)
  - Relative Humidity in $[60\%, 80\%]$ (Weight: `0.3`)
  - Rain Probability in $[0\%, 30\%]$ (Weight: `0.2`)
- **Adjusted Severity:** Upgrades to `High` if weather risk $\ge 60\%$.

### 4. Sucking Pests & Disease Risk Engines

| Pest / Disease       | Vulnerable Stages | Weather Risk Triggers                                                                              | Key Advisory Actions                                      |
| :------------------- | :---------------- | :------------------------------------------------------------------------------------------------- | :-------------------------------------------------------- |
| **Aphids**           | P1, P2, P3        | $T_{\max} \in [25, 35]^\circ\text{C}$, Humidity $\in [60, 80]\%$, Sunshine $\in [4, 8]\text{ hrs}$ | Neem oil, release chrysoperla/ladybugs, scout weekly      |
| **Whitefly**         | P2, P3, P4        | $T_{\max} \in [28, 38]^\circ\text{C}$, Humidity $\in [50, 70]\%$, Rain Prob $\in [0, 30]\%$        | Yellow sticky traps, imidacloprid / thiamethoxam          |
| **Bacterial Blight** | P2, P3, P4, P5    | $T_{\max} \in [25, 35]^\circ\text{C}$, Humidity $\in [70, 90]\%$, Rain Prob $\in [50, 100]\%$      | Copper-based bactericides, resistant cultivars            |
| **Fusarium Wilt**    | P3, P4, P5, P6    | $T_{\max} \in [25, 32]^\circ\text{C}$, Humidity $\in [60, 85]\%$, $\ge 5$ monthly rainy days       | Seed treatment, soil fungicide application, crop rotation |

### 5. Harvest Window Prediction

When the crop has not yet reached maturity (P10):

1. Calculates remaining GDD: $\text{GDD}_{\text{remaining}} = \text{Median}(\text{GDD}_{\text{P10}}) - \text{Cumulative GDD}$.
2. Assumes an average late-season temperature of $25.0^\circ\text{C}$ ($\approx 9.4\text{ GDD/day}$).
3. Projects earliest and latest harvest dates spanning an operational window of 7 days.

---

## 📁 Directory Structure

```text
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git ignore file (prevents committing secrets/cache)
├── requirements.txt              # Production Python package dependencies
├── main.py                       # Main Streamlit router entrypoint
├── updated.py                    # Core agronomic GDD model, risk calculators & CLI
├── updated_orignal.py            # Baseline reference implementation (archival)
├── gdd_result_script.py          # Batch calculation script for database upserts
├── gdd_result_table.sql          # PostgreSQL DDL for results storage table
├── gddgeojson.py                 # PostGIS geometry to GeoJSON converter script
├── gddkml1.py                    # PostGIS geometry to Google Earth KML converter
├── userappend.py                 # Farmer account provisioning script
├── geojson_files/                # Spatial GeoJSON layers
│   ├── all_farms_and_grids.geojson
│   ├── GRID_0001.geojson
│   └── ... (grid-wise geojson files)
└── pages/                        # Multi-page Streamlit dashboards
    ├── Farmer_ID.py              # Single farmer diagnostics page
    ├── Cluster_grid_page.py      # Cluster and grid group analysis page
    └── Grid_Map.py               # Interactive geospatial Folium map
```

---

## 🗄 Database Schema Requirements

The system integrates with a PostgreSQL database containing the following core tables:

### 1. `farmer_grid_mapping` (Input)

Stores farmer metadata, geolocation coordinates, and sowing records:

- `Farmer ID` (Numeric/Float, Primary Key)
- `Farmer Name` (Text)
- `Cluster name` (Text)
- `Grid_ID` (Text, e.g., `GRID_0001`)
- `grid_lat`, `grid_lon` (Float)
- `Cotton sowing date ( कापसाची पेरणी त` (Date / Text)
- `geom` (PostGIS geometry, optional for spatial mapping)

### 2. `farmer_grid_weather_data` (Input)

Daily weather records per grid location:

- `date` (Timestamp / Date)
- `Grid_ID` (Text)
- `temperature_2m_max`, `temperature_2m_min` (Float)
- `precipitation_sum` (Float)
- `relative_humidity_2m_mean` (Float)
- `sunshine_duration` (Float in seconds)
- `cloud_cover_mean` (Float)

### 3. `cotton_gdd_results` (Output)

Generated automatically by running [`gdd_result_table.sql`](file:///D:/New%20folder/GDD%20stre/gdd_result_table.sql) to record batch analysis runs with JSONB advisory fields.

---

## ⚙️ Installation & Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Create and Activate a Virtual Environment

- **On Linux/macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- **On Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```

### 3. Install Required Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔧 Configuration

1. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your PostgreSQL credentials:

   ```env
   # PostgreSQL Connection URL
   DB_URL=postgresql+psycopg2://myuser:mypassword@localhost:5432/gdd_model

   # Optional Connection Pool Fine-Tuning
   DB_POOL_SIZE=5
   DB_MAX_OVERFLOW=10
   DB_POOL_RECYCLE_SECONDS=1800
   ```

---

## 🚀 Running the Application

### 1. Streamlit Web Dashboard

Launch the multi-page web application:

```bash
streamlit run main.py
```

- Navigate to `http://localhost:8501` in your browser.
- Select between **Farmer ID wise** or **Cluster + Grid ID wise** modes from the sidebar.
- Switch to the **Grid Map** page to view farm boundaries and grid overlays.

### 2. CLI Single Farmer Analysis

You can execute single-farmer analyses directly via terminal:

```bash
python updated.py --farmer-id 10811 --question-date 2024-09-15
```

_Optional Flags:_

- `--insects-only`: Restrict output to insect risk evaluation.
- `--diseases-only`: Restrict output to disease risk evaluation.
- `--risk-threshold 50`: Set custom risk advisory threshold percentage.

### 3. Batch Pipeline Processing

Execute the batch calculator across all registered farmers and persist outputs into PostgreSQL:

```bash
# Ensure target table exists first
psql -d gdd_model -f gdd_result_table.sql

# Run the batch job
python gdd_result_script.py
```

### 4. Geospatial Data Exporters

Export boundary polygons directly from the PostGIS database:

- **GeoJSON export:**
  ```bash
  python gddgeojson.py
  ```
  Generates files under `./geojson_files/`.
- **KML export (Google Earth):**
  ```bash
  python gddkml1.py
  ```
  Generates files under `./kml_files/`.

### 5. Farmer User Provisioning

Synchronize farmer credentials and profiles into `gdd_users_table`:

```bash
python userappend.py
```

---

## 🚢 Git & GitHub Migration Guide

Follow these exact steps to push this project to your new GitHub repository:

### Step 1: Verify Secrets are Safe

Make sure `.env` is ignored by git so sensitive passwords are never pushed:

```bash
git status
```

_(Ensure `.env` does **not** appear in the untracked files list)._

### Step 2: Initialize Git & Commit Files

```bash
# Initialize local repository
git init

# Add all project files
git add .

# Create the initial commit
git commit -m "feat: initial commit for Cotton Crop GDD & Risk Management Platform"
```

### Step 3: Link to Your GitHub Repository

1. Go to [GitHub](https://github.com/new) and click **New Repository**.
2. Name your repository (e.g., `cotton-gdd-crop-dashboard`).
3. Leave **"Initialize this repository with a README"** **UNCHECKED** (we already have one).
4. Run the following commands in your project directory:

```bash
# Rename default branch to main
git branch -M main

# Add your GitHub remote (replace with your actual GitHub repo URL)
git remote add origin https://github.com/<your-username>/<your-repo-name>.git

# Push code to GitHub
git push -u origin main
```

---

## Security & Best Practices

---

## 📄 License
