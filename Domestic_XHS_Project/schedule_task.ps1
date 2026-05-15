# ============================================================
# 小红书每日运营 — Windows 定时任务配置脚本
# 以管理员身份运行此脚本
# ============================================================

# ============================================================
# 小红书每日运营 — Windows 定时任务
# 养号 5:00-5:30 → 运营 5:30-6:00 → Git 存档 6:00
# 以管理员身份运行: powershell -ExecutionPolicy Bypass -File schedule_task.ps1
# ============================================================

$taskName = "XHS_Daily_Ops_0500"
$scriptPath = "d:\马思纯\Metaphysics_Startup\Domestic_XHS_Project\daily_ops.py"
$archiveScript = "d:\马思纯\Metaphysics_Startup\Domestic_XHS_Project\git_archive.py"
$pythonPath = "d:\马思纯\app\venv_xhs\Scripts\python.exe"
$workDir = "d:\马思纯\Metaphysics_Startup\Domestic_XHS_Project"

Unregister-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

# 步骤 1: 养号 (5:00-5:30) + 运营 (5:30-6:00)
$action1 = New-ScheduledTaskAction -Execute $pythonPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workDir

# 步骤 2: Git 自动存档 (6:00)
$action2 = New-ScheduledTaskAction -Execute $pythonPath `
    -Argument "`"$archiveScript`"" `
    -WorkingDirectory $workDir

# 每天 05:00 执行 (养号+运营)
$trigger = New-ScheduledTaskTrigger -Daily -At 05:00

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName `
    -Action $action1, $action2 `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "小红书每日自动化: 5:00养号 → 5:30运营 → 6:00Git存档" `
    -Force

Write-Host "================================================"  -ForegroundColor Green
Write-Host "   定时任务: $taskName" -ForegroundColor Green
Write-Host "   养号+运营: 每天 05:00" -ForegroundColor Green
Write-Host "   Git存档:  每天 06:00" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "手动测试:" -ForegroundColor Yellow
Write-Host "  & '$pythonPath' '$scriptPath' --skip-yanghao" -ForegroundColor White
Write-Host ""
Write-Host "查看任务: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Yellow
Write-Host "手动运行: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Yellow
