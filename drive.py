#!/usr/bin/python3

import os
from os.path import isfile, isdir, islink, join
from multiprocessing import Process, Manager, Value, Pool
import hashlib
import argparse

from livelog import LiveLog
from livelog2 import LiveLog as LiveLog2

SRC_PATHS=[]
DST_PATHS=[]

def add_path(src, dst):
    SRC_PATHS.append(src)
    if dst:
        DST_PATHS.append(dst)

#add_path('t0', 't1')

src_total_files = 0
src_total_dirs = 0
src_total_size = 0

dst_total_files = 0
dst_total_dirs = 0
dst_total_size = 0

import sys

def md5(fname):
    size = 0
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
            size += len(chunk)

    return hash_md5.hexdigest(), size

def hash_files(RES, SIZES, i, src, fmap):
    total_size = 0
#    print "hash_files", i
    for f in fmap:
        if fmap[f]['type'] == 'file':
#            print "HASH:", src, f
            fmap[f]['md5'], fmap[f]['size'] = md5(join(src, f))
            total_size += fmap[f]['size']
            print("MD5:", fmap[f]['md5'], src, f, fmap[f]['size'])

    RES[i] = fmap
    SIZES[i] = total_size

    return fmap

def hash_files_thread_start(i, src, fmap):
    p = Process(target=hash_files, args=(RES, SIZES, i, src, fmap))
    p.start()
    return p

def llog_files(src, fmap):
    for f in fmap:
        if fmap[f]['type'] == 'file':
            llogfiles.put("MD5 " + fmap[f]['md5'] + ' "' + src + '/' + f + '" ' + str(fmap[f]['size']))

def human_readable_size(size_in_bytes):
    # Define size units
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    
    # Start with Bytes, and keep dividing by 1024 for higher units
    if size_in_bytes == 0:
        return f"0 {units[0]}"
    
    unit_index = 0
    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024
        unit_index += 1
    
    if size_in_bytes == int(size_in_bytes):
        return f"{int(size_in_bytes)} {units[unit_index]}"
    else:
        return f"{size_in_bytes:.2f} {units[unit_index]}"

def process_root(src, dst):
    process_dir(src, dst)


def process():
    llog.begin('pwd')
    llog.put(os.getcwd())
    llog.end()
    llog.begin('process')
    llogfiles.begin('files')

    for i in range(0, len(SRC_PATHS)):
        dst = DST_PATHS[i] if DST_PATHS and i < len(DST_PATHS) else None
        process_root(SRC_PATHS[i], dst)

    llogfiles.end()
    llog.end()
    llog.begin('total')
    llog.put('src_files: ' + str(src_total_files))
    llog.put('src_dirs: ' + str(src_total_dirs))
    llog.put('src_size: ' + str(src_total_size))
    llog.put('src_size_unit: ' + human_readable_size(src_total_size))
    llog.put('dst_files: ' + str(dst_total_files))
    llog.put('dst_dirs: ' + str(dst_total_dirs))
    llog.put('dst_size: ' + str(dst_total_size))
    llog.put('dst_size_unit: ' + human_readable_size(dst_total_size))
    llog.end()

    print(f'Processed {src_total_files} files {src_total_dirs} dirs {human_readable_size(dst_total_size)} size')


def process_dir(src, dst):
    global src_total_files, src_total_dirs, src_total_size
    global dst_total_files, dst_total_dirs, dst_total_size

    llogdiff.begin(src)

    llog.put('SRC ' + src)
    if dst:
        llog.put('DST ' + dst)

#    print 'PROCESS', src, '->', dst

    src = os.path.expanduser(src)
    if dst:
        dst = os.path.expanduser(dst)

    sfiles = os.listdir(src)
    if dst:
        dfiles = os.listdir(dst)

    smap = {}
    for f in sfiles:
        type = '?'
        if islink(join(src, f)):
            type = 'link'
        elif isfile(join(src, f)):
            type = 'file'
            src_total_files += 1
        elif isdir(join(src, f)):
            type = 'dir'
            src_total_dirs += 1

        # Set eq, type
        if dst:
            smap[f] = {"eq": 'missed', "type": type}
        else:
            # force ok
            smap[f] = {"eq": 'ok', "type": type}


    if dst:
        dmap = {}
        for f in dfiles:
            type = '?'
            if islink(join(dst, f)):
                type = 'link'
            elif isfile(join(dst, f)):
                type = 'file'
                dst_total_files += 1
            elif isdir(join(dst, f)):
                type = 'dir'
                dst_total_dirs += 1
            dmap[f] = {"eq": 'missed', "type": type}

    sthread = hash_files_thread_start(0, src, smap)
    if dst:
        dthread = hash_files_thread_start(1, dst, dmap)
    sthread.join()
    if dst:
        dthread.join()
    smap = RES[0]
    if dst:
        dmap = RES[1]
    src_total_size += SIZES[0]
    if dst:
        dst_total_size += SIZES[1]

    llog_files(src, smap)
    if dst:
        llog_files(dst, dmap)

    if dst:
        for f in sfiles:
            if dmap.get(f) != None:
                if dmap[f]["type"] == smap[f]["type"]:
                    smap[f]["eq"] = 'ok'
                    dmap[f]["eq"] = 'ok'
                    if dmap[f]["type"] == 'file' and dmap[f].get("md5") != smap[f].get("md5"):
                        smap[f]["eq"] = 'md5-diff'
                        dmap[f]["eq"] = 'md5-diff'
                else:
                    smap[f]["eq"] = 'diff'
                    dmap[f]["eq"] = 'diff'

        for f in smap:
            if smap[f]["eq"] != 'ok':
        #            print "src=", f, smap[f]["eq"], smap[f]["type"]
                llogdiff.put("src= "+ f + ' ' + smap[f]["eq"] + ' ' + smap[f]["type"] + ' ' + str(smap[f].get("md5")))


        for f in dmap:
            if dmap[f]["eq"] != 'ok':
        #            print "drc=", f, smap[f]["eq"], smap[f]["type"]
                llogdiff.put("dst= " + f + ' ' + dmap[f]["eq"] + ' ' + dmap[f]["type"] + ' ' + str(dmap[f].get("md5")))

    llogdiff.end()

    for f in smap:
        if smap[f]["eq"] == 'ok' and smap[f]["type"] == 'dir':
            if dst:
                dst = join(dst, f)
            process_dir(join(src, f), dst)

def load_log_parse_line(ctx, line):
    parts = line.split(maxsplit=3)  # Split into 4 parts (hashtype, hash, file, size)
    if len(parts) == 4:
        hashtype, hash_value, file, size = parts
        id_ = f"{hashtype}:{hash_value}:{size}"  # Construct ID
        file = file.strip('"')  # Remove surrounding quotes

        hashes = ctx["hashes"]
        files = ctx["files"]

        # Add to hashes dictionary
        if id_ not in hashes:
            hashes[id_] = set()
        hashes[id_].add(file)

        # Add to files dictionary
        if file not in files:
            files[file] = set()
        files[file].add(id_)
    else:
        # Error
        msg = "Can't parse line: {line}"
        print(f"\033[91mError: {msg}\033[0m")

# PROCESS COMPARE [

from datetime import datetime
import time
import pprint

pp = pprint.PrettyPrinter(indent=4, width=50, sort_dicts=True)

def process_compare(files, logdir):
    right = {
        "hashes": {},
        "files": {},
        "file_types": {},
        "modified": {} # deleted, modified
    }

    for file in files:
        load_log(right, file)

    # Gen filename llog-20250328-0700.000.sh
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y%m%d-%H%M%S")
    milliseconds = int(round(time.time() * 1000)) % 1000  # Get last 3 digits for MS
    suffix = f"{formatted_time}.{milliseconds:03d}"
#    filename = f"llog-{suffix}-files.sh"
    #to=f"{logdir}/{filename}"
    #print(to)

#    filename_files = f"llog-{suffix}-files.sh"
#    filename_compare = f"llog-{suffix}.sh"
    filename_files = f"llog-files.sh"
    filename_compare = f"llog-compare.sh"


    compared = right

    # CHECK DISK MODIFIED [

    for fname, file in compared["files"].items():
        type = '?'
        if islink(fname):
            type = 'link'
        elif isfile(fname):
            type = 'file'
        elif isdir(fname):
            type = 'dir'
        else:
            type = 'deleted'
        
        compared["file_types"][fname] = type

        if type != 'file':
            compared["modified"][fname] = type

    # CHECK DISK MODIFIED ]
    # EXPORT FILES LIST [

    # Export files list
