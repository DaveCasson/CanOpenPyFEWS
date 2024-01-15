import os
from pathlib import Path
import optparse as op
from datetime import *
from xml.etree.ElementTree import *
import logging
from pprint import pprint


from download_settings import read_download_settings
from logging_utils import set_logger

# Initialize the logger with the same settings
ds_dict = read_download_settings()
fews_name_space = ds_dict['fews_name_space']
logger = logging.getLogger(ds_dict['logger_name'])

def read_default_arguments(log_args=False):

    """Function to read default arguments from download_settings.py"""
    ds_dict = read_download_settings()

    # log the command line arguments
    if log_args:
        logger.info(f'Settings: {pprint(ds_dict)}')

    return ds_dict

def read_cmd_line():

    # Get command line arguments

    #First check source argument is given for the data source
    cmdLineArgs = op.OptionParser()
    cmdLineArgs.add_option('--data-source', default='ECCC_NWP', help='Data source to download from', choices=['ECCC_NWP','ECCC_PRECIP_GRID','ECCC_RADAR','SNOWCAST','GLOBSNOW','SNODAS'])
    
    # Check if the source is ECCC_NWP, if so read the model specific command line arguments defaults
    if cmdLineArgs.parse_args()[0].data_source == 'ECCC_NWP':
        cmdLineArgs.add_option('--model',         '-m',  default='HRDPS')
        default_dict = ds_dict[cmdLineArgs.parse_args()[0].data_source][cmdLineArgs.parse_args()[0].model]
    #Else read the source default command line arguments
    else:
        default_dict = ds_dict[cmdLineArgs.parse_args()[0].data_source]

    # Read in the command line arguments, and use the default values if not provided
    cmdLineArgs.add_option('--run_info_file', '-r',  default=ds_dict['run_info_file']) 
    cmdLineArgs.add_option('--output_dir',    '-o',  default=ds_dict['output_dir'])
    cmdLineArgs.add_option('--urlBase',       '-u',  default=default_dict['url_base'])
    cmdLineArgs.add_option('--interval',      '-i',  default=default_dict['interval'])
    cmdLineArgs.add_option('--leadTime',      '-l',  default=default_dict['lead_time']) 
    cmdLineArgs.add_option('--parameter',     '-p',  default=default_dict['parameter'][0]) 
    cmdLineArgs.add_option('--delay',         '-d',  default=default_dict['delay']) 
    cmdLineArgs.add_option('--timestep',      '-t',  default=default_dict['timestep'])
    cmdLineArgs.add_option('--firstLeadTime', '-f',  default=default_dict['first_lead_time'][0])
    cmdLineArgs.add_option('--delay_minutes', '--delay-minutes',  default=10) 
    cmdLineArgs.add_option('--maxThreads',    '-n',  default='10')  
    cmdLineArgs.add_option('--num_days',      '-s',  default='14') 
    
    cmd_options, _ = cmdLineArgs.parse_args()    

    #Read command line options
    cmd_dict = dict()   
    cmd_dict['run_info_file']   = cmd_options.run_info_file
    cmd_dict['model']           = cmd_options.model
    cmd_dict['lead_time']       = int(cmd_options.leadTime)
    cmd_dict['delay_hours']     = int(cmd_options.delay)
    cmd_dict['delay_minutes']   = int(cmd_options.delay_minutes)
    cmd_dict['url_base']        = cmd_options.urlBase
    cmd_dict['parameters']      = cmd_options.parameter
    cmd_dict['first_lead_time'] = int(cmd_options.firstLeadTime)
    cmd_dict['max_num_threads'] = int(cmd_options.maxThreads)
    cmd_dict['num_days_back']   = int(cmd_options.num_days)
    cmd_dict['interval']        = int(cmd_options.interval)
    cmd_dict['timestep']        = int(cmd_options.timestep)

    # Add a key to the cmd dict for the data source
    cmd_dict['data_source'] = cmd_options.data_source

    # Add all options to the cmd_dict data_source key
    cmd_dict[cmd_options.data_source] = dict()
    if cmd_options.data_source == 'ECCC_NWP':
        for key in cmd_dict.keys():
            cmd_dict[cmd_options.data_source][cmd_options.model][key] = cmd_dict[key]
    else:
        for key in cmd_dict.keys():
            cmd_dict[cmd_options.data_source][key] = cmd_dict[key]

    # log the command line arguments
    logger.info(f'Settings: {pprint(cmd_dict)}')

    return cmd_dict

def get_run_info(settings_dict):
    """Function to retrieve run time information from run info file"""
    run_info_file = settings_dict['run_info_file']

    work_dir   = get_element_from_run_info(run_info_file, 'workDir')
    start_time = get_start_time_from_run_info(run_info_file)
    end_time   = get_end_time_from_run_info(run_info_file)
    
    # Add to settings dictionary
    settings_dict['start_time'] = start_time
    settings_dict['end_time']   = end_time
    settings_dict['work_dir']   = work_dir
    
    settings_dict['diagnosticFile']  = get_elements_from_run_info(run_info_file, 'outputDiagnosticFile')
    settings_dict['destinationDir'] =  get_key_value_from_run_info(run_info_file, 'destinationDir', True)
    
    return settings_dict

def add_run_info_to_cmd_dict(cmd_dict):

    # Read run information file if present
    if not Path(cmd_dict['run_info_file']).exists():
        logger.info(f'Run info file not provided, or available at location {cmd_dict["run_info_file"]}')
        cmd_dict['output_dir'] = Path(ds_dict['output_dir']).resolve()
        cmd_dict['xml_log'] = False
    else:
        # in this case a run file is provided as well as other command line arguments        
        cmd_dict = get_run_info(cmd_dict)
        cmd_dict['output_dir'] = cmd_dict['destinationDir']
        if cmd_dict['diagnosticFile']:
            cmd_dict['xml_log'] = True

    cmd_dict['log_file'] = ds_dict['log_file']
    cmd_dict['xml_log_file'] = ds_dict['log_xml_file']

    return cmd_dict

def get_end_time_from_run_info(xmlfile):
    """ 
    Gets the endtime of the run from the FEWS runinfo file
    """
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        edate=runinf.find('.//{' + fews_name_space + '}endDateTime')
        ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
    else:
        print(xmlfile + " does not exist.")
        ed = None
        
    return ed

def get_start_time_from_run_info(xmlfile):
    """ 
    Gets the starttime from the FEWS runinfo file
    """
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        edate=runinf.find('.//{' + fews_name_space + '}startDateTime')
        ttime = edate.attrib['time']
        if len(ttime) ==  12: # Hack for millisecons in testrunner runinfo.xml...
            ttime = ttime.split('.')[0]
        ed = datetime.strptime(edate.attrib['date'] + ttime,'%Y-%m-%d%H:%M:%S')
    else:
        return None
    return ed

def get_element_from_run_info(xmlfile, elmName):
    """
    Gets an element from the run file and returns a string with element content
    """
    elmString = "Empty"
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        
        print(xmlfile)
        
        print('.//{{{0}}}{1}'.format(fews_name_space,elmName))
        
        elmString=runinf.find('.//{{{0}}}{1}'.format(fews_name_space,elmName)).text
        print(elmString)
    else:
        print(xmlfile + " does not exist.")
        
    return elmString

def get_element_property_from_run_info(xmlfile, elmName, elmProperty):
    """
    Gets the property of an element from the run file and returns a string with element content
    """
    propertyString = "Empty"
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        element=runinf.find('.//{' + fews_name_space + '}%s' %elmName)
        propertyString = element.get(elmProperty)
        
    else:
        print(xmlfile + " does not exist.")
        
    return propertyString

def get_key_value_from_run_info(xmlfile, key, Optional):
    """
    Gets the property of a key value pair from the run info file
    """
    keyValue = 'None'
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        # retrieve the properties eleemnt
        propertiesElement=runinf.find('.//{' + fews_name_space + '}properties')
        for propertyElement in propertiesElement:
            if key in propertyElement.get('key') and len(key)==len(propertyElement.get('key')):
                keyValue = propertyElement.get('value')
                print('Property key <{0}> defined as <{1}>'.format(key, keyValue))
        
        if 'None' in keyValue and not Optional:
            print('ERROR: - property with key <{0}> not found in <{1}>'.format(key,xmlfile)) 
        
    else:
        print(xmlfile + " does not exist.")
        
    return keyValue

def get_elements_from_run_info(xmlfile,elementName):
    """
    Gets a list of mapstacks fews expects from the runinfo file
    """
    elementList = list()
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        # loop over the elements to find the input mapstacks
        for element in runinf:
            if elementName in element.tag:
                elementList.append(element.text)
                
            
        
        #edate=runinf.find('.//{' + fews_name_space + '}startDateTime')
        #ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
    else:
        print(xmlfile + " does not exist.")
        
    return elementList