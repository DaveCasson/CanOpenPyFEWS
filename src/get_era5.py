
"""

Get ERA5 data from CDS

TO DO: Expand documentation

"""


# Import required packages
import os
import threading
import logging
import datetime as dt
import cdsapi
import math

#Import local packages
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])

def round_coords_to_ERA5(coords):
    
    # Function credit to https://github.com/CH-Earth/CWARHM, Wouter Knoben
    # Source https://github.com/CH-Earth/CWARHM/blob/main/3a_forcing/1a_download_forcing/download_ERA5_surfaceLevel_annual.py

    '''Assumes coodinates are an array: [lat_max,lon_min,lat_min,lon_max] (top-left, bottom-right).
    Returns separate lat and lon vectors.'''
    
    # Extract values
    lon = [coords[1],coords[3]]
    lat = [coords[2],coords[0]]
    
    # Round to ERA5 0.25 degree resolution
    rounded_lon = [math.floor(lon[0]*4)/4, math.ceil(lon[1]*4)/4]
    rounded_lat = [math.floor(lat[0]*4)/4, math.ceil(lat[1]*4)/4]
    
    # Find if we are still in the representative area of a different ERA5 grid cell
    if lat[0] > rounded_lat[0]+0.125:
        rounded_lat[0] += 0.25
    if lon[0] > rounded_lon[0]+0.125:
        rounded_lon[0] += 0.25
    if lat[1] < rounded_lat[1]-0.125:
        rounded_lat[1] -= 0.25
    if lon[1] < rounded_lon[1]-0.125:
        rounded_lon[1] -= 0.25
    
    # Make a download string
    dl_string = '{}/{}/{}/{}'.format(rounded_lat[1],rounded_lon[0],rounded_lat[0],rounded_lon[1])
    
    return dl_string, rounded_lat, rounded_lon

def download_era5(cmd_dict, data_source='ERA5'):

    #Read model independent settings
    output_dir = cmd_dict['output_dir']
    bounding_box = cmd_dict['bounding_box']

    #Read command line list
    num_days_back = cmd_dict[data_source]['num_days_back']
    delay_days = cmd_dict[data_source]['delay_days']
    surface_level_variable_list = cmd_dict[data_source]['variables_surface_level']
    grid = cmd_dict[data_source]['grid']

    coordinates,_,_ = round_coords_to_ERA5(bounding_box)

    #Read settings file
    hour_list = cmd_dict[data_source]['hours']

    # Initialize the reference date (UTC+00)
    ref_date = dt.datetime.utcnow()

    # Calculate start and end dates
    end_date = ref_date - dt.timedelta(days=delay_days)
    start_date = end_date - dt.timedelta(days=num_days_back)

    # Calculate the total number of days to download
    total_download_days = num_days_back - delay_days

    # Iterate over each day in the download period
    for day_counter in range(total_download_days):

        date = start_date + dt.timedelta(days=day_counter)

        c = cdsapi.Client()
        
        surface_level_output_filename = 'surface_level_variables_'+date.strftime('%Y%m%d')+'.nc'
        surface_level_output_file = os.path.join(output_dir,surface_level_output_filename)

        # Surface level variable download

        c.retrieve(
            'reanalysis-era5-single-levels',
            {
            'product_type':'reanalysis',
            'variable':surface_level_variable_list,
            'year':date.year,
            'month':date.month,
            'day': date.day,
            'time': hour_list,
            'area': coordinates,
            'grid': grid,
            'format':'netcdf'
            },
            surface_level_output_file
        )

        # Pressure level variable download
        pressure_level_output_filename = 'pressure_level_variables_'+date.strftime('%Y%m%d')+'.nc'
        pressure_level_output_file = os.path.join(output_dir,pressure_level_output_filename)

        c = cdsapi.Client()

        c.retrieve('reanalysis-era5-complete', 
            {   
            'class': 'ea',
            'expver': '1',
            'stream': 'oper',
            'type': 'an',
            'levtype': 'ml',
            'levelist': '137',
            'param': '130/131/132/133',
            'date': date.strftime('%Y-%m-%d'),
            'time': '00/to/23/by/1',
            'area': coordinates,
            'grid': grid, 
            'format'  : 'netcdf',
        }, pressure_level_output_file)

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])


    return
