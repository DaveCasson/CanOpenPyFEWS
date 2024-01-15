''' 

Download utilities for downloading data from the web

'''

import os
import urllib3
import threading
import socket
import logging
import datetime as dt
import certifi

from download_settings import read_download_settings
from logging_utils import log2xml

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict['logger_name'])
timeout = 10
socket.setdefaulttimeout(timeout)

def run_download_threads(download_threads):
    return [thread.join() for thread in download_threads]

def get_reference_time(delay_seconds=0):
    ''' Function to get the reference time for the data download'''
    # reference time is utc+00 - configurable delay (cfs data is in utc+00)

    ref_date= dt.datetime.utcnow()-dt.timedelta(seconds=delay_seconds)

    return ref_date

def start_thread(url,outputDir,filename,threadLimiter,maximumNumberOfThreads, username=None, password=None):
    ''' Function implement threading for data download'''

    thread = threading.Thread(target=data_download, args=(url,outputDir,filename,threadLimiter,maximumNumberOfThreads,username,password))
    thread.start()
       
    return thread

def data_download(url, outputDir, filename, threadLimiter, maximumNumberOfThreads, username=None, password=None):
    ''' Function to download data from url, called by threading'''

    outputFile = os.path.join(outputDir, filename)
    semaphore_acquired = False

    try:
        # Check if file already exists
        if os.path.isfile(outputFile):
            logger.info(f'File {outputFile} already exists. Download cancelled.')
            return False

        # Acquire the semaphore
        threadLimiter.acquire()
        semaphore_acquired = True

        if username is not None and password is not None:
            headers = urllib3.make_headers(basic_auth=f'{username}:{password}')
            http = urllib3.PoolManager(timeout=60, retries=3,cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
            response = http.request('GET',url,preload_content=False,headers=headers)
        else:
            http = urllib3.PoolManager(timeout=60, retries=3,maxsize=5)
            response = http.request('GET',url,preload_content=False)

        # Check if the response was successful
        if response.status < 200 or response.status >= 300:
            logger.warning(f'Failed to download URL {url} with status code: {response.status}')
            response.release_conn()
            return False

        try:
            with open(outputFile, 'wb') as out:
                for data in iter(lambda: response.read(1024), b''):
                    out.write(data)
        except IOError as e:
            logger.warning(f'Error writing to file {outputFile}: {e}')
            response.release_conn()
            return False

        response.release_conn()
        logger.info(f'Downloading URL complete [{url}]')
        return True

    except urllib3.exceptions.NewConnectionError:
        logger.warning(f'New Connection Error for URL {url}')
    except urllib3.exceptions.HTTPError as e:
        logger.warning(f'HTTP Error for URL {url}: {e}')
    except Exception as e:
        logger.warning(f'Unexpected error for URL {url}: {e}', exc_info=True)
    finally:
        if semaphore_acquired:
            threadLimiter.release()
            semaphore_acquired = False

        # Log thread information
        maximumNumberOfThreads = threadLimiter._value  
        activeThreads = threading.active_count() - 1
        logger.debug(f'Maximum Number of Concurrent Threads Allowed = {maximumNumberOfThreads}, Number of Threads Active = {activeThreads}')

    if ds_dict['xml_Log']: log2xml(ds_dict['log_file'],ds_dict['log_xml_file'])

    return
