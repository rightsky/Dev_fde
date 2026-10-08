# FDE Data Studio 복원 — backup.ps1 로 만든 폴더에서 DB 와 업로드 파일을 되돌린다. 지금 데이터는 지워진다.
# 사용 (프로젝트 폴더에서, 서비스가 떠 있는 상태):
#   powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\20261008-203000
param([Parameter(Mandatory = $true)][string]$Backup)
$ErrorActionPreference = "Stop"
$Backup = (Resolve-Path $Backup).Path
Set-Location (Split-Path $PSScriptRoot -Parent)

function Compose {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) { throw "실패: docker compose $($args -join ' ')" }
}

foreach ($f in "fde.dump", "storage.tgz") {
    if (-not (Test-Path (Join-Path $Backup $f))) { throw "$Backup 에 $f 가 없습니다" }
}
Write-Host "복원할 백업: $Backup"
$answer = Read-Host "지금 데이터를 모두 지우고 이 백업으로 되돌립니다. 계속하려면 yes 를 입력하세요"
if ($answer -ne "yes") { Write-Host "취소했습니다."; exit 1 }

# docker compose cp 로 넣은 파일은 root 소유라 백엔드 사용자(fde)가 지울 수 없다. 풀기는 root 로 하고 소유자를 fde 로 돌린다
Write-Host "1/3 업로드 파일 되돌리는 중..."
Compose cp (Join-Path $Backup "storage.tgz") backend:/tmp/storage.tgz
Compose exec -T -u root backend sh -c "find /data/storage -mindepth 1 -delete && tar xzf /tmp/storage.tgz -C /data/storage && chown -R fde /data/storage && rm -f /tmp/storage.tgz"

Write-Host "2/3 데이터베이스 되돌리는 중 (백엔드 잠시 중지)..."
Compose stop backend
Compose cp (Join-Path $Backup "fde.dump") db:/tmp/fde.dump
Compose exec -T db pg_restore -U fde -d fde --clean --if-exists --no-owner --exit-on-error /tmp/fde.dump
Compose exec -T db rm -f /tmp/fde.dump

Write-Host "3/3 백엔드 다시 시작..."
Compose start backend
Write-Host ""
Write-Host "복원 완료. 브라우저를 새로 고치세요."
