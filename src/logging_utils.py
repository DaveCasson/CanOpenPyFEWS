
import os, sys
import logging

def set_logger(logfilename,loggername,thelevel=logging.INFO):
    """
    Set-up the logging system and return a logger object. Exit if this fails
    """

    try:    
        #create logger
        logger = logging.getLogger(loggername)
        if not isinstance(thelevel, int):
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(thelevel)
        ch = logging.FileHandler(logfilename,mode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        #create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        #add formatter to ch
        ch.setFormatter(formatter)
        console.setFormatter(formatter)
        #add ch to logger
        logger.addHandler(ch)
        logger.addHandler(console)
        logger.debug("File logging to " + logfilename)
        return logger
    except IOError:
        print( "ERROR: Failed to initialize logger with logfile: " + logfilename)
        sys.exit(2)



def log2xml(logfile,xmldiag):
    """
    Converts a text log file to a Delft-Fews XML diag file
    """
    trans = {'WARNING': '2', 'ERROR': '1', 'INFO': '3','DEBUG': '4'}
    if os.path.exists(logfile):
        ifile = open(logfile,"r")
        ofile = open(xmldiag,"w")
        all = ifile.readlines()

        ofile.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        ofile.write("<Diag xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" \n")
        ofile.write("xmlns=\"http://www.wldelft.nl/fews/PI\" xsi:schemaLocation=\"http://www.wldelft.nl/fews/PI \n")
        ofile.write("http://fews.wldelft.nl/schemas/version1.0/pi-schemas/pi_diag.xsd\" version=\"1.2\">\n")
        for aline in all:
            try:
                lineparts = aline.strip().split(" - ")
                ofile.write("<line level=\"" + trans[lineparts[2]] + "\" description=\"" + lineparts[3] + " [" + lineparts[0] + "]\"/>\n")
            except:
                print( 'Could not convert line to XML log')
        ofile.write("</Diag>\n")
        ifile.close()
        ofile.close()