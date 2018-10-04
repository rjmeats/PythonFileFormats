# Read a specified file a byte at a time, and dump out the byte offset and value

import sys
import binascii

if len(sys.argv) == 1 :
    print("No filename command line argument provided")
    exit()

filename = sys.argv[1]

print("Reading bytes from file:", filename)
print()

bytesDisplayedPerRow = 20

try :
    bytecount = 0
    with open(filename, "rb") as f:
        bytes = f.read(bytesDisplayedPerRow)
        while bytes:
            row="{0:07d} :".format(bytecount)
            chars=""
            for b in bytes :
                c = " "
                if b >= 32 and b < 128:
                    c = chr(b)
                elif b >= 128+32 and b < 128+128:
                    c = chr(b)
                chars += c
                row += "  {0:02x}".format(b)
            # Pad out last row if not filled
            if len(bytes) < bytesDisplayedPerRow :
                for i in range(0, bytesDisplayedPerRow - len(bytes)) :
                    row += "    "
            print(row + "      " + chars)
            bytecount += len(bytes)
            bytes = f.read(bytesDisplayedPerRow)

            
except OSError as err:
    print()
    print("*** Error accessing file:", filename, " : ", err)
else :
    print()
    print("Read all bytes:", bytecount, "bytes")
