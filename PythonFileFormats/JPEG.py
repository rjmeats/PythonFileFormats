import sys
import os

import MapURLs  # My module for providing mapping URLs

# Convert a byte array to an unsigned integer
def bytesToInt(bytes, alignmentIndicator, signed=False) :    
    # Exif / TIFF byte order indicators
    if alignmentIndicator == "MM" :
        alignment = "big"
    elif alignmentIndicator == "II" :
        alignment = "little"
    else :
        alignment = alignmentIndicator

    i = int.from_bytes(bytes, signed=signed, byteorder=alignment)
    return i

def bytesToASCIIString(bytes) :

    if len(bytes) == 0 :
        return ""
    # Remove trailing null used in IFD string elements
    elif bytes[-1] == 0x00 :
        bytes = bytes[0:len(bytes)-1]

    try :
        s = bytes.decode()
    except Exception as e :
        # Not an ASCII string
        s = ""

    return s

# Extract first n bytes up to a 0 byte, expect this to be an ASCII string identifying the type of App Segment, e.g. "Exif"
def getAppSegmentIdentifier(segment) :
    n = 0
    while n < len(segment) and segment[n] != 0x00 :
        n += 1

#    if n == 0 :
#        print("*** Empty Segment identifier: ", len(segment), segment)
#        return ""
    return bytesToASCIIString(segment[0:n])

##
###########################################################################
##

# Read the bytes related to a data segment which consists of 
# - two bytes (big-endian) to indicate the length l in bytes of this segment (including these two bytes)
# - the data bytes, l-2 of them
# ???? Check for reads returning the expected number of bytes
def readDataSegment(f) :
    lenBytes = f.read(2)
    segmentLength = int.from_bytes(lenBytes, signed=False, byteorder='big')
    segmentBytes = f.read(segmentLength-2)
    return segmentLength, segmentBytes

# 'Entropy coded' data segments are laid out differently
# - no initial length bytes
# - just data bytes
# - which may include <FF> data bytes. These are 'stuffed' with a trailing <00> byte to allow
#   genuine <FF> data bytes to be distinguished from the '<FF><markerbyte>' sequence which starts
#   the segment following this one.
# - consequently we can only detect the end of the segment by reading beyond it to find the first
#   <FF><non-00> 2-byte sequence, which we return to allow processing of the subsequent segment by the caller.
# ???? Check for reads returning the expected number of bytes 
def readEntropyCodedDataSegment(f) :
    segmentLength = 0
    dataBytes = f.read(1)
    segmentData = []
    nextSegmentMarkerBytes = bytearray(0)
    while dataBytes :
        dataByte = dataBytes[0]
        if dataByte != 0xFF :       # Normal data            
            segmentLength += 1
            segmentData.append(dataByte)
        else :  # an <FF> - is it the start of the next segment, or does a following <00> indicate it is true data ?
            nextDataBytes = f.read(1)
            nextDataByte = nextDataBytes[0]
            if nextDataByte == 0x00 :
                # Stuffing, add the <FF> and <00> bytes to the segment length count and segment data 
                # ???? Or remove the stuffing here ?
                segmentLength += 2
                segmentData.append(dataByte)
                segmentData.append(nextDataByte)
            elif nextDataByte >= 0xD0 and nextDataByte <= 0xD7 :
                # An RST Restart marker within the encoded data segment, keeping going
                segmentLength += 2
                segmentData.append(dataByte)
                segmentData.append(nextDataByte)
            else :
                # The <FF> is not part of the data, it is the start of the next segment
                nextSegmentMarkerBytes = bytearray(2)
                nextSegmentMarkerBytes[0] = 0xFF
                nextSegmentMarkerBytes[1] = nextDataByte
                break
        dataBytes = f.read(1)

    return segmentLength, segmentData, nextSegmentMarkerBytes

#
#############################################
#

