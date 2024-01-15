"""

CanOpenPyFEWS

Data Access and Download for Operational Hydrological Forecasting

This script provides functionality to download various types of hydrological data
from multiple sources. It supports downloading and processing data from services
such as ECCC NWP, ECCC Reanalysis Precipitation, ECCC Radar, SNOWCAST, GLOBSNOW, and SNODAS.

The script utilizes external modules for specific download and processing tasks,
and logs its operations for better traceability and debugging.


"""

import argparse
import logging
from pprint import pprint

# Import local data download scripts
import get_eccc_nwp
import get_eccc_gridded_precip
import get_eccc_radar
import get_snowcast
import get_snodas
import get_era5

# Note import get_globsnow is done in download_data function, to avoid unneeded netCDF4 dependency

# Import local utility scripts
from get_run_info_utils import read_cmd_line, add_run_info_to_cmd_dict, read_default_arguments
from logging_utils import set_logger, log2xml
from download_settings import read_download_settings
from logging_utils import set_logger
from download_utils import run_download_threads

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = set_logger(ds_dict['log_file'], ds_dict['logger_name'], logging.DEBUG)


def download_data(data_source, cmd_dict, model=None):
    """
    Download data from the specified source.

    This function initiates the download process for a given data source. It reads
    the download commands, builds the download threads, and runs them. For certain
    data sources like GLOBSNOW, additional processing is done after downloading.

    Parameters:
    - data_source (str): The name of the data source to download data from. 
                         Options include 'ECCC_NWP', 'ECCC_PRECIP_GRID', 'ECCC_RADAR',
                         'SNOWCAST', 'GLOBSNOW', 'SNODAS'.
    - cmd_dict (dict): Dictionary containing command line arguments or parameters 
                       necessary for the download process.
    - model (optional): The model to use for data processing, if applicable.

    Raises:
    - ValueError: If an unknown data source is specified.
    """

    logger.debug(f'Running with following settings')
    logger.debug(pprint(cmd_dict))
    if data_source == 'ECCC_NWP':
        logger.info('Reading ECCC NWP download commands')
        download_threads = get_eccc_nwp.build_threads(cmd_dict, data_source='ECCC_NWP', model=model)
        run_download_threads(download_threads)

    elif data_source == 'ECCC_PRECIP_GRID':
        logger.info('Reading ECCC Precip Grid download commands')
        download_threads = get_eccc_gridded_precip.build_threads(cmd_dict,data_source='ECCC_PRECIP_GRID',model=model)
        run_download_threads(download_threads)
    
    elif data_source == 'ECCC_RADAR':
        logger.info('Reading ECCC Radar download commands')
        download_threads = get_eccc_radar.build_threads(cmd_dict)
        run_download_threads(download_threads)
    
    elif data_source == 'SNOWCAST':
        logger.info('Reading SNOWCAST download commands')
        download_threads = get_snowcast.build_threads(cmd_dict)
        run_download_threads(download_threads)
    
    elif data_source == 'GLOBSNOW':
        import get_globsnow
        logger.info('Reading GLOBSNOW download commands')
        download_threads, download_dates,filenames = get_globsnow.build_threads(cmd_dict)
        run_download_threads(download_threads)
        get_globsnow.process_downloads(download_dates, filenames, cmd_dict)

    elif data_source == 'SNODAS':
        logger.info('Reading SNODAS download commands')
        download_threads = get_snodas.build_threads(cmd_dict)
        run_download_threads(download_threads)

    elif data_source == 'ERA5':
        logger.info('Reading ERA5 download commands')
        get_era5.download_era5(cmd_dict)
    else:
        raise ValueError(f"Unknown data source: {data_source}")
    
    logger.info(f'Download of data for {data_source} finished')
    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return 

def mainscript(run_info_file, data_source, use_default_settings=True, model=None):
    """
    Main script for initiating the data download process.

    This function starts the process of downloading data from a specified source. 
    It can either use default settings or read command line arguments for configuration. 
    After setting up the necessary parameters, it calls the download_data function to 
    perform the actual download.

    Parameters:
    - data_source (str): The name of the data source to download data from.
    - use_default_settings (bool, optional): Flag to indicate whether to use default settings 
      or command line arguments. Defaults to True.
    - model (str, optional): Specifies the model to be used in the download process, 
      particularly relevant for certain data sources like ECCC NWP.

    The function logs the start of the download process, reads the necessary run info and arguments,
    initiates the download process, and logs the completion of the process.
    """

    logger.info(f'Initiating download for data source: {data_source}')

    #Check whether default settings (stored in yaml) or command line arguments should be used
    if use_default_settings:
        logger.info('Started download script, and reading default arguments')
        cmd_dict = read_default_arguments()
    else:
        logger.info('Started download script, and reading command line arguments')
        cmd_dict = read_cmd_line()

    #Read run info file, overwriting the default if specified in command line
    if run_info_file is not None:
        cmd_dict['run_info_file'] = run_info_file
    cmd_dict = add_run_info_to_cmd_dict(cmd_dict)

    #Download data
    download_data(data_source, cmd_dict, model)

    #Log completion of download process
    logger.info('Download data script finished')
    if cmd_dict['xml_log']:
        log2xml(cmd_dict['log_file'], cmd_dict['xml_log_file'])

if __name__ == '__main__':

    """
    The script's entry point when executed as a standalone program.

    This block sets up command line argument parsing and calls the mainscript 
    function with the appropriate arguments. It allows the user to specify the data 
    source, whether to use default settings, and the model (if applicable).

    """
    # Create a command line argument parser
    parser = argparse.ArgumentParser(description='Download data from an online source.')
    
    # Add command line arguments
    parser.add_argument('--run_info_file', type=str, default=None, help='Run info file for data download')
    parser.add_argument('--data-source', type=str, default='ECCC_NWP', help='Specify the data source.')
    parser.add_argument('--model', type=str, default='RDPS', help='When ECCC NWP used for data source, model should also be specified')
    parser.add_argument('--use-default-settings', action='store_true', default=True, help='Use settings provided in accompanying yaml file')
    
    # Parse the command line arguments
    args = parser.parse_args()

    #Testing block - set arguments below to test the script
    # NOTE: Be sure to comment again once complete testing!

    args.data_source = 'ECCC_NWP'
    
    # Model setting only needed for ECCC_NWP
    #args.model = 'HRDPS'

    # Call mainscript with the parsed arguments
    mainscript(args.run_info_file, args.data_source, args.use_default_settings, args.model)