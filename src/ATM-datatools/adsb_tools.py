"""Tools to process ADS-B data"""

# Imports
import pandas as pd
import geopandas as gpd
from shapely.geometry import *
import os

##---Main functions---##
def adsb_preprocessing(df_, datestr, downsample=0, floor=100, ceiling=0, radius=0):
    """
    Function for pre-processing before filtering functions. Generally, there is no need to call this function directly.
    Returns a df with the columns ['id','datetime','unix_timestamp','geometry'].
    The geometry column has Shapely point objects with lat, long, and altitude information.
    Increments the id of a position if a time gap of more than 15 minutes is detected. e.g. MEDIC77 becomes MEDIC77_1
    """
    df = df_.copy()
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
    df.id = df.id.apply(lambda x: x.strip())
    
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
      
    # get the date
    date = f'{datestr[0:4]}-{datestr[4:6]}-{datestr[6:8]}'

    # change timeforpos to readable format (string)
    df['timeforpos'] = pd.to_datetime(df['timeforpos'], unit = 's').dt.time
    
    # datetime field and unix timestamp
    df['datetime'] = pd.to_datetime(date + ' ' + df['timeforpos'].astype(str).apply(lambda x: x[0:8]))
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
    return df2


def read_adsb_byairport(fname, airport, **kwargs):
    """
    Returns a GeoPandas dataframe with flight tracks filtered by airport, with additional parameters for filtering.

    Parameters:
        fname: the filename of the adsb csv file
        airport: accepts 'WSSS', 'WSSL'
        [Optional] arrdep = 0: accepts 'arr' or 'dep' to filter for arriving or departing flights, default value of 0 will keep all flights.
        [Optional] downsample = 0: downsample the track data, e.g. 2 will take every 2nd point in the track data
        [Optional] floor = 100: cuts off tracks below this altitude in feet
        [Optional] ceiling = 0: cuts off tracks above this altitude in feet
        [Optional - future feature] radius = 0: discard tracks outside this radius from airport in nautical miles (1 deg is 60NM)
    
    Returns:
        df_geo (GeoPandas dataframe): GeoPandas dataframe with flight tracks filtered by the parameters
    """

    # Process kwargs
    arrdep = kwargs.get('arrdep', 0)
    downsample = kwargs.get('downsample', 0)
    floor = kwargs.get('floor', 100)
    ceiling = kwargs.get('ceiling', 0)
    radius = kwargs.get('radius', 0)

    # Read file
    df = pd.read_csv(fname)
    datestr = os.path.basename(fname)[0:8]
    df = adsb_preprocessing(df, datestr, downsample, floor, ceiling, radius)
    
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


def read_adsb_byflightid(fname, flightid, **kwargs):
    """
    Returns a GeoPandas dataframe with flight tracks filtered by flightid, with additional parameters for filtering.

    Parameters:
        fname: the filename of the adsb csv file
        flightid: the flightid of interest
        [Optional] downsample = 0: downsample the track data, e.g. 2 will take every 2nd point in the track data
        [Optional] floor = 100: cuts off tracks below this altitude in feet
        [Optional] ceiling = 0: cuts off tracks above this altitude in feet
        [Optional - future feature] radius = 0: discard tracks outside this radius from airport in nautical miles (1 deg is 60NM)
    """
    # Process kwargs
    downsample = kwargs.get('downsample', 0)
    floor = kwargs.get('floor', 100)
    ceiling = kwargs.get('ceiling', 0)
    radius = kwargs.get('radius', 0)

    df = pd.read_csv(fname)
    datestr = os.path.basename(fname)[0:8]
    df = adsb_preprocessing(df, datestr, downsample, floor, ceiling, radius)

    # filter for flights
    df = df.loc[df['id'].str.contains(flightid)]
    df_geo = gpd.GeoDataFrame(df, crs='EPSG:4326')

    df_geo.reset_index(drop=True, inplace=True)

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
    elif arrdep == 0:
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
    elif arrdep == 0:
        if ((103.86 <= p.coords[-1][0] <= 103.88) and (1.40 <= p.coords[-1][1] <= 1.43)) or ((103.86 <= p.coords[0][0] <= 103.88) and (1.40 <= p.coords[0][1] <= 1.43)):
            return True
        return False
    else:
        raise ValueError('Did not specify arrival or departure correctly, use "arr" or "dep". Or leave blank to select all flights.')