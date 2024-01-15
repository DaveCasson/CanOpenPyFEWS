"""

Simple script to call the Alberta Environment Data API and download data.

Currently this only downloads snow data for a limited number of hardcoded stations (see params below).

base_url = "https://data.environment.alberta.ca/Services/PCAS/"  
endpoint = "api/PrincipalComponentAnalysis"

TODO: 
- Add logging
- Connect to main download script
- Read start and end date from run_info file to add to request
- Add more stations+parameters

Script by Dave Casson

"""



import requests
import pandas as pd
import argparse
from pathlib import Path
import logging

def call_pca_api(endpoint,base_url,params_list,output_dir):
    """
    Function to call the PCA API and download data
    Response is read as JSON and converted to a pandas dataframe
    Dataframe is saved as a csv file of the station name
    """

    url = base_url + endpoint

    #headers = {'Accept': 'application/json'}
    for params in params_list:

        # Make the GET request
        response = requests.get(url, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Try parsing the response as JSON
            try:
                data = response.json()
                df = pd.DataFrame(data)
                if not df.empty:
                    df.to_csv(f"{output_dir}/{params['StationNumber']}.csv", index=False)
                    logging.info(f"Saved data for station {params['StationNumber']}")
                else:
                    logging.info(f"Empty dataframe for station {params['StationNumber']}")
                
            except ValueError as e:
                # Handle the case where the response is not in JSON format
                logging.info(f"Error parsing response as JSON: {e}")
                logging.info("Raw response:", response.text)
        else:
            logging.warning(f"Failed to retrieve data. Status code: {response.status_code}")

    return

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='Download data from an online source.')
    parser.add_argument('--output-dir', type=str, default='../../../Import/AlbertaAPI', help='Output directory for script')

    # Parse the command line arguments
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()

    
    # Example usage
    base_url = "https://data.environment.alberta.ca/Services/PCAS/"  
    endpoint = "api/PrincipalComponentAnalysis"

    params = [
        {
            "StationId": 38616,
            "StationName": "Sunshine Village",
            "StationNumber": "05BB803",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        },
        {
            "StationId": 38620,
            "StationName": "Three Isle Lake",
            "StationNumber": "05BF824",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        },
        {
            "StationId": 38630,
            "StationName": "Skoki Lodge",
            "StationNumber": "05BJ805",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        },
        {
            "StationId": 39043,
            "StationName": "Lost Creek South",
            "StationNumber": "05BL811",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        },
        {
            "StationId": 39044,
            "StationName": "Mount Odlum",
            "StationNumber": "05BL812",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        },
        {
            "StationId": 39053,
            "StationName": "Wilkinson Summit Bush",
            "StationNumber": "05CA805",
            "TimeSeriesName": "A.DayMax",
            "ParameterTypeName": "SW"
        }
    ]

    call_pca_api(endpoint, base_url, params, output_dir)
