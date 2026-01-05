
"""

Get Environment and Climate Change Canada - Re-analysis Precipitation Data
https://eccc-msc.github.io/open-data/readme_en/

TO DO: Expand documentation

"""


# Import required packages
import threading
import logging
import datetime as dt

#Import local packages
from download_utils import start_thread
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])

def build_threads(cmd_dict,data_source='ECCC_PRECIP_GRID', model='RDPA'):

    #Read model independent settings
    max_num_threads = cmd_dict['max_num_threads']
    output_dir = cmd_dict['output_dir']

    #Read command line list
    url_base = cmd_dict[data_source][model]['url_base']
    url_detail = cmd_dict[data_source][model]['url_detail']
    num_days_back = cmd_dict[data_source][model]['num_days_back']
    parameters = [cmd_dict[data_source][model]['parameters']]

    delay_seconds = cmd_dict[data_source][model]['delay_hours']*3600

    #Read settings file
    hour_str_list = cmd_dict[data_source][model]['hour_list']
    
    #Set number of threads
    threadLimiter = threading.BoundedSemaphore(max_num_threads) 
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    # reference time is utc+00 - configurable delay (cfs data is in utc+00)
    ref_date= dt.datetime.utcnow()-dt.timedelta(days=num_days_back)-dt.timedelta(seconds=delay_seconds)

    download_threads = []

    for day in range(0,num_days_back):

        ref_date = ref_date+dt.timedelta(days=1)
        day_str = ref_date.date().strftime("%Y%m%d")
       
        for hStr in hour_str_list:
            for parameter in parameters:
                if model == "RDPA":
                    filename =  day_str + 'T' + hStr + 'Z_MSC_RDPA_APCP-Accum6h_Sfc_RLatLon0.09_PT0H.grib2'
                    #filename = 'CMC_'+ model +'_APCP-006-0100cutoff' + parameter + '_ps10km_' + day_str + hStr + '_' + '000' +'.grib2'
                elif model == "HRDPA":
                    filename =  day_str + 'T' + hStr + 'Z_MSC_HRDPA_APCP-Accum6h_Sfc_RLatLon0.0225_PT0H.grib2'
                    #filename = 'CMC_' + model + '_APCP-006-0100cutoff' + parameter + '_ps2.5km_' + day_str + hStr + '_' + '000' + '.grib2'
                #url = url_base + '/' + hStr + '/' + filename
                url = url_base + day_str + url_detail + hStr + '/' + filename
            logger.debug('Preparing download for url [%s]' %url)
            download_threads.append(start_thread(url, output_dir, filename,threadLimiter,max_num_threads))

    #if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads
