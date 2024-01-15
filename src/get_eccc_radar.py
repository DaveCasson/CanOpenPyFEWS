'''

This script is used to download radar data provided by Environment and Climate 
Change Canada. The script can be used either in as stand-alone via command-line script, or via connection with Delft-FEWS software.

This script can be run from the command line, to facilitate use with arguments defined in Delft-FEWS.

Data Source: https://hpfx.collab.science.gc.ca/
Documentation: https://eccc-msc.github.io/open-data/msc-datamart/readme_en/
Data License: https://climate.weather.gc.ca/prods_servs/attachment1_e.html

'''

#Import required libraries
import datetime as dt
import threading
import logging

#Import local packages
from download_utils import start_thread, get_reference_time
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])

def get_reference_time(basis_unit_minutes):
    now = dt.datetime.utcnow()

    minutes_past_hour = now.minute
    nearest_basis = round(minutes_past_hour / basis_unit_minutes) * basis_unit_minutes

        # If the adjusted time is in the next hour, handle the hour increment
    if nearest_basis >= 60:
        adjusted_time = now.replace(minute=nearest_basis, hour=adjusted_time.hour - 1)
    else:
    # Adjusting the time
        adjusted_time = now.replace(minute=nearest_basis, second=0, microsecond=0)



    return adjusted_time

def create_timestamps(timestep_minutes, delay_minutes, search_period_hours):
    """Create the timestamps used for the url and file name """

    # Use the reference time and subtract the defined delay
    endTime = get_reference_time(timestep_minutes) - dt.timedelta(minutes=delay_minutes)
    startTime = get_reference_time(timestep_minutes) - dt.timedelta(hours=search_period_hours)

    logger.info(f'Preparing to download files from: {endTime} to {startTime}')

    timestamps = []
    currentTime = startTime
    while currentTime <= endTime:
        timestamps.append(currentTime)
        currentTime += dt.timedelta(minutes=timestep_minutes)

    return timestamps

def create_file_and_url_list(url_base,data_type,timestamps):
    """Create the file and url list needed to download files"""
    file_list = []
    url_list =[]

    for timestamp in timestamps:
        timestamp_day_str = timestamp.strftime("%Y%m%d")
        timestamp_minute_str = f'{timestamp.strftime("%Y%m%d")}T{timestamp.strftime("%H%M")}'

        if data_type == 'composite':
            file_name = f'{timestamp_minute_str}Z_MSC_Radar-Composite_MMHR_1km.tif'
            file_list.append(file_name)
            url_list.append(f'{url_base}{timestamp_day_str}/radar/{data_type}/{timestamp_minute_str}Z_MSC_Radar-Composite_MMHR_1km.tif')
        else:
            logger.error(f'Data type {data_type} is not yet defined. Please check and update python script as needed.')

    return file_list, url_list

def build_threads(cmd_dict,data_source = 'ECCC_RADAR'):
    
    #Read general settings
    output_dir = cmd_dict['output_dir']
    max_num_threads = cmd_dict['max_num_threads']

    url_base = ds_dict[data_source]['url_base']
    radar_data_type = ds_dict[data_source]['data_type']
    username = ds_dict[data_source]['username']
    password = ds_dict[data_source]['password']

    delay_minutes = cmd_dict[data_source]['delay_minutes']
    timestep_minutes = cmd_dict[data_source]['timestep_minutes']
    search_period_hours = cmd_dict[data_source]['search_period_hours']

    #Create timestamps
    timestamps = create_timestamps(timestep_minutes, delay_minutes,search_period_hours)

    #Create file and url lists
    file_list, url_list = create_file_and_url_list(url_base, radar_data_type,timestamps)

    #Create empty list for threads
    threadLimiter = threading.BoundedSemaphore(max_num_threads) #Additional Variable to Control Threading, defined even if threading not used
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    download_threads = []

    for url, file in zip(url_list, file_list):
        download_threads.append(start_thread(url,output_dir,file,threadLimiter,max_num_threads,username,password))

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads



    