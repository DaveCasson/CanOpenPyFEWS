"""

ECMWF IFS and AIFS downloads

Downloads complete grib2 files from ftp site
IFS original access develop Shahram Sahraei, Hydrologic Forecast Engineer, Hydrologic Forecast Centre, Manitoba Transportation and Infrastructure, November 2022. 
Adapted and integrated by Dave Casson, Feb 2025

"""
import os
import subprocess
import logging
import datetime as dt
import threading
import re
import netCDF4 as nc

#Import local packages
from download_utils import start_thread, get_reference_time
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['logger_name'])

def build_time_strs(timestep,interval,delay_hours,lead_time,first_lead_time):

    # reference time is utc+00 - configurable delay (cfs data is in utc+00)
    refDate = get_reference_time(delay_hours*3600)

    # time stamps
    day_str = refDate.date().strftime("%Y%m%d")
    hour_str = '%02d'%(interval*int(refDate.time().hour/interval))

    # list with lead times to download
    lead_times = list()
    for lead_time in range(first_lead_time, lead_time + timestep,timestep):
        lead_times.append(str(lead_time))

    return day_str, hour_str, lead_times

# Main function to build download threads using settings from YAML.
def build_threads(cmd_dict, data_source='ECMWF', model='IFS'):
    """
    Build download threads based on a YAML config.
    The config should provide keys such as:
      - max_num_threads, output_dir
      - Under the data_source (e.g., 'ECMWF'): model, delay, lead_time, interval, timestep, 
        parameter, first_lead_time, url_base
    """
    # Use the ds_dict from the config for potential XML logging.
    global ds_dict
    ds_dict = cmd_dict

    #model = cmd_dict[data_source].get('model', 'default')
    max_num_threads = cmd_dict['max_num_threads']
    output_dir = cmd_dict['output_dir']

    # Model-specific parameters.
    delay_hours = cmd_dict[data_source][model]['delay']
    lead_time = cmd_dict[data_source][model]['lead_time']
    interval = cmd_dict[data_source][model]['interval']
    timestep = cmd_dict[data_source][model]['timestep']
    first_lead_time = cmd_dict[data_source][model]['first_lead_time']
    url_base = cmd_dict[data_source][model]['url_base']

    threadLimiter = threading.BoundedSemaphore(max_num_threads)
    logger.info(f"Threading enabled with maximum number of threads = {max_num_threads}")

    download_threads = []
    filenames = []

    # Loop through parameters and corresponding first lead times.

    day_str, hour_str, lead_times = build_time_strs(timestep, interval, delay_hours, lead_time, first_lead_time)
    for lead_time_str in lead_times:
        # Build filename following a convention. Adjust as needed.
        filename = f"{day_str}{hour_str}0000-{lead_time_str}h-oper-fc.grib2"
        # Construct the URL. The following assumes a structure similar to your original code.
        url = f"{url_base}/{day_str}/{hour_str}z/{model.lower()}/0p25/oper/{filename}"
        logger.debug(f"Preparing download for URL: {url}")
        download_threads.append(start_thread(url, output_dir, filename, threadLimiter, max_num_threads))
        filenames.append(filename)

    return download_threads, filenames


def parse_filename(filename):
    """
    Parses a filename like '20250224000000-9h-oper-fc.grib2' to extract:
      - forecast_lead: forecast lead time as a 3-digit string (e.g., "009", "012", "138")
    """
    basename = os.path.basename(filename)
    
    # Extract reference time from the first 14 characters
    ref_time_str = basename[:14]  # e.g., "20250224000000"

    # Extract forecast lead time by searching for a pattern like "-9h-"
    m = re.search(r"-(\d+)h-", basename)
    if m:
        forecast_lead_int = int(m.group(1))
    else:
        forecast_lead_int = 000  # default if pattern not found
    
    # Format the forecast lead time as a 3-digit string
    forecast_lead = f"{forecast_lead_int:03d}"
        
    return forecast_lead, ref_time_str

def convert_grib_to_netcdf(cmd_dict, filenames, data_source='ECMWF', model='IFS'):
    """
    Converts each GRIB2 file in 'filenames' (located in the output directory) to a NetCDF file.
    After conversion, parses the filename to determine the forecast lead and reference time, 
    then adds a 'forecast_reference_time' variable with the appropriate attributes.
    Finally, deletes the original GRIB2 file.
    
    The filename is expected to follow the pattern:
      YYYYMMDDHHMMSS-<lead>h-<other_text>.grib2
      
    Parameters:
      cmd_dict (dict): Dictionary with keys 'output_dir' and 'wgrib2_path'.
      filenames (list): List of GRIB2 filenames (strings) in the output directory.
    """
    output_dir = cmd_dict['output_dir']
    wgrib2_exe = cmd_dict['wgrib2_path']
    parameters = cmd_dict[data_source][model]['parameters']
    parameter_str = f"':({'|'.join(parameters)}):'"

    for filename in filenames:
        grib2_path = os.path.join(output_dir, filename)
        

        # Parse the filename to get forecast lead time and reference time string
        forecast_lead, ref_time_str = parse_filename(filename)
        netcdf_filename = f'{ref_time_str}_{forecast_lead}H.nc'
        netcdf_path = os.path.join(output_dir, netcdf_filename)
        logger.debug(f'Converting grib file {filename} to {netcdf_path}')
        # Build the conversion command (customize with additional options if needed)
        cmd = [wgrib2_exe, grib2_path, '-netcdf', netcdf_path,'-match', ':(TPRATE|TMP):']

        try:
            subprocess.run(cmd, check=True)
            print(f"Converted {grib2_path} to {netcdf_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {grib2_path}: {e}")
            continue

        # Delete the original GRIB2 file after a successful conversion
        try:
            os.remove(grib2_path)
            print(f"Deleted {grib2_path}")
        except OSError as e:
            print(f"Error deleting {grib2_path}: {e}")