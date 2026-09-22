"""Sample virtual filesystem navigation."""

# IMPORT SAMPLE VIRTUAL FILESYSTEM NAVIGATION DEPENDENCIES [

from .filesystem import VirtualFS

# IMPORT SAMPLE VIRTUAL FILESYSTEM NAVIGATION DEPENDENCIES ]
# DEMONSTRATE VIRTUAL FILESYSTEM NAVIGATION [

def test_vfs():
    data = {
        "files": {
            "test0/t0/fileA": {"MD5:c6f057b86584942e415435ffb1fa93d4:3"},
            "test0/t0/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileA": {"MD5:202cb962ac59075b964b07152d234b70:3"},
            "test0/t1/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileC": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
        }
    }

    vfs = VirtualFS(data)

    print(vfs.pwd())
    print(vfs.listdir())

    vfs.enter("test0")
    print(vfs.listdir())

    vfs.enter("t1")
    print(vfs.listdir())

    file = vfs.get("fileC")
    print(file.info)

# DEMONSTRATE VIRTUAL FILESYSTEM NAVIGATION ]
