#! /usr/bin/python3

from __future__ import print_function

import datetime
import logging
import os
import subprocess
import time


def getUserConfig(fileName, splitterChar):
    userConfig = {}

    with open(fileName) as configFile:
        for eachLine in configFile:
            eachLine = eachLine.split("#")[0].strip()

            if "=" in eachLine:
                (settingName, settingValue) = eachLine.split(splitterChar)
                settingName = settingName.strip()
                settingValue = settingValue.strip()
                userConfig[settingName] = settingValue

    return userConfig


def logPrint(text, prynt=True):
    logging.debug(text)

    if prynt:
        print()
        print(text)


def ensureDir(path):
    """
    Ensure path is a directory. If a regular file exists with same name, rename it (backup) and create dir.
    """
    if os.path.isdir(path):
        return True
    if os.path.isfile(path):
        backup = path + ".conflict_file_" + str(int(time.time()))
        try:
            os.rename(path, backup)
            logPrint("ensureDir: renamed conflicting file to %s" % backup)
        except Exception as e:
            logPrint("ensureDir: FAILED to rename conflicting file %s: %s" % (path, e))
            return False
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        logPrint("ensureDir: FAILED to create dir %s: %s" % (path, e))
        return False


def mountFs(ip, fsDest, mountTo, creds, exitOnFail, remount):
    def isMountPoint(path):
        cmd = "mountpoint %s" % path
        subClient = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        subOut = subClient.communicate()

        if "is a mountpoint" in subOut[0].decode("utf-8").lower():
            return True

        return False

    def unmount(path):
        cmd = "sudo umount %s" % path

        try:
            logPrint("mountFs: unmount: remounting %s" % path)
            subprocess.run(cmd, shell=True)

        except Exception as e:
            logPrint("mountFs: unmount: failed to unmount:\n%s" % cmd)

    if isMountPoint(mountTo):
        logPrint("mountFs: NAS already mounted")

        if remount:
            unmount(mountTo)
            mountFs(ip, fsDest, mountTo, creds, exitOnFail, remount=False)

        return

    # Enhanced mount options for CIFS write permissions
    cmd = (
        "sudo mount -t cifs //%s/%s %s -o credentials=%s,uid=pi,gid=pi,file_mode=0664,dir_mode=0775"
        % (ip, fsDest, mountTo, creds)
    )
    subprocess.run(cmd, shell=True)

    if isMountPoint(mountTo):
        logPrint("mountFs: mounted NAS to %s" % mountTo)
        return
    else:
        logPrint("mountFs: FAILED to mount NAS:\n%s" % cmd)
        if exitOnFail:
            exit()


def findAllFiles(exts, paths):
    def findFiles(exts, path):
        foundFiles = []

        if not os.path.exists(path):
            logPrint("findFiles: path does not exist:\n%s" % path)
            return []

        for root, dirs, files in os.walk(path):
            for file in files:
                isExt = any([file.endswith(ext) for ext in exts])
                isDirIgnore = any(
                    [dirname.startswith("_") for dirname in root.split("/")]
                )
                isFileIgnore = file.startswith("_")

                if isExt and not isDirIgnore and not isFileIgnore:
                    foundFiles.append(os.path.join(root, file))

        return foundFiles

    allFiles = []

    for path in paths:
        allFiles += findFiles(exts, path)

    logPrint("findAllFiles: found files:\n%s" % allFiles)
    return allFiles


def findLatest(files, exts):
    latest = {}
    logPrint("findLatest: finding latest files")

    try:
        latest = {
            ext: sorted(
                [
                    file if os.path.splitext(file)[1][1:] == ext else None
                    for file in files
                ],
                key=lambda x: os.path.getmtime(x) if x else -1,
            )[-1]
            for ext in exts
        }
        logPrint("findLatest: found latest files:\n%s" % latest)

    except Exception as e:
        logPrint("findLatest: FAILED to find the latest files:\n%s" % e)

    return latest


def convertVideo(file, fps, keepSource=False):
    newFile = os.path.splitext(file)[0] + ".mp4"
    # cmd = "ffmpeg -framerate %s -i %s -c:v copy -r %s %s -y && rm %s" % (fps, file, fps, newFile, file)
    cmd = "ffmpeg -framerate %s -i %s -c:v copy -r %s %s -y" % (fps, file, fps, newFile)

    if not keepSource:
        cmd += " && rm %s" % file

    try:
        logPrint("convertVideo: converting:\n%s" % cmd)
        subProc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        subOut, subErr = subProc.communicate()
        subOut = subOut.decode("utf-8").lower()
        subErr = subErr.decode("utf-8").lower()

        if subProc.returncode != 0:
            print("asdf")
            raise Exception("ffmpeg failed with return code %d" % subProc.returncode)

        if (
            "exception" in subOut
            or "exception" in subErr
            or "unexpected" in subOut
            or "unexpected" in subErr
        ):
            raise Exception("rror detected in FFmpeg output")

        return newFile

    except Exception as e:
        logPrint(
            "convertVideo: FAILED to convert:\n%s\n%s\n%s\n%s"
            % (cmd, e, subOut, subErr)
        )
        raise Exception("failed to convert video")


