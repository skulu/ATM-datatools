"""Tools to process ADS-B data"""

# Imports
import pandas as pd
import geopandas as gpd
from shapely.geometry import *

##---Main functions---##
def read_adsb(fname, datestr, **kwargs):
    """
    Function for reading raw ADSB files, returning a GeoDataFrame with the columns ['id','datetime','unix_timestamp','geometry']. Times are in UTC.
    The geometry column has Shapely point objects with lat, long, and altitude information.
    Increments the id of a position if a time gap of more than 15 minutes is detected. e.g. MEDIC77 becomes MEDIC77_1
    
    Parameters:
        fname: the filename of the adsb csv file
        datestr: date in the format 'YYYYMMDD'
        [Optional] downsample = None: downsample the track data, e.g. 2 will take every 2nd point in the track data
        [Optional] floor = None: cuts off tracks below this altitude in feet
        [Optional] ceiling = None: cuts off tracks above this altitude in feet
        [Optional - future feature] radius = None: discard tracks outside this radius from airport in nautical miles (1 deg is 60NM)
    """
    # kwargs
    downsample = kwargs.get('downsample', None)
    floor = kwargs.get('floor', None)
    ceiling = kwargs.get('ceiling', None)
    radius = kwargs.get('radius', None)

    # read file
    df = pd.read_csv(fname)
    # Retain relevant columns only
    df = df[['073:071_073TimeforPos','131:Latitude','131:Longitude','140:GeometricHeight','170:TargetID']]
    new_columns = ['timeforpos','lat','lon','height','id']
    df.columns = new_columns
    df.dropna(inplace=True)

    # Ensure right data type
    df = df.astype({'timeforpos': float,
                    'lat': float,
                    'lon': float,
                    'height': float,
                    'id': object})

    # strip whitespace from ids
    # df.id = df.id.apply(lambda x: x.strip())
    df['id'] = df['id'].str.strip()
    
    # drop rows with empty ids
    df = df.loc[df.id.str.len() != 0]

    # drop ids that only consist of 0
    df = df.loc[~df['id'].str.contains('^0+$')]

    # only keep tracks above floor (in feet)
    if floor:
        df = df.loc[(df.height >= floor)]

    # only keep tracks below ceiling (in feet)
    if ceiling:
        df = df.loc[(df.height <= ceiling)]

    # only keep tracks within this radius (in NM)
    # if radius:
    #     df=df.loc[]
      
    # get the date (date1 is the previous day, due to timezone. date2 is the current day.)
    date2 = f'{datestr[0:4]}-{datestr[4:6]}-{datestr[6:8]}'
    date1 = pd.to_datetime(date2) - pd.Timedelta(1, unit='day')
    date1 = date1.strftime('%Y-%m-%d')
    
    # start index of new day
    dayidx = df.loc[df['timeforpos'] == df['timeforpos'].min()].index[0]

    # get datetime field and unix timestamp
    df['timeforpos'] = pd.to_datetime(df['timeforpos'], unit = 's').dt.time
    prev_day = pd.to_datetime(date1 + ' ' + df.loc[:dayidx-1,'timeforpos'].astype(str).apply(lambda x: x[0:8]))
    curr_day = pd.to_datetime(date2 + ' ' + df.loc[dayidx:,'timeforpos'].astype(str).apply(lambda x: x[0:8]))
    df['datetime'] = pd.concat([prev_day,curr_day])
    df['unix_timestamp'] = df['datetime'].apply(pd.Timestamp.timestamp)

    # generate shapely points
    df['geometry'] = [Point(xyz) for xyz in zip(df['lon'], df['lat'], df['height'])]
    
    # increment id if gap larger than 15 minutes is detected
    by_id = df.groupby('id')
    df2 = pd.DataFrame()
    for i in by_id.groups.keys():
        tmp = by_id.get_group(i).copy()
        tmp['datetime2'] = tmp['datetime'].shift(-1)
        tmp['timediff'] = tmp['datetime2'] - tmp['datetime']
        indices = tmp.loc[(tmp['timediff'] > pd.Timedelta(15, unit='min')) | (tmp['timediff'] < pd.Timedelta(-15, unit='min'))].index

        suffix = 1
        for idx in indices:
            tmp.loc[idx+1:, 'id'] = f'{i}_{suffix}'
            suffix += 1
        df2 = pd.concat([df2,tmp], axis=0)

    # downsample:
    if downsample:
        df2 = df2.iloc[::downsample,:]

    # drop ids with 2 or less points
    dropid = (df2.id.value_counts() <= 2)
    dropid = dropid.index[dropid == True].tolist()
    df2 = df2.loc[[True if x not in dropid else False for x in df2.id]]

    # keep relevant columns
    df2 = df2[['id','datetime','unix_timestamp','geometry']]

    df2.reset_index(inplace=True, drop=True)
    df2 = gpd.GeoDataFrame(df2, crs='EPSG:4326')

    return df2


