from ctypes import (
    c_char,
    c_void_p,
    byref,
    POINTER,
    cast,
)
from .hkipcamsdk import (
    loadLibrary,
    netSdkPath,
    playSdkPath,
    NET_DVR_DEVICEINFO,
    NET_DVR_CLIENTINFO,
    FRAME_INFO,
    fDecCBFun,
    fRealDataCallBack,
    LONG,
    FALSE,
    NULL,
    T_YV12,
    NET_DVR_SYSHEAD,
    NET_DVR_STREAMDATA,
)
from cv2 import Mat, cvtColor, COLOR_YUV2BGR_YV12
from time import sleep
from numpy import frombuffer, uint8


def _yv12toBGRMat(inYv12, width, height) -> Mat:
    yuvHeight = int(height * 3 / 2)
    bufLen = int(width * yuvHeight)
    yv12Bytes = bytes(cast(inYv12, POINTER(c_char * bufLen)).contents)
    yv12Array = frombuffer(yv12Bytes, dtype=uint8)
    yv12Array = yv12Array.reshape((yuvHeight, width))
    return cvtColor(yv12Array, COLOR_YUV2BGR_YV12)


class VideoCapture:
    def __init__(self) -> None:
        self.netSdk = loadLibrary(netSdkPath)
        self.playSdk = loadLibrary(playSdkPath)
        self.loginId = -1
        self.playId = -1

        self._frames = []
        self._nPort = LONG(-1)
        self._fDecCBFun = fDecCBFun(self._decCBFun)
        self._fRealDataCallBack = fRealDataCallBack(self._realDataCallBack)

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

        self.loginId = self.netSdk.NET_DVR_Login(
            ip.encode(), port, usr.encode(), password.encode(), byref(deviceInfo)
        )
        return self.loginId >= 0

    def _logout(self) -> bool:
        return bool(self.netSdk.NET_DVR_Logout(self.loginId))

    def _realPlay(self, channel: int = 1, linkMode: int = 0, playWnd: int = 0) -> bool:
        clientInfo = NET_DVR_CLIENTINFO()
        clientInfo.hPlayWnd = playWnd
        clientInfo.lChannel = channel
        clientInfo.lLinkMode = linkMode

        self.playId = self.netSdk.NET_DVR_RealPlay_V30(
            self.loginId, byref(clientInfo), self._fRealDataCallBack, NULL, FALSE
        )
        return self.playId >= 0

    def _stopRealPlay(self) -> bool:
        return bool(self.netSdk.NET_DVR_StopRealPlay(self.playId))

    def _decCBFun(self, nPort, pBuf, nSize, pFrameInfo, pUser, nReserved2) -> None:
        frameInfo = cast(pFrameInfo, POINTER(FRAME_INFO)).contents

        if frameInfo.nType == T_YV12:
            bgrMat = _yv12toBGRMat(pBuf, frameInfo.nWidth, frameInfo.nHeight)
            self._frames.insert(0, bgrMat)

            if len(self._frames) > 2:
                self._frames = self._frames[:2]

    def _realDataCallBack(
        self, lRealHandle, dwDataType, pBuffer, dwBufSize, pUser
    ) -> None:
        if lRealHandle != self.playId:
            return

        if dwDataType == NET_DVR_SYSHEAD:
            if not self.playSdk.PlayM4_GetPort(byref(self._nPort)):
                return
            if dwBufSize > 0:
                if not self.playSdk.PlayM4_OpenStream(
                    self._nPort, pBuffer, dwBufSize, 1024 * 1024
                ):
                    return
                if not self.playSdk.PlayM4_SetDecCallBackMend(
                    self._nPort, self._fDecCBFun, c_void_p(pUser)
                ):
                    return
                if not self.playSdk.PlayM4_Play(self._nPort, NULL):
                    return

        elif dwDataType == NET_DVR_STREAMDATA:
            if (dwBufSize > 0) and (self._nPort != -1):
                inData = self.playSdk.PlayM4_InputData(self._nPort, pBuffer, dwBufSize)
                while not inData:
                    sleep(10)
                    inData = self.playSdk.PlayM4_InputData(
                        self._nPort, pBuffer, dwBufSize
                    )
