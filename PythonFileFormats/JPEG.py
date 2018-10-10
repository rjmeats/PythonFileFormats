import sys


if len(sys.argv) == 1 :
    print("No filename command line argument provided")
    exit()

filename = sys.argv[1]

def handleIFDElement(n, ifd, segment, byteAlignment) :
    embeddedIFDOffset = (0,0)

    tagNo = ifd[0:2]
    itagNo = bytesToInt(tagNo, byteAlignment)
    dataFormat = ifd[2:4]
    idataFormat = bytesToInt(dataFormat, byteAlignment)
    numComponents = ifd[4:8]
    inumComponents = bytesToInt(numComponents, byteAlignment)
    dataValue = ifd[8:12]

    if idataFormat in [3] and inumComponents == 1:
        dataValue = ifd[8:10]   # 2 bytes not 4
        idataValue = bytesToInt(dataValue, byteAlignment)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, ", num:", inumComponents, ", val:", idataValue)
    elif idataFormat in [3] and inumComponents == 2:
        dataValue1 = ifd[8:10]   # 2 bytes not 4
        idataValue1 = bytesToInt(dataValue1, byteAlignment)
        dataValue2 = ifd[10:12]   # 2 bytes not 4
        idataValue2 = bytesToInt(dataValue2, byteAlignment)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, ", num:", inumComponents, ", val:", [idataValue1, idataValue2])
    elif idataFormat in [3] and inumComponents > 2:
        offset = bytesToInt(dataValue, byteAlignment)
        vals = []
        for i in range (0, inumComponents) :
            valStartOffset = offset + i*2
            dataValue = ifd[valStartOffset:valStartOffset+2]
            idataValue = bytesToInt(dataValue, byteAlignment)
            vals.append(idataValue)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, ", num:", inumComponents, ", val:", vals)
    elif idataFormat in [4] and inumComponents == 1:
        idataValue = bytesToInt(dataValue, byteAlignment)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, ", num:", inumComponents, ", val:", idataValue)
        if itagNo in [34853, 34665] :
            embeddedIFDOffset = (itagNo, idataValue)

    elif idataFormat == 2 and inumComponents <= 4:
        idataValue = bytesToASCIIString(dataValue)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, "(String), num:", inumComponents, ", val:", "'" + idataValue + "'")
    elif idataFormat == 2 and inumComponents > 4:
        offset = bytesToInt(dataValue, byteAlignment)
        dataValue2 = segment[offset:offset+inumComponents]
        #print(".. offset is:", offset, "dataValue2 is:", dataValue2)
        idataValue = bytesToASCIIString(dataValue2)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, "(String), num:", inumComponents, ", val:", "'" + idataValue + "'")
    elif idataFormat == 5 and inumComponents == 1:
        # Unsigned rational - fraction of two unsigned longs
        offset = bytesToInt(dataValue, byteAlignment)
        numeratorBytes = segment[offset:offset+4]
        denominatorBytes = segment[offset+4:offset+8]
        numerator = bytesToInt(numeratorBytes, byteAlignment)
        denominator = bytesToInt(denominatorBytes, byteAlignment)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, "(Rational), num:", inumComponents, ", val:", numerator,"/", denominator)
    elif idataFormat == 5 and inumComponents > 1:
        # Unsigned rational - fraction of two unsigned longs
        offset = bytesToInt(dataValue, byteAlignment)
        vals = []
        for i in range (0, inumComponents) :
            valStartOffset = offset + i*8
            numeratorBytes = segment[valStartOffset:valStartOffset+4]
            denominatorBytes = segment[valStartOffset+4:valStartOffset+8]
            numerator = bytesToInt(numeratorBytes, byteAlignment)
            denominator = bytesToInt(denominatorBytes, byteAlignment)
            vals.append( (numerator, denominator))
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, "(Rational), num:", inumComponents, ", vals:", vals)
    else :
        #print(n, ifd)
        #        idataValue = "????"
        idataValue = bytesToInt(dataValue, byteAlignment)
        print(".. IFD item no:", n, "tagNo:", itagNo, ", dataFormat:", idataFormat, ", num:", inumComponents, ", val:", dataValue, ", ???? idataValue:", idataValue)

    return embeddedIFDOffset

# MM version
def bytesToInt(bytes, byteAlignment) :    
    alignment = 'big'
    if byteAlignment == "II" :
        alignment = 'little'

    i = int.from_bytes(bytes, signed=False, byteorder=alignment)
    return i