def transfer(files, dest, latest, fps=None, skipLatest=False):
    logPrint("transfer: started convert and transfer")
    transferred = []
    dailyDirCreated = False

    for file in files:
        ext = os.path.splitext(file)[1][1:]

        if skipLatest and file == latest[ext]:
            logPrint("tranfer: latest file, ignored:\n%s" % file)
            continue

        if ext == "h264":
            try:
                file = convertVideo(file, fps)

            except:
                logPrint("transfer: skipping\n%s" % file)
                continue

            if file is None:
                continue

            ext = "mp4"

        extDest = os.path.join(dest, ext)

        # cmd = "sudo rsync %s %s" % (file, os.path.join(file, extDest))
        cmd = "sudo rsync %s %s" % (file, extDest)

        try:
            logPrint("transfer: moving:\n%s" % cmd)
            subprocess.run(cmd, shell=True)
            transferred.append(cmd)

        except Exception as e:
            logPrint("transfer: FAILED to copy:\n%s\n%s" % (cmd, e))

    logPrint("transfer: moved:\n%s" % transferred)
    return transferred


def specificTransfer(files, dest, latest, fps=None, skipLatest=False):
    transferred = []

    for file in files:
        ext = os.path.splitext(file)[1][1:]

        if skipLatest and latest[ext] == file:
            logPrint("specificTransfer: latest file, ignored:\n%s" % file)
            continue

        if ext == "h264":
            try:
                file = convertVideo(file, fps)

            except:
                logPrint("specificTransfer: skipping\n%s" % file)
                continue

            ext = "mp4"

        if ext == "events" or ext == "frames" or ext == "mp4":
            extDest = (
                os.path.join(dest, "Video", os.path.basename(os.path.dirname(file)))
                + "/"
            )

            if not os.path.exists(extDest):
                os.makedirs(extDest)

        else:
            extDest = (
                os.path.join(dest, "Data", os.path.basename(os.path.dirname(file)))
                + "/"
            )

            if not os.path.exists(extDest):
                os.makedirs(extDest)

        cmd = "sudo rsync %s %s" % (file, extDest)

        try:
            logPrint("specificTransfer: moving:\n%s" % cmd)
            subprocess.run(cmd, shell=True)
            transferred.append(cmd)

        except Exception as e:
            logPrint("transfer: FAILED to copy:\n%s\n%s" % (cmd, e))

    logPrint("specificTransfer: moved:\n%s" % transferred)
    return transferred


def makeDirs(exts, mountPoint, specificTransfer):
    dailyDirPath = str(datetime.datetime.now().date())
    dailyDirPath = os.path.join(mountPoint, dailyDirPath)

    if not os.path.exists(dailyDirPath):
        logPrint("makeDirs: creating daily dir")
        os.makedirs(dailyDirPath)

        if specificTransfer:
            return dailyDirPath

    logPrint("makeDirs: creating ext dirs")

    for ext in exts:
        ext = "mp4" if ext == "h264" else ext
        extDirPath = os.path.join(dailyDirPath, ext)

        if not os.path.exists(extDirPath):
            try:
                os.makedirs(extDirPath)

            except Exception as e:
                logPrint("makeDirs: FAILED to create ext dir: %s\n%s" % (extDirPath, e))

    return dailyDirPath


def deleteMoved(transferred, latest, keepLatest=True):
    logPrint("deleteMoved: deleting moved files")

    for transferCmd in transferred:
        file = transferCmd.split()[2]

        if keepLatest and file in latest.values():
            logPrint("deleteMoved: is the latest file, skipping:\n%s" % file)
            continue

        logPrint("deleteMoved: deleting %s" % file)
        cmd = "sudo rm %s" % file

        try:
            subprocess.run(cmd, shell=True)

        except Exception as e:
            logPrint("deleteMoved: FAILED to delete:\n%s\n%s" % (cmd, e))


def verify(cmds):
    for cmd in cmds:
        source = cmd.split(" ")[2]
        file = os.path.basename(source)
        dest = cmd.split(" ")[3]
        files = os.listdir(dest)
        logPrint("verify: found %s in %s: %s" % (file, dest, file in files))


def routeRawDataPaths(mountpoint, userConfig):
    """
    Build <mountpoint>/<Subject_Name>/raw_data/videos layout.
    """
    subj = userConfig.get("Subject_Name", "Subject").strip()
    subject_base = os.path.join(mountpoint, subj)
    raw_base = os.path.join(subject_base, "raw_data")
    videos_dir = os.path.join(raw_base, "videos")

    for p in (subject_base, raw_base, videos_dir):
        if not ensureDir(p):
            logPrint("routeRawDataPaths: directory setup failed: %s" % p)
    return raw_base, videos_dir


