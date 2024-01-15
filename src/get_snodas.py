"""

Get SNODAS

Snow Data Assimilation System (SNODAS)


This data set contains snow pack properties, such as depth and snow water equivalent (SWE), from the NOAA National Weather Service's National Operational Hydrologic Remote Sensing Center (NOHRSC) SNOw Data Assimilation System (SNODAS). 
SNODAS is a modeling and data assimilation system developed by NOHRSC to provide the best possible estimates of snow cover and associated parameters to support hydrologic modeling and analysis.

National Operational Hydrologic Remote Sensing Center. 2004. Snow Data Assimilation System
(SNODAS) Data Products at NSIDC, Version 1. Boulder, Colorado USA.
NSIDC: National Snow and Ice Data Center. https://doi.org/10.7265/N5TB14TC. 

"""
import logging
import datetime as dt
import threading

#Import local packages
from download_utils import start_thread
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])

def build_threads(cmd_dict,data_source = 'SNODAS'):

    output_dir = cmd_dict['output_dir']
    max_num_threads = cmd_dict['max_num_threads']

    url_base = cmd_dict[data_source]['url_base']
    parameters = cmd_dict[data_source]['parameters']
    num_days_back = cmd_dict[data_source]['num_days_back']
    file_suffixes = cmd_dict[data_source]['file_suffixes']

    # reference time is utc+00 - configurable delay (cfs data is in utc+00)
    ref_date= dt.datetime.utcnow()-dt.timedelta(days=num_days_back)

    threadLimiter = threading.BoundedSemaphore(max_num_threads) #Additional Variable to Control Threading, defined even if threading not used
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    #Create empty list for threads
    download_threads = list()

    for day in range(0,num_days_back):

        ref_date = ref_date+dt.timedelta(days=1)
        ref_date_str = ref_date.date().strftime("%Y%m%d")

        for parameter, file_suffix in zip(parameters, file_suffixes):

            filename = f'{parameter}{ref_date_str}{file_suffix}.grib2'
            url = f'{url_base}{filename}'

            logger.debug('Preparing download for url [%s]' %url) 

            download_threads.append(start_thread(url, output_dir, filename, threadLimiter, max_num_threads))
    
    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads