import numpy as np
import cv2 as cv
import sys
import os
from tempfile import TemporaryDirectory

FRAMERATE = 25
PROG_START_THRESHOLD = 180 * FRAMERATE
AD_BREAK_MINIMUM = 120 * FRAMERATE
BLANK_NEAR_THRESHOLD = 2 * FRAMERATE
SEG_START_DELAY = int(1.0 * FRAMERATE)

# Set params
in_file = sys.argv[1]
out_file = sys.argv[2]

# Create a new tempdir
tmpdir = TemporaryDirectory()

# Create an array for the blank frame indexes
blanks = [-BLANK_NEAR_THRESHOLD]

# Collect blank frames
cap = cv.VideoCapture(in_file)
i = 1
while(cap.isOpened()):
    ret, frame = cap.read()
    if frame is None:
        break
    if frame.mean() < 0.5 and (i - blanks[-1]) > BLANK_NEAR_THRESHOLD:
        print('Blank frame at %i' % i)
        blanks.append(i)
    i += 1
cap.release()
cv.destroyAllWindows()

blanks.pop(0)

# Find the program start
program_start = None
for frame in list(blanks):
    if(frame > PROG_START_THRESHOLD):
        break
    program_start = frame
    blanks.pop(0) # Pop the frame to add the last one later

print("Program start: %if" % program_start)

# Strip in-ad blanks
i = 0
in_ad = False
while i < len(blanks):
    frame = blanks[i]
    if in_ad: # In an ad
        if frame - blanks[i - 1] < AD_BREAK_MINIMUM:
            print("Removing in-ad blank %i" % frame)
            blanks.pop(i)
            # i -= 1 # Wind back the for loop as we just deleted an element
        else:
            in_ad = False
            i += 1
    else:
        in_ad = True 
        i += 1

blanks.insert(0, program_start)
print("Blanks: %s" % blanks)

# Split the program segments
print('Splitting program...')
i = 0
blanks = list(zip(blanks[0::2], blanks[1::2]))
for i in range(len(blanks)):
    start_s = (blanks[i][0] + SEG_START_DELAY) / FRAMERATE
    end_s   = blanks[i][1] / FRAMERATE
    time_s  = end_s - start_s
    print("%i: %i to %i" % (i, blanks[i][0] + SEG_START_DELAY, blanks[i][1]))
    print("    %fs to %fs, len %fs" % (start_s, end_s, time_s))
    os.system("ffmpeg -ss %f -i %s -t %f -c:v copy -c:a copy %s/%i.mkv" % (start_s, in_file, time_s, tmpdir.name, i))

print('Creating file list...')
with open(('%s/filelist.txt' % tmpdir.name), 'w') as filelist:
    for i in range(len(blanks)):
        filelist.write("file %s.mkv\n" % i)

print('Compiling segments...')
os.system("ffmpeg -f concat -i %s/filelist.txt -c:v h264 -crf 18 -c:a libvo_aacenc %s" % (tmpdir.name, out_file))

print('Cleaning up...')
tmpdir.cleanup()