#http://gvsoft.no-ip.org/exif/exif-explanation.html
def processExifSegment(info, segment) :

    # Expect first six bytes to be 'Exif\x00\x00'
    ExifIdentifierLength = 6
    Exif = "Exif"
    if not (segment[0] == Exif.encode()[0] and segment[1] == Exif.encode()[1] and segment[2] == Exif.encode()[2] and segment[3] == Exif.encode()[3] and segment[4] == 0 and segment[5] == 0) :
        print("*** Exif segment header format not as expected:", segment[0:10], file=sys.stderr)
        return

    # The rest is TIFF format content
    TIFF = segment[ExifIdentifierLength:]
    TIFFHeader = TIFF[0:8]

    # - 2 bytes to define the multi-byte number byte alignment indicator 'MM' (Motorola) = big-endian, 'II' (Intel) = little-endian
    byteAlignmentIndicator = bytesToASCIIString(TIFFHeader[0:2])
    #print(byteAlignmentIndicator)
    # - 2 bytes to show TIFF version - expect this to always be set to integer value 0x2A = 42
    TIFFVersion = bytesToInt(TIFFHeader[2:4], byteAlignmentIndicator)
    #print(TIFFVersion)
    # - 4 byte offset within TIFF of the first IFD - usually 8, i.e. bytes immediately after header bytes
    firstIFDOffset = bytesToInt(TIFFHeader[4:8], byteAlignmentIndicator) 
    #print(firstIFDOffset)

    nextIFDOffset = firstIFDOffset
    IFDCount = 0

    # Dictionary to record each IFD, keyed an IFD name, storing the detailed IFD dictionary as the value
    dict = {}

    while nextIFDOffset != 0 :
        IFDname = "IFD" + str(IFDCount)
        #print("Handling main chain IFD:", IFDname)
        IFDentries, nextIFDOffset = processIFD(TIFF, nextIFDOffset, byteAlignmentIndicator)
        dict[IFDname] = IFDentries
        IFDCount += 1

    # Search for embedded IFD elements within the IFDs we've already identified. Assume only one embedded IFD
    # of each type. IFDs can be nested by more than one level, so keep going as long as we find a new IFDs

    continueLooking = True
    while(continueLooking) :
        newIFDinfo = []
        for d in dict.values() :            
            for embeddedIFDtag, embeddedIFDname in knownEmbeddedIFDs().items() :
                # This will re-search all IFDs each time through the loop, not just ones we've added last time
                # around, so ignore embedded IFDs we've already picked up. (Assuming the only exist in one place.)
                if embeddedIFDtag in d and embeddedIFDname not in dict:
                    IFDname = embeddedIFDname
                    embeddedIFDOffset = d[embeddedIFDtag]['value']
                    embeddedIFDentries, nextIFDOffset = processIFD(TIFF, embeddedIFDOffset, byteAlignmentIndicator)
                    # Put info about embedded IFD onto a list, we can't put it directly in the main dictionary
                    # while looping over the dictionary,
                    newIFDinfo.append( (embeddedIFDname, embeddedIFDentries) )
                    if nextIFDOffset != 0000 :
                        print("*** - unexpected next IFD offset in IFD", embeddedIFDname, file=sys.stderr)
        # Can now add the new IFD(s) to the main dictionary
        for additionalIFDname, IFDentries in newIFDinfo :
            dict[additionalIFDname] = IFDentries
        continueLooking = len(newIFDinfo) > 0

    return dict

def knownEmbeddedIFDs() :
    return { 
        34665 : "Exif",
        34853 : "GPS",
        40965 : "Interoperability"
    }

# Add an IFD element (itself a dictionary) to an IFD-level dictionary. If the element's tag does not already exist in the
# IFD dictionary just add the element. If it does, add the element to a list associated with the tag instead.
def addToIFDDictionary (IFDdict, element) :
    tag = element['tag']
    if tag not in IFDdict :
        IFDdict[tag] = element
    else :
        currentValue = IFDdict[tag]
        #print("tag already in dict:", tag, type(currentValue))
        if type(currentValue) is dict :
            # Convert to a list of elements
            IFDdict['tag'] = [currentValue, element]
            #print("... converted to a list: ", IFDdict['tag'])
        elif type(currentValue) is list :
            # Already multiple entries for this tag - append to it
            IFDdict['tag'].append(element)
            #print("... appended to existing list: ", IFDdict['tag'])
        
# Each IFD (Image File Directory) consists of:
# - a two-byte int giving the number of directory elements
# - the 12-byte elements
# - a four-byte offset to the start of the next IFD in this chain, or 0000 if the end of the chain
def processIFD(TIFF, IFDOffset, byteAlignmentIndicator) :

        # List of dictionaries for output, one per IFD element
        IFDEntries = {}

        IFDBytes = TIFF[IFDOffset:]
        # 2 byte value indicating the number of elements
        elementCount = bytesToInt(IFDBytes[0:2], byteAlignmentIndicator)
        # Bytes containing the 12-byte entries
        elementSize = 12
        elementBytes = IFDBytes[2:elementSize*elementCount+2]

        # Then n IFD elements
        for n in range (0, elementCount) :
            thisElementBytes = elementBytes[elementSize*n : elementSize*(n+1)]
            element = processIFDElement(n, thisElementBytes, TIFF, byteAlignmentIndicator)
            addToIFDDictionary (IFDEntries, element)
    
        # The final four bytes are either an offset to the next IFD in the chain, or 0000 if no more IFDs in this chain
        nextOffsetBytesPosition = 2+elementSize*elementCount
        nextIFDOffsetBytes = IFDBytes[nextOffsetBytesPosition: nextOffsetBytesPosition+4]
        nextIFDOffset = bytesToInt(nextIFDOffsetBytes, byteAlignmentIndicator)

        # Return the list of extracted IFD details, and the offset of the next IFD in this chain
        return IFDEntries, nextIFDOffset

