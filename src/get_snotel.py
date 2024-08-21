
"""

Get Environment and Climate Change Canada - Re-analysis Precipitation Data
https://eccc-msc.github.io/open-data/readme_en/

TO DO: Expand documentation

"""


# Import required packages
import threading
import logging
import datetime as dt
import pandas as pd
from pathlib import Path

#Import local packages
from download_utils import start_thread
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])


def build_threads(cmd_dict, data_source='SNOTEL'):

    #Read model independent settings
    max_num_threads = cmd_dict['max_num_threads']
    output_dir = cmd_dict['output_dir']

    station_csv = Path(cmd_dict['output_dir'], cmd_dict[data_source]['station_csv'])
    station_df = df = pd.read_csv(station_csv)

    #Read command line list
    url_base = cmd_dict[data_source]['url_base']

    #Set number of threads
    threadLimiter = threading.BoundedSemaphore(max_num_threads) 
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    download_threads = []

    for index, row in station_df.iterrows():
        station_name_with_spaces = str(row['SITE_NAME'])
        station_name = station_name_with_spaces.replace(" ", "_")
        filename = Path(cmd_dict['output_dir'], f"{station_name_with_spaces}.csv")
        url_site = str(row['SITE_ID']) + ':' + str(row['STATE']) +':SNTL%7Cid=%22%22%7Cname/'
        url_param = 'POR_BEGIN,POR_END/WTEQ::value,PREC::value,PRCP::value,SNWD::value,TAVG::value,WSPDV::value,TMAX::value,TMIN::value,SRADV::value'

        url = url_base + url_site + url_param
        logger.debug('Preparing download for url [%s]' %url)
        download_threads.append(start_thread(url, output_dir, filename,threadLimiter,max_num_threads))

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads
