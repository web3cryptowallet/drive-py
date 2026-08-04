# drive.py

drive.py v0.92

v0.92 - added a file indicator to the file list

Multithreaded disk file comparison tool for verification and MD5 checksum reporting.

- **drive.py** — CLI disk analyzer.
- **drive-tui.py** — TUI for the disk database.

![drive.py main](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/console-2.png)
![drive.py file compare](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/console-1.png)


## Prerequisites
- Python 3
- virtualenv (required for the TUI)
- Node.js (required for the web viewer)

## Usage
```bash
usage: drive.py [-h] [-s SRC] [-d DST] [-f FILE] [-e EXCLUDE] [-n NOTREE] [-t THREADS] logdir

Compare directories. Usage examples:
  drive.py -s <src>.. <logdir> # scan dirs only
  drive.py -s <src>.. -d <dst>.. <logdir> # compare dirs
  drive.py -f <log>.. -e <dir>.. <logdir> # compare logs

positional arguments:
  logdir                Log directory path

options:
  -h, --help            show this help message and exit
  -s SRC, --src SRC     Source directory path
  -d DST, --dst DST     Destination directory path
  -f FILE, --file FILE  Log file path
  -e EXCLUDE, --exclude EXCLUDE
                        Exclude dir for scanning (with -f)
  -n NOTREE, --notree NOTREE
                        No files tree
  -t THREADS, --threads THREADS
                        Number of threads for file hashing
```

## Run demo: Build demo report

Just try this demo:
```bash
./drive.py -s test0/t0 -d test0/t1 log-test0
```

## TUI
```
sudo apt install python3-venv

python3 -m venv .venv

pip install textual
pip install pyperclip

sudo apt install xclip

```

Run with in-memory db for small amount of files
```
python drive-tui.py
```

Build SQLite cache for big disks
```
python drive-tui.py -c sqlite -b
```
Run with SQLite cache
```
python drive-tui.py -c sqlite
```

## Run demo: View demo log files in your browser 

1. Install LiveComment
```bash
npm i -g livecomment
```
2. Start LiveComment web server
```bash
livecomment --path log-test0
```
3. Open http://localhost:3070/
```bash
open http://localhost:3070/
```

![log-test0](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/llog-demo.jpg)

### Dump log files to shell
```bash
$ cd log-test0/

# Differences log llog-diff.sh

$ cat llog-diff.sh 

# test0/t0 [
src= fileA md5-diff file c6f057b86584942e415435ffb1fa93d4
dst= fileC missed file d41d8cd98f00b204e9800998ecf8427e
dst= fileA md5-diff file 202cb962ac59075b964b07152d234b70
# test0/t0 ]

# All files llog-llogfiles.sh

$ cat llog-llogfiles.sh 

# files [
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t0 fileB 0
MD5 c6f057b86584942e415435ffb1fa93d4 test0/t0 fileA 3
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t1 fileC 0
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t1 fileB 0
MD5 202cb962ac59075b964b07152d234b70 test0/t1 fileA 3
# files ]

# Resume llog-proc.sh 

$ cat llog-proc.sh 

# process [
PROCESS test0/t0 -> test0/t1
# process ]
# total [
src_files:2
src_dirs:0
src_size:3
dst_files:3
dst_dirs:0
dst_size:3
# total ]
```

## TODO

- TODO: Redis test
- TODO: files: Page up/down keys navigation
- TODO: actionsview: Delete key - remove from actlions list
- TODO: actionsview: show file status in list
- TODO: actionsview: highlight dir
- TODO: info: show dir status - n files

## FAQ

### Why is the config in Livecomment format instead of JSON?

> Why is the config in Livecomment format instead of JSON?

Livecomment is an extensible format that can store multiple types of data. It supports both traditional Linux-style configuration formats (such as `fstab`-style mappings and plain text) as well as structured data like JSON, allowing different configuration styles to coexist in a single format.

## License
MIT

## Author
Github [@web3cryptowallet](https://github.com/web3cryptowallet)

Twitter [@web3wallet](https://twitter.com/web3wallet)

## Contribute
Just add an issue and push pull request

## Contact

[web3future@protonmail.com](mailto:web3future@protonmail.com)

## Sponsorship

If you appreciate this project, please star it on GitHub and/or sponsor on GitHub or donate crypto below.

Looking for sponsors to help fund development.

BTC 💰
18Bth1u3pSJzPrCf21tx1F6iSzA2fgKdfU

SOL Solana 💰
9gLVQr97baX3KrG9DyaUDd5FwXaiLcDuU6CK5RCNMnWu

ETH Ethereum 💰
0x072c709a8Ad95Fc182e0E2EEF834C3d944122f0b

USDT Ethereum 💰
0x072c709a8Ad95Fc182e0E2EEF834C3d944122f0b

DOGE Dogecoin 💰
DJP8425i4sGT4tSEXwEDRPJb4vJBGroJs6

LTC Litecoin 💰
ltc1q69gg9udgqnky60n7mfzfaj0w7lu80ujx6fysly

TRX Tron 💰
TLjkoQfnu7aRRbVRkEYN1vZPzW7ntuM4tn


## License

[MIT](https://github.com/web3cryptowallet/drive-py/blob/main/LICENSE)

## Version History

v0.91 - added actions generation
v0.92 - added a file indicator to the file list

## Recomended projects

- [livecomment](https://github.com/d08ble/livecomment) project
- [bitchatX21](https://github.com/goldenwebb/bitchatX21) a better version of Bitchat for iOS

*AI-Independet code. Created through human work*
