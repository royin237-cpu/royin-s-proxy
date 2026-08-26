@echo off
chcp 65001 >nul
set OUT=D:\1_software\clash\AutoMergePublicNodes\tmp\netdiag_result.txt
echo === 采集时间 %date% %time% === > "%OUT%"

echo === [1] 系统代理三项（关键） === >> "%OUT%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -v ProxyEnable >> "%OUT%" 2>&1
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -v ProxyServer >> "%OUT%" 2>&1
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -v AutoConfigURL >> "%OUT%" 2>&1

echo === [2] WLAN IP/网关/DNS === >> "%OUT%"
ipconfig | findstr /i "IPv4 默认网关 网关" >> "%OUT%" 2>&1
netsh interface ip show dns "WLAN" >> "%OUT%" 2>&1

echo === [3] 五域名 TCP443 连通（约30秒） === >> "%OUT%"
powershell -NoProfile -Command "foreach ($d in @('copilot.tencent.com','chat.deepseek.com','metaso.cn','www.bilibili.com','pan.baidu.com')) { $r = Test-NetConnection $d -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue; Write-Output ('{0} = {1}' -f $d, $r) }" >> "%OUT%" 2>&1

echo === [4] 全部本地监听端口+PID === >> "%OUT%"
netstat -ano | findstr "LISTENING" >> "%OUT%" 2>&1

echo === [5] 相关进程与PID === >> "%OUT%"
tasklist | findstr /i "aTrust verge mihomo" >> "%OUT%" 2>&1

echo === [6] 路由表默认路由 === >> "%OUT%"
route print 0.0.0.0 | findstr "0.0.0.0" >> "%OUT%" 2>&1

echo.
echo ===== 采集完成，结果如下 =====
type "%OUT%"
echo.
echo 结果已保存: %OUT%
echo 现在可以切回热点，然后把结果发给我。
pause