def bytesToASCIIString(bytes) :
    s = bytes.decode()
    return s

def handleIFD(seg, nextIDOffset, byteAlignment) :

        # 2 byte value indicating the number of entries
        ifdcount = bytesToInt(seg[nextIDOffset:nextIDOffset+2], byteAlignment)
        ifdElements = seg[nextIDOffset+2:]

        embeddedIFDOffsets = []
        # Then n 12 byte IFD entries
        elementSize = 12
        for i in range (0, ifdcount) :
            ifdElement = ifdElements[elementSize*i : elementSize*(i+1)]
            embeddedIFDOffset = handleIFDElement(i, ifdElement, seg, byteAlignment)

            if embeddedIFDOffset[0] != 0 :
                print("Found embedded offset in IFD:", embeddedIFDOffset)
                embeddedIFDOffsets.append(embeddedIFDOffset)

            #print(i, ifd)
            # https://www.awaresystems.be/imaging/tiff/tifftags/baseline.html
    
        # The next four bytes are either an offset for the next IFD, or 0000 if no more IFDs
        offsetReached = elementSize*ifdcount
        print("After IFD: ", ifdElements[offsetReached : offsetReached+4])     # Non-zero means pointing to a further IFD area (thumbnail ?). Set seg2 and repeat above ?
        nextIFDOffsetBytes = ifdElements[offsetReached : offsetReached+4]
        nextIFDOffset = bytesToInt(nextIFDOffsetBytes, byteAlignment)
        print("nextIFDOffset:", nextIFDOffset)
        return nextIFDOffset, embeddedIFDOffsets

# Extract first n bytes up to a 0 byte, expect this to be an ASCII string identifying the type of App Segment, e.g. "Exif"
def getAppSegmentIdentifier(segmentData) :
    n = 0
    while n < len(segmentData) and segmentData[n] != 0x00 :
        n += 1

    return bytesToASCIIString(segmentData[0:n])

def processAppSegement(segment) :
    #print("..", segment[0:1000])
    # First four bytes = Exif
    Exif = "Exif"
    JFIF = "JFIF"
    if (segment[0] == Exif.encode()[0] and segment[1] == Exif.encode()[1] and segment[2] == Exif.encode()[2] and segment[3] == Exif.encode()[3] and segment[4] == 0 and segment[5] == 0) :
        #http://gvsoft.no-ip.org/exif/exif-explanation.html
        print("Found Exif segment ..")
        seg2 = segment[6:]  ## TIFF Header
        print("0-1", seg2[0:2]) ## MM = Motorola byte alignment, i.e. highest-order bytes first in a multi-byte number
        # Need to check/handle II as well as default MM
        byteAlignment = bytesToASCIIString(seg2[0:2])
        print("2-3", seg2[2:4]) ## Always 0x002A = \x00 *
        print("4-7", seg2[4:8]) ## Offset to to first IFD Image File Directory from start of TIFF Header. Usually 0008, i.e. next bytes
        nextIFDOffset = bytesToInt(seg2[4:8], byteAlignment)
        print("Next IFD start offset:", nextIFDOffset)

        IFDCount = 0
        while nextIFDOffset != 0 :
            IFDCount += 1
            print("Handling IFD:", IFDCount)
            nextIFDOffset, embeddedIFDOffsets = handleIFD(seg2, nextIFDOffset, byteAlignment)
            if len(embeddedIFDOffsets) > 0 :
                print("Found embedded IFDs within this IFD:", embeddedIFDOffsets)
                for (id, os) in embeddedIFDOffsets :
                    print("Looking at embedded IFD:", id)
                    handleIFD(seg2, os, byteAlignment)

        print("No more IFDs in this segment")
    elif (segment[0] == JFIF.encode()[0] and segment[1] == JFIF.encode()[1] and segment[2] == JFIF.encode()[2] and segment[3] == JFIF.encode()[3] and segment[4] == 0) :
        print("Found JFIF segment .. details ignored:", segment )
    else :
        print("Segment doesn't start as expected - not an EXIF or JFIF")

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
    
##
###########################################################################
##

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
            #processAppSegement(segmentData)
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

zipped = zip(segmentsInfo, segmentsData)
for s,d in zipped :
    print(s)

if EOIFound and trailingBytes :
    print("Found", len(trailingBytes), "unknown bytes after EOI marker:", *trailingBytes[0:10], "...")

if not aborted :
    print("Read all bytes:", bytecount, "bytes")
else :
    print("*** Aborted read")