def read_adsb_byflightid(fname, datestr, flightid, **kwargs):
    """
    Returns a GeoDataFrame with flight tracks filtered by flightid, with additional parameters for filtering.

    Parameters:
        fname: the filename of the adsb csv file
        datestr: date in the format 'YYYYMMDD'
        flightid: the flightid of interest
        [Optional] downsample = None: downsample the track data, e.g. 2 will take every 2nd point in the track data
        [Optional] floor = None: cuts off tracks below this altitude in feet
        [Optional] ceiling = None: cuts off tracks above this altitude in feet
    """
    # Process kwargs
    downsample = kwargs.get('downsample', None)
    floor = kwargs.get('floor', None)
    ceiling = kwargs.get('ceiling', None)
    radius = kwargs.get('radius', None)

    # Read file
    df = read_adsb(fname, datestr, downsample=downsample, floor=floor, ceiling=ceiling, radius=radius)

    # filter for flights
    df = df.loc[df['id'].str.contains(flightid)]
    df_geo = gpd.GeoDataFrame(df, crs='EPSG:4326')

    df_geo.reset_index(drop=True, inplace=True)

    return df_geo


def read_adsb_byairport(fname, datestr, airport, **kwargs):
    """
    Returns a GeoDataFrame with flight tracks filtered by airport, with additional parameters for filtering.

    Parameters:
        fname: the filename of the adsb csv file
        datestr: date in the format 'YYYYMMDD'
        airport: accepts 'WSSS', 'WSSL'
        [Optional] arrdep = None: accepts 'arr' or 'dep' to filter for arriving or departing flights, default value of 0 will keep all flights.
        [Optional] downsample = None: downsample the track data, e.g. 2 will take every 2nd point in the track data
        [Optional] floor = None: cuts off tracks below this altitude in feet
        [Optional] ceiling = None: cuts off tracks above this altitude in feet
        [Optional - future feature] radius = None: discard tracks outside this radius from airport in nautical miles (1 deg is 60NM)
    
    Returns:
        df_geo (GeoPandas dataframe): GeoPandas dataframe with flight tracks filtered by the parameters
    """

    # kwargs
    arrdep = kwargs.get('arrdep', None)
    downsample = kwargs.get('downsample', None)
    floor = kwargs.get('floor', None)
    ceiling = kwargs.get('ceiling', None)
    radius = kwargs.get('radius', None)

    # Read file
    df = read_adsb(fname, datestr, downsample=downsample, floor=floor, ceiling=ceiling, radius=radius)
    
    # Organise into rows, each row is 1 flight and has a LineString representing the flightpath
    df_geo = df.groupby('id')['geometry'].apply(list)
    df_geo = df_geo.apply(LineString)

    # Airport filtering
    airport_filters = {
        'WSSS': WSSS_arrdep,
        'WSSL': WSSL_arrdep
    }
    # if airport == 'WSSS':
    #     pass
    # elif airport == 'WSSL':
    filterlist = df_geo.apply(airport_filters[airport], args=[arrdep])
    df_geo = df_geo.loc[filterlist]
    
    df_geo = gpd.GeoDataFrame(df_geo, crs='EPSG:4326')
    df_geo = df_geo.reset_index()
    
    return df_geo


##---Airport filter functions---##
def WSSS_arrdep(p, arrdep):
    # coords to get first [0] and last [-1] point of track
    # within the coords, 0 is long, 1 is lat, 2 is height
    if arrdep == 'arr':
        if (103.9 <= p.coords[-1][0] <= 104.1) and (1.3 <= p.coords[-1][1] <= 1.4):
            return True
        return False
    elif arrdep == 'dep':
        if (103.9 <= p.coords[0][0] <= 104.1) and (1.3 <= p.coords[0][1] <= 1.4):
            return True
        return False
    elif arrdep is None:
        if ((103.9 <= p.coords[-1][0] <= 104.1) and (1.3 <= p.coords[-1][1] <= 1.4)) or ((103.9 <= p.coords[0][0] <= 104.1) and (1.3 <= p.coords[0][1] <= 1.4)):
            return True
        return False
    else:
        raise ValueError('Did not specify arrival or departure correctly, use "arr" or "dep". Or leave blank to select all flights.')

def WSSL_arrdep(p, arrdep):
    # coords to get first [0] and last [-1] point of track
    # within the coords, 0 is long, 1 is lat, 2 is height
    if arrdep == 'arr':
        if (103.86 <= p.coords[-1][0] <= 103.88) and (1.40 <= p.coords[-1][1] <= 1.43):
            return True
        return False
    elif arrdep == 'dep':
        if (103.86 <= p.coords[0][0] <= 103.88) and (1.40 <= p.coords[0][1] <= 1.43):
            return True
        return False
    elif arrdep is None:
        if ((103.86 <= p.coords[-1][0] <= 103.88) and (1.40 <= p.coords[-1][1] <= 1.43)) or ((103.86 <= p.coords[0][0] <= 103.88) and (1.40 <= p.coords[0][1] <= 1.43)):
            return True
        return False
    else:
        raise ValueError('Did not specify arrival or departure correctly, use "arr" or "dep". Or leave blank to select all flights.')