"""

Get Snowcast
https://snowcast.ca/

SnowCast is an experimental Canadian Hydrological Model (CHM) data product that downscales the Global Environmental Multiscale (GEM) model forecasts from Environment and Climate Change Canada (ECCC) to provide high resolution snowpack forecasts that take into account variable windflow, solar radiation, precipitation, and temperature over complex terrain.

Downscaling is accomplished through a coupled snow redistribution and ablation model that is run at high resolution. Redistribution is calculated by gravity and wind transport and forest canopy interception. Ablation is calculated by snow sublimation and melt of forest canopy and surface snowpacks.

The model domain is centred over Banff National Park, Canada and extends over a region from the US border north to Mount Robson Provincial Park, and from east of Strathmore, Alberta west to Mara Lake, British Columbia.

SnowCast is developed as part of Global Water Futures Next Generation modelling theme in the Core Modelling Team and the Centre for Hydrology, University of Saskatchewan and in collaboration with Dr. Vincent Vionnet at ECCC. The high-performance computing advances in CHM are made in collaboration with Dr. Raymond Spiteri and Dr. Kevin Green at the Numerical Simulation Lab (USask).

Two GEM forecasts are currently used:

GEM 2.5 km 2-day forecasts (High Resolution Deterministic Prediction System (HRDPS))
[Under development] GEM 25 km 6-day forecasts (Global Deterministic Forecast System (GDPS)

"""

from datetime import datetime, timedelta
import threading
import logging

#Import local packages
from download_utils import start_thread
from download_settings import read_download_settings
from logging_utils import log2xml


# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['logger_name'])

def build_threads(cmd_dict,data_source = 'SNOWCAST'):

    output_dir = cmd_dict['output_dir']
    max_num_threads = cmd_dict['max_num_threads']

    delay_hours = cmd_dict[data_source]['delay_hours']
    url_base = cmd_dict[data_source]['url_base']

    adjusted_current_time = datetime.utcnow() - timedelta(hours=delay_hours)
    start_date = adjusted_current_time - timedelta(days=7)
    end_date = adjusted_current_time

    current_date = start_date

    threadLimiter = threading.BoundedSemaphore(max_num_threads) #Additional Variable to Control Threading, defined even if threading not used
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    download_threads = []

    while current_date <= end_date:
        # Format the URL with the current date
        filename = f'swe_{current_date.strftime("%Y%m%d")}010000.asc'
        url = f"{url_base}{filename}"

        # Add the thread to the list of threads
        download_threads.append(start_thread(url, output_dir,filename,threadLimiter,max_num_threads))

        # Increment the date by one day for the next file
        current_date += timedelta(days=1)

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads

