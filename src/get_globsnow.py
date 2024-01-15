''' 

 Script to harvest GLOBSNOW daily SWE and SE products

 Original script credit: Micha Werner
 Refactored by Dave Casson
 
 Downloads daily file from website
 Adds date/time stamp now in file mame to make the NC file NetCDF-CF compliant
 
 Downlaods the the data between start and end time 
 
 Can be run with command line arguments
 1. Name of XML run file (exported from FEWS - contains paths)
 2. Mode time step (in hours)
 4. Maximum lead time to download (in hours)

'''

import os, sys
import time
import datetime as dt
import gzip
import netCDF4 as nc
import numpy as np
import logging
import threading
from pathlib import Path

#Import local packages
from download_utils import start_thread
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['log_file'])

def Gunzip(fileName):
        '''Gunzip the given file.'''
        try:
            r_file = gzip.GzipFile(fileName, 'rb')
            write_file = str.strip(fileName, '.gz')
            w_file = open(write_file, 'wb')
            w_file.write(r_file.read())
            w_file.close()
            r_file.close()
            os.unlink(fileName) # Yes this one too.
        except:
            message = "Gunzip failed. Exception type: " + str(sys.exc_info()[0])  + ", Exception: " + str(sys.exc_info()[1]) 
            logger.debug(message)
            return None
        
        return w_file.name

def Gzip(fileName, storePath):
        '''Gzip the given file and then remove the file.'''
        if not storePath:
            pathName = os.path.split(fileName)[0]
            fileName = os.path.split(fileName)[1]
            curdir   = os.path.realpath(os.curdir)
            os.chdir(pathName)

        r_file = open(fileName, 'rb')
        w_file = gzip.GzipFile(fileName + '.gz', 'wb', 9)
        w_file.write(r_file.read())
        w_file.flush()
        w_file.close()
        r_file.close()
        
        os.remove(fileName)
        #os.unlink(fileName) #We don't need the file now
        if not storePath:
            os.chdir(curdir)
            
           
def ncAddTime(ncFile, timeValue, formatString):
    """Add time to the NetCDF file to make it CF compliant"""

    rootgrp = nc.Dataset(ncFile,'r+' , format='NETCDF4')

    # check if the time variable already exists - if not create and fill it    
    time_variables = rootgrp.get_variables_by_attributes(standard_name='time')

    if len(time_variables) == 0: # this means that there is no time variable - then add
        logger.debug('Writing time [%s] to NetCDF File ' %timeValue)
        rootgrp.createDimension("time", 0)
        image_time = rootgrp.createVariable("time","f8",("time",))
        
        image_time.units = 'hours since 1990-01-01 00:00:00.0'
        image_time.calendar = 'gregorian'
        image_time.standard_name = 'time'
        image_time.long_name = 'Hours Since 1990-01-01_000000.0'
        
        TimeObj = time.strptime(timeValue,formatString)
        
        image_time[0] = nc.date2num(dt.datetime(TimeObj[0],TimeObj[1],TimeObj[2],TimeObj[3]),units=image_time.units,calendar=image_time.calendar)
        rootgrp.sync()
    else:
        logger.debug('Skipping writing time to NetCDF File as it already exists')

    rootgrp.close()

def ncFlipGrid(ncFile, parameter):
    """Routine to flip the NC grid of the given variable - flips L-R"""
    
    rootgrp = nc.Dataset(ncFile,'r+' , format='NETCDF4')

    # retrieve the variable to an numpy grid
    logger.debug('Retrieving grid for variable %s from %s' %(parameter, ncFile))
    variable = rootgrp.variables[parameter]
    
    #flip the variable
    logger.debug('Flipping variable  %s in file %s' %(parameter, ncFile))
    '''
    for dname, the_dim in rootgrp.dimensions.iteritems():
        print dname, len(the_dim)
    '''
    # check if this one has already been flipped
    if parameter+'_FLIPPED' in rootgrp.variables:
        rootgrp.close()
        return
    
    logger.info(variable.dimensions)
    flipped_variable = rootgrp.createVariable(parameter+'_FLIPPED','f4',variable.dimensions, fill_value=-9999)
    
    flipped_variable.standard_name = variable.standard_name+'_flipped'
    flipped_variable.coordinates  = variable.coordinates
    flipped_variable.units= variable.units
    flipped_variable.long_name = variable.long_name

    
    rootgrp.variables[parameter+'_FLIPPED'][:,:] = np.fliplr(variable)    #np.zeros(np.shape(flipped_variable), dtype=float)

    rootgrp.sync()
    
    logger.debug('Retrieving grid for variable %s from %s' %(parameter, ncFile))

    rootgrp.close() 

def getDataSet(url, verbose):

    logger.info('Getting dataset from URL %s' % url)
    try:
        dataSet  = nc.Dataset(url) # opendap(url_grid) # when netCDF4 was not compiled with OPeNDAP
    except:
        message = "Reading URL failed. Exception type: " + str(sys.exc_info()[0])  + ", Exception: " + str(sys.exc_info()[1]) 
        if verbose:
            logger.debug(message)
        return None
    return dataSet
    
def build_threads(cmd_dict,data_source = 'GLOBSNOW'):

    output_dir = cmd_dict['output_dir']
    max_num_threads = cmd_dict['max_num_threads']

    url_base = cmd_dict[data_source]['url_base']

    num_days_back = cmd_dict[data_source]['num_days_back']
    delay_hours = cmd_dict[data_source]['delay_hours']

    threadLimiter = threading.BoundedSemaphore(max_num_threads) #Additional Variable to Control Threading, defined even if threading not used
    logger.info(f'Threading enabled with maximum number of threads = {max_num_threads}')

    # calculate the number of days to download
    end_time = dt.datetime.utcnow() - dt.timedelta(hours=delay_hours)
    start_time = end_time - dt.timedelta(days=num_days_back)

    logger.debug(f'Downloading Globsnow product for {num_days_back} starting at {start_time}')

    download_threads = list()
    download_dates = list()
    filenames = list()

    for day in range(0,num_days_back+1):
            
        download_date = start_time + dt.timedelta(days=day)

        filename = 'GlobSnow_SWE_L3A_' + download_date.strftime('%Y%m%d') + '_v.1.0.nc.gz' 
        url = url_base + '/'  + download_date.strftime('%Y') + '/' + 'data' + '/' + filename

        logger.debug('Preparing download for url [%s]' %url)

        download_threads.append(start_thread(url, output_dir, filename,threadLimiter,max_num_threads))

        filenames.append(filename)
        download_dates.append(download_date)

    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return download_threads, download_dates, filenames
 
def process_downloads(download_dates,filenames, cmd_dict):

    #Filter for the files that have been downloaded

    output_dir = cmd_dict['output_dir']
    parameter = cmd_dict['GLOBSNOW']['parameter']

    for download_date,filename in zip(download_dates,filenames):

        file_path = Path(output_dir, filename)
        if not file_path.is_file():
            logger.info(f'File {filename} not found in {output_dir}. No processing performed.')
            continue

        # Unzip the downloaded file
        unzippedFile = Gunzip(str(file_path))
        
        # Add time to the NetCDF file to make it CF compliant
        ncAddTime(unzippedFile, download_date.strftime('%Y%m%d'),'%Y%m%d')

        # Flip the grid
        ncFlipGrid(unzippedFile, parameter)
        
        # Gzip the file again
        Gzip(unzippedFile,file_path)

        logging.info(f'GLOBSNOW file processed and output to {file_path}')
        
    if ds_dict['xml_log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return




