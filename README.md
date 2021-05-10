# drive.py

Multithread disk files comparasion tool for verification and md5sum report in livecomment format

## Prerequirements
* python3
* NodeJS for web viewer

## Usage
```bash
$ ./drive.py <src> <dst> <logdir>
```

src - source directory

dst - destination directory

logdir - log directory

## Demo example
Try this demo example
```bash
./drive.py "test0/t0" "test0/t1" "log-test0"
```

### View log files in browser 
1. Install LiveComment
```bash
npm i -g livecomment
```
2. Start LiveComment web server
```bash
cd log-test0/
livecomment
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

## License
MIT

## Author
Github [@web3cryptowallet](https://github.com/web3cryptowallet)

Twitter [@web3wallet](https://twitter.com/web3wallet)

## Contribute
Just add an issue and push pull request

## See also
[livecomment-cli](https://github.com/web3cryptowallet/livecomment-cli) project



