from ctypes import (
    c_char,
    c_int,
    c_void_p,
    byref,
    POINTER,
    cast,
)
from .sdk_struct import (
    loadLibrary,
    netSdkPath,
    playSdkPath,
    NET_DVR_DEVICEINFO,
    NET_DVR_CLIENTINFO,
    FRAME_INFO,
    LONG,
    DWORD,
    BYTE,
    FALSE,
    NULL,
    T_YV12,
    NET_DVR_SYSHEAD,
    NET_DVR_STREAMDATA,
    FUNCTYPE,
)
from cv2 import Mat, cvtColor, COLOR_YUV2BGR_YV12
from time import sleep
from numpy import frombuffer, uint8

_hkipc: "HKIPcamera" = None


def _yv12toBGRMat(inYv12: POINTER(c_char), width: c_int, height: c_int) -> Mat:
    yuvHeight = int(height * 3 / 2)
    bufLen = int(width * yuvHeight)
    yv12Bytes = bytes(cast(inYv12, POINTER(c_char * bufLen)).contents)
    yv12Array = frombuffer(yv12Bytes, dtype=uint8)
    yv12Array = yv12Array.reshape((yuvHeight, width))
    return cvtColor(yv12Array, COLOR_YUV2BGR_YV12)


@FUNCTYPE(None, c_int, POINTER(c_char), c_int, POINTER(FRAME_INFO), c_void_p, c_int)
def _decCBFun(
    nPort: c_int,
    pBuf: POINTER(c_char),
    nSize: c_int,
    pFrameInfo: POINTER(FRAME_INFO),
    pUser: c_void_p,
    nReserved2: c_int,
) -> None:
    frameInfo = cast(pFrameInfo, POINTER(FRAME_INFO)).contents

    if frameInfo.nType == T_YV12:
        bgrMat = _yv12toBGRMat(pBuf, frameInfo.nWidth, frameInfo.nHeight)
        _hkipc._frames.insert(0, bgrMat)

        if len(_hkipc._frames) > 2:
            _hkipc._frames = _hkipc._frames[:2]


@FUNCTYPE(None, LONG, DWORD, POINTER(BYTE), DWORD, c_void_p)
def _realDataCallBack(
    lRealHandle: LONG,
    dwDataType: DWORD,
    pBuffer: POINTER(BYTE),
    dwBufSize: DWORD,
    pUser: c_void_p,
) -> None:
    if lRealHandle != _hkipc.realPlayHandle:
        return

    if dwDataType == NET_DVR_SYSHEAD:
        if not _hkipc.playSdk.PlayM4_GetPort(byref(_hkipc._nPort)):
            return
        if dwBufSize > 0:
            if not _hkipc.playSdk.PlayM4_OpenStream(
                _hkipc._nPort, pBuffer, dwBufSize, 1024 * 1024
            ):
                return
            if not _hkipc.playSdk.PlayM4_SetDecCallBackMend(
                _hkipc._nPort, _decCBFun, c_void_p(pUser)
            ):
                return
            if not _hkipc.playSdk.PlayM4_Play(_hkipc._nPort, NULL):
                return

    elif dwDataType == NET_DVR_STREAMDATA:
        if (dwBufSize > 0) and (_hkipc._nPort != -1):
            inData = _hkipc.playSdk.PlayM4_InputData(_hkipc._nPort, pBuffer, dwBufSize)
            while not inData:
                sleep(10)
                inData = _hkipc.playSdk.PlayM4_InputData(
                    _hkipc._nPort, pBuffer, dwBufSize
                )


class HKIPcamera:
    def __init__(self) -> None:
        global _hkipc

        self.netSdk = loadLibrary(netSdkPath)
        self.playSdk = loadLibrary(playSdkPath)
        self.userId = -1
        self.realPlayHandle = -1

        self._frames = []
        self._nPort = LONG(-1)
        _hkipc = self

    def open(self, ip: str, usr: str, password: str, port: int = 8000) -> bool:
        self.release()
        self._init()
        if self._login(ip, usr, password, port) and self._realPlay():
            return True
        return False

    def read(self) -> tuple[bool, Mat]:
        if self._frames:
            return (True, self._frames.pop())
        return (False, None)

    def release(self) -> None:
        self._stopRealPlay()
        self._logout()
        self._cleanup()

    def _init(self) -> bool:
        return bool(self.netSdk.NET_DVR_Init())

    def _cleanup(self) -> bool:
        return bool(self.netSdk.NET_DVR_Cleanup())

    def _login(self, ip: str, usr: str, password: str, port: int = 8000) -> bool:
        deviceInfo = NET_DVR_DEVICEINFO()

        self.userId = self.netSdk.NET_DVR_Login(
            ip.encode(), port, usr.encode(), password.encode(), byref(deviceInfo)
        )
        return self.userId >= 0

    def _logout(self) -> bool:
        return bool(self.netSdk.NET_DVR_Logout(self.userId))

    def _realPlay(self, channel: int = 1, linkMode: int = 0, playWnd: int = 0) -> bool:
        clientInfo = NET_DVR_CLIENTINFO()
        clientInfo.hPlayWnd = playWnd
        clientInfo.lChannel = channel
        clientInfo.lLinkMode = linkMode

        self.realPlayHandle = self.netSdk.NET_DVR_RealPlay_V30(
            self.userId, byref(clientInfo), _realDataCallBack, NULL, FALSE
        )
        return self.realPlayHandle >= 0

    def _stopRealPlay(self) -> bool:
        return bool(self.netSdk.NET_DVR_StopRealPlay(self.realPlayHandle))
