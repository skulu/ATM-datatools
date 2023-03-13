# ATM Data Tools
 Tools for air traffic data analysis. The package currently consists of 3 functions for reading ADSB files.

# Installation
This package is available via PyPi:

```
pip install atm-datatools
```

# Import
You can import the package by using

```
import atmdatatools as adt
```

# Functions
## read_adsb()
**`read_adsb(fname, datestr, downsample=None, floor=None, ceiling=None)`**

Reads raw ADSB files, assuming that each file only has 1 day worth of data. Raw ADSB files should have the columns `['073:071_073TimeforPos','131:Latitude','131:Longitude','140:GeometricHeight','170:TargetID']`. The column `073:071_073TimeforPos` contains the time elapsed in seconds in UTC and the timezone of the file is currently hardcoded for UTC+8. Hence, the first row of this column starts at approximately 57,600s representing 16:00 UTC of the previous day.

Returns a GeoDataFrame with the columns `['id','datetime','unix_timestamp','geometry']`. Each row represents 1 ADSB position report.

### Parameters
- **fname:** the filename of the adsb csv file
- **datestr**: date string in the format 'YYYYMMDD'
- [Optional] **downsample = None:** downsample the track data, e.g. 2 will take every 2nd point in the track data
- [Optional] **floor = None:** cuts off tracks below this altitude in feet, recommend 100 feet if you wish to exclude ground movements
- [Optional] **ceiling = None:** cuts off tracks above this altitude in feet

### Returns
- **GeoDataFrame:** A GeoDataFrame with the columns `['id','datetime','unix_timestamp','geometry']`. Each row represents 1 ADSB position report.
    - `id` contains the flight number (e.g. SIA92). Increments the id of a position if a time gap of more than 15 minutes is detected. e.g. MEDIC77 becomes MEDIC77_1.
    - Times are in UTC
    - `geometry` column has Shapely Point objects with lat, long, and altitude information


## read_adsb_byflightid()
**`read_adsb_byflightid(fname, datestr, flightid, downsample=None, floor=None, ceiling=None)`**

Reads raw ADSB files, assuming that each file only has 1 day worth of data, returning a GeoDataFrame with flight tracks of the desired flightid. Each row represents 1 ADSB position report. Parameters allow for additional filtering.

See the `read_adsb()` function documentation for raw ADSB file format.

### Parameters
- **fname:** the filename of the adsb csv file
- **datestr**: date string in the format 'YYYYMMDD'
- **airport**: Accepts ICAO airport codes, currently accepts `WSSS`, `WSSL`.
- [Optional] **downsample = None:** downsample the track data, e.g. 2 will take every 2nd point in the track data
- [Optional] **floor = None:** cuts off tracks below this altitude in feet, recommend 100 feet if you wish to exclude ground movements
- [Optional] **ceiling = None:** cuts off tracks above this altitude in feet

### Returns
- **GeoDataFrame:** A GeoDataFrame with the columns `['id','datetime','unix_timestamp','geometry']`. Each row represents 1 ADSB position report.
    - `id` contains the flight number (e.g. SIA92). Increments the id of a position if a time gap of more than 15 minutes is detected. e.g. MEDIC77 becomes MEDIC77_1.
    - Times are in UTC
    - `geometry` column has Shapely Point objects with lat, long, and altitude information


## read_adsb_byairport()
**`read_adsb_byairport(fname, datestr, airport, arrdep=None, downsample=None, floor=None, ceiling=None)`**

Reads raw ADSB files, assuming that each file only has 1 day worth of data, returning a GeoDataFrame with flight tracks filtered by airport of interest. Each row represents 1 flightpath. Parameters allow for additional filtering.

See the `read_adsb()` function documentation for raw ADSB file format.

### Parameters
- **fname:** the filename of the adsb csv file
- **datestr**: date string in the format 'YYYYMMDD'
- **airport**: Accepts ICAO airport codes, currently accepts `WSSS`, `WSSL`.
- [Optional] **downsample = None:** downsample the track data, e.g. 2 will take every 2nd point in the track data
- [Optional] **floor = None:** cuts off tracks below this altitude in feet, recommend 100 feet if you wish to exclude ground movements
- [Optional] **ceiling = None:** cuts off tracks above this altitude in feet

### Returns
- **GeoDataFrame:** A GeoDataFrame with the columns `['id','geometry']`. Each row represents 1 flightpath.
    - `id` contains the flight number (e.g. SIA92). Increments the id of a position if a time gap of more than 15 minutes is detected. e.g. MEDIC77 becomes MEDIC77_1.
    - `geometry` column contains a Shapely LineString representing the flight's flightpath

