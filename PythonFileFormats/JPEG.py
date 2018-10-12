import sys


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
    # Remove trailing null used in IFD string elements
    if bytes[-1] == 0x00 :
        bytes = bytes[0:len(bytes)-1]
    return bytes.decode()

# Extract first n bytes up to a 0 byte, expect this to be an ASCII string identifying the type of App Segment, e.g. "Exif"
def getAppSegmentIdentifier(segment) :
    n = 0
    while n < len(segment) and segment[n] != 0x00 :
        n += 1

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
        print("*** Exif segment header format not as expected:", segment[0:10])
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
        for knownIFDname, d in dict.items() :            
            for embeddedIFDtag, embeddedIFDname in knownEmbeddedIFDs().items() :
                # This will re-search all IFDs each time through the loop, not just ones we've added last time
                # around, so ignore embedded IFDs we've already picked up. (Assuming the only exist in one place.)
                if embeddedIFDtag in d and embeddedIFDname not in dict:
                    IFDname = embeddedIFDname
                    #print("Handling embedded IFD:", IFDname)
                    embeddedIFDOffset = d[embeddedIFDtag]['value']
                    embeddedIFDentries, nextIFDOffset = processIFD(TIFF, embeddedIFDOffset, byteAlignmentIndicator)
                    # Put info about embedded IFD onto a list, we can't put it directly in the main dictionary
                    # while looping over the dictionary,
                    newIFDinfo.append( (embeddedIFDname, embeddedIFDentries) )
                    if nextIFDOffset != 0000 :
                        print("*** - unexpected next IFD offset in IFD", embeddedIFDname)
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
        print("*** IFD data type not implemented: IFD item no:", elementNo, "tag:", tag, ", dataFormat:", dataFormat, ", num:", componentCount, ", bytes:", dataBytes)

    return entry

#
#############################################
#

def processJFIFSegment(dict, info, data) :
    print("- to do : JFIF")

def processICCProfileSegment(dict, info, data) :
    print("- to do : ICC_Profile")

##
###########################################################################
##

def processFile(filename) :

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
                print("*** [", bytecount, "]", "Unexpected bytes length: ", len(bytes), ", contents:", bytes, )
                aborted = True
                break

            if bytes[0] != 0xFF :
                print("*** [", bytecount, "]", "Expected <FF> but found : ", bytes[0])
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
            else :
                # DRI ? RSTn ? COM ?
                segmentType = '????'
                segmentLength = 0
                print("*** Found unhandled segment marker:", bytes, " at: ", bytecount-2)
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
    for s in segmentsInfo :
        print(s)

    if EOIFound and trailingBytes :
        print("Found", len(trailingBytes), "unknown bytes after EOI marker:", *trailingBytes[0:10], "...")

    if not (SOIFound and EOIFound) :
        print("*** Start/End of Image character(s) not found")

    if not aborted :
        print("Read all bytes:", bytecount, "bytes")
    else :
        print("*** Aborted read")

    # Dump out app data segment info
    for info, data in zip(segmentsInfo, segmentsData) :
        if 'app' in info :
            appName = info['app']
            dict = {}
            if appName == "Exif" :
                ExifDict = processExifSegment(info, data)
                print("Extracted these IFDs from the Exif segment:")
                for n, d in ExifDict.items() :
                    print("- ", n, ":", len(d), "item(s)")
            elif appName == "JFIF" :
                processJFIFSegment(dict, info, data)
            elif appName == "ICC_PROFILE" :
                processICCProfileSegment(dict, info, data)
            else :
                print("Not examining", appName, " data segment")
            #print(dict)

#
####################################
#

if len(sys.argv) == 1 :
    print("No filename command line argument provided")
    exit()

filename = sys.argv[1]
processFile(filename)