#    llog = LiveLog2(to)
    llog = LiveLog(join(logdir, filename_files))
    llog.begin('files')

    for key, file in compared["files"].items():
        fid = list(file)[0]
        parts = fid.split(":")
        parts.insert(-1, f'"{key}"')
        s = " ".join(parts)
        llog.put(s)

    llog.end()
    llog.flush()

    # EXPORT FILES LIST ]
    # EXPORT COMPARE RESULTS [

    # Export compare results
    llog = LiveLog(join(logdir, filename_compare))
    llog.begin('Duplicate')

    for key, hash in compared["hashes"].items():
        if len(hash) > 1:
            llog.put(f"DUP {key}")
            for filename in hash:
                llog.put(filename)

    llog.end()
    llog.begin('Modified')

    for filename, type in compared["modified"].items():
        length = 8
        type = type[:length].ljust(length, ' ')
        llog.put(f'{type} {filename}')

    llog.end()
    llog.begin('Deleted')

    for filename, type in compared["modified"].items():
        if type == 'deleted':
            llog.put(f'{type} {filename}')

    llog.end()
    llog.flush()

    # EXPORT COMPARE RESULTS ]



def load_log(ctx, filename):
    print("Load file:", filename)
    ll = LiveLog2(filename)
    ll.load()
    for node in ll._tree._items_index:
        print("#", node.name, "count", len(node._ss))
#        print(node.text)
        for line in node._ss:
            print(line)
            load_log_parse_line(ctx, line)

    print(f"Loaded hashes {len(ctx['hashes'])} files {len(ctx['files'])}")
    #print("->", ctx)
    pp.pprint(ctx)


# PROCESS COMPARE ]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    description="Compare directories. Usage examples:\n"
                "  drive.py -s <src>.. <logdir> # scan dirs only\n"
                "  drive.py -s <src>.. -d <dst>.. <logdir> # compare dirs"
                "  drive.py -f <log>.. -e <dir>.. <logdir> # compare logs"
    )
    parser.add_argument('-s', '--src', action='append', help='Source directory path')
    parser.add_argument('-d', '--dst', action='append', help='Destination directory path')
 
    parser.add_argument('-f', '--file', action='append', help='Log file path')
    parser.add_argument('-e', '--exclude', help='Exclude dir for scanning (with -f)')

    parser.add_argument('logdir', help='Log directory path')

    try:
        args = parser.parse_args()
    except SystemExit as e:
        print(f"Error: Missing required arguments. Use `-h` for help.")
        exit(e.code)  # Exit with the same error code
    
    if not args.file:
        if not args.src:
            parser.error('Need source (-s)')

    print("PWD", os.getcwd())

    # MKDIR LOGDIR [

    logdir = args.logdir
    
    if not isdir(logdir):
        os.makedirs(logdir)

    # MKDIR LOGDIR ]
    # MODE: COMPARE [

    if args.file:
        process_compare(args.file, logdir)
        exit(0)
    
    # MODE: COMPARE ]
    # MODE: SCAN [

    # For thread scan index 0-src, 1-dst
    global RES, SIZES
    manager = Manager()
    RES = manager.list(range(2)) 
    SIZES = manager.list(range(2))

    if args.dst:
        if len(args.src) != len(args.dst):
            parser.error('Wrong src and dst count', len(args.src), len(args.dst))

    for i, src_item in enumerate(args.src):
        dst = args.dst[i] if args.dst and i < len(args.dst) else None
        add_path(args.src[i], dst)

    llog = LiveLog(join(logdir, "llog-proc.sh"))
    llogdiff = LiveLog(join(logdir, "llog-diff.sh"))
    llogfiles = LiveLog(join(logdir, "llog-llogfiles.sh"))

    print('SRC_PATHS =', SRC_PATHS)
    print('DST_PATHS =', DST_PATHS)
    process()

    # MODE: SCAN ]
