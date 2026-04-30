import pycdlib

iso = pycdlib.PyCdlib()
iso.new(rock_ridge=None)

# Add files from the extracted/mounted raw image directory
iso.add_directory('D:/convert', rr_name='DIR')
iso.write("disk.iso")
iso.close()