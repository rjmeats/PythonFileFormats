import os
import sys
import re
import csv

import JPEG  
import MapURLs

def getCSVHeader() :
    return ["Filename", "Size (bytes)", "Make", "Model", "Software", "Timestamp", "Columns", "Rows", "Latitude", "Longitude", "Altitude (m)", "FromGPS", 
            "OSMaps URL", "Google Maps URL", "Google Street View URL" ]

def processJpegFile(dirName, jpegFileName) :
    fullPath = dirName + "\\" + jpegFileName

    try :
        p = JPEG.processFile(fullPath)
    except Exception as e :
        print("Exception processing JPEG file:", fullPath, " : ", e, file=sys.stderr)
        p = ""

    l = []
    l.append(p['filename'])
    l.append(p['bytes'])
    l.append(p['make'] if 'make' in p else '')
    l.append(p['model'] if 'model' in p else '')
    l.append(p['software'] if 'software' in p else '')
    l.append(p['timestamp'] if 'timestamp' in p else '')    # NB Excel will automatically convert / display this as its own date/time format
    l.append(p['columns'] if 'columns' in p else '')
    l.append(p['rows'] if 'rows' in p else '')
    l.append(p['latitude'] if 'latitude' in p else '')
    l.append(p['longitude'] if 'longitude' in p else '')
    l.append(p['altitude'] if 'altitude' in p else '')
    fromGPS = '' 
    if 'latitude' in p :
        fromGPS = 'Y' if p['fromGPS'] else 'N'
    l.append(fromGPS)

    if 'latitude' in p and 'longitude' in p:
        zoomLevel = 16
        l.append(MapURLs.urlForOrdnanceSurveyMaps(p['latitude'], p['longitude'], zoomLevel))
        l.append(MapURLs.urlForGoogleMaps(p['latitude'], p['longitude'], zoomLevel))
        l.append(MapURLs.urlForGoogleMapsStreetView(p['latitude'], p['longitude']))

    # Convert to a CSV line for output
    return str(p), l

# Only deal with files with a .jpeg or .jpeg file extension
p = re.compile(r"^.*\.jpe?g$", re.IGNORECASE)
def isJpegName(n) :
    return p.match(n)

# Extract a list of (directory-path, filename) tuples for all the JPEG files under
# this directory, recursing into sub-directories.
def processDirectory(topdir) :
    outputList = []
    
    # os.walk returns a generator object which produces a tuple for each directory
    # in the filesystem tree beneath (and including) our top-level directory:
    # - directory name
    # - list of sub-directories directly under this directory
    # - list of files in this directory

    for dirpath, dirnamesList, filenamesList in os.walk(topdir) :
        outputList.extend([(dirpath, name) for name in filenamesList if isJpegName(name)])

    return outputList


#
####################################
#

def main(location) :

    if os.path.isdir(location) :
        jpegFilesList = processDirectory(location)
    elif os.path.isfile(location) :
        dirname, filename = os.path.split(location)
        if isJpegName(filename) :
            jpegFilesList = [(dirname, filename)]
        else :
            print('*** ', location, " is not a JPEG file name")
            exit()
    else :
        print('*** ', location, " is not a file or directory name")
        exit()

    print("Found", len(jpegFilesList), "JPEG file(s) to process under", location)

    CSVFileName = "JPEGs.csv"
    with open(CSVFileName, "w", newline="") as csvfile:
        myCSVWriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvHeader = getCSVHeader()
        myCSVWriter.writerow(csvHeader)
        n = 0
        for dirName, jpegFileName in jpegFilesList :
            n += 1
            (dict, summaryList) = processJpegFile(dirName, jpegFileName)
            myCSVWriter.writerow(summaryList)
            if n % 10 == 0 :
                print(" .. ", n, "/", len(jpegFilesList), " .. ", dirName, jpegFileName)

    print("Produced CSV file:", CSVFileName)
#
####################################
#

if __name__ == "__main__" :

    if len(sys.argv) == 1 :
        print("No directory/file name command line argument provided")
        exit()

    location = sys.argv[1]
    main(location)