def transferRawMode(
    files, mountpoint, latest, fps=None, skipLatest=False, userConfig=None
):
    """
    Raw data mode: session files -> raw_data, video + events/frames -> raw_data/videos[/subdir]
    """
    raw_base, videos_dir = routeRawDataPaths(mountpoint, userConfig or {})
    moved = []
    for file in files:
        if not os.path.isfile(file):
            continue
        ext = os.path.splitext(file)[1][1:].lower()
        if skipLatest and ext in latest and file == latest[ext]:
            continue

        # Convert h264
        if ext == "h264":
            try:
                file = convertVideo(file, fps)
                ext = "mp4"
            except Exception as e:
                logPrint("transferRawMode: skip h264 (convert fail) %s: %s" % (file, e))
                continue

        # Decide destination
        if ext in ("mp4", "events", "frames"):
            dest_dir = videos_dir
            if ext in ("events", "frames"):
                sub = os.path.basename(os.path.dirname(file))
                # Optional subfolder for organizing by recording folder
                sub_dir = os.path.join(videos_dir, sub)
                if ensureDir(sub_dir):
                    dest_dir = sub_dir
        else:
            dest_dir = raw_base

        if not os.path.isdir(dest_dir):
            logPrint(
                "transferRawMode: destination not a directory (skip): %s" % dest_dir
            )
            continue

        # Trailing slash ensures rsync treats dest as directory
        cmd = "sudo rsync %s %s/" % (file, dest_dir)
        try:
            logPrint("RAW_MODE: %s" % cmd)
            proc = subprocess.run(cmd, shell=True)
            if proc.returncode != 0:
                logPrint(
                    "transferRawMode: rsync non-zero exit (%d) %s"
                    % (proc.returncode, file)
                )
                continue
            moved.append(cmd)
        except Exception as e:
            logPrint("transferRawMode: rsync exception %s: %s" % (file, e))
    return moved


def main():
    # read config files
    userInfo = getUserConfig("userInfo.in", "=")
    camInfo = getUserConfig("camInfoM.in", "=")

    # initialise log file
    dateTime = (
        str(datetime.datetime.now().date())
        + "_"
        + str(datetime.datetime.now().time())[:-7]
    ).replace(":", "-")
    logging.basicConfig(
        filename="%s.log" % os.path.join(userInfo["Logs_Dir"], dateTime),
        format="%(asctime)s > %(message)s\n",
    )
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logPrint("main: START @ %s" % time.ctime())
    logPrint("main:\nuserInfo:\n%s\n\ncamInfo:\n%s" % (userInfo, camInfo))

    exts = [ext.strip() for ext in userInfo["File_Exts"].split(",")]
    lookInPaths = [path.strip() for path in userInfo["Look_In_Paths"].split(",")]
    mountpoint = userInfo["Mountpoint"]

    if userInfo["Transfer_Enabled"].lower() == "false":
        logPrint("main: automated transfer not enabled")
        exit()

    remountNas = userInfo["Remount"].lower() == "true"

    mountFs(
        ip=userInfo["Nas_Ip"],
        fsDest=userInfo["Destination_In_Fs"],
        mountTo=mountpoint,
        creds=userInfo["Nas_Creds"],
        exitOnFail=False,
        remount=remountNas,
    )

    allFiles = findAllFiles(exts, lookInPaths)

    if len(allFiles) == 0:
        logPrint("main: no files found for transfer")
        return

    latest = findLatest(allFiles, exts)
    skipLatest = userInfo["Skip_Latest"].lower() == "true"
    specificDests = userInfo["Specific_Dests"].lower() == "true"

    rawMode = userInfo.get("Raw_Data_Mode", "false").lower() == "true"

    if rawMode:
        transferred = transferRawMode(
            allFiles,
            mountpoint,
            latest,
            camInfo.get("Camera_FPS"),
            skipLatest,
            userConfig=userInfo,
        )
    elif not specificDests:
        dailyDir = makeDirs(exts, mountpoint, specificDests)
        transferred = transfer(
            allFiles, dailyDir, latest, camInfo.get("Camera_FPS"), skipLatest
        )
    else:
        dest = mountpoint
        transferred = specificTransfer(
            allFiles, dest, latest, camInfo.get("Camera_FPS"), skipLatest
        )

    time.sleep(10)
    verify(transferred)

    if userInfo["Delete_Moved"].lower() == "true":
        keepLatest = userInfo["Keep_Latest"].lower() == "true"
        deleteMoved(transferred, latest, keepLatest)


if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        logPrint("main: error:\n%s" % e)