# Pull apart each individual 12-byte IFD element and convert it to a value, returning
# information about the element in a dictionary
# - 2-byte tag number - integer identifying the type of data
# - 2-byte format - integer identifying if this is an int, string, etc
# - 4-byte component count - how many items of the above format are in this element
# - 4-byte value/offset - the element value if <= 4 bytes long, otherwise an offset to where the data resides
def processIFDElement(elementNo, element, TIFF, byteAlignmentIndicator) :
    
    tag = bytesToInt(element[0:2], byteAlignmentIndicator)
    dataFormat = bytesToInt(element[2:4], byteAlignmentIndicator)
    componentCount = bytesToInt(element[4:8], byteAlignmentIndicator)
    dataBytes = element[8:12]
    dataBytesAsOffset = bytesToInt(dataBytes, byteAlignmentIndicator)

    implemented = True
    dataValue = "-"
    # 1 = unsigned byte, 1 byte per component, not implemented
    if dataFormat == 1 :
        if componentCount == 1 :
            dataValue = bytesToInt(dataBytes[0:1], byteAlignmentIndicator)
        elif componentCount <= 4:
            dataValue = []
            for i in range (0, componentCount) :
                dataValue.append(bytesToInt(dataBytes[i:i+1], byteAlignmentIndicator))
        elif componentCount > 4 :
            dataValue = []
            for i in range (0, componentCount) :
                offset = dataBytesAsOffset + i
                dataValue.append(bytesToInt(TIFF[offset:offset+1], byteAlignmentIndicator))
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, "(ubyte), num:", componentCount, ", val:", dataValue)
    # 2 = ASCII string, 1 byte per character
    elif dataFormat == 2 :
        if componentCount <= 4:
            dataValue = bytesToASCIIString(dataBytes[0:componentCount])
        else :
            dataValue = bytesToASCIIString(TIFF[dataBytesAsOffset:dataBytesAsOffset+componentCount])
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, "(String), num:", componentCount, ", val:", dataValue)
    # 3 = unsigned short, 2 bytes per component
    elif dataFormat == 3 :
        if componentCount == 1 :
            dataValue = bytesToInt(dataBytes[0:2], byteAlignmentIndicator)
        elif componentCount == 2:
            dataValue = [ bytesToInt(dataBytes[0:2], byteAlignmentIndicator), bytesToInt(dataBytes[2:4], byteAlignmentIndicator) ]
        elif componentCount > 2 :
            dataValue = []
            for i in range (0, componentCount) :
                offset = dataBytesAsOffset + i*2
                dataValue.append(bytesToInt(TIFF[offset:offset+2], byteAlignmentIndicator))
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, "(ushort), num:", componentCount, ", val:", dataValue)
    # 4 = unsigned long, 4 bytes per component
    elif dataFormat in [4, 9] :
        signed = dataFormat == 9
        desc = "(ulong)" if dataFormat == 4 else "(long)"
        if componentCount == 1 :
            dataValue = bytesToInt(dataBytes[0:4], byteAlignmentIndicator, signed)
        elif componentCount > 1 :
            dataValue = []
            for i in range (0, componentCount) :
                offset = dataBytesAsOffset + i*4
                dataValue.append(bytesToInt(TIFF[offset:offset+2], byteAlignmentIndicator, signed))
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, desc, ", num:", componentCount, ", val:", dataValue)
    elif dataFormat in [5, 10] :
        signed = dataFormat == 10
        desc = "(urational)" if dataFormat == 5 else "(rational)"
        values = []
        for i in range (0, componentCount) :
            offset = dataBytesAsOffset + i*8
            numerator = bytesToInt(TIFF[offset:offset+4], byteAlignmentIndicator, signed)
            denominator = bytesToInt(TIFF[offset+4:offset+8], byteAlignmentIndicator, signed)
            values.append( (numerator, denominator) )
        if componentCount == 1 :
            dataValue = values[0]
        else :
            dataValue = values
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, desc, ", num:", componentCount, ", val:", dataValue)
    # 7 = General purpose 'undefined' type. 1 byte per component
    elif dataFormat == 7 :
        if componentCount == 1 :
            dataValue = dataBytes[0:1]
        elif componentCount <= 4:
            dataValue = []
            for i in range (0, componentCount) :
                dataValue.append(dataBytes[i:i+1])
        elif componentCount > 4 :
            dataValue = []
            for i in range (0, componentCount) :
                offset = dataBytesAsOffset + i
                dataValue.append(TIFF[offset:offset+1])
        #print(".. IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, "(undefined), num:", componentCount, ", val:", dataValue[0:12])        
    else :
        implemented = False

    # Put values for the element into a dictionary and return it
    entry = {}
    entry['tag'] = tag
    entry['index'] = elementNo
    entry['format'] = dataFormat
    entry['count'] = componentCount
    entry['value'] = dataValue

    if not implemented :
        entry['unhandled'] = True
        print("*** IFD data type not implemented: IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, ", num:", componentCount, ", bytes:", dataBytes, file=sys.stderr)

    return entry

#
#############################################
#

def processJFIFSegment(info, segment) :
    
    JFIF = "JFIF"
    if not (segment[0] == JFIF.encode()[0] and segment[1] == JFIF.encode()[1] and segment[2] == JFIF.encode()[2] and segment[3] == JFIF.encode()[3] and segment[4] == 0) :
        print("*** JFIF segment header format not as expected:", segment[0:10], file=sys.stderr)
        return

    if len(segment) < 14 :
        print("*** JFIF segment header size not as expected:", len(segment), file=sys.stderr)
        return

    majorversion = segment[5]
    minorversion = segment[6]
    units = segment[7]
    Xdensity = bytesToInt(segment[8:10], 'big')
    Ydensity = bytesToInt(segment[10:12], 'big')
    Xthumbnail = segment[12]
    Ythumbnail = segment[13]

    if len(segment) > 14:
        print("*** JFIF segment header - ignoring data beyond first 14 bytes", len(segment), file=sys.stderr)

    dict = {}
    dict['majorversion'] = majorversion
    dict['minorversion'] = minorversion
    dict['units'] = units
    dict['Xdensity'] = Xdensity
    dict['Ydensity'] = Ydensity
    dict['Xthumbnail'] = Xthumbnail
    dict['Ythumbnail'] = Ythumbnail

    return dict

#
#############################################
#

def processICCProfileSegment(info, segment) :

    # http://www.color.org/specification/ICC1v43_2010-12.pdf 
    # Appendix B.4 explains embedding mechanism for JPEGs, including:
    # - the segment starts with "ICC_PROFILE" and then a NULL byte
    # - followed by two bytes which indicate 'chunking', allowing the ICC Profile info to be split over more than one
    #   JPEG segment if necessary.
    #   - the first byte is the current chunk number
    #   - the second byte is the total number of chunks
    #   So both will be '1' if the ICC Profile info fits into a single JPEG APP segment
    #   And the next 128 bytes are the Profile header info - see 7.2

    ICC_ProfileString = "ICC_PROFILE"    
    thisChunkNo = segment[len(ICC_ProfileString)+1]
    totalChunks = segment[len(ICC_ProfileString)+2]

    # ???? Check profile string is present 

    if not (thisChunkNo == 1 and totalChunks == 1) :
        print("*** ICC profile has more than one chunk:", thisChunkNo, totalChunks, file=sys.stderr)
    
    mainSegmentOffset = len(ICC_ProfileString)+3 
    mainSegment = segment[mainSegmentOffset:]
    header = mainSegment[mainSegmentOffset:mainSegmentOffset+128]

    # Pull out fields from the header
    profileSize = bytesToInt(header[0:4], 'big')
    preferredCMMtype = bytesToInt(header[4:8], 'big')
    profileVersion = header[8:12]
    profileDeviceClass = header[12:16]
    colourSpace = header[16:20]
    profileConnectionSpace = header[20:24]
    profileCreationDate = header[24:36]
    acsp = header[36:40]
    primaryPlatform= header[40:44]
    profileFlags = header[44:48]
    deviceManufacturer = header[48:52]
    deviceModel = header[52:56]
    deviceAttributes = header[56:64]
    renderingIntent = header[64:68]
    nCIEXYZIlluminant = header[68:80]
    profileCreator = header[80:84]
    profileID = header[84:100]
    reservedBytes = header[100:128]

    printOut = False
    if printOut :
        print("size", profileSize)
        print("preferred type", preferredCMMtype)
        print("version", profileVersion)
        print("device class", profileDeviceClass)
        print("colour space", colourSpace)
        print("PCS", profileConnectionSpace)
        print("profile date", profileCreationDate)
        print("- y", bytesToInt(profileCreationDate[0:2], 'big'))
        print("- m", bytesToInt(profileCreationDate[2:4], 'big'))
        print("- d", bytesToInt(profileCreationDate[4:6], 'big'))
        print("- h", bytesToInt(profileCreationDate[6:8], 'big'))
        print("- m", bytesToInt(profileCreationDate[8:10], 'big'))
        print("- s", bytesToInt(profileCreationDate[10:12], 'big'))
        print("acsp", acsp)
        print("platform", primaryPlatform)
        print("flags", profileFlags)
        print("manufacturer", deviceManufacturer)
        print("model", deviceModel)
        print("attributes", deviceAttributes)
        print("intent", renderingIntent)
        print("CIEXYZ illuminant", nCIEXYZIlluminant, nCIEXYZIlluminant[0:4], nCIEXYZIlluminant[4:8], nCIEXYZIlluminant[8:12])
        print("creator", profileCreator)
        print("profileID", profileID)
        print("reserved", reservedBytes)

    # Tag table consists of a 4-byte count 'n' and then n 12-byte entries:
    # - 0-3 = tag signature
    # - 4-7 = offset to tag data element
    # - 8 - 11 = size in bytes of tag data element
    tagTableOffset = 128
    
    tagTableLength = bytesToInt(mainSegment[tagTableOffset:tagTableOffset+4], 'big')

    for n in range(0, tagTableLength) :
        tagEntryOffset = tagTableOffset+4 + 12*n
        tagSignature = bytesToASCIIString(mainSegment[tagEntryOffset+0:tagEntryOffset+4])
        tagDataOffset = bytesToInt(mainSegment[tagEntryOffset+4:tagEntryOffset+8], 'big')
        tagDataSize = bytesToInt(mainSegment[tagEntryOffset+8:tagEntryOffset+12], 'big')
        tagData = mainSegment[tagDataOffset:tagDataOffset+tagDataSize]
        if printOut :
            print("Tag", n, tagSignature, tagDataOffset, tagDataSize)
            print(".. ", tagData[0:150])
    
        # Each of these tag data items has its own structure for potential further examination ...

    # Nothing found so far is general metadata about the image / device, all detailed image stuff. So
    # don't add to the dictionary for now
    dict = {}
    return dict

##
###########################################################################
##

def latLongAsStringNumber(NSEW, latLongTuples, fromGPS) :
    s = ""
    n = 0
    # Check format
    if not NSEW in ["N", "S", "E", "W"] :
        print("*** Unexpected direction indicator:", NSEW, file=sys.stderr)
    elif len(latLongTuples) != 3 :
        print("*** Unexpected latitude/longitude value:", latLongTuples, file=sys.stderr)
    elif (latLongTuples[0][1] != 1) or (latLongTuples[1][1] != 1) :
        print("*** Unexpected latitude/longitude value:", latLongTuples, file=sys.stderr)
    else :
        degrees = latLongTuples[0][0] 
        minutes = latLongTuples[1][0]
        seconds = latLongTuples[2][0] / latLongTuples[2][1]

        s = "{0:d}° {1:02d}' {2:06.4f}\" {3:s}".format(degrees, minutes, seconds, NSEW)

        multiplier = 1
        if NSEW in ["W", "S"] :
            multiplier = -1

        # Round to 5 decimal places. 1 degree at equator ~= 75 miles / 110 km, so rounded to about a metre.
        # But if not from GPS, increase rounding.
        rounding = 5 if fromGPS else 4
        n = round((degrees + (minutes / 60.0) + (seconds / 60.0 / 60.0) ) * multiplier, rounding)  
        return (s,n)

def summariseTags(propertiesDict, allTags, verbose) :

    # Where was the image (photo) produced ?
    if 'GPS' in allTags :
        GPSTags = allTags['GPS']

        # Normally 'GPS' but CELLID also seen, but didn't seem to be an accurate position, or give an altitude
        fromGPS = False
        if 27 in GPSTags:
            processingMethod = GPSTags[27]['value']
            if processingMethod != "GPS" :
                fromGPS = False
                if verbose :
                    print("*** Processing method is not GPS:", processingMethod, file=sys.stderr)
            else :
                fromGPS = True

        NS = None
        latitude = None
        EW = None
        longitude = None
        if 1 in GPSTags :
            NS = GPSTags[1]['value']
        if 2 in GPSTags :
            latitude = GPSTags[2]['value']
        if 3 in GPSTags :
            EW = GPSTags[3]['value']
        if 4 in GPSTags :
            longitude = GPSTags[4]['value']

        if NS and latitude and EW and longitude :
            sLatitude, nLatitude = latLongAsStringNumber(NS, latitude, fromGPS)
            sLongitude, nLongitude = latLongAsStringNumber(EW, longitude, fromGPS)
            propertiesDict['latitude'] = nLatitude
            propertiesDict['longitude'] = nLongitude
            propertiesDict['latitudetext'] = sLatitude
            propertiesDict['longitudetext'] = sLongitude
            propertiesDict['fromGPS'] = fromGPS

        if fromGPS and 6 in GPSTags :
            altitudeTuple = GPSTags[6]['value']
            altitude = round(altitudeTuple[0]/altitudeTuple[1], -2)
            propertiesDict['altitude'] = altitude

        # for k,d in GPSTags.items() :
        #    print(k, d)

    if 'IFD0' in allTags :
        IFD0Tags = allTags['IFD0']
        #for k,d in IFD0Tags.items() :
        #    print(k, d)

        if 306 in IFD0Tags :
            timestamp = IFD0Tags[306]['value']
            if timestamp[0:4] != "0000" :
                propertiesDict['timestamp'] = timestamp

        if 256 in IFD0Tags and 257 in IFD0Tags :
            columns = IFD0Tags[256]['value']
            rows = IFD0Tags[257]['value']
            propertiesDict['columns'] = columns
            propertiesDict['rows'] = rows

        if 271 in IFD0Tags :
            make = IFD0Tags[271]['value']
            propertiesDict['make'] = make

        if 272 in IFD0Tags :
            model = IFD0Tags[272]['value']
            propertiesDict['model'] = model

        if 305 in IFD0Tags :
            software = IFD0Tags[305]['value']
            propertiesDict['software'] = software

        # IFD1 = thumbnail
        # 256, 257, 259, 274, 282, 283, 296, 512, 514
        # 259 6 = thumbnail uses JPEG compression
        # 513, 514 = offset/length of thumbnail JPEG

    if 'Exif' in allTags :
        ExifTags = allTags['Exif']

        # Alternative dimension source
        if not 'columns' in propertiesDict:
            if 40962 in ExifTags and 40963 in ExifTags :
                columns = ExifTags[40962]['value']
                rows = ExifTags[40963]['value']
                propertiesDict['columns'] = columns
                propertiesDict['rows'] = rows

        # Alternative timestamp field
        if not 'timestamp' in propertiesDict :
            if 36867 in ExifTags :
                timestamp = ExifTags[36867]['value']
                if timestamp[0:4] != "0000" :
                    pass
                    propertiesDict['timestamp'] = timestamp

        # Exif segment includes
        # 33434 Exposure
        # 33437 F no
        # 34855 ISO speed
        # 36867 date/time string
        # 37377 shutter speed
        # 37378 aperture
        # 37385 flash
        # 37386 focal length mm


def displayMainProperties(mainProperties) :

    print()

    if 'latitude' in mainProperties :
        latitude = mainProperties['latitude']
        longitude = mainProperties['longitude']
        print("Latitude:", mainProperties['latitudetext'], " = ", latitude)
        print("Longitude:", mainProperties['longitudetext'], " = ", longitude)

        # Maps seem to use a common zoom level domain. 
        # https://wiki.openstreetmap.org/wiki/Zoom_levels
        zoomLevel = 16

        print("OSMaps Link:", "https://osmaps.ordnancesurvey.co.uk/{0:f}%2C{1:f}%2C{2:d}".format(latitude, longitude, zoomLevel))  # No Pn
        print("OSMaps Link:", MapURLs.urlForOSMaps(latitude, longitude, zoomLevel))

        # Google Maps URL API doesn't seem to allow a Pin to be displayed at the lat/long coordinates at the same time as specifying a zoom and a map type
        gpinurl = "https://www.google.com/maps/search/?api=1&query={0:f}%2C{1:f}&zoom={2:d}".format(latitude, longitude, zoomLevel)   # Pin
        print("Google Link:", "https://www.google.com/maps/%40?api=1&map_action=map&center={0:f}%2C{1:f}&zoom={2:d}&basemap=satellite".format(latitude, longitude, zoomLevel)) # No pin
        print("Google Link with Pin:", gpinurl)   # Pin

        # https://wiki.openstreetmap.org/wiki/Browsing#Sharing_a_link_to_the_maps
        osmpinurl = "https://www.openstreetmap.org/?&mlat={0:f}&mlon={1:f}#map={2:d}/{0:f}/{1:f}".format(latitude, longitude, zoomLevel)
        print("OSM Link with Pin:", osmpinurl)   # Pin

        # https://msdn.microsoft.com/en-us/library/dn217138.aspx
        maptitle="title"
        mapnotes="Some notes"
        mapurl="a url"
        mapphoto="a photo url"
        # a = aerial, can also be r for road, h= aerial with labels
        bingparams = "cp={0:f}~{1:f}&lvl={2:d}&style=r&sp=point.{0:f}_{1:f}_{3:s}_{4:s}_{5:s}_{6:s}".format(latitude, longitude, zoomLevel, 
                            maptitle, mapnotes, mapurl, mapphoto)
        bingpinurl = "http://bing.com/maps/default.aspx?" + bingparams

        print("Bing Link with Pin:", bingpinurl)   # Pin

    if 'altitude' in mainProperties :
        print("Rough Altitude:", "{0:.0f} m".format(mainProperties['altitude']))

    if 'timestamp' in mainProperties :
        print("Timestamp:", mainProperties['timestamp'], "GMT")

    if 'columns' in mainProperties :
        print("Size:", mainProperties['columns'], "x", mainProperties['rows'], "pixels")

    if 'make' in mainProperties :
        print("Make:", mainProperties['make'])

    if 'model' in mainProperties :
        print("Model:", mainProperties['model'])

    if 'software' in mainProperties :
        print("Software:", mainProperties['software'])
##
###########################################################################
##

def displayAllTags(allTags) :
    print("#############################################")
    for n,dict in allTags.items() :
        print(n)
        for k,v in dict.items() :
            #print(k, v)
            print(k, v)
    print("#############################################")

def processFile(filename, verbose=False, veryVerbose=False) :

    if verbose :
        print("Reading from:", filename)

    bytecount = 0
    aborted = False
    SOIFound = False
    EOIFound = False

    # Lists with an entry for each segment found. 
    segmentsInfo = []
    segmentsData = []

    with open(filename, "rb") as f:

        # Each time round the read loop try to process a complete segment, with the segment starting with a two byte marker <FF><xx>.
        
        bytes = f.read(2)
        while bytes:

            # Check a few expectations:
            # - the 'bytes' array hold two bytes at the start of the loop, the first being <FF>
            # - the first thing in the file is the SOI marker
            # - we don't expect anything after the EOI marker

            if len(bytes) != 2 :
                print("*** [", bytecount, "]", "Unexpected bytes length: ", len(bytes), ", contents:", bytes, file=sys.stderr)
                aborted = True
                break

            if bytes[0] != 0xFF :
                print("*** [", bytecount, "]", "Expected <FF> but found : ", bytes[0], file=sys.stderr)
                aborted = True
                break

            markerByteDetail = bytes[1]
            # print("Read marker bytes ", bytes, " at ", bytecount)
                    
            segmentInfo = {}
            segmentData = bytearray(0)
            segmentInfo['marker'] = bytes[1]
            segmentInfo['markerOffset'] = bytecount
            segmentInfo['segmentOffset'] = bytecount+2
            bytecount += 2

            # Clear out the array holding the marker bytes. If it's still empty at the end of the loop, we'll read some more. If it's not empty,
            # then segment processing has already read the next 2 bytes for us.
            bytes = bytearray(0)
            
            appSegmentIdentifier = ""

            # NB No switch statement in Python!
            if markerByteDetail == 0xD8 :
                segmentType = 'SOI'
                segmentLength = 0
                SOIFound = True
            elif markerByteDetail == 0xD9 :            
                segmentType = 'EOI'
                segmentLength = 0
                EOIFound = True
            elif markerByteDetail >= 0xE0 and markerByteDetail <= 0xEF :
                segmentType = 'APP' + str(markerByteDetail-0xE0)
                segmentLength, segmentData = readDataSegment(f)
                appSegmentIdentifier = getAppSegmentIdentifier(segmentData)
                if not appSegmentIdentifier :
                    appSegmentIdentifier = "unnamed"
                    #print("Unnamed APP segment:", segmentLength, segmentData)   # ????
            elif markerByteDetail == 0xDB :
                segmentType = 'DQT'
                segmentLength, segmentData = readDataSegment(f)
            elif markerByteDetail == 0xC4 :
                segmentType = 'DHT'
                segmentLength, segmentData = readDataSegment(f)
            elif markerByteDetail == 0xC0 :
                segmentType = 'SOF0'            
                segmentLength, segmentData = readDataSegment(f)
            elif markerByteDetail == 0xC2 :
                segmentType = 'SOF2'
                segmentLength, segmentData = readDataSegment(f)
            elif markerByteDetail == 0xDA :
                segmentType = 'SOS'
                segmentLength, segmentData, nextBytes = readEntropyCodedDataSegment(f)
                bytes = nextBytes
            elif markerByteDetail == 0xDD :
                segmentType = 'DRI'
                segmentLength, segmentData = readDataSegment(f)
            elif markerByteDetail >= 0xD0 and markerByteDetail <= 0xD7 :
                # RST markers seem to be just inserted within runs of Coded data, and so are
                # handled by the readEntropyCodedDataSegment method, don't expect to detect
                # them here.
                segmentType = 'RST?'
                segmentLength = 0
                print("*** Found unexpected RST marker:", markerByteDetail, " at: ", bytecount-2, file=sys.stderr)
                aborted = True
                break
            else :
                # DRI ? RSTn ? COM ?
                segmentType = '????'
                segmentLength = 0
                print("*** Found unhandled segment marker:", markerByteDetail, " at: ", bytecount-2, file=sys.stderr)
                aborted = True
                break

            segmentInfo['length'] = segmentLength
            segmentInfo['type'] = segmentType
            if appSegmentIdentifier :
                segmentInfo['app'] = appSegmentIdentifier

            segmentsInfo.append(segmentInfo)
            segmentsData.append(segmentData)
            bytecount += segmentLength

            if EOIFound :
                break

            if len(bytes) == 0 :
                bytes = f.read(2)

        # End of main read loop. If we exited because we found the EOI marker, read any remaining
        # bytes in the file.
        if EOIFound :
            b = f.read(1)
            trailingBytes = []
            while b :
                trailingBytes.append(b)
                b = f.read(1)
            bytecount += len(trailingBytes)            

    # Summarise what we've found
    if verbose :
        for s in segmentsInfo :
            print(s)

        if EOIFound and trailingBytes :
            print("Found", len(trailingBytes), "unknown bytes after EOI marker:", *trailingBytes[0:10], "...")

    if not (SOIFound and EOIFound) :
        print("*** Start/End of Image character(s) not found in file:", filename, file=sys.stderr)

    if aborted :
        print("*** Aborted read of file:", filename, file=sys.stderr)
    elif verbose :
        print("Read all bytes:", bytecount, "bytes")

    allTags = {}

    # Dump out app data segment info
    for info, data in zip(segmentsInfo, segmentsData) :
        if 'app' in info :
            appName = info['app']
            if appName == "Exif" :
                Exifdict = processExifSegment(info, data)
                if verbose :
                    print("Extracted these IFDs from the Exif segment:")
                for n, d in Exifdict.items() :
                    if verbose :
                        print("- ", n, ":", len(d), "item(s)")
                    allTags[n] = d
            elif appName == "JFIF" :
                JFIFdict = processJFIFSegment(info, data)
                if verbose :
                    print("Extracted JFIF segment data:", len(JFIFdict), "item(s)")
                allTags['JFIF'] = JFIFdict
            elif appName == "ICC_PROFILE" :
                ICCdict = processICCProfileSegment(info, data)
                if verbose :
                    print("Extracted ICC Profile segment data:", len(ICCdict), "item(s)")
                allTags['ICC'] = ICCdict
            elif appName == "" :
                if verbose :
                    print("Found unnamed segment data:", info, data)
            elif appName == "http://ns.adobe.com/xap/1.0/" :
                # Contains XML, probably https://wwwimages2.adobe.com/content/dam/acom/en/devnet/xmp/pdfs/XMP%20SDK%20Release%20cc-2016-08/XMPSpecificationPart1.pdf
                # Possibly including <MicrosoftPhoto:DateAcquired>2013-06-23T12:01:02.200</MicrosoftPhoto:DateAcquired>
                if verbose :
                    print("Not examining", appName, "app data segment")
                    print(info, data)
            else :
                if verbose :
                    print("Not examining", appName, "app data segment")

    propertiesDict = {}
    propertiesDict['filename'] = filename
    propertiesDict['bytes'] = bytecount
    summariseTags(propertiesDict, allTags, verbose)

    if veryVerbose :
        displayAllTags(allTags)

    return propertiesDict
#
####################################
#

def main(filename) :

    if not os.path.isfile(filename) :
        print("***",  filename, "is not a file", file=sys.stderr)
        return

    veryVerbose = True  # For debugging
    mainProperties = processFile(filename, True, veryVerbose)
    displayMainProperties(mainProperties)

if __name__ == "__main__" :

    if len(sys.argv) == 1 :
        print("No filename command line argument provided")
        exit()

    filename = sys.argv[1]
    main(filename)
