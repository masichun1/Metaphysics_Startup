# ============================================================
# 小红书每日运营 — Windows 定时任务配置脚本
# 以管理员身份运行此脚本
# ============================================================

$taskName = "XHS_Daily_Ops"
$scriptPath = "d:\马思纯\Metaphysics_Startup\Domestic_XHS_Project\daily_ops.py"
$pythonPath = "d:\马思纯\app\venv_xhs\Scripts\python.exe"
$workDir = "d:\马思纯\Metaphysics_Startup\Domestic_XHS_Project"

# 删除旧任务 (如果存在)
Unregister-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

# 创建每日任务 — 每天上午 09:00 执行
$action = New-ScheduledTaskAction -Execute $pythonPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -Daily -At 09:00

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "小红书每日自动化运营: 数据追踪 + 竞品分析 + AI文案 + 养号" `
    -Force

Write-Host "================================================"  -ForegroundColor Green
Write-Host "   定时任务已创建: $taskName" -ForegroundColor Green
Write-Host "   执行时间: 每天 09:00" -ForegroundColor Green
Write-Host "   脚本: $scriptPath" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "手动测试运行:" -ForegroundColor Yellow
Write-Host "  & '$pythonPath' '$scriptPath' --skip-yanghao" -ForegroundColor White
Write-Host ""
Write-Host "查看任务状态:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor White
