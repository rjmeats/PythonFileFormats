# Read a specified file a byte at a time, and dump out the byte offset and value

import sys
import binascii

if len(sys.argv) == 1 :
    print("No filename command line argument provided")
    exit()

filename = sys.argv[1]

print("Reading bytes from file:", filename)
print()

try :
    bytecount = 0
    with open(filename, "rb") as f:
        bytes = f.read(1)
        while bytes:
            # Print out as hex and decimal and as a printable ASCII character
            s = ""
            if bytes[0] >= 32 and bytes[0] < 127:
                s = str(bytes).replace("b'", "").replace("'", "")   # Convert from "b'x'"" to just "x"
            print("{0:07d} : 0x{1:02x}  {1:3d}  {2:s}".format(bytecount, bytes[0], s))
            bytecount += 1
            bytes = f.read(1)
except OSError as err:
    print()
    print("*** Error accessing file:", filename, " : ", err)
else :
    print()
    print("Read all bytes:", bytecount, "bytes")
