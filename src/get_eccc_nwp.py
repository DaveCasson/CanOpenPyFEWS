"""

Get Environment and Climate Change Canada - Numerical Weather Prediction Data
https://eccc-msc.github.io/open-data/readme_en/

TO DO: Expand documentation

"""

import logging
import datetime as dt
import threading

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
        lead_times.append('%03d' %lead_time)

    return day_str, hour_str, lead_times

def build_threads(cmd_dict, data_source = 'ECCC_NWP', model = None):

    if model is None:
        model = cmd_dict[data_source]['model']

    #Read model independent settings
    max_num_threads = cmd_dict['max_num_threads']
    output_dir = cmd_dict['output_dir']

    #Read model specific settings
    delay_hours = cmd_dict[data_source][model]['delay']
    lead_time = cmd_dict[data_source][model]['lead_time']
    interval = cmd_dict[data_source][model]['interval']
    timestep = cmd_dict[data_source][model]['timestep']

    parameters = cmd_dict[data_source][model]['parameter']
    first_lead_times = cmd_dict[data_source][model]['first_lead_time']

    threadLimiter = threading.BoundedSemaphore(max_num_threads) #Additional Variable to Control Threading, defined even if threading not used
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    url_base = cmd_dict[data_source][model]['url_base']
    url_detail = cmd_dict[data_source][model]['url_detail']

    #Create empty list for threads
    download_threads = list()
    #Loop through corresponding parameters and first lead times
    for parameter, first_lead_time in zip(parameters, first_lead_times):
        # Calculate lead_times, and strings for day and hour
        day_str, hour_str, lead_times = build_time_strs(timestep, interval, delay_hours, lead_time, first_lead_time)
        # Loop through all lead times
        for lead_time_str in lead_times:
            
            if 'HRDPS' in model: 
                filename = day_str + 'T' + hour_str +'Z_MSC_HRDPS_' + parameter + '_RLatLon0.0225_PT' + lead_time_str +'H.grib2'
            elif 'RDPS' in model:  
                filename = 'CMC_reg_' + parameter + '_ps10km_' + day_str + hour_str + '_P' + lead_time_str +'.grib2'
            elif 'GDPS' in model:
                filename = 'CMC_glb_' + parameter + '_latlon.15x.15_' + day_str + hour_str + '_P' + lead_time_str +'.grib2'
            elif 'REPS' in model:
                filename = day_str + 'T' + hour_str +'Z_MSC_REPS_' + parameter + '_RLatLon0.09x0.09_PT' + lead_time_str +'H.grib2'
            elif 'GEPS' in model:
                filename = 'CMC_geps-raw_' + parameter + '_latlon0p5x0p5_' + day_str + hour_str + '_P' + lead_time_str + '_allmbrs.grib2'
            else:
                raise ValueError(f"Unknown model: {model}")

            #url = url_base + hour_str + '/' + lead_time_str + '/' + filename
            url = url_base + day_str + url_detail + hour_str + '/' + lead_time_str + '/' + filename

            
            logger.debug('Preparing download for url [%s]' %url)
            download_threads.append(start_thread(url, output_dir, filename,threadLimiter,max_num_threads))

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads