
"""

Download settings

This script contains functions for download settings.
Principally reading default settings from a yaml file, and setting file paths.


"""
import os
import yaml

def read_download_settings(download_settings_file='..\settings\data_download_settings.yaml'):
    """Function to read download settings from yaml file"""

    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, download_settings_file)

    with open(file_path, 'r') as file:
        download_settings_dict = yaml.safe_load(file)

    #Resolve relative paths
    download_settings_dict['output_dir'] = os.path.join(dir_path, download_settings_dict['output_dir'])
    download_settings_dict['log_file'] = os.path.join(download_settings_dict['output_dir'], download_settings_dict['log_file'])
    download_settings_dict['log_xml_file'] = os.path.join(download_settings_dict['output_dir'], download_settings_dict['log_xml_file'])

    return download_settings_dict
