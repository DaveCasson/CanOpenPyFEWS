import requests
from owslib.ogcapi.features import Features
import pandas as pd
from pathlib import Path
import logging
import copy
import time
# Import local packages
from download_utils import start_thread, get_reference_time
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['logger_name'])

def retrieve_data_from_api(stations, collection, download_variable, datetime_column, api_url, output_dir, other_variables=[], time_limits=False, start_date=None, end_date=None, limit=100000):
    # Set the time limits for the data retrieval
    if time_limits:
        time_ = f"{start_date}/{end_date}"
        logger.info(f"Retrieving {download_variable} from {collection} for the period {time_}")
    else:
        logger.info(f"Retrieving {download_variable} from {collection} with no time limits")

    # Set columns to be saved to the dataframe
    query_variables = [
                    "STATION_NUMBER",
                    "STATION_NAME"
                    ]
    
    # Append additional query variables
    query_variables.append(datetime_column)
    query_variables.append(download_variable)
    query_variables = query_variables + other_variables
    logger.info(f"Query variables: {query_variables}")

    # Output data frame to csv file
    collection_output_dir = Path(output_dir, collection)
    collection_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {collection_output_dir}")

    # Instantiate features
    oafeat = Features(api_url)

    # List of stations with no water level data
    stations_with_data = copy.copy(stations)
    stations_without_data = []

    # Create a session
    session = requests.Session()

    # Data retrieval and creation of the data frame
    for station in stations:
        path = f"{collection}/items?STATION_NUMBER={station}&limit={limit}"
        if time_limits:
            path += f"&datetime={time_}"
        
        #logger.info(f"Query URL: {path}")
        
        # Retry logic with exponential backoff
        retries = 5
        backoff_factor = 1

        for retry in range(retries):
            try:
                response = session.get(f"{api_url}/{path}")
                response.raise_for_status()  # Raise an exception for HTTP errors
                data = response.json()
                logger.info(f"Data retrieved for station {station}")
                break
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {retry + 1}/{retries} failed: {e}")
                if retry < retries - 1:
                    sleep_time = backoff_factor * (2 ** retry)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to retrieve data for station {station} after {retries} attempts")
                    stations_without_data.append(station)
                    stations_with_data.remove(station)

        if station in stations_without_data:
            continue
        
        # Process and save the data
        records = data.get("features", [])
        if records:
            historical_data_df = pd.DataFrame.from_records([record["properties"] for record in records])
            historical_data_df.set_index(datetime_column, inplace=True, drop=True)
            
            output_csv_path = Path(collection_output_dir, f'{station}.csv')
            historical_data_df.to_csv(output_csv_path, index=True)
            
            logger.info(f"{download_variable} from {collection} for station {station} output to {output_csv_path}")
        else:
            stations_without_data.append(station)
    
    # Removing hydrometric stations without water level data from the station list
    for station in stations_without_data:
        logger.warning(f"Station {station} has no {download_variable} data for the chosen time period.")
        stations_with_data.remove(station)
    
    # Raising an error if no station is left in the list
    if not stations_with_data:
        raise ValueError(f"No {download_variable} data was returned from {collection}, please check the query.")
    
    return stations_with_data

def download_from_eccc_api(cmd_dict,collection, data_source='ECCC_API'):

    station_csv = Path(cmd_dict['output_dir'], cmd_dict[data_source]['station_csv'])
    hydro_stations_df = pd.read_csv(station_csv)
    search_stations = hydro_stations_df["ID"].tolist()
    #logger.info(f'Search stations: {hydro_stations_df}')
    
    url_base = cmd_dict[data_source]['url_base']
    limit = cmd_dict[data_source]['limit']
    output_dir = cmd_dict['output_dir']
    
    # Read model specific settings
    datetime_column = cmd_dict[data_source][collection]['datetime_column']
    download_variables = cmd_dict[data_source][collection]['download_variables']
    #for download_variable in download_variables:
    retrieve_data_from_api(search_stations, collection, download_variables[0], datetime_column, url_base, output_dir)
    if ds_dict['xml_log']:
        log2xml(ds_dict['log_file'], ds_dict['log_xml_file'])
    
    return
