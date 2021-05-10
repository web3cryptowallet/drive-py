#!/usr/bin/python3

import os
from os.path import isfile, isdir, islink, join
from multiprocessing import Process, Manager, Value, Pool
import hashlib

from livelog import LiveLog

SRC_PATHS=[]
DST_PATHS=[]

def add_path(src, dst):
    SRC_PATHS.append(src)
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
            llogfiles.put("MD5 " + fmap[f]['md5'] + ' ' + src + ' ' + f + ' ' + str(fmap[f]['size']))

def process_root(src, dst):
    llog.begin('process')
    llogfiles.begin('files')
    process_dir(src, dst)
    llogfiles.end()
    llog.end()
    llog.begin('total')
    llog.put('src_files:' + str(src_total_files))
    llog.put('src_dirs:' + str(src_total_dirs))
    llog.put('src_size:' + str(src_total_size))
    llog.put('dst_files:' + str(dst_total_files))
    llog.put('dst_dirs:' + str(dst_total_dirs))
    llog.put('dst_size:' + str(dst_total_size))
    llog.end()


def process_dir(src, dst):
    global src_total_files, src_total_dirs, src_total_size
    global dst_total_files, dst_total_dirs, dst_total_size

    llogdiff.begin(src)
    llog.put('PROCESS ' + src + ' -> ' + dst)
#    print 'PROCESS', src, '->', dst

    src = os.path.expanduser(src)
    dst = os.path.expanduser(dst)

    sfiles = os.listdir(src)
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
        smap[f] = {"eq": 'missed', "type": type}


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
    dthread = hash_files_thread_start(1, dst, dmap)
    sthread.join()
    dthread.join()
    smap = RES[0]
    dmap = RES[1]
    src_total_size += SIZES[0]
    dst_total_size += SIZES[1]

    llog_files(src, smap)
    llog_files(dst, dmap)

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
            process_dir(join(src, f), join(dst, f))

def process():
    for i in range(0, len(SRC_PATHS)):
        process_root(SRC_PATHS[i], DST_PATHS[i])

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: drive.py <src> <dst> <logdir>')
        exit(1)

    src = sys.argv[1]
    dst = sys.argv[2]
    logdir = sys.argv[3]

    if not isdir(logdir):
        os.makedirs(logdir)

    global RES, SIZES
    manager = Manager()
    RES = manager.list(range(2))
    SIZES = manager.list(range(2))

    add_path(src, dst)

    llog = LiveLog(join(logdir, "llog-proc.sh"))
    llogdiff = LiveLog(join(logdir, "llog-diff.sh"))
    llogfiles = LiveLog(join(logdir, "llog-llogfiles.sh"))

    print('SRC_PATHS =', SRC_PATHS)
    print('DST_PATHS =', DST_PATHS)
    process()

